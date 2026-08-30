from datetime import datetime

from pydantic import BaseModel, Field


class CallEngineEnableIn(BaseModel):
    ttl_seconds: int | None = Field(default=None, ge=1, le=86_400)


class CallEngineStateOut(BaseModel):
    enabled: bool
    expires_at: datetime | None
    default_enabled: bool
