import asyncio
import base64
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from vtherm_assistant.main import create_app
from vtherm_assistant.oauth import OAuthConfig, OAuthFailure, current_admin, exchange_code, refresh_access_token, revoke_token
from vtherm_assistant.oauth import OAuthTokens
from vtherm_assistant.oauth_flow import OAuthFlow, SESSION_COOKIE, Session


def test_authorization_uses_public_urls_and_pkce() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    verifier = "a" * 64
    url = config.authorization_url(state="state-value", verifier=verifier)
    parsed = urlsplit(url)
    parameters = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "ha.example"
    assert parsed.path == "/auth/authorize"
    assert parameters["client_id"] == ["https://assistant.example/"]
    assert parameters["redirect_uri"] == ["https://assistant.example/auth/callback"]
    assert parameters["state"] == ["state-value"]
    assert parameters["code_challenge_method"] == ["S256"]
    assert parameters["code_challenge"] == [base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")]
    assert verifier not in url


@pytest.mark.parametrize("invalid", ["http://assistant.example", "https://user:pass@example.com", "https://example.com/path", "https://example.com/?next=other"])
def test_public_app_url_must_be_https_and_unambiguous(invalid: str) -> None:
    with pytest.raises(ValueError):
        OAuthConfig(invalid, "https://ha.example", "http://homeassistant:8123")


def test_internal_ha_url_accepts_https() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "https://homeassistant:8123")
    assert config.ha_internal_url == "https://homeassistant:8123/"


def test_code_exchange_uses_internal_url_and_verifier() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")

    def handle(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://homeassistant:8123/auth/token"
        body = parse_qs(request.content.decode())
        assert body["client_id"] == ["https://assistant.example/"]
        assert body["code"] == ["authorization-code"]
        assert body["code_verifier"] == ["verifier-value"]
        assert request.headers.get("authorization") is None
        return httpx.Response(200, json={"access_token": "secret-access", "refresh_token": "secret-refresh", "token_type": "Bearer", "expires_in": 1800})

    tokens = asyncio.run(exchange_code(config, "authorization-code", "verifier-value", transport=httpx.MockTransport(handle)))
    assert tokens.access_token == "secret-access"
    assert "secret-access" not in repr(tokens)
    assert "secret-refresh" not in repr(tokens)


def test_invalid_token_response_is_rejected() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"access_token": "secret"}))
    with pytest.raises(OAuthFailure):
        asyncio.run(exchange_code(config, "code", "verifier", transport=transport))


def test_refresh_preserves_existing_refresh_token() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")

    def handle(request: httpx.Request) -> httpx.Response:
        body = parse_qs(request.content.decode())
        assert body["grant_type"] == ["refresh_token"]
        assert body["refresh_token"] == ["old-refresh"]
        assert body["client_id"] == [config.app_url]
        return httpx.Response(200, json={"access_token": "new-access", "token_type": "Bearer", "expires_in": 1800})

    tokens = asyncio.run(refresh_access_token(config, "old-refresh", transport=httpx.MockTransport(handle)))
    assert tokens.access_token == "new-access"
    assert tokens.refresh_token == "old-refresh"


def test_revoke_uses_home_assistant_revocation_endpoint() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")

    def handle(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://homeassistant:8123/auth/revoke"
        assert parse_qs(request.content.decode())["token"] == ["refresh-secret"]
        return httpx.Response(200)

    asyncio.run(revoke_token(config, "refresh-secret", transport=httpx.MockTransport(handle)))


@pytest.mark.parametrize("is_admin, expected", [(True, "user-123"), (False, None), ("true", None)])
def test_current_user_must_be_an_administrator(is_admin, expected) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    websocket = AsyncMock()
    websocket.recv.side_effect = [
        json.dumps({"type": "auth_required"}),
        json.dumps({"type": "auth_ok"}),
        json.dumps({"id": 1, "type": "result", "success": True, "result": {"id": "user-123", "is_admin": is_admin}}),
    ]
    connection = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=websocket)
    connection.__aexit__ = AsyncMock(return_value=None)
    with patch("vtherm_assistant.oauth.connect", return_value=connection) as connect:
        assert asyncio.run(current_admin(config, "secret-access")) == expected
    assert connect.call_args.args[0] == "ws://homeassistant:8123/api/websocket"
    assert json.loads(websocket.send.await_args_list[1].args[0]) == {"id": 1, "type": "auth/current_user"}


