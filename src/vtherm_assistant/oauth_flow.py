import asyncio
import hmac
import secrets
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.requests import HTTPConnection

from .oauth import OAuthConfig, OAuthFailure, OAuthTokens, current_admin, exchange_code, refresh_access_token, revoke_token

PENDING_COOKIE = "__Host-vtherm-oauth"
SESSION_COOKIE = "__Host-vtherm-session"
PENDING_TTL = 600
MAX_PENDING = 1024
SESSION_TTL = 12 * 60 * 60
MAX_SESSIONS = 1024


@dataclass
class PendingLogin:
    state: str = field(repr=False)
    verifier: str = field(repr=False)
    expires_at: float


@dataclass
class Session:
    user_id: str
    tokens: OAuthTokens = field(repr=False)
    expires_at: float
    access_expires_at: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class OAuthFlow:
    def __init__(self, config: OAuthConfig) -> None:
        self.config = config
        self.pending: dict[str, PendingLogin] = {}
        self.sessions: dict[str, Session] = {}
        self.router = APIRouter()
        self.router.add_api_route("/auth/login", self.login, methods=["GET"])
        self.router.add_api_route("/auth/callback", self.callback, methods=["GET"])
        self.router.add_api_route("/auth/logout", self.logout, methods=["POST"])

    async def login(self) -> Response:
        now = time.monotonic()
        self.pending = {key: value for key, value in self.pending.items() if value.expires_at > now}
        if len(self.pending) >= MAX_PENDING:
            return JSONResponse({"detail": "Connexion temporairement indisponible"}, status_code=503)
        browser_key = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        self.pending[browser_key] = PendingLogin(state, verifier, now + PENDING_TTL)
        response = RedirectResponse(self.config.authorization_url(state=state, verifier=verifier), status_code=302)
        response.set_cookie(PENDING_COOKIE, browser_key, max_age=PENDING_TTL, secure=True, httponly=True, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    async def callback(self, request: Request) -> Response:
        browser_key = request.cookies.get(PENDING_COOKIE, "")
        pending = self.pending.pop(browser_key, None)
        states = request.query_params.getlist("state")
        codes = request.query_params.getlist("code")
        if (
            pending is None
            or pending.expires_at <= time.monotonic()
            or len(states) != 1
            or len(codes) != 1
            or not codes[0]
            or not hmac.compare_digest(states[0].encode(), pending.state.encode())
            or "error" in request.query_params
        ):
            return self._denied()
        try:
            tokens = await exchange_code(self.config, codes[0], pending.verifier)
            user_id = await current_admin(self.config, tokens.access_token)
        except OAuthFailure:
            return self._denied()
        if user_id is None:
            return self._denied()
        now = time.monotonic()
        self.sessions = {key: value for key, value in self.sessions.items() if value.expires_at > now}
        if len(self.sessions) >= MAX_SESSIONS:
            await self._revoke_safely(tokens.refresh_token)
            return self._denied()
        previous_key = request.cookies.get(SESSION_COOKIE, "")
        previous = self.sessions.pop(previous_key, None)
        if previous is not None:
            await self._revoke_safely(previous.tokens.refresh_token)
        session_key = secrets.token_urlsafe(32)
        self.sessions[session_key] = Session(user_id, tokens, now + SESSION_TTL, now + tokens.expires_in)
        response = RedirectResponse(self.config.app_url, status_code=303)
        response.delete_cookie(PENDING_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
        response.set_cookie(SESSION_COOKIE, session_key, max_age=SESSION_TTL, secure=True, httponly=True, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    async def require_admin(self, request: HTTPConnection) -> str:
        session_key = request.cookies.get(SESSION_COOKIE, "")
        session = self.sessions.get(session_key)
        if session is None:
            raise HTTPException(status_code=403, detail="Accès refusé")
        async with session.lock:
            if self.sessions.get(session_key) is not session or session.expires_at <= time.monotonic():
                self.sessions.pop(session_key, None)
                raise HTTPException(status_code=403, detail="Accès refusé")
            if session.access_expires_at <= time.monotonic():
                try:
                    session.tokens = await refresh_access_token(self.config, session.tokens.refresh_token)
                except OAuthFailure:
                    self.sessions.pop(session_key, None)
                    raise HTTPException(status_code=403, detail="Accès refusé") from None
                session.access_expires_at = time.monotonic() + session.tokens.expires_in
            user_id = await current_admin(self.config, session.tokens.access_token)
            if self.sessions.get(session_key) is not session:
                raise HTTPException(status_code=403, detail="Accès refusé")
            if user_id != session.user_id:
                self.sessions.pop(session_key, None)
                await self._revoke_safely(session.tokens.refresh_token)
                raise HTTPException(status_code=403, detail="Accès refusé")
            return user_id

    async def logout(self, request: Request) -> Response:
        if request.headers.get("origin") != self.config.app_url.rstrip("/"):
            return self._denied()
        session_key = request.cookies.get(SESSION_COOKIE, "")
        session = self.sessions.pop(session_key, None)
        revoked = True
        if session is not None:
            async with session.lock:
                revoked = await self._revoke_safely(session.tokens.refresh_token)
        if revoked:
            response = Response(status_code=204)
        else:
            response = JSONResponse({"detail": "Déconnexion locale effectuée, révocation HA impossible"}, status_code=503)
        response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    async def _revoke_safely(self, refresh_token: str) -> bool:
        try:
            await revoke_token(self.config, refresh_token)
        except OAuthFailure:
            return False
        return True

    @staticmethod
    def _denied() -> JSONResponse:
        response = JSONResponse({"detail": "Accès refusé"}, status_code=403)
        response.delete_cookie(PENDING_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response