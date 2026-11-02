import os
import stat

import pytest
from fastapi.testclient import TestClient

from vtherm_assistant.conversations import ConversationStore
from vtherm_assistant.main import SUPERVISOR_ADDRESS, create_app


def test_conversations_persist_and_are_isolated_by_user(tmp_path) -> None:
    directory = tmp_path / "private"
    store = ConversationStore(directory)
    store.save("alice", [{"role": "user", "text": "Chauffage"}], {"thermostat": "salon"})
    store.save("bob", [{"role": "user", "text": "Température"}], {"thermostat": "bureau"})

    restarted = ConversationStore(directory)
    assert restarted.load("alice") == ([{"role": "user", "text": "Chauffage"}], {"thermostat": "salon"})
    assert restarted.load("bob") == ([{"role": "user", "text": "Température"}], {"thermostat": "bureau"})
    assert restarted.load("unknown") is None
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "conversations.sqlite3").stat().st_mode) == 0o600


def test_store_rejects_missing_identity_and_unprotected_directory(tmp_path) -> None:
    store = ConversationStore(tmp_path / "private")
    with pytest.raises(ValueError):
        store.load("")
    with pytest.raises(ValueError):
        store.save("", [], {})
    directory = tmp_path / "public"
    directory.mkdir(mode=0o755)
    os.chmod(directory, 0o755)
    with pytest.raises(PermissionError):
        ConversationStore(directory).load("alice")


def test_conversation_route_uses_verified_identity_after_restart(tmp_path) -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id in {"alice", "bob"}

    directory = tmp_path / "private"
    first_app = create_app("ingress", verify_admin=verify_admin, data_dir=directory)
    first_app.state.conversations.save("alice", [{"text": "Alice"}], {"thermostat": "salon"})
    first_app.state.conversations.save("bob", [{"text": "Bob"}], {"thermostat": "bureau"})
    restarted = create_app("ingress", verify_admin=verify_admin, data_dir=directory)
    with TestClient(restarted, client=(SUPERVISOR_ADDRESS, 12345)) as client:
        response = client.get("/api/conversation?user_id=bob", headers={"X-Remote-User-Id": "alice"})
        assert response.json() == {"messages": [{"text": "Alice"}]}
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/conversation", headers={"X-Remote-User-Id": "bob"}).json() == {"messages": [{"text": "Bob"}]}
        assert client.get("/api/conversation", headers={"X-Remote-User-Id": "other"}).status_code == 403
    assert restarted.state.conversations.load("alice")[1] == {"thermostat": "salon"}