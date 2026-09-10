"""ASGI middleware for request correlation."""

import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

TRACE_ID_HEADER = "X-Trace-Id"


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Honor incoming X-Trace-Id or mint one, bind it to logs, and echo it back."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(TRACE_ID_HEADER)
        trace_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        request.state.trace_id = trace_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        response = await call_next(request)
        response.headers[TRACE_ID_HEADER] = trace_id
        return response
