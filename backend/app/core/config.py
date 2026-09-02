from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_JWT_SECRETS = {"change-me", "changeme", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: Literal["local", "test", "staging", "production"] = "local"
    LOG_LEVEL: str = "INFO"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/calle"

    REDIS_URL: str = "redis://localhost:6379/0"

    FACILITY_IMPORT_MODE: Literal["mock", "real"] = "mock"
    KMHFL_BASE_URL: str = "https://api.kmhfl.health.go.ke"
    KMHFL_API_KEY: str = ""

    CALL_E_MODE: Literal["mock", "live"] = "mock"
    CALLE_API_KEY: str = ""
    CALLE_BASE_URL: str = "https://api.heycall-e.com"
    CALLE_WEBHOOK_TOKEN: str = ""
    MAX_RECIPIENTS_PER_TASK: int = 50
    FACILITY_CALL_COOLDOWN_HOURS: int = 168
    MAX_CALL_ATTEMPTS: int = 3
    RETRY_DELAY_HOURS: int = 4

    CALL_DEMO_REDIRECT_NUMBERS: list[str] = []
    CALLS_ENABLED_DEFAULT: bool = False

    SMS_MODE: Literal["mock", "live"] = "mock"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    TWILIO_MESSAGING_SERVICE_SID: str = ""

    SMS_DEMO_REDIRECT_NUMBERS: list[str] = []

    EMAIL_MODE: Literal["mock", "live"] = "mock"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_ADDRESS: str = ""

    STOCKOUT_THRESHOLD_PCT: float = 0.5

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    PUBLIC_QUERY_RATE_LIMIT: int = 10
    PUBLIC_QUERY_RATE_WINDOW_SECONDS: int = 60

    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_ORIGIN_REGEX: str = ""

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
