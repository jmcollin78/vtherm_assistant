import json
import os
import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vtherm_assistant.__main__ import _configure_ingress, main
from vtherm_assistant.main import SUPERVISOR_ADDRESS, app, create_app
from vtherm_assistant.oauth import OAuthConfig, OAuthTokens
from vtherm_assistant.oauth_flow import SESSION_COOKIE, Session


def test_frontend_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "VTherm Assistant" in response.text
    assert 'src="brand/logo.png"' in response.text

    logo = client.get("/brand/logo.png")
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"
    assert logo.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_private_endpoints_are_unavailable() -> None:
    with TestClient(app) as client:
        for path in ("/conversation", "/configuration", "/api/conversation"):
            assert client.get(path, headers={"X-Remote-User-Id": "forged"}).status_code == 403


def test_adk_and_app_start_without_provider_credentials() -> None:
    environment = os.environ.copy()
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        environment.pop(name, None)

    result = subprocess.run(
        [sys.executable, "-c", "from google.adk.agents import Agent; from vtherm_assistant.main import app"],
        env={**environment, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_ingress_accepts_only_supervisor_with_an_unambiguous_identity(tmp_path) -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id == "user-123"

    ingress_app = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")

    @ingress_app.get("/identity")
    def identity(request: Request) -> dict[str, str]:
        return {"user_id": request.state.ingress_user_id}

    with TestClient(ingress_app, client=(SUPERVISOR_ADDRESS, 12345)) as client:
        assert client.get("/", headers={"X-Remote-User-Id": "user-123"}).status_code == 200
        assert client.get("/identity", headers={"X-Remote-User-Id": "user-123"}).json() == {"user_id": "user-123"}
        assert client.get("/").status_code == 403
        assert client.get("/", headers={"X-Remote-User-Id": " "}).status_code == 403
        assert client.get("/", headers=[("X-Remote-User-Id", "a"), ("X-Remote-User-Id", "b")]).status_code == 403
        assert client.get("/", headers={"X-Remote-User-Id": "other-user"}).status_code == 403


def test_ingress_refuses_direct_requests_and_forged_forwarded_headers() -> None:
    ingress_app = create_app("ingress")
    with TestClient(ingress_app, client=("127.0.0.1", 12345)) as client:
        response = client.get(
            "/",
            headers={"X-Remote-User-Id": "forged", "X-Forwarded-For": SUPERVISOR_ADDRESS},
        )
        assert response.status_code == 403
        assert response.headers["x-vtherm-deployment-mode"] == "ingress"
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("mode", ["ingress", "standalone"])
def test_private_refusal_identifies_only_deployment_mode(tmp_path, mode) -> None:
    async def verify_admin(_user_id):
        return False

    application = create_app(mode, verify_admin=verify_admin, data_dir=tmp_path / "private")
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client:
        response = client.get("/api/conversation", headers={"X-Remote-User-Id": "unknown"})
    assert response.status_code == 403
    assert response.headers["x-vtherm-deployment-mode"] == mode
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "Accès refusé"}


def test_server_does_not_trust_forwarded_client_addresses(monkeypatch) -> None:
    monkeypatch.setenv("VTHERM_DEPLOYMENT_MODE", "ingress")
    with patch("vtherm_assistant.__main__.uvicorn.run") as run:
        main()

    assert run.call_args.kwargs["proxy_headers"] is False


@pytest.mark.parametrize("options,expected", [
    ({}, "http://homeassistant:8123/"),
    ({"ha_internal_url": "http://homeassistant:8124"}, "http://homeassistant:8124/"),
    ({"ha_internal_url": "https://ha.example:8443/"}, "https://ha.example:8443/"),
])
def test_ingress_options_are_applied_before_server_load(tmp_path, monkeypatch, options, expected):
    options_path = tmp_path / "options.json"
    options_path.write_text(json.dumps(options), encoding="utf-8")
    monkeypatch.setenv("VTHERM_DEPLOYMENT_MODE", "ingress")
    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "http://previous:8123")

    def check_server_environment(*_args, **_kwargs):
        assert os.environ["VTHERM_HA_INTERNAL_URL"] == expected

    with patch("vtherm_assistant.__main__._configure_ingress", side_effect=lambda: _configure_ingress(options_path)), \
         patch("vtherm_assistant.__main__.uvicorn.run") as run:
        run.side_effect = check_server_environment
        main()
    assert run.called
    assert os.environ["VTHERM_HA_INTERNAL_URL"] == expected
    assert run.call_args.args == ("vtherm_assistant.main:app",)


