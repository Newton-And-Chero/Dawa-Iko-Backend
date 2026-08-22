"""Domain enums shared across entities. Pure Python — no framework imports."""

from enum import StrEnum


class FacilityType(StrEnum):
    PUBLIC = "public"
    DISPENSARY = "dispensary"
    PRIVATE_CHEMIST = "private_chemist"
    FAITH_BASED = "faith_based"


class FacilitySource(StrEnum):
    KMHFL = "kmhfl"
    MANUAL = "manual"
    CROWD = "crowd"


class CommodityCategory(StrEnum):
    ESSENTIAL_MEDICINE = "essential_medicine"
    VACCINE = "vaccine"
    SUPPLY = "supply"


class SweepTrigger(StrEnum):
    ON_DEMAND = "on_demand"
    SCHEDULED = "scheduled"


class SweepStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CallStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"


class StockStatus(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class EscalationSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EscalationStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class UserRole(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    PUBLIC = "public"


class NotificationChannel(StrEnum):
    SMS = "sms"
    EMAIL = "email"
    WEBHOOK = "webhook"


class PhoneVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    BOUNCED = "bounced"


class CallListIntent(StrEnum):
    """Which facility type a call-list sweep should reach first (PROJECT.md 2.2)."""

    PUBLIC_FIRST = "public_first"
    PRIVATE_FIRST = "private_first"
