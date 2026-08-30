import re

from app.core.exceptions import ValidationError

_E164_KE_PATTERN = re.compile(r"^\+254[17]\d{8}$")

_LOCAL_KE_PATTERN = re.compile(r"^0[17]\d{8}$")


def normalize_phone(phone: str) -> str:
    stripped = re.sub(r"[\s\-()]", "", phone)
    if _LOCAL_KE_PATTERN.fullmatch(stripped):
        return "+254" + stripped[1:]
    return stripped


def is_valid_phone(phone: str) -> bool:
    return bool(_E164_KE_PATTERN.fullmatch(normalize_phone(phone)))


def validate_phone(phone: str) -> str:
    normalized = normalize_phone(phone)
    if not _E164_KE_PATTERN.fullmatch(normalized):
        raise ValidationError(f"invalid Kenyan phone number: {phone!r}")
    return normalized
