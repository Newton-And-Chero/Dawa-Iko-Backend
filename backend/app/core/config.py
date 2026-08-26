"""Application configuration.

Settings is the single source of truth for configuration. Nothing else in
this codebase should read ``os.environ`` directly.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    ENV: Literal["local", "test", "staging", "production"] = "local"
    LOG_LEVEL: str = "INFO"
    # Externally reachable base URL this deployment is running at, used to build
    # the CALL-E webhook_url. Must be a real HTTPS URL in staging/production.
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/calle"

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Facility import (KMHFL) ---
    FACILITY_IMPORT_MODE: Literal["mock", "real"] = "mock"
    KMHFL_BASE_URL: str = "https://api.kmhfl.health.go.ke"
    KMHFL_API_KEY: str = ""

    # --- CALL-E ---
    CALL_E_MODE: Literal["mock", "live"] = "mock"
    CALLE_API_KEY: str = ""
    CALLE_BASE_URL: str = "https://api.heycall-e.com"
    CALLE_WEBHOOK_TOKEN: str = ""
    MAX_RECIPIENTS_PER_TASK: int = 50
    # Never call the same facility more than once within this window, to avoid
    # pharmacy fatigue/harassment (PROJECT.md 2.2).
    FACILITY_CALL_COOLDOWN_HOURS: int = 168
    # Total attempts allowed per facility per sweep (first attempt + retries).
    MAX_CALL_ATTEMPTS: int = 3
    # Minimum delay before retrying a no_answer/failed call.
    RETRY_DELAY_HOURS: int = 4

    # --- SMS (Africa's Talking) ---
    SMS_MODE: Literal["mock", "live"] = "mock"
    AFRICAS_TALKING_USERNAME: str = ""
    AFRICAS_TALKING_API_KEY: str = ""
    AFRICAS_TALKING_SENDER_ID: str = ""

    # --- Auth ---
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Rate limiting (POST /v1/sweeps/query) ---
    PUBLIC_QUERY_RATE_LIMIT: int = 10
    PUBLIC_QUERY_RATE_WINDOW_SECONDS: int = 60

    # --- CORS ---
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
