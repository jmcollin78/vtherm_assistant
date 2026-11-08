import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, Tool

from .oauth import _validate_base_url, current_admin_for_url
from .redaction import log_failure, protect_logs, redact_data
from .storage import SecretStore


_LOGGER = logging.getLogger(__name__)


READ_ONLY_TOOL_DEFINITIONS = {
    "homeassistant__GetLiveContext": (
        "Lire les états courants des entités exposées à Assist.",
        {"type": "object", "properties": {"name": {"type": "string"}, "area": {"type": "string"},
         "domain": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}}},
    ),
    "versatile_thermostat__list_vtherms": (
        "Lister les thermostats VTherm exposés à Assist.", {"type": "object", "properties": {}},
    ),
    "versatile_thermostat__get_status": (
        "Lire l'état courant d'un thermostat VTherm exposé.",
        {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]},
    ),
    "versatile_thermostat__diagnose": (
        "Lire le diagnostic courant d'un thermostat VTherm exposé.",
        {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]},
    ),
}
READ_ONLY_TOOL_DEFINITIONS.update({
    f"assist__{name}": READ_ONLY_TOOL_DEFINITIONS[name]
    for name in (
        "versatile_thermostat__list_vtherms",
        "versatile_thermostat__get_status",
        "versatile_thermostat__diagnose",
    )
})
READ_ONLY_TOOLS = frozenset(READ_ONLY_TOOL_DEFINITIONS)


class MCPConnectionError(RuntimeError):
    pass


class MCPToolDenied(RuntimeError):
    pass


class ReadOnlyMCPTool(BaseTool):
    def __init__(self, client: "HomeAssistantMCP", user_id: str, tool: Tool, additional_secrets: tuple[str, ...] = ()) -> None:
        if tool.name not in READ_ONLY_TOOLS:
            raise MCPToolDenied("Outil MCP non autorisé")
        description, schema = READ_ONLY_TOOL_DEFINITIONS[tool.name]
        super().__init__(name=tool.name, description=description)
        self.client = client
        self.user_id = user_id
        self.input_schema = schema
        self.additional_secrets = additional_secrets

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(name=self.name, description=self.description, parameters_json_schema=self.input_schema)

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
        if tool_context.user_id != self.user_id:
            raise MCPToolDenied("Utilisateur MCP non autorisé")
        secrets = list(self.client.secrets.values(self.user_id)) + list(self.additional_secrets)
        if redact_data(args, secrets) != args:
            raise MCPToolDenied("Les arguments contiennent un identifiant secret")
        result = await self.client.call_read_only_tool(self.user_id, self.name, args)
        return redact_data(result.model_dump(mode="json", exclude_none=True), secrets)


class HomeAssistantMCP:
    def __init__(self, base_url: str, secrets: SecretStore, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = _validate_base_url(base_url, public=False)
        self.url = self.base_url + "api/mcp"
        self.secrets = secrets
        self.transport = transport

    @asynccontextmanager
    async def _session(self, user_id: str) -> AsyncIterator[ClientSession]:
        token = self.secrets.get(user_id, "home_assistant")
        if not token:
            _LOGGER.error("operation=mcp.session stage=authentication category=missing_token")
            raise MCPConnectionError("Jeton Home Assistant manquant")
        stage = "authentication"

        async def record_response(response: httpx.Response) -> None:
            if response.is_error:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as error:
                    log_failure(_LOGGER, "mcp.http", error, stage=stage)

        try:
            if await current_admin_for_url(self.base_url, token) is None:
                _LOGGER.error("operation=mcp.session stage=authentication category=permission")
                raise MCPConnectionError("Jeton Home Assistant non autorisé")
            stage = "initialize"
            async with protect_logs(self.secrets.values(user_id)), httpx.AsyncClient(
                headers={"Authorization": f"Bearer {token}"},
                timeout=httpx.Timeout(10, read=30),
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
                event_hooks={"response": [record_response]},
            ) as client:
                async with streamable_http_client(self.url, http_client=client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        stage = "operation"
                        yield session
        except MCPToolDenied as error:
            log_failure(_LOGGER, "mcp.session", error, stage=stage)
            raise
        except ExceptionGroup as error:
            log_failure(_LOGGER, "mcp.session", error, stage=stage)
            denied, other = error.split(MCPToolDenied)
            if denied is not None and other is None:
                exception = denied.exceptions[0]
                while isinstance(exception, BaseExceptionGroup):
                    exception = exception.exceptions[0]
                raise exception from None
            raise MCPConnectionError("Connexion au serveur MCP Home Assistant impossible") from None
        except Exception as error:
            log_failure(_LOGGER, "mcp.session", error, stage=stage)
            raise MCPConnectionError("Connexion au serveur MCP Home Assistant impossible") from None

    async def check_connection(self, user_id: str) -> None:
        async with self._session(user_id):
            pass

    async def _read_only_tools(self, session: ClientSession) -> list[Tool]:
        tools: dict[str, Tool] = {}
        cursor = None
        discovered = 0
        seen_cursors: set[str] = set()
        while True:
            page = await session.list_tools(cursor=cursor)
            discovered += len(page.tools)
            for tool in page.tools:
                if tool.name in READ_ONLY_TOOLS:
                    if tool.name in tools:
                        raise MCPToolDenied("Outil MCP ambigu")
                    tools[tool.name] = tool
            cursor = page.nextCursor
            if cursor is None:
                if not tools:
                    _LOGGER.warning("operation=mcp.discover category=no_allowed_tools discovered=%s allowed=0", discovered)
                return list(tools.values())
            if cursor in seen_cursors or len(seen_cursors) >= 100:
                raise MCPToolDenied("Pagination MCP invalide")
            seen_cursors.add(cursor)

    async def list_read_only_tools(self, user_id: str) -> list[Tool]:
        async with self._session(user_id) as session:
            return await self._read_only_tools(session)

    async def tools_for(self, user_id: str, additional_secrets: tuple[str, ...] = ()) -> list[ReadOnlyMCPTool]:
        return [ReadOnlyMCPTool(self, user_id, tool, additional_secrets) for tool in await self.list_read_only_tools(user_id)]

    async def call_read_only_tool(self, user_id: str, name: str, arguments: dict[str, Any]) -> CallToolResult:
        if name not in READ_ONLY_TOOLS:
            raise MCPToolDenied("Outil MCP non autorisé")
        async with self._session(user_id) as session:
            tools = await self._read_only_tools(session)
            if not any(tool.name == name for tool in tools):
                raise MCPToolDenied("Outil MCP indisponible")
            result = await session.call_tool(name, arguments)
            if result.isError:
                _LOGGER.warning("operation=mcp.call category=tool_error tool=%s", name)
            return result