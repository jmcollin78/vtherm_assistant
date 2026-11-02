import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vtherm_assistant.ha_auth import verify_ingress_admin


@pytest.mark.parametrize(
    ("users", "expected"),
    [
        ([{"id": "user", "is_active": True, "is_owner": False, "group_ids": ["system-admin"]}], True),
        ([{"id": "user", "is_active": True, "is_owner": True, "group_ids": []}], True),
        ([{"id": "user", "is_active": True, "is_owner": False, "group_ids": []}], False),
        ([{"id": "user", "is_active": False, "is_owner": True, "group_ids": ["system-admin"]}], False),
        ([{"id": "other", "is_active": True, "is_owner": True, "group_ids": []}], False),
        ([{"id": "user", "is_active": "true", "is_owner": True, "group_ids": []}], False),
        ([{"id": "user", "is_active": True, "is_owner": False, "group_ids": "system-admin"}], False),
        ([{"id": "user", "is_active": True, "is_owner": True}] * 2, False),
        ([], False),
    ],
)
def test_admin_status_uses_current_home_assistant_user(monkeypatch, users, expected) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
    websocket = AsyncMock()
    websocket.recv.side_effect = [
        json.dumps({"type": "auth_required"}),
        json.dumps({"type": "auth_ok"}),
        json.dumps({"id": 1, "type": "result", "success": True, "result": users}),
    ]
    connection = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=websocket)
    connection.__aexit__ = AsyncMock(return_value=None)

    with patch("vtherm_assistant.ha_auth.connect", return_value=connection) as connect:
        assert asyncio.run(verify_ingress_admin("user")) is expected

    assert connect.call_args.kwargs["proxy"] is None
    assert json.loads(websocket.send.await_args_list[1].args[0]) == {"id": 1, "type": "config/auth/list"}


@pytest.mark.parametrize("failure", [OSError("connection failed"), ValueError("bad response"), TimeoutError()])
def test_verification_errors_fail_closed(monkeypatch, failure) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
    with patch("vtherm_assistant.ha_auth.connect", side_effect=failure):
        assert asyncio.run(verify_ingress_admin("user")) is False


@pytest.mark.parametrize(
    "messages",
    [
        [json.dumps({"type": "auth_invalid"})],
        [json.dumps({"type": "auth_required"}), json.dumps({"type": "auth_invalid"})],
        [json.dumps({"type": "auth_required"}), json.dumps({"type": "auth_ok"}), "invalid json"],
        [json.dumps({"type": "auth_required"}), json.dumps({"type": "auth_ok"}),
         json.dumps({"id": 1, "type": "result", "success": False})],
        [json.dumps({"type": "auth_required"}), json.dumps({"type": "auth_ok"}),
         json.dumps({"id": 2, "type": "result", "success": True, "result": []})],
    ],
)
def test_invalid_websocket_responses_fail_closed(monkeypatch, messages) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
    websocket = AsyncMock()
    websocket.recv.side_effect = messages
    connection = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=websocket)
    connection.__aexit__ = AsyncMock(return_value=None)
    with patch("vtherm_assistant.ha_auth.connect", return_value=connection):
        assert asyncio.run(verify_ingress_admin("user")) is False


def test_missing_supervisor_token_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    with patch("vtherm_assistant.ha_auth.connect") as connect:
        assert asyncio.run(verify_ingress_admin("user")) is False
    connect.assert_not_called()