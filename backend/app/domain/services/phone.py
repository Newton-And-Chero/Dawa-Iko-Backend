"""Kenyan phone number validation and normalization. Pure — no DB, no framework."""

import re

from app.core.exceptions import ValidationError

# Kenyan mobile numbers in E.164: +254 then a 7xx/1xx line, then 7 more digits.
_E164_KE_PATTERN = re.compile(r"^\+254[17]\d{8}$")

# Local-format equivalents (0712345678) that normalize to the same E.164 number.
_LOCAL_KE_PATTERN = re.compile(r"^0[17]\d{8}$")


def normalize_phone(phone: str) -> str:
    """Strip formatting noise and convert a local 07xx/01xx number to +254 E.164."""
    stripped = re.sub(r"[\s\-()]", "", phone)
    if _LOCAL_KE_PATTERN.fullmatch(stripped):
        return "+254" + stripped[1:]
    return stripped


def is_valid_phone(phone: str) -> bool:
    return bool(_E164_KE_PATTERN.fullmatch(normalize_phone(phone)))


def validate_phone(phone: str) -> str:
    """Return the normalized E.164 number, or raise ValidationError."""
    normalized = normalize_phone(phone)
    if not _E164_KE_PATTERN.fullmatch(normalized):
        raise ValidationError(f"invalid Kenyan phone number: {phone!r}")
    return normalized
