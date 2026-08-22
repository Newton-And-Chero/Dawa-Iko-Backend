"""FastAPI app factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.api.v1.routers.webhooks import router as webhooks_router
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="CALL-E Medicine & Commodity Availability Agent")

    # Permissive for now — revisit in Sprint 05 (auth).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)
    # Mounted without the /v1 prefix: not part of the public API surface (see
    # workflows/03) — this is where CALL-E's webhook_url points.
    app.include_router(webhooks_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
