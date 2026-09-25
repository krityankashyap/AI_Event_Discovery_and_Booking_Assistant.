class AppError(Exception):
    """Base class for all domain erros. Carries an HTTP status and a machine code."""

    status_code: int = 500
    code: str = "internal_errors"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class EventNotFound(AppError):
    status_code = 404
    code = "event_not_found"


class TicketmasterUnavailable(AppError):
    status_code = 502
    code = "ticketmaster_api_error"


class TicketmasterRateLimited(AppError):
    status_code = 429
    code = "ticketmaster_rate_limited"


class TicketmasterAuthError(AppError):
    status_code = 502
    code = "ticketmaster_auth_error"


class LLMUnavailable(AppError):
    status_code = 503
    code = "llm_api_error"


class SessionNotFound(AppError):
    status_code = 404
    code = "session_not_found"


class NoPendingApprovals(AppError):
    status_code = 409
    code = "no_pending_approvals"


class SessionBusy(AppError):
    status_code = 409
    code = "session_busy"
