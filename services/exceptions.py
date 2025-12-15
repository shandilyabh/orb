"""Custom exceptions for the services layer."""


class OrbError(Exception):
    """Base exception class for the application."""
    def __init__(self, message="An unexpected error occurred."):
        self.message = message
        super().__init__(self.message)


class DatabaseError(OrbError):
    """Raised for general database-related errors."""
    def __init__(self, message="A database error occurred."):
        super().__init__(message)


class DocumentNotFoundError(DatabaseError):
    """Raised when a specific document is not found in the database."""
    def __init__(self, message="The requested document was not found."):
        super().__init__(message)


class DuplicateUserError(DatabaseError):
    """Raised when attempting to create a user that already exists."""
    def __init__(self, message="This user ID already exists."):
        super().__init__(message)


class PolicyNotFoundError(DatabaseError):
    """Raised when a specified policy is not found in the policy store."""
    def __init__(self, message="The specified policy was not found."):
        super().__init__(message)


class AuthenticationError(OrbError):
    """Raised for authentication failures (e.g., invalid API key or expired token)."""
    def __init__(self, message="Authentication failed."):
        super().__init__(message)


class AuthorizationError(OrbError):
    """Raised for authorization failures (e.g., insufficient permissions)."""
    def __init__(self, message="You are not authorized to perform this action."):
        super().__init__(message)


class ExplicitDenyError(AuthorizationError):
    """Raised when access is denied by an explicit 'none' rule."""
    def __init__(self, message="This action is explicitly denied by your permissions policy."):
        super().__init__(message)