def test_login_callback_creates_a_protected_session_and_cannot_be_replayed() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    app = create_app("standalone", oauth_config=config)
    with TestClient(app, base_url=config.app_url, follow_redirects=False) as client:
        login = client.get("/auth/login")
        parameters = parse_qs(urlsplit(login.headers["location"]).query)
        assert login.status_code == 302
        assert "Secure" in login.headers["set-cookie"]
        assert "HttpOnly" in login.headers["set-cookie"]
        assert "SameSite=lax" in login.headers["set-cookie"]
        with patch("vtherm_assistant.oauth_flow.exchange_code", new_callable=AsyncMock, return_value=OAuthTokens("access", "refresh", 1800)) as exchange, patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value="user-123"):
            callback = client.get("/auth/callback", params={"state": parameters["state"][0], "code": "auth-code"})
            assert callback.status_code == 303
            assert callback.headers["location"] == config.app_url
            assert "access" not in callback.headers["set-cookie"]
            assert exchange.await_count == 1
            assert client.get("/auth/callback", params={"state": parameters["state"][0], "code": "auth-code"}).status_code == 403
    assert len(app.state.oauth.sessions) == 1
    assert next(iter(app.state.oauth.sessions.values())).user_id == "user-123"


@pytest.mark.parametrize("params", [{"state": "forged", "code": "code"}, {"state": "é", "code": "code"}, {"state": "forged"}, {"code": "code"}])
def test_forged_callbacks_are_rejected_without_exchanging_code(params) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    app = create_app("standalone", oauth_config=config)
    with TestClient(app, base_url=config.app_url, follow_redirects=False) as client:
        client.get("/auth/login")
        with patch("vtherm_assistant.oauth_flow.exchange_code", new_callable=AsyncMock) as exchange:
            assert client.get("/auth/callback", params=params).status_code == 403
            exchange.assert_not_awaited()
    assert not app.state.oauth.sessions


@pytest.mark.parametrize("failure", ["non_admin", "exchange", "expired"])
def test_login_failures_do_not_create_a_session(failure) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    app = create_app("standalone", oauth_config=config)
    with TestClient(app, base_url=config.app_url, follow_redirects=False) as client:
        login = client.get("/auth/login")
        state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
        if failure == "expired":
            next(iter(app.state.oauth.pending.values())).expires_at = 0
        exchange_result = OAuthTokens("access", "refresh", 1800)
        with patch("vtherm_assistant.oauth_flow.exchange_code", new_callable=AsyncMock, return_value=exchange_result) as exchange, patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value=None):
            if failure == "exchange":
                exchange.side_effect = OAuthFailure("secret should not be shown")
            response = client.get("/auth/callback", params={"state": state, "code": "auth-code"})
            assert response.status_code == 403
            assert "secret" not in response.text
            assert response.headers["cache-control"] == "no-store"
    assert not app.state.oauth.sessions


def test_sessions_are_isolated_and_logout_revokes_only_the_current_user() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    app = create_app("standalone", oauth_config=config)

    @app.get("/test-private")
    async def private(request: Request) -> dict[str, str]:
        return {"user_id": request.state.user_id}

    with TestClient(app, base_url=config.app_url, follow_redirects=False) as first, TestClient(app, base_url=config.app_url, follow_redirects=False) as second:
        for client, user_id in ((first, "first"), (second, "second")):
            login = client.get("/auth/login")
            state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
            with patch("vtherm_assistant.oauth_flow.exchange_code", new_callable=AsyncMock, return_value=OAuthTokens(user_id, f"refresh-{user_id}", 1800)), patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value=user_id):
                assert client.get("/auth/callback", params={"state": state, "code": "code"}).status_code == 303
        with patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, side_effect=lambda config, token: token), patch("vtherm_assistant.oauth_flow.revoke_token", new_callable=AsyncMock) as revoke:
            assert first.get("/test-private").json() == {"user_id": "first"}
            assert second.get("/test-private").json() == {"user_id": "second"}
            assert first.post("/auth/logout", headers={"Origin": "https://attacker.example"}).status_code == 403
            assert first.post("/auth/logout", headers={"Origin": "https://assistant.example"}).status_code == 204
            revoke.assert_awaited_once_with(config, "refresh-first")
            assert first.get("/test-private").status_code == 403
            assert second.get("/test-private").json() == {"user_id": "second"}


