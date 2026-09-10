"""Typed application errors and FastAPI exception handlers."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base error for expected failures that map to a stable API contract."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(code="not_found", message=message, status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(code="conflict", message=message, status_code=409)


class BadRequestError(AppError):
    def __init__(self, message: str = "Bad request") -> None:
        super().__init__(code="bad_request", message=message, status_code=400)


class UnsupportedMediaTypeError(AppError):
    def __init__(self, message: str = "Unsupported media type") -> None:
        super().__init__(code="unsupported_media_type", message=message, status_code=415)


class DependencyUnavailableError(AppError):
    """Used later for graceful degradation when OCR/LLM/index is down."""

    def __init__(self, message: str = "A required dependency is unavailable") -> None:
        super().__init__(code="dependency_unavailable", message=message, status_code=503)


class ErrorBody(BaseModel):
    code: str
    message: str
    trace_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody = Field(description="Stable error envelope for clients")


def _trace_id_from_request(request: Request) -> str:
    return getattr(request.state, "trace_id", "unknown")


def error_payload(code: str, message: str, trace_id: str) -> dict[str, Any]:
    body = ErrorBody(code=code, message=message, trace_id=trace_id)
    return ErrorResponse(error=body).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        trace_id = _trace_id_from_request(request)
        logger.warning("app_error", code=exc.code, status_code=exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, trace_id),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        trace_id = _trace_id_from_request(request)
        logger.warning("validation_error", errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content=error_payload("validation_error", "Request validation failed", trace_id),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        trace_id = _trace_id_from_request(request)
        logger.exception("unhandled_error", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=error_payload("internal_error", "An unexpected error occurred", trace_id),
        )
