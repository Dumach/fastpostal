"""FastAPI app: server time, libpostal health check and address parsing."""

from __future__ import annotations

import logging

from typing import cast

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import parse_service
from .config import Environment, Settings, get_settings
from .models import (
    HealthErrorResponse,
    HealthOkResponse,
    InternalServerErrorResponse,
    ParseErrorResponse,
    ParsedComponent,
    UnauthorizedResponse,
)

logger: logging.Logger = logging.getLogger(__name__)

NO_AUTH_PATHS = {"/", "/health"}


def rate_limit_handler(request: Request, exc: Exception) -> Response:
    """Adapter so slowapi's private handler matches Starlette's exception-handler signature."""
    # Registered for RateLimitExceeded only, so this always holds at runtime.
    return _rate_limit_exceeded_handler(request, cast(RateLimitExceeded, exc))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app for the given settings (process defaults when omitted)."""
    settings = settings or get_settings()
    # In-memory state: the 60/minute limit applies per worker process, so with
    # N uvicorn workers the effective cap is 60 * N / min. A strict global
    # limit would need a shared backend (e.g. Redis).
    limiter = Limiter(key_func=get_remote_address)

    app = FastAPI(title="postal", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Require X-API-KEY header or token param on protected paths; skipped in DEV mode."""
        if request.url.path in NO_AUTH_PATHS:
            return await call_next(request)

        is_authenticated = False
        api_key = request.headers.get("X-API-KEY") or request.query_params.get("token")
        if api_key and api_key in settings.access_keys:
            is_authenticated = True
        if settings.environment == Environment.DEV:
            is_authenticated = True

        if is_authenticated:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        logger.warning("Invalid API key for %s %s from %s", request.method, request.url.path, client_host)

        return JSONResponse(
            status_code=401,
            content=UnauthorizedResponse(
                error="unauthorized", detail="A valid API key is required to access this resource"
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
        # Log the real error server-side; the client only gets a generic body.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=InternalServerErrorResponse(
                detail="Internal server error",
            ).model_dump(),
        )

    @app.get(
        "/health",
        response_model=HealthOkResponse,
        responses={503: {"model": HealthErrorResponse}},
    )
    @limiter.limit("10/minute")
    def health(request: Request):
        """Parse a fixed address to verify libpostal; 503 on label mismatch, 500 on parse error."""
        try:
            mismatches = parse_service.health_mismatches()
        except Exception:
            # Log the traceback; don't echo internal error details to clients.
            logger.exception("Health check parse failed")
            return JSONResponse(
                status_code=500,
                content=ParseErrorResponse(error="Failed to parse address").model_dump(),
            )

        if mismatches:
            return JSONResponse(
                status_code=503,
                content=HealthErrorResponse(
                    status="unhealthy",
                    message="Address parsing verification failed",
                    mismatches=mismatches,
                ).model_dump(),
            )

        return HealthOkResponse(status="ok")

    @app.get(
        "/parse",
        response_model=list[ParsedComponent],
        responses={
            401: {"description": "Unauthorized"},
            500: {"model": ParseErrorResponse},
        },
    )
    @limiter.limit("60/minute")
    def parse(
        request: Request,
        address: str = Query(..., description="Address to parse"),
    ):
        """Parse an address into labeled components using libpostal."""
        try:
            return parse_service.parse(address)
        except Exception:
            # Log the traceback; don't echo internal error details to clients.
            logger.exception("Parse failed")
            return JSONResponse(
                status_code=500,
                content=ParseErrorResponse(error="Failed to parse address").model_dump(),
            )

    # from app builder
    return app


# Module-level instance so `uvicorn fastpostal.app:app` (fastpostal.serve, systemd) keeps working.
app = create_app()
