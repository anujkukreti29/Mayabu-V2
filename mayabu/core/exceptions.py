"""Domain exceptions for Mayabu."""

class MayabuError(Exception):
    """Base Mayabu exception."""

class ValidationError(MayabuError):
    """Raised when external data fails validation."""

class NotFoundError(MayabuError):
    """Raised when a requested entity is not found."""
