"""API error handling.

Instruction:
- Provide structured JSON error responses.
- Map domain exceptions to appropriate HTTP status codes.
- Keep error messages helpful but not leaking internal details.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from sourcelab.api.schemas import ErrorResponse


# Error codes
class ErrorCode:
    """Error code constants."""
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    BAD_REQUEST = "BAD_REQUEST"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class APIError(HTTPException):
    """Structured API error with code and detail."""

    def __init__(
        self,
        status_code: int,
        message: str,
        code: str = "",
        detail: str = "",
    ):
        self.error_code = code
        self.detail = detail
        super().__init__(status_code=status_code, detail=message)


def not_found_error(resource: str, resource_id: str) -> APIError:
    """Create a 404 not found error."""
    return APIError(
        status_code=404,
        message=f"{resource} '{resource_id}' not found",
        code=ErrorCode.NOT_FOUND,
        detail=f"No {resource.lower()} found with ID '{resource_id}'",
    )


def validation_error(message: str, detail: str = "") -> APIError:
    """Create a 422 validation error."""
    return APIError(
        status_code=422,
        message=message,
        code=ErrorCode.VALIDATION_ERROR,
        detail=detail,
    )


def bad_request_error(message: str, detail: str = "") -> APIError:
    """Create a 400 bad request error."""
    return APIError(
        status_code=400,
        message=message,
        code=ErrorCode.BAD_REQUEST,
        detail=detail,
    )


def internal_error(message: str, detail: str = "") -> APIError:
    """Create a 500 internal error."""
    return APIError(
        status_code=500,
        message=message,
        code=ErrorCode.INTERNAL_ERROR,
        detail=detail,
    )


def conflict_error(message: str, detail: str = "") -> APIError:
    """Create a 409 conflict error."""
    return APIError(
        status_code=409,
        message=message,
        code=ErrorCode.RESOURCE_CONFLICT,
        detail=detail,
    )


def service_unavailable_error(message: str, detail: str = "") -> APIError:
    """Create a 503 service unavailable error."""
    return APIError(
        status_code=503,
        message=message,
        code=ErrorCode.SERVICE_UNAVAILABLE,
        detail=detail,
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions and return structured JSON."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=str(exc.detail) if exc.detail else str(exc),
            detail=exc.detail,
            code=exc.error_code,
        ).model_dump(),
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic exceptions and return structured JSON."""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            code=ErrorCode.INTERNAL_ERROR,
        ).model_dump(),
    )
