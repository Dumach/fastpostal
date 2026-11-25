"""FastAPI app: server time, libpostal health check and address parsing."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import Environment, Settings, get_settings
from .models import (
    HealthErrorResponse,
    HealthMismatch,
    HealthOkResponse,
    ParseErrorResponse,
    ParsedComponent,
    ServerTimeResponse,
    UnauthorizedResponse,
)

logger: logging.Logger = logging.getLogger("uvicorn.default")

NO_AUTH_PATHS = {"/", "/health"}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app for the given settings (process defaults when omitted)."""
    settings = settings or get_settings()
    # In-memory state: the 60/minute limit applies per worker process, so with
    # N uvicorn workers the effective cap is 60 * N / min. A strict global
    # limit would need a shared backend (e.g. Redis).
    limiter = Limiter(key_func=get_remote_address)

    app = FastAPI(title="postal")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Require X-API-KEY header or token param on protected paths; skipped in DEV mode."""
        if request.url.path in NO_AUTH_PATHS:
            return await call_next(request)

        if settings.environment == Environment.DEV:
            return await call_next(request)

        api_key = request.headers.get("X-API-KEY") or request.query_params.get("token")
        if api_key and api_key in settings.access_keys:
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content=UnauthorizedResponse(
                error="unauthorized",
                detail="A valid API key is required to access this resource"
            ).model_dump(),
        )

    @app.get("/", response_model=ServerTimeResponse)
    @limiter.limit("60/minute")
    def root(request: Request):
        """Return the server's current UTC time."""
        now = datetime.now(tz=timezone.utc)
        return ServerTimeResponse(
            server_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            timestamp=int(time.time()),
            timezone=str(timezone.utc),
        )

    @app.get(
        "/health",
        response_model=HealthOkResponse,
        responses={503: {"model": HealthErrorResponse}},
    )
    @limiter.limit("60/minute")
    def health(request: Request):
        """Parse a fixed address to verify libpostal; 503 on label mismatch, 500 on parse error."""
        from postal.parser import parse_address as _parse_address

        address = "1 Apple Park Way Cupertino, California United States"
        expected: dict[str, str] = {
            "house_number": "1",
            "road": "apple park way",
            "city": "cupertino",
            "state": "california",
            "country": "united states",
        }

        try:
            parsed = _parse_address(address)
            actual: dict[str, str] = {label: value for value, label in parsed}

            missing: list[dict[str, str | None]] = []
            for label, value in expected.items():
                actual_value = actual.get(label)
                if actual_value is None or actual_value != value:
                    missing.append(
                        {"label": label, "expected": value, "actual": actual_value}
                    )

            if missing:
                return JSONResponse(
                    status_code=503,
                    content=HealthErrorResponse(
                        status="unhealthy",
                        message="Address parsing verification failed",
                        mismatches=[HealthMismatch(**m) for m in missing],
                    ).model_dump(),
                )
        except Exception:
            # Log the traceback; don't echo internal error details to clients.
            logger.exception("Health check parse failed")
            return JSONResponse(
                status_code=500,
                content=ParseErrorResponse(error="Failed to parse address").model_dump(),
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
        from postal.parser import parse_address as _parse_address

        try:
            parsed = _parse_address(address)
            return [ParsedComponent(label=label, value=value) for value, label in parsed]
        except Exception:
            # Log the traceback; don't echo internal error details to clients.
            logger.exception("Parse failed")
            return JSONResponse(
                status_code=500,
                content=ParseErrorResponse(error="Failed to parse address").model_dump(),
            )

    return app


# Module-level instance so `uvicorn fastpostal.app:app` (fastpostal.serve, systemd) keeps working.
app = create_app()
