from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx
from google.adk.tools import BaseTool, ToolContext
from google.genai import types


SITEMAP_URL = "https://www.versatile-thermostat.org/sitemap.xml"
ALLOWED_HOST = "www.versatile-thermostat.org"
MAX_PAGES = 20
MAX_PAGE_SIZE = 200_000


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "header"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "header"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class VersatileThermostatDocumentationTool(BaseTool):
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(
            name="search_vtherm_documentation",
            description=(
                "Rechercher dans la documentation officielle Versatile Thermostat en français, anglais ou allemand. "
                "Choisir la langue utilisée par l'utilisateur. À utiliser pour les questions de configuration, "
                "fonctionnalités et diagnostic."
            ),
        )
        self.transport = transport

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Mots-clés ou question à rechercher"},
                    "language": {"type": "string", "enum": ["fr", "en", "de"]},
                },
                "required": ["query", "language"],
            },
        )

    @staticmethod
    def _valid_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme == "https" and parsed.hostname == ALLOWED_HOST and not parsed.username and not parsed.password

    async def _get(self, client: httpx.AsyncClient, url: str) -> str:
        if not self._valid_url(url):
            raise ValueError("URL de documentation non autorisée")
        response = await client.get(url)
        response.raise_for_status()
        if len(response.content) > MAX_PAGE_SIZE:
            raise ValueError("Page de documentation trop volumineuse")
        return response.text

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
        query = args.get("query")
        language = args.get("language")
        if not isinstance(query, str) or not query.strip() or len(query) > 500 or language not in {"fr", "en", "de"}:
            return {"error": "Recherche invalide"}
        terms = {term.casefold() for term in re.findall(r"[\wÀ-ÿ-]+", query) if len(term) > 2}
        if not terms:
            return {"results": []}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(8, read=15), follow_redirects=False, trust_env=False, transport=self.transport,
        ) as client:
            sitemap = await self._get(client, SITEMAP_URL)
            root = ET.fromstring(sitemap)
            pages: list[tuple[int, str]] = []
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] != "loc" or not node.text:
                    continue
                url = node.text.strip()
                path = urlparse(url).path
                if self._valid_url(url) and path.startswith(f"/{language}/docs/"):
                    path_text = re.sub(r"[-_/]+", " ", path).casefold()
                    pages.append((sum(term in path_text for term in terms), url))
            pages.sort(key=lambda page: page[0], reverse=True)
            results = []
            for _, url in pages[:MAX_PAGES]:
                try:
                    html = await self._get(client, url)
                except (httpx.HTTPError, ValueError):
                    continue
                parser = _TextExtractor()
                parser.feed(html)
                text = re.sub(r"\s+", " ", " ".join(parser.parts))
                lowered = text.casefold()
                score = sum(lowered.count(term) for term in terms)
                if score:
                    position = min((lowered.find(term) for term in terms if term in lowered), default=0)
                    start = max(0, position - 250)
                    results.append({"url": url, "excerpt": text[start:start + 900], "score": score})
            results.sort(key=lambda result: result["score"], reverse=True)
            return {"results": [{key: value for key, value in result.items() if key != "score"} for result in results[:5]]}
