import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from google.adk.agents import Agent
from google.adk.models import Gemini, LlmRequest, LlmResponse
from google.adk.models.base_llm import BaseLlmConnection
from google.adk.models.lite_llm import LiteLlm

from .redaction import log_failure, protect_logs, redact_data
from .storage import ModelConfigStore, SecretStore


_LOGGER = logging.getLogger(__name__)
MODEL_SUGGESTIONS = {
    "openai": ("gpt-6-luna", "gpt-4.1", "gpt-4.1-mini"),
    "anthropic": ("claude-sonnet-4-5", "claude-haiku-4-5"),
    "gemini": ("gemini-2.5-flash", "gemini-2.5-pro"),
    "ollama": ("qwen3", "llama3.1"),
}


async def _protected_responses(responses: AsyncIterator[LlmResponse], secret: str | None) -> AsyncIterator[LlmResponse]:
    while True:
        try:
            async with protect_logs((secret,)):
                response = await anext(responses)
        except StopAsyncIteration:
            return
        except Exception as error:
            log_failure(_LOGGER, "provider.generate", error)
            raise RuntimeError("La requête au fournisseur a échoué") from None
        yield response


class ProtectedGemini(Gemini):
    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncIterator[LlmResponse]:
        secret = (self.client_kwargs or {}).get("api_key")
        async for response in _protected_responses(super().generate_content_async(llm_request, stream), secret):
            yield response


class ProtectedLiteLlm(LiteLlm):
    def connect(self, llm_request: LlmRequest) -> AbstractAsyncContextManager[BaseLlmConnection]:
        raise NotImplementedError(f"Live connection is not supported for {self.model}.")

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncIterator[LlmResponse]:
        secret = self._additional_args.get("api_key")
        async for response in _protected_responses(super().generate_content_async(llm_request, stream), secret):
            yield response


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    url: str | None = None

    def validate(self) -> None:
        if self.provider not in {"gemini", "openai", "anthropic", "ollama"}:
            raise ValueError("Fournisseur inconnu")
        if not self.model or self.model != self.model.strip() or any(char.isspace() for char in self.model):
            raise ValueError("Modèle invalide")
        if self.provider == "ollama":
            if not self.url:
                raise ValueError("URL Ollama requise")
            try:
                parsed = urlsplit(self.url)
                valid_url = parsed.scheme in {"http", "https"} and bool(parsed.hostname) and parsed.port != 0 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
            except ValueError:
                valid_url = False
            if not valid_url:
                raise ValueError("URL Ollama invalide")
        elif self.url is not None:
            raise ValueError("URL non prise en charge pour ce fournisseur")


