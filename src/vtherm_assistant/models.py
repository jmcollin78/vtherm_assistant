from dataclasses import dataclass
from urllib.parse import urlsplit

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.models.lite_llm import LiteLlm

from .storage import ModelConfigStore, SecretStore


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

    def agent_for(self, user_id: str) -> Agent:
        stored = self.configs.get(user_id)
        if stored is None:
            raise ValueError("Aucun modèle configuré")
        config = ModelConfig(*stored)
        config.validate()
        if config.provider == "ollama":
            model = LiteLlm(model=f"ollama_chat/{config.model}", api_base=config.url, api_key="ollama")
        else:
            api_key = self.secrets.get(user_id, config.provider)
            if not api_key:
                raise ValueError("Clé du fournisseur manquante")
            if config.provider == "gemini":
                model = Gemini(model=config.model, client_kwargs={"api_key": api_key, "vertexai": False})
            else:
                model = LiteLlm(model=f"{config.provider}/{config.model}", api_key=api_key)
        return Agent(name="vtherm_assistant", model=model)