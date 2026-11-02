import pytest
from google.adk.models import Gemini
from google.adk.models.lite_llm import LiteLlm
from fastapi.testclient import TestClient

from vtherm_assistant.main import SUPERVISOR_ADDRESS, create_app
from vtherm_assistant.models import ModelConfig, ModelRegistry
from vtherm_assistant.storage import ModelConfigStore, PrivateDatabase, SecretStore


def test_model_configuration_and_keys_are_isolated_by_user(tmp_path) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "gemini", "alice-key")
    secrets.put("bob", "openai", "bob-key")
    registry.configure("alice", ModelConfig("gemini", "gemini-test"))
    registry.configure("bob", ModelConfig("openai", "model-test"))

    alice = registry.agent_for("alice").model
    bob = registry.agent_for("bob").model
    assert isinstance(alice, Gemini)
    assert getattr(alice, "client_kwargs") == {"api_key": "alice-key", "vertexai": False}
    assert isinstance(bob, LiteLlm)
    assert getattr(bob, "model") == "openai/model-test"
    assert getattr(bob, "_additional_args")["api_key"] == "bob-key"
    assert "alice-key" not in repr(alice)
    assert "bob-key" not in repr(bob)
    with pytest.raises(ValueError):
        registry.agent_for("unknown")


def test_local_model_does_not_require_a_remote_key(tmp_path) -> None:
    database = PrivateDatabase(tmp_path / "private")
    registry = ModelRegistry(ModelConfigStore(database), SecretStore(database))
    registry.configure("alice", ModelConfig("ollama", "model:latest", "http://ollama:11434"))
    model = registry.agent_for("alice").model
    assert isinstance(model, LiteLlm)
    assert getattr(model, "model") == "ollama_chat/model:latest"
    assert getattr(model, "_additional_args")["api_base"] == "http://ollama:11434"


@pytest.mark.parametrize("config", [
    ModelConfig("unknown", "model"),
    ModelConfig("openai", ""),
    ModelConfig("ollama", "model", "http://user:secret@localhost"),
    ModelConfig("ollama", "model", "file:///tmp/model"),
    ModelConfig("gemini", "model", "https://example.com"),
])
def test_invalid_model_configuration_is_rejected(config) -> None:
    with pytest.raises(ValueError):
        config.validate()


def test_model_config_route_is_private_and_isolated(tmp_path) -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id in {"alice", "bob"}

    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    alice = {"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"}
    bob = {"X-Remote-User-Id": "bob", "X-VTherm-Request": "1"}
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client:
        assert client.get("/api/model").status_code == 403
        assert client.put("/api/model", headers=alice, json={"provider": "gemini", "model": "model-a"}).status_code == 204
        assert client.put("/api/model", headers=bob, json={"provider": "ollama", "model": "model-b", "url": "http://ollama:11434"}).status_code == 204
        assert client.get("/api/model?user_id=bob", headers=alice).json() == {"provider": "gemini", "model": "model-a", "url": None}
        assert client.get("/api/model", headers=bob).json() == {"provider": "ollama", "model": "model-b", "url": "http://ollama:11434"}
        response = client.put("/api/model", headers=alice, json={"provider": "bad-secret", "model": "model"})
        assert response.status_code == 400
        assert "bad-secret" not in response.text