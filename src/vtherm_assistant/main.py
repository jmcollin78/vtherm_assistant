import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.requests import HTTPConnection

from .conversations import ConversationAgentFactory, ConversationRunner, ConversationStore, public_confirmation
from .ha_auth import verify_ingress_admin
from .ha_mcp import HomeAssistantMCP, MCPConnectionError, MCPToolDenied
from .models import ModelConfig, ModelRegistry
from .oauth import OAuthConfig
from .oauth_flow import SESSION_COOKIE, OAuthFlow
from .redaction import log_failure, protect_logs, redact_data
from .storage import ModelConfigStore, PrivateDatabase, SecretStore

FRONTEND = Path(__file__).parent / "frontend" / "index.html"
BRAND_LOGO = Path(__file__).parent / "frontend" / "brand-logo.png"
SUPERVISOR_ADDRESS = "172.30.32.2"
SECRET_NAMES = frozenset({"home_assistant", "gemini", "openai", "anthropic"})
_LOGGER = logging.getLogger(__name__)


class AccessMiddleware:
    def __init__(self, application, *, mode: str, verify_admin, oauth: OAuthFlow | None, secrets: SecretStore) -> None:
        self.app = application
        self.mode = mode
        self.verify_admin = verify_admin
        self.oauth = oauth
        self.secrets = secrets

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
                (method == "GET" and path in ("/", "/brand/logo.png", "/auth/login", "/auth/callback"))
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
                response = JSONResponse({"detail": "Accès refusé"}, status_code=403, headers={"Cache-Control": "no-store", "X-VTherm-Deployment-Mode": self.mode})
                await response(scope, receive, send)
            return
        scope.setdefault("state", {})["user_id"] = user_id
        if self.mode == "ingress":
            scope["state"]["ingress_user_id"] = user_id
        values = list(self.secrets.values(user_id))
        values.append(os.environ.get("SUPERVISOR_TOKEN"))
        if self.oauth is not None:
            session_key = connection.cookies.get(SESSION_COOKIE)
            session = self.oauth.sessions.get(session_key)
            if session is not None:
                values.extend((session_key, session.tokens.access_token, session.tokens.refresh_token))
        async with protect_logs(values):
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
    if mode == "standalone":
        oauth_config = oauth_config or OAuthConfig.from_environment()
    ha_internal_url = oauth_config.ha_internal_url if oauth_config else os.environ.get("VTHERM_HA_INTERNAL_URL")
    application.state.mcp = HomeAssistantMCP(ha_internal_url, application.state.secrets) if ha_internal_url else None
    application.state.conversation_agent = ConversationAgentFactory(application.state.models, application.state.mcp) if application.state.mcp else None
    application.state.conversation_runner = ConversationRunner(application.state.conversation_agent, application.state.conversations) if application.state.conversation_agent else None

    def sensitive_values(request: Request) -> list[str]:
        values = list(application.state.secrets.values(request.state.user_id))
        supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
        if supervisor_token:
            values.append(supervisor_token)
        if oauth is not None:
            session_key = request.cookies.get(SESSION_COOKIE)
            if session_key:
                values.append(session_key)
            for key, session in oauth.sessions.items():
                if session.user_id == request.state.user_id:
                    values.extend((key, session.tokens.access_token, session.tokens.refresh_token))
        return values

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
        if oauth_config is not None:
            oauth = OAuthFlow(oauth_config)
            application.state.oauth = oauth
            application.include_router(oauth.router)
    application.add_middleware(AccessMiddleware, mode=mode, verify_admin=verify_admin, oauth=oauth, secrets=application.state.secrets)

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND)

    @application.get("/brand/logo.png", include_in_schema=False)
    def brand_logo() -> FileResponse:
        return FileResponse(BRAND_LOGO, media_type="image/png")

    @application.get("/api/conversation")
    def get_conversation(request: Request) -> JSONResponse:
        conversation, version = application.state.conversations.snapshot(request.state.user_id)
        messages = conversation[0] if conversation else []
        inventory = conversation[1].get("inventory") if conversation else None
        pending = conversation[1].get("pending_confirmation") if conversation else None
        return JSONResponse(redact_data({
            "messages": messages,
            "inventory": inventory,
            "pending_confirmation": public_confirmation(pending, sensitive_values(request)),
            "version": version,
        }, sensitive_values(request)), headers={"Cache-Control": "no-store"})

    @application.post("/api/conversation/inventory")
    async def initialize_inventory(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            if not isinstance(payload, dict) or set(payload) != {"version"} or type(payload["version"]) is not int or payload["version"] < 0:
                raise ValueError
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return JSONResponse({"detail": "Version de conversation invalide"}, status_code=400, headers={"Cache-Control": "no-store"})
        user_id = request.state.user_id
        conversation, version = application.state.conversations.snapshot(user_id)
        messages, context = conversation if conversation else ([], {})
        if payload["version"] != version:
            return JSONResponse({"detail": "La conversation a changé ; rechargez-la.", "code": "conversation_changed"}, status_code=409, headers={"Cache-Control": "no-store"})
        if context.get("inventory") is not None:
            return JSONResponse(redact_data({"inventory": context["inventory"], "version": version}, sensitive_values(request)), headers={"Cache-Control": "no-store"})
        if messages:
            return JSONResponse({"detail": "La conversation a déjà commencé.", "code": "conversation_changed"}, status_code=409, headers={"Cache-Control": "no-store"})
        if application.state.mcp is None:
            return JSONResponse({"detail": "Connexion Home Assistant non configurée ; vérifiez les paramètres de l'app.", "code": "missing_connection"}, status_code=503, headers={"Cache-Control": "no-store"})
        if not application.state.secrets.get(user_id, "home_assistant"):
            return JSONResponse({"detail": "Enregistrez votre jeton Home Assistant dans la configuration, puis réessayez.", "code": "missing_token"}, status_code=503, headers={"Cache-Control": "no-store"})
        try:
            async with asyncio.timeout(40):
                inventory = await application.state.mcp.inventory_for(user_id)
        except MCPToolDenied as error:
            log_failure(_LOGGER, "conversation.inventory", error)
            return JSONResponse({"detail": "Outil de liste VTherm absent ou ambigu ; vérifiez les API MCP exposées.", "code": "missing_tool"}, status_code=502, headers={"Cache-Control": "no-store"})
        except (MCPConnectionError, TimeoutError) as error:
            log_failure(_LOGGER, "conversation.inventory", error)
            return JSONResponse({"detail": "Lecture de l'inventaire impossible ; vérifiez la connexion MCP et le jeton, puis réessayez.", "code": "mcp_error"}, status_code=502, headers={"Cache-Control": "no-store"})
        inventory = redact_data(inventory, sensitive_values(request))
        if not application.state.conversations.save_if_version(user_id, version, messages, {**context, "inventory": inventory}):
            return JSONResponse({"detail": "La conversation a changé ; rechargez-la.", "code": "conversation_changed"}, status_code=409, headers={"Cache-Control": "no-store"})
        return JSONResponse({"inventory": inventory, "version": version + 1}, headers={"Cache-Control": "no-store"})

    @application.post("/api/conversation")
    async def send_question(request: Request) -> Response:
        if application.state.conversation_runner is None:
            return JSONResponse({"detail": "Connexion Home Assistant non configurée"}, status_code=503, headers={"Cache-Control": "no-store"})
        try:
            payload = await request.json()
            if not isinstance(payload, dict) or "question" not in payload or set(payload) - {"question", "created_at"} or not isinstance(payload["question"], str) or not payload["question"].strip() or len(payload["question"]) > 4000:
                raise ValueError
            sent_at = None
            if "created_at" in payload:
                if not isinstance(payload["created_at"], str) or len(payload["created_at"]) > 64:
                    raise ValueError
                sent_at = datetime.fromisoformat(payload["created_at"])
                if sent_at.tzinfo is None:
                    raise ValueError
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return JSONResponse({"detail": "Question invalide"}, status_code=400, headers={"Cache-Control": "no-store"})
        user_id = request.state.user_id
        secrets = sensitive_values(request)

        async def events():
            arguments = (user_id, payload["question"], secrets) if sent_at is None else (user_id, payload["question"], secrets, sent_at)
            async for event in application.state.conversation_runner.respond(*arguments):
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @application.post("/api/conversation/confirm")
    async def confirm_tool_call(request: Request) -> Response:
        if application.state.conversation_runner is None:
            return JSONResponse({"detail": "Connexion Home Assistant non configurée"}, status_code=503, headers={"Cache-Control": "no-store"})
        try:
            payload = await request.json()
            if (
                not isinstance(payload, dict)
                or set(payload) != {"confirmation_id", "confirmed"}
                or not isinstance(payload["confirmation_id"], str)
                or not payload["confirmation_id"]
                or type(payload["confirmed"]) is not bool
            ):
                raise ValueError
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return JSONResponse({"detail": "Confirmation invalide"}, status_code=400, headers={"Cache-Control": "no-store"})
        user_id = request.state.user_id
        secrets = sensitive_values(request)

        async def events():
            async for event in application.state.conversation_runner.confirm(
                user_id, payload["confirmation_id"], payload["confirmed"], secrets,
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @application.delete("/api/conversation", status_code=204)
    def new_conversation(request: Request) -> Response:
        application.state.conversations.delete(request.state.user_id)
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @application.get("/api/models")
    async def get_models(request: Request, provider: str) -> JSONResponse:
        try:
            payload = await application.state.models.catalog_for(request.state.user_id, provider)
        except ValueError:
            return JSONResponse({"detail": "Fournisseur invalide"}, status_code=400, headers={"Cache-Control": "no-store"})
        return JSONResponse(redact_data(payload, sensitive_values(request)), headers={"Cache-Control": "no-store"})

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