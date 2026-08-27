"""Application configuration.

Settings is the single source of truth for configuration. Nothing else in
this codebase should read ``os.environ`` directly.
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Obviously-placeholder JWT secrets — never a real deployment's actual
# signing key, so a production boot with one of these still set means the
# real secret was never supplied (workflows/09: refuse to boot in that case
# rather than silently signing tokens with a guessable key).
_PLACEHOLDER_JWT_SECRETS = {"change-me", "changeme", ""}


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

    # --- CALL-E demo guardrail (hackathon) ---
    # When non-empty, NO real facility number is ever dialed: every outbound
    # call is redirected to one of these numbers (one per facility, assigned by
    # position), and a single call task covers at most len(list) facilities —
    # the rest are dropped from that chunk. JSON array of E.164 numbers. Leave
    # as [] in production so real facilities are called.
    CALL_DEMO_REDIRECT_NUMBERS: list[str] = []

    # --- SMS (Africa's Talking) ---
    SMS_MODE: Literal["mock", "live"] = "mock"
    AFRICAS_TALKING_USERNAME: str = ""
    AFRICAS_TALKING_API_KEY: str = ""
    AFRICAS_TALKING_SENDER_ID: str = ""

    # --- Email (subscriber notification_channel=email) ---
    EMAIL_MODE: Literal["mock", "live"] = "mock"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_ADDRESS: str = ""

    # --- Escalation & alerting ---
    # A sweep at or below this in-stock fraction is scarce enough to warrant
    # running severity classification at all (domain/services/severity.py is
    # still the authority on whether an alert is actually created — this is a
    # cheap pre-filter kept in sync with its own scarcity threshold).
    STOCKOUT_THRESHOLD_PCT: float = 0.5

    # --- Auth ---
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Rate limiting (POST /v1/sweeps/query) ---
    PUBLIC_QUERY_RATE_LIMIT: int = 10
    PUBLIC_QUERY_RATE_WINDOW_SECONDS: int = 60

    # --- CORS ---
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @model_validator(mode="after")
    def _refuse_placeholder_jwt_secret_in_production(self) -> "Settings":
        if self.ENV == "production" and self.JWT_SECRET.strip().lower() in _PLACEHOLDER_JWT_SECRETS:
            raise ValueError(
                "JWT_SECRET is still a placeholder but ENV=production — set a real secret "
                "via the deployment environment's own secret store before booting."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
