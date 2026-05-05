"""
Cross-cutting middleware: request IDs, security headers, body-size cap.

Each middleware is a thin BaseHTTPMiddleware subclass. They are deliberately
self-contained so the Dockerfile can ship the same image for dev and prod
without runtime configuration of an external proxy.
"""

from __future__ import annotations

import contextvars
import logging
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


# Per-request correlation id, available to log records via RequestIdLogFilter.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdLogFilter(logging.Filter):
    """Inject the current request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Assign a short correlation id to each request. Honour an inbound
    X-Request-ID header if present (e.g. from a reverse proxy), otherwise
    generate one. The id is echoed back so clients can quote it in bug reports.
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add a baseline set of security headers to every response.

    These are appropriate for a JSON API (no HTML, no inline scripts):
    - X-Content-Type-Options: prevent MIME sniffing.
    - X-Frame-Options / CSP frame-ancestors: defend against clickjacking
      even though the API doesn't render HTML.
    - Referrer-Policy: don't leak the API path to third parties.
    - Strict-Transport-Security: only meaningful behind HTTPS, harmless on HTTP.
    - Cache-Control: API responses must not be cached by intermediaries.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
        response.headers.setdefault(
            "Cache-Control", "no-store"
        )
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """
    Reject requests whose declared Content-Length exceeds `max_bytes`.

    This is a coarse first line of defence against memory exhaustion. A
    determined attacker can still stream chunked bodies; for that we rely on
    Pydantic's `max_length` limits on the parsed payload (200 files,
    500-char filenames, etc).
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length"},
                )
        return await call_next(request)
