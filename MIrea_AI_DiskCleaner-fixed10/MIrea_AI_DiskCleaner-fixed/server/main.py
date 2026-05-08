"""FastAPI entry point: CORS, security middleware, rate limit, routers."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import CORS_ORIGINS, MAX_REQUEST_BODY_BYTES
from database.db import init_db
from middleware import (
    MaxBodySizeMiddleware,
    RequestIdLogFilter,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from rate_limit import limiter
from routers import analysis, auth

# ===== Logging =====
# request_id is injected by RequestIdLogFilter and is "-" outside of a request.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [rid=%(request_id)s] %(name)s: %(message)s",
)
logging.getLogger().addFilter(RequestIdLogFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logging.info("Database initialized")
    yield
    logging.info("Application shutting down")


app = FastAPI(
    title="SmartCleaner API",
    description="Backend for SmartCleaner file analysis service",
    version="1.0.0",
    lifespan=lifespan,
)

# Register the slowapi limiter on app.state and its 429-handler so rate-limited
# routes return a clean response instead of raising into the user.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Strip Pydantic's verbose 422 detail in non-test environments — those
# messages can leak internal field names and validation rules to attackers.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, __: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed"},
    )


# ===== Middleware chain =====
# Starlette runs the LAST-added middleware FIRST on the request path. We add
# them in the reverse of the desired execution order: CORS innermost (handles
# preflight close to the router), MaxBodySize outermost (rejects oversized
# requests before any other work happens).
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(MaxBodySizeMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)


# ===== Routers =====
app.include_router(auth.router)
app.include_router(analysis.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
