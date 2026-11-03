import asyncio
import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc6749.errors import OAuth2Error
from authlib.oauth2.client import OAuth2Client
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .redaction import protect_logs


def _validate_base_url(url: str, *, public: bool) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme not in ({"https"} if public else {"http", "https"})
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path not in ("", "/")
    ):
        raise ValueError("URL de base OAuth invalide")
    try:
        parts.port
    except ValueError as error:
        raise ValueError("URL de base OAuth invalide") from error
    return url.rstrip("/") + "/"


@dataclass(frozen=True)
class OAuthConfig:
    app_url: str
    ha_browser_url: str
    ha_internal_url: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_url", _validate_base_url(self.app_url, public=True))
        object.__setattr__(self, "ha_browser_url", _validate_base_url(self.ha_browser_url, public=True))
        object.__setattr__(self, "ha_internal_url", _validate_base_url(self.ha_internal_url, public=False))

    def authorization_url(self, *, state: str, verifier: str) -> str:
        client = OAuth2Client(
            session=None,
            client_id=self.app_url,
            redirect_uri=self.app_url + "auth/callback",
            code_challenge_method="S256",
        )
        url, _ = client.create_authorization_url(
            self.ha_browser_url + "auth/authorize", state=state, code_verifier=verifier
        )
        return url

    @classmethod
    def from_environment(cls) -> "OAuthConfig | None":
        values = [os.environ.get(name) for name in ("VTHERM_APP_URL", "VTHERM_HA_BROWSER_URL", "VTHERM_HA_INTERNAL_URL")]
        if not any(values):
            return None
        if not all(values):
            raise ValueError("Configuration OAuth incomplète")
        return cls(values[0], values[1], values[2])


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int


class OAuthFailure(Exception):
    pass


async def exchange_code(
    config: OAuthConfig, code: str, verifier: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> OAuthTokens:
    try:
        async with protect_logs((code, verifier)), AsyncOAuth2Client(
            client_id=config.app_url,
            redirect_uri=config.app_url + "auth/callback",
            token_endpoint_auth_method="none",
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=5,
        ) as client:
            token = await client.fetch_token(
                config.ha_internal_url + "auth/token",
                grant_type="authorization_code",
                code=code,
                code_verifier=verifier,
            )
    except (httpx.HTTPError, OAuth2Error, ValueError, TypeError) as error:
        raise OAuthFailure("Échange OAuth impossible") from error

    return _parse_tokens(token)


def _parse_tokens(token: dict, previous_refresh_token: str | None = None) -> OAuthTokens:
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token", previous_refresh_token)
    expires_in = token.get("expires_in")
    if (
        not isinstance(access_token, str)
        or not access_token
        or not isinstance(refresh_token, str)
        or not refresh_token
        or not isinstance(expires_in, int)
        or isinstance(expires_in, bool)
        or expires_in <= 0
        or str(token.get("token_type", "")).lower() != "bearer"
    ):
        raise OAuthFailure("Réponse OAuth invalide")
    return OAuthTokens(access_token, refresh_token, expires_in)


async def refresh_access_token(
    config: OAuthConfig, refresh_token: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> OAuthTokens:
    try:
        async with protect_logs((refresh_token,)), AsyncOAuth2Client(
            client_id=config.app_url,
            token_endpoint_auth_method="none",
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=5,
        ) as client:
            token = await client.refresh_token(config.ha_internal_url + "auth/token", refresh_token=refresh_token)
    except (httpx.HTTPError, OAuth2Error, ValueError, TypeError) as error:
        raise OAuthFailure("Renouvellement OAuth impossible") from error
    return _parse_tokens(token, refresh_token)


async def revoke_token(
    config: OAuthConfig, refresh_token: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    try:
        async with protect_logs((refresh_token,)), AsyncOAuth2Client(
            client_id=config.app_url,
            token_endpoint_auth_method="none",
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=5,
        ) as client:
            response = await client.revoke_token(config.ha_internal_url + "auth/revoke", token=refresh_token)
            response.raise_for_status()
    except (httpx.HTTPError, OAuth2Error, ValueError, TypeError) as error:
        raise OAuthFailure("Révocation OAuth impossible") from error


async def current_admin(config: OAuthConfig, access_token: str) -> str | None:
    return await current_admin_for_url(config.ha_internal_url, access_token)


async def current_admin_for_url(ha_internal_url: str, access_token: str) -> str | None:
    parts = urlsplit(ha_internal_url)
    websocket_url = urlunsplit(("wss" if parts.scheme == "https" else "ws", parts.netloc, "/api/websocket", "", ""))
    try:
        async with protect_logs((access_token,)), asyncio.timeout(5):
            async with connect(websocket_url, proxy=None, close_timeout=1) as websocket:
                greeting = json.loads(await websocket.recv())
                if not isinstance(greeting, dict) or greeting.get("type") != "auth_required":
                    return None
                await websocket.send(json.dumps({"type": "auth", "access_token": access_token}))
                authentication = json.loads(await websocket.recv())
                if not isinstance(authentication, dict) or authentication.get("type") != "auth_ok":
                    return None
                await websocket.send(json.dumps({"id": 1, "type": "auth/current_user"}))
                response = json.loads(await websocket.recv())
    except (OSError, TimeoutError, WebSocketException, ValueError, TypeError):
        return None

    if (
        not isinstance(response, dict)
        or response.get("id") != 1
        or response.get("type") != "result"
        or response.get("success") is not True
        or not isinstance(response.get("result"), dict)
    ):
        return None
    user = response["result"]
    user_id = user.get("id")
    if user.get("is_admin") is not True or not isinstance(user_id, str) or not user_id:
        return None
    return user_id