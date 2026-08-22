"""App-wide exception types."""


class AppError(Exception):
    """Base class for all application-raised errors."""


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class ValidationError(AppError):
    """Raised when input fails a domain-level validation rule."""


class UnknownCallError(AppError):
    """Raised when a webhook references a call_id we have no queued/in_progress record of."""


class CallProviderError(AppError):
    """Base class for CALL-E API errors. Carries the provider's own error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UnsupportedRegionError(CallProviderError):
    """CALL-E does not support outbound calling to the requested region."""


class UnsupportedLanguageError(CallProviderError):
    """CALL-E does not support the requested locale/language."""


class InvalidPhoneError(CallProviderError):
    """A recipient phone number was rejected by CALL-E."""


class NoRecipientsError(CallProviderError):
    """A call task was submitted with no valid recipients."""


class ResultSchemaInvalidError(CallProviderError):
    """`result_schema` was rejected by CALL-E as invalid JSON Schema."""


class RecipientResultSchemaInvalidError(CallProviderError):
    """`recipient_result_schema` was rejected by CALL-E as invalid JSON Schema."""


class RateLimitExceededError(CallProviderError):
    """CALL-E rejected the request due to rate limiting."""


class IdempotencyConflictError(CallProviderError):
    """The same `Idempotency-Key` was reused with a different request body."""


class ProviderUnavailableError(CallProviderError):
    """CALL-E's own upstream provider was unavailable."""
