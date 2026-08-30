from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.api.v1.routers.webhooks import router as webhooks_router
from app.api.v1.websocket.geography_ws import router as geography_ws_router
from app.api.v1.websocket.sweep_ws import router as sweep_ws_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(title="CALL-E Medicine & Commodity Availability Agent")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)
    app.include_router(webhooks_router)
    app.include_router(sweep_ws_router)
    app.include_router(geography_ws_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
