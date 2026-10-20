"""Exceptions raised by the OpenAPI understanding module."""


class OpenAPIError(Exception):
    """Base exception for OpenAPI document processing errors."""


class OpenAPIParseError(OpenAPIError):
    """Raised when an OpenAPI document cannot be parsed."""


class OpenAPIValidationError(OpenAPIError):
    """Raised when an OpenAPI document is structurally invalid."""


class UnsupportedOpenAPIVersionError(OpenAPIValidationError):
    """Raised when the document uses an unsupported OpenAPI version."""


class OpenAPIReferenceError(OpenAPIValidationError):
    """Raised when a reference is unsupported or cannot be resolved."""
