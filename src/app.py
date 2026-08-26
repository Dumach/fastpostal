from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .models import (
    HealthErrorResponse,
    HealthMismatch,
    HealthOkResponse,
    ParseErrorResponse,
    ParsedComponent,
    ServerTimeResponse,
)

from main import ProductionMode, mode, ACCESS_KEYS

app = FastAPI(title="postal")
logger: logging.Logger = logging.getLogger("uvicorn.default")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

NO_AUTH_PATHS = {"/", "/health"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in NO_AUTH_PATHS:
        return await call_next(request)

    if mode == ProductionMode.DEV:
        return await call_next(request)

    api_key = request.headers.get("X-API-KEY") or request.query_params.get("token")
    if api_key and api_key in ACCESS_KEYS:
        return await call_next(request)

    return JSONResponse(status_code=401, content=None)


@app.get("/", response_model=ServerTimeResponse)
@limiter.limit("60/minute")
def root(request: Request):
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
async def health(request: Request):
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
    except Exception as exc:
        logger.exception("Health check parse failed")
        return JSONResponse(
            status_code=500,
            content=ParseErrorResponse(
                error=f"Failed to parse address: {exc}"
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
    from postal.parser import parse_address as _parse_address

    try:
        parsed = _parse_address(address)
        return [ParsedComponent(label=label, value=value) for value, label in parsed]
    except Exception as exc:
        logger.exception("Parse failed")
        return JSONResponse(
            status_code=500,
            content=ParseErrorResponse(
                error=f"Failed to parse address: {exc}"
            ).model_dump(),
        )