def test_expired_access_is_refreshed_and_loss_of_admin_revokes_session() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    app = create_app("standalone", oauth_config=config)

    @app.get("/test-private")
    async def private(request: Request) -> dict[str, str]:
        return {"user_id": request.state.user_id}

    with TestClient(app, base_url=config.app_url, follow_redirects=False) as client:
        state = parse_qs(urlsplit(client.get("/auth/login").headers["location"]).query)["state"][0]
        with patch("vtherm_assistant.oauth_flow.exchange_code", new_callable=AsyncMock, return_value=OAuthTokens("old", "refresh", 1800)), patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value="user"):
            assert client.get("/auth/callback", params={"state": state, "code": "code"}).status_code == 303
        session = next(iter(app.state.oauth.sessions.values()))
        session.access_expires_at = 0
        with patch("vtherm_assistant.oauth_flow.refresh_access_token", new_callable=AsyncMock, return_value=OAuthTokens("new", "refresh", 1800)) as refresh, patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, side_effect=["user", None]), patch("vtherm_assistant.oauth_flow.revoke_token", new_callable=AsyncMock) as revoke:
            assert client.get("/test-private").status_code == 200
            refresh.assert_awaited_once_with(config, "refresh")
            assert client.get("/test-private").status_code == 403
            revoke.assert_awaited_once_with(config, "refresh")
            assert client.get("/test-private").status_code == 403


def test_logout_during_rights_check_denies_the_inflight_request() -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")

    async def scenario() -> None:
        flow = OAuthFlow(config)
        flow.sessions["session"] = Session("user", OAuthTokens("access", "refresh", 1800), float("inf"), float("inf"))
        checked = asyncio.Event()
        resume = asyncio.Event()

        async def verify(config, token):
            checked.set()
            await resume.wait()
            return "user"

        scope = {"type": "http", "method": "GET", "path": "/", "headers": [(b"cookie", f"{SESSION_COOKIE}=session".encode()), (b"origin", b"https://assistant.example")]}
        with patch("vtherm_assistant.oauth_flow.current_admin", side_effect=verify), patch("vtherm_assistant.oauth_flow.revoke_token", new_callable=AsyncMock):
            authentication = asyncio.create_task(flow.require_admin(Request(scope)))
            await checked.wait()
            logout = asyncio.create_task(flow.logout(Request(scope)))
            await asyncio.sleep(0)
            resume.set()
            with pytest.raises(HTTPException) as error:
                await authentication
            assert error.value.status_code == 403
            assert (await logout).status_code == 204

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["expired", "refresh", "revoke"])
def test_session_and_revocation_fail_closed(failure) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    app = create_app("standalone", oauth_config=config)

    @app.get("/test-private")
    async def private(request: Request) -> dict[str, str]:
        return {"user_id": request.state.user_id}

    with TestClient(app, base_url=config.app_url, follow_redirects=False) as client:
        state = parse_qs(urlsplit(client.get("/auth/login").headers["location"]).query)["state"][0]
        with patch("vtherm_assistant.oauth_flow.exchange_code", new_callable=AsyncMock, return_value=OAuthTokens("access", "refresh", 1800)), patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value="user"):
            assert client.get("/auth/callback", params={"state": state, "code": "code"}).status_code == 303
        session = next(iter(app.state.oauth.sessions.values()))
        if failure == "expired":
            session.expires_at = 0
            assert client.get("/test-private").status_code == 403
        elif failure == "refresh":
            session.access_expires_at = 0
            with patch("vtherm_assistant.oauth_flow.refresh_access_token", new_callable=AsyncMock, side_effect=OAuthFailure("secret")):
                assert client.get("/test-private").status_code == 403
        else:
            with patch("vtherm_assistant.oauth_flow.revoke_token", new_callable=AsyncMock, side_effect=OAuthFailure("secret")):
                response = client.post("/auth/logout", headers={"Origin": "https://assistant.example"})
                assert response.status_code == 503
                assert "secret" not in response.text
            assert client.get("/test-private").status_code == 403