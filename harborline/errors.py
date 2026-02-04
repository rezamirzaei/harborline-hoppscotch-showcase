class DomainError(Exception):
    """Base class for domain/service errors."""


class NotFoundError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class ConflictError(DomainError):
    def __init__(self, detail):
        super().__init__("Conflict")
        self.detail = detail


class ValidationError(DomainError):
    def __init__(self, detail):
        super().__init__("Validation error")
        self.detail = detail