class ModelRegistry:
    def __init__(self, configs: ModelConfigStore, secrets: SecretStore) -> None:
        self.configs = configs
        self.secrets = secrets

    def configure(self, user_id: str, config: ModelConfig) -> None:
        config.validate()
        self.configs.put(user_id, config.provider, config.model, config.url)

    async def catalog_for(self, user_id: str, provider: str, *, transport: httpx.AsyncBaseTransport | None = None) -> dict:
        if not user_id or provider not in MODEL_SUGGESTIONS:
            raise ValueError("Fournisseur inconnu")
        models = {}
        values = self.secrets.values(user_id)

        def result(source: str, message: str, complete: bool = True) -> dict:
            entries = list(models.values()) if source == "dynamic" else [
                {"id": name, "compatibility": "unverified"} for name in MODEL_SUGGESTIONS[provider]
            ]
            return redact_data({"provider": provider, "source": source, "models": entries, "message": message, "complete": complete}, values)

        headers = {}
        params = {}
        if provider == "ollama":
            config = self.configs.get(user_id)
            if config is None or config[0] != "ollama":
                return result("suggestions", "URL Ollama non enregistrée. Suggestions sans garantie d'installation.", False)
            ModelConfig(*config).validate()
            url = config[2].rstrip("/") + "/api/tags"
        else:
            secret = self.secrets.get(user_id, provider)
            if not secret:
                return result("suggestions", "Clé fournisseur non enregistrée. Suggestions sans garantie d'accès.", False)
            if provider == "openai":
                url = "https://api.openai.com/v1/models"
                headers = {"Authorization": f"Bearer {secret}"}
            elif provider == "anthropic":
                url = "https://api.anthropic.com/v1/models"
                headers = {"x-api-key": secret, "anthropic-version": "2023-06-01"}
                params = {"limit": "100"}
            else:
                url = "https://generativelanguage.googleapis.com/v1beta/models"
                headers = {"x-goog-api-key": secret}
                params = {"pageSize": "1000"}
        cursors = set()
        try:
            async with protect_logs(values), asyncio.timeout(15), httpx.AsyncClient(
                headers=headers, timeout=5, follow_redirects=False, trust_env=False, transport=transport,
            ) as client:
                for _page in range(10):
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    if len(response.content) > 2_000_000:
                        raise ValueError("Catalogue trop volumineux")
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("Catalogue invalide")
                    entries = payload.get("models" if provider in {"gemini", "ollama"} else "data")
                    if not isinstance(entries, list):
                        raise ValueError("Catalogue invalide")
                    for entry in entries:
                        if not isinstance(entry, dict):
                            raise ValueError("Modèle invalide")
                        identifier = entry.get("name" if provider in {"gemini", "ollama"} else "id")
                        if not isinstance(identifier, str) or not identifier or len(identifier) > 256:
                            raise ValueError("Modèle invalide")
                        if provider == "gemini":
                            if "generateContent" not in entry.get("supportedGenerationMethods", []):
                                continue
                            identifier = identifier.removeprefix("models/")
                        if provider == "openai" and identifier.startswith(("text-embedding-", "whisper-", "tts-", "dall-e-")):
                            continue
                        if provider == "anthropic" and entry.get("lifecycle") == "retired":
                            continue
                        if any(character.isspace() for character in identifier) or redact_data(identifier, values) != identifier:
                            continue
                        models[identifier] = {"id": identifier, "compatibility": "unverified"}
                        if len(models) > 10000:
                            raise ValueError("Catalogue trop volumineux")
                    cursor = payload.get("nextPageToken") if provider == "gemini" else payload.get("last_id") if provider == "anthropic" and payload.get("has_more") else None
                    if cursor is None and not (provider == "anthropic" and payload.get("has_more")):
                        return result("dynamic", "Modèles retournés par le fournisseur ; compatibilité non vérifiée." if models else "Aucun modèle retourné.")
                    if not isinstance(cursor, str) or not cursor or cursor in cursors:
                        raise ValueError("Pagination invalide")
                    cursors.add(cursor)
                    params["pageToken" if provider == "gemini" else "after_id"] = cursor
        except (httpx.HTTPError, ValueError, TypeError, TimeoutError) as error:
            log_failure(_LOGGER, "provider.catalog", error)
        if models:
            return result("dynamic", "Catalogue incomplet ; réessayez ou saisissez le modèle manuellement. Compatibilité non vérifiée.", False)
        return result("suggestions", "Catalogue inaccessible ; réessayez. Suggestions sans garantie d'accès ou d'installation.", False)

    def agent_for(self, user_id: str) -> Agent:
        stored = self.configs.get(user_id)
        if stored is None:
            raise ValueError("Aucun modèle configuré")
        config = ModelConfig(*stored)
        config.validate()
        if config.provider == "ollama":
            model = ProtectedLiteLlm(model=f"ollama_chat/{config.model}", api_base=config.url, api_key="ollama")
        else:
            api_key = self.secrets.get(user_id, config.provider)
            if not api_key:
                raise ValueError("Clé du fournisseur manquante")
            if config.provider == "gemini":
                model = ProtectedGemini(model=config.model, client_kwargs={"api_key": api_key, "vertexai": False})
            else:
                additional_args = {}
                if config.provider == "openai" and config.model == "gpt-6-luna":
                    additional_args["reasoning_effort"] = "none"
                model = ProtectedLiteLlm(
                    model=f"{config.provider}/{config.model}", api_key=api_key, **additional_args
                )
        return Agent(name="vtherm_assistant", model=model)