import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.requests import HTTPConnection

from .conversations import ConversationStore
from .ha_auth import verify_ingress_admin
from .oauth import OAuthConfig
from .oauth_flow import OAuthFlow

FRONTEND = Path(__file__).parent / "frontend" / "index.html"
SUPERVISOR_ADDRESS = "172.30.32.2"


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
    application.state.conversations = ConversationStore(data_dir or Path(os.environ.get("VTHERM_DATA_DIR", default_data_dir)))
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

    return application


app = create_app(os.environ.get("VTHERM_DEPLOYMENT_MODE", "standalone"))