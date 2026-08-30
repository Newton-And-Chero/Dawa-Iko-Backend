class AppError(Exception):
    pass


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class InvalidCredentialsError(AppError):
    pass


class CallProviderError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UnsupportedRegionError(CallProviderError):
    pass


class UnsupportedLanguageError(CallProviderError):
    pass


class InvalidPhoneError(CallProviderError):
    pass


class NoRecipientsError(CallProviderError):
    pass


class ResultSchemaInvalidError(CallProviderError):
    pass


class RecipientResultSchemaInvalidError(CallProviderError):
    pass


class RateLimitExceededError(CallProviderError):
    pass


class IdempotencyConflictError(CallProviderError):
    pass


class ProviderUnavailableError(CallProviderError):
    pass


class InsufficientBalanceError(CallProviderError):
    pass


class RecipientBlockedError(CallProviderError):
    pass


class PolicyViolationError(CallProviderError):
    pass


class InvalidRecipientError(CallProviderError):
    pass


class InvalidRequestError(CallProviderError):
    pass


class UnauthorizedError(CallProviderError):
    pass


class ForbiddenError(CallProviderError):
    pass


class CallNotReadyError(CallProviderError):
    pass


class CallNotFoundError(CallProviderError):
    pass


class InternalCallProviderError(CallProviderError):
    pass