@pytest.mark.parametrize("contents", [
    b'{"ha_internal_url": "FAKE_SECRET"', b"\xff", b"[]", b"null",
    b'{"unknown": "FAKE_SECRET"}', b'{"ha_internal_url": null}', b'{"ha_internal_url": 8123}',
    b'{"ha_internal_url": "http://FAKE_SECRET@homeassistant:8123"}',
    b'{"ha_internal_url": "http://homeassistant:invalid/FAKE_SECRET"}',
    b'{"ha_internal_url": "http://homeassistant:8123/api/mcp?FAKE_SECRET"}',
    b'{"ha_internal_url": "ftp://homeassistant/FAKE_SECRET"}',
])
def test_ingress_invalid_options_fail_without_exposing_contents(tmp_path, monkeypatch, contents):
    options_path = tmp_path / "options.json"
    options_path.write_bytes(contents)
    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "http://previous:8123")
    with pytest.raises(ValueError) as failure:
        _configure_ingress(options_path)
    assert "FAKE_SECRET" not in str(failure.value)
    assert os.environ["VTHERM_HA_INTERNAL_URL"] == "http://previous:8123"


@pytest.mark.parametrize("supervised", [False, True])
def test_ingress_missing_options_depends_on_supervisor(tmp_path, monkeypatch, supervised):
    options_path = tmp_path / "absent.json"
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "https://ha.example:8443")
    if supervised:
        monkeypatch.setenv("SUPERVISOR_TOKEN", "FAKE_SUPERVISOR_TOKEN")
        with pytest.raises(ValueError, match="manquantes"):
            _configure_ingress(options_path)
        assert os.environ["VTHERM_HA_INTERNAL_URL"] == "https://ha.example:8443"
    else:
        _configure_ingress(options_path)
        assert os.environ["VTHERM_HA_INTERNAL_URL"] == "https://ha.example:8443/"


def test_ingress_missing_development_options_preserves_unconfigured_state(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    monkeypatch.delenv("VTHERM_HA_INTERNAL_URL", raising=False)
    _configure_ingress(tmp_path / "absent.json")
    assert "VTHERM_HA_INTERNAL_URL" not in os.environ


def test_ingress_unreadable_options_fail_safely(tmp_path):
    with patch("pathlib.Path.read_text", side_effect=PermissionError("FAKE_SECRET")):
        with pytest.raises(ValueError, match="illisibles") as failure:
            _configure_ingress(tmp_path / "options.json")
    assert "FAKE_SECRET" not in str(failure.value)


def test_standalone_launch_never_reads_app_options(monkeypatch):
    monkeypatch.setenv("VTHERM_DEPLOYMENT_MODE", "standalone")
    with patch("vtherm_assistant.__main__._configure_ingress") as configure, \
         patch("vtherm_assistant.__main__.uvicorn.run") as run:
        main()
    configure.assert_not_called()
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert run.call_args.kwargs["port"] == 8765


def test_private_http_and_websocket_routes_require_verified_identity() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    secured_app = create_app("standalone", oauth_config=config)

    async def private(request: Request) -> dict[str, str]:
        return {"user_id": request.state.user_id}

    for path in ("/test/conversation", "/api/configuration", "/api/request"):
        secured_app.add_api_route(path, private, methods=["GET", "POST"])

    @secured_app.websocket("/api/stream")
    async def stream(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text(websocket.state.user_id)
        await websocket.close()

    with TestClient(secured_app, base_url=config.app_url) as client:
        for path in ("/test/conversation", "/api/configuration", "/api/request"):
            assert client.get(path, headers={"X-Remote-User-Id": "forged"}).status_code == 403
            assert client.post(path, headers={"Origin": "https://assistant.example"}).status_code == 403
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/stream", headers={"Origin": "https://assistant.example"}):
                pass

        secured_app.state.oauth.sessions["session"] = Session("user", OAuthTokens("access", "refresh", 1800), float("inf"), float("inf"))
        client.cookies.set(SESSION_COOKIE, "session")
        with patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value="user"):
            for path in ("/test/conversation", "/api/configuration", "/api/request"):
                assert client.get(path).json() == {"user_id": "user"}
                assert client.post(path, headers={"Origin": "https://attacker.example"}).status_code == 403
                assert client.post(path, headers={"Origin": "https://assistant.example"}).status_code == 200
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect("/api/stream", headers={"Origin": "https://attacker.example"}):
                    pass
            with client.websocket_connect("/api/stream", headers={"Origin": "https://assistant.example"}) as websocket:
                assert websocket.receive_text() == "user"