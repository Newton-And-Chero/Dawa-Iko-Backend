"""App-wide exception types."""


class AppError(Exception):
    """Base class for all application-raised errors."""


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class ValidationError(AppError):
    """Raised when input fails a domain-level validation rule."""
