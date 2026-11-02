import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.requests import HTTPConnection

from .conversations import ConversationStore
from .ha_auth import verify_ingress_admin
from .models import ModelConfig, ModelRegistry
from .oauth import OAuthConfig
from .oauth_flow import OAuthFlow
from .storage import ModelConfigStore, PrivateDatabase, SecretStore

FRONTEND = Path(__file__).parent / "frontend" / "index.html"
SUPERVISOR_ADDRESS = "172.30.32.2"
SECRET_NAMES = frozenset({"home_assistant", "gemini", "openai", "anthropic"})


class AccessMiddleware:
    def __init__(self, application, *, mode: str, verify_admin, oauth: OAuthFlow | None) -> None:
        self.app = application
        self.mode = mode
        self.verify_admin = verify_admin
        self.oauth = oauth

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        connection = HTTPConnection(scope)
        user_id = None
        if self.mode == "ingress":
            user_ids = connection.headers.getlist("x-remote-user-id")
            if (
                connection.client is not None
                and connection.client.host == SUPERVISOR_ADDRESS
                and len(user_ids) == 1
                and user_ids[0].strip()
                and user_ids[0] == user_ids[0].strip()
                and (scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS") or connection.headers.getlist("x-vtherm-request") == ["1"])
                and await self.verify_admin(user_ids[0])
            ):
                user_id = user_ids[0]
        else:
            method = scope.get("method")
            path = scope["path"]
            if scope["type"] == "http" and (
                (method == "GET" and path in ("/", "/auth/login", "/auth/callback"))
                or (method == "POST" and path == "/auth/logout")
            ):
                await self.app(scope, receive, send)
                return
            if self.oauth is not None:
                origins = connection.headers.getlist("origin")
                requires_origin = scope["type"] == "websocket" or method not in ("GET", "HEAD", "OPTIONS")
                if not requires_origin or origins == [self.oauth.config.app_url.rstrip("/")]:
                    try:
                        user_id = await self.oauth.require_admin(connection)
                    except HTTPException:
                        pass
        if user_id is None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                response = JSONResponse({"detail": "Accès refusé"}, status_code=403, headers={"Cache-Control": "no-store"})
                await response(scope, receive, send)
            return
        scope.setdefault("state", {})["user_id"] = user_id
        if self.mode == "ingress":
            scope["state"]["ingress_user_id"] = user_id
        await self.app(scope, receive, send)


def create_app(mode: str, *, verify_admin: Callable[[str], Awaitable[bool]] = verify_ingress_admin, oauth_config: OAuthConfig | None = None, data_dir: Path | None = None) -> FastAPI:
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    if mode not in ("ingress", "standalone"):
        raise ValueError("Mode de déploiement inconnu")
    default_data_dir = Path("/data/vtherm-assistant") if mode == "ingress" else Path.home() / ".local" / "share" / "vtherm-assistant"
    database = PrivateDatabase(data_dir or Path(os.environ.get("VTHERM_DATA_DIR", default_data_dir)))
    application.state.conversations = ConversationStore(database)
    application.state.secrets = SecretStore(database)
    application.state.models = ModelRegistry(ModelConfigStore(database), application.state.secrets)

    def redact_secrets(user_id: str, value: str | None) -> str | None:
        if value is None:
            return None
        for name in SECRET_NAMES:
            secret = application.state.secrets.get(user_id, name)
            if secret:
                value = value.replace(secret, "[masqué]")
        return value

    oauth = None
    if mode == "standalone":
        oauth_config = oauth_config or OAuthConfig.from_environment()
        if oauth_config is not None:
            oauth = OAuthFlow(oauth_config)
            application.state.oauth = oauth
            application.include_router(oauth.router)
    application.add_middleware(AccessMiddleware, mode=mode, verify_admin=verify_admin, oauth=oauth)

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND)

    @application.get("/api/conversation")
    def get_conversation(request: Request) -> JSONResponse:
        conversation = application.state.conversations.load(request.state.user_id)
        messages = conversation[0] if conversation else []
        return JSONResponse({"messages": messages}, headers={"Cache-Control": "no-store"})

    @application.delete("/api/conversation", status_code=204)
    def new_conversation(request: Request) -> Response:
        application.state.conversations.delete(request.state.user_id)
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @application.get("/api/model")
    def get_model(request: Request) -> JSONResponse:
        config = application.state.models.configs.get(request.state.user_id)
        payload = {"provider": redact_secrets(request.state.user_id, config[0]), "model": redact_secrets(request.state.user_id, config[1]), "url": redact_secrets(request.state.user_id, config[2])} if config else None
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})

    @application.put("/api/model", status_code=204)
    async def put_model(request: Request) -> Response:
        try:
            payload = await request.json()
            if not isinstance(payload, dict) or set(payload) - {"provider", "model", "url"}:
                raise ValueError
            provider, model, url = payload.get("provider"), payload.get("model"), payload.get("url")
            if not isinstance(provider, str) or not isinstance(model, str) or (url is not None and not isinstance(url, str)):
                raise ValueError
            if any(redact_secrets(request.state.user_id, value) != value for value in (provider, model, url)):
                raise ValueError
            application.state.models.configure(request.state.user_id, ModelConfig(provider, model, url))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return JSONResponse({"detail": "Configuration invalide"}, status_code=400, headers={"Cache-Control": "no-store"})
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @application.put("/api/secrets/{name}", status_code=204)
    async def put_secret(name: str, request: Request) -> Response:
        if name not in SECRET_NAMES:
            return JSONResponse({"detail": "Identifiant inconnu"}, status_code=404, headers={"Cache-Control": "no-store"})
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse({"detail": "Valeur invalide"}, status_code=400, headers={"Cache-Control": "no-store"})
        if not isinstance(payload, dict) or set(payload) != {"value"} or not isinstance(payload["value"], str) or not payload["value"].strip() or len(payload["value"]) > 8192:
            return JSONResponse({"detail": "Valeur invalide"}, status_code=400, headers={"Cache-Control": "no-store"})
        application.state.secrets.put(request.state.user_id, name, payload["value"])
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @application.delete("/api/secrets/{name}", status_code=204)
    def delete_secret(name: str, request: Request) -> Response:
        if name not in SECRET_NAMES:
            return JSONResponse({"detail": "Identifiant inconnu"}, status_code=404, headers={"Cache-Control": "no-store"})
        application.state.secrets.delete(request.state.user_id, name)
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    return application


app = create_app(os.environ.get("VTHERM_DEPLOYMENT_MODE", "standalone"))