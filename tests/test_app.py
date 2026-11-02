import os
import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vtherm_assistant.__main__ import main
from vtherm_assistant.main import SUPERVISOR_ADDRESS, app, create_app
from vtherm_assistant.oauth import OAuthConfig, OAuthTokens
from vtherm_assistant.oauth_flow import SESSION_COOKIE, Session


def test_frontend_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "VTherm Assistant" in response.text


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


def test_ingress_accepts_only_supervisor_with_an_unambiguous_identity() -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id == "user-123"

    ingress_app = create_app("ingress", verify_admin=verify_admin)

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


def test_server_does_not_trust_forwarded_client_addresses(monkeypatch) -> None:
    monkeypatch.setenv("VTHERM_DEPLOYMENT_MODE", "ingress")
    with patch("vtherm_assistant.__main__.uvicorn.run") as run:
        main()

    assert run.call_args.kwargs["proxy_headers"] is False


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