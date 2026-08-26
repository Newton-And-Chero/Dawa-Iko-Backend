"""Settings safety guards (Sprint 09): refuse to boot in production with an
obviously-placeholder JWT secret."""

from typing import Literal

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("placeholder", ["change-me", "changeme", ""])
def test_production_with_placeholder_jwt_secret_refuses_to_boot(placeholder: str) -> None:
    with pytest.raises(ValidationError):
        Settings(ENV="production", JWT_SECRET=placeholder)


def test_production_with_a_real_jwt_secret_boots_fine() -> None:
    settings = Settings(ENV="production", JWT_SECRET="a-real-32-byte-or-longer-secret-value")
    assert settings.ENV == "production"


@pytest.mark.parametrize("env", ["local", "test", "staging"])
def test_non_production_env_allows_placeholder_jwt_secret(
    env: Literal["local", "test", "staging"],
) -> None:
    settings = Settings(ENV=env, JWT_SECRET="change-me")
    assert settings.JWT_SECRET == "change-me"
