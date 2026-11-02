import os
import subprocess
import sys
from unittest.mock import patch

from fastapi import Request
from fastapi.testclient import TestClient

from vtherm_assistant.__main__ import main
from vtherm_assistant.main import SUPERVISOR_ADDRESS, app, create_app


def test_frontend_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "VTherm Assistant" in response.text


def test_private_endpoints_are_unavailable() -> None:
    with TestClient(app) as client:
        for path in ("/conversation", "/configuration", "/api/conversation"):
            assert client.get(path, headers={"X-Remote-User-Id": "forged"}).status_code == 404


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