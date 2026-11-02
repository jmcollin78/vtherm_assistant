import pytest
from fastapi.testclient import TestClient

from vtherm_assistant.main import SUPERVISOR_ADDRESS, create_app
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