import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .ha_auth import verify_ingress_admin

FRONTEND = Path(__file__).parent / "frontend" / "index.html"
SUPERVISOR_ADDRESS = "172.30.32.2"


def create_app(mode: str, *, verify_admin: Callable[[str], Awaitable[bool]] = verify_ingress_admin) -> FastAPI:
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    if mode == "ingress":
        @application.middleware("http")
        async def identify_ingress(request: Request, call_next):
            user_ids = request.headers.getlist("x-remote-user-id")
            if (
                request.client is None
                or request.client.host != SUPERVISOR_ADDRESS
                or len(user_ids) != 1
                or not user_ids[0].strip()
                or user_ids[0] != user_ids[0].strip()
            ):
                return JSONResponse({"detail": "Accès refusé"}, status_code=403)
            if not await verify_admin(user_ids[0]):
                return JSONResponse({"detail": "Accès refusé"}, status_code=403)
            request.state.ingress_user_id = user_ids[0]
            return await call_next(request)
    elif mode != "standalone":
        raise ValueError("Mode de déploiement inconnu")

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND)

    return application


app = create_app(os.environ.get("VTHERM_DEPLOYMENT_MODE", "standalone"))