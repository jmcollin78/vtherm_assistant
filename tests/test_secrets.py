import pytest
from fastapi.testclient import TestClient

from vtherm_assistant.main import SUPERVISOR_ADDRESS, create_app
from vtherm_assistant.redaction import StreamingRedactor
from vtherm_assistant.storage import PrivateDatabase, SecretStore


@pytest.mark.parametrize("name", ["home_assistant", "gemini", "openai", "anthropic"])
def test_secret_storage_persists_replaces_and_isolates_users(tmp_path, name) -> None:
    directory = tmp_path / "private"
    secrets = SecretStore(PrivateDatabase(directory))
    secrets.put("alice", name, "first-secret")
    secrets.put("bob", name, "other-secret")
    secrets.put("alice", name, "replacement-secret")
    restarted = SecretStore(PrivateDatabase(directory))
    assert restarted.get("alice", name) == "replacement-secret"
    assert restarted.get("bob", name) == "other-secret"
    restarted.delete("alice", name)
    assert restarted.get("alice", name) is None
    assert restarted.get("bob", name) == "other-secret"


def test_secret_routes_require_admin_do_not_return_values_and_respect_identity(tmp_path, caplog) -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id in {"alice", "bob"}

    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client:
        headers = {"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"}
        assert client.put("/api/secrets/openai", json={"value": "secret-alice"}).status_code == 403
        assert client.put("/api/secrets/openai?user_id=bob", headers=headers, json={"value": "secret-alice"}).status_code == 204
        assert client.get("/api/secrets/openai", headers=headers).status_code == 405
        response = client.put("/api/secrets/openai", headers=headers, json={"value": ["secret-invalid"]})
        assert response.status_code == 400
        assert "secret-invalid" not in response.text
        assert client.delete("/api/secrets/openai", headers={"X-Remote-User-Id": "bob", "X-VTherm-Request": "1"}).status_code == 204
        assert application.state.secrets.get("alice", "openai") == "secret-alice"
        assert client.delete("/api/secrets/openai", headers=headers).status_code == 204
        assert application.state.secrets.get("alice", "openai") is None
    assert "secret-alice" not in caplog.text
    assert "secret-invalid" not in caplog.text


def test_model_configuration_does_not_expose_a_saved_key(tmp_path) -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id == "alice"

    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    headers = {"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"}
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client:
        assert client.put("/api/secrets/openai", headers=headers, json={"value": "secret-alice"}).status_code == 204
        response = client.put("/api/model", headers=headers, json={"provider": "openai", "model": "secret-alice"})
        assert response.status_code == 400
        assert "secret-alice" not in client.get("/api/model", headers=headers).text
        application.state.models.configs.put("alice", "ollama", "model", "http://secret-alice:11434")
        assert "secret-alice" not in client.get("/api/model", headers=headers).text


@pytest.mark.parametrize("fragments", [
    ["token-alice"],
    ["token-", "ali", "ce"],
    ["to", "ken-alice", " et ", "api", "-key"],
    ["token-alice et api-key"],
])
def test_streaming_redaction_masks_secrets_across_fragments(fragments) -> None:
    redactor = StreamingRedactor(["token-alice", "api-key"])
    output = "".join(redactor.feed(fragment) for fragment in fragments) + redactor.feed("", final=True)
    assert "token-alice" not in output
    assert "api-key" not in output
    assert "[masqué]" in output


def test_streaming_redaction_handles_overlapping_secrets_and_incomplete_prefix() -> None:
    redactor = StreamingRedactor(["secret", "secret-long"])
    output = redactor.feed("secret") + redactor.feed("-long et sec") + redactor.feed("", final=True)
    assert output == "[masqué] et sec"