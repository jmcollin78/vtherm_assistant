import os
import stat
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from vtherm_assistant.conversations import ConversationStore
from vtherm_assistant.main import SUPERVISOR_ADDRESS, create_app
from vtherm_assistant.oauth import OAuthConfig, OAuthTokens
from vtherm_assistant.oauth_flow import SESSION_COOKIE, Session
from vtherm_assistant.storage import PrivateDatabase


def test_conversations_persist_and_are_isolated_by_user(tmp_path) -> None:
    directory = tmp_path / "private"
    store = ConversationStore(PrivateDatabase(directory))
    store.save("alice", [{"role": "user", "text": "Chauffage"}], {"thermostat": "salon"})
    store.save("bob", [{"role": "user", "text": "Température"}], {"thermostat": "bureau"})

    restarted = ConversationStore(PrivateDatabase(directory))
    assert restarted.load("alice") == ([{"role": "user", "text": "Chauffage"}], {"thermostat": "salon"})
    assert restarted.load("bob") == ([{"role": "user", "text": "Température"}], {"thermostat": "bureau"})
    assert restarted.load("unknown") is None
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "conversations.sqlite3").stat().st_mode) == 0o600


def test_store_rejects_missing_identity_and_unprotected_directory(tmp_path) -> None:
    store = ConversationStore(PrivateDatabase(tmp_path / "private"))
    with pytest.raises(ValueError):
        store.load("")
    with pytest.raises(ValueError):
        store.save("", [], {})
    directory = tmp_path / "public"
    directory.mkdir(mode=0o755)
    os.chmod(directory, 0o755)
    with pytest.raises(PermissionError):
        ConversationStore(PrivateDatabase(directory)).load("alice")


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
        assert client.delete("/api/conversation", headers={"X-Remote-User-Id": "alice"}).status_code == 403
        assert client.delete("/api/conversation?user_id=bob", headers={"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"}).status_code == 204
        assert client.get("/api/conversation", headers={"X-Remote-User-Id": "alice"}).json() == {"messages": []}
        assert client.get("/api/conversation", headers={"X-Remote-User-Id": "bob"}).json() == {"messages": [{"text": "Bob"}]}
    assert restarted.state.conversations.load("alice") is None
    assert restarted.state.conversations.load("bob")[1] == {"thermostat": "bureau"}


def test_new_conversation_removes_only_the_current_users_messages_and_context(tmp_path) -> None:
    directory = tmp_path / "private"
    store = ConversationStore(PrivateDatabase(directory))
    store.save("alice", [{"text": "Ancienne question"}], {"thermostat": "salon"})
    store.save("bob", [{"text": "Autre question"}], {"thermostat": "bureau"})
    store.delete("alice")

    restarted = ConversationStore(PrivateDatabase(directory))
    assert restarted.load("alice") is None
    assert restarted.load("bob") == ([{"text": "Autre question"}], {"thermostat": "bureau"})
    restarted.save("alice", [{"text": "Nouvelle question"}], {})
    assert restarted.load("alice") == ([{"text": "Nouvelle question"}], {})
    with pytest.raises(ValueError):
        restarted.delete("")


def test_standalone_new_conversation_requires_admin_and_same_origin(tmp_path) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    application.state.conversations.save("alice", [{"text": "Question"}], {"thermostat": "salon"})
    with TestClient(application, base_url=config.app_url) as client:
        assert client.delete("/api/conversation", headers={"Origin": config.app_url.rstrip("/")}).status_code == 403
        application.state.oauth.sessions["session"] = Session("alice", OAuthTokens("access", "refresh", 1800), float("inf"), float("inf"))
        client.cookies.set(SESSION_COOKIE, "session")
        with patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value="alice"):
            assert client.delete("/api/conversation", headers={"Origin": "https://attacker.example"}).status_code == 403
            assert client.delete("/api/conversation", headers={"Origin": config.app_url.rstrip("/")}).status_code == 204
    assert application.state.conversations.load("alice") is None