"""Aggregates every versioned (`/v1`) router (Sprint 05)."""

from fastapi import APIRouter

from app.api.v1.routers.analytics import router as analytics_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.availability_results import router as availability_results_router
from app.api.v1.routers.calls import router as calls_router
from app.api.v1.routers.commodities import router as commodities_router
from app.api.v1.routers.escalations import router as escalations_router
from app.api.v1.routers.facilities import router as facilities_router
from app.api.v1.routers.subscribers import router as subscribers_router
from app.api.v1.routers.sweeps import router as sweeps_router
from app.api.v1.routers.sweeps_sse import router as sweeps_sse_router
from app.api.v1.routers.users import router as users_router

router = APIRouter(prefix="/v1")

router.include_router(auth_router)
router.include_router(facilities_router)
router.include_router(commodities_router)
router.include_router(sweeps_router)
router.include_router(sweeps_sse_router)
router.include_router(calls_router)
router.include_router(availability_results_router)
router.include_router(users_router)
router.include_router(escalations_router)
router.include_router(subscribers_router)
router.include_router(analytics_router)
