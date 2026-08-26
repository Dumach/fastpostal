from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ServerTimeResponse(BaseModel):
    server_time: str
    timestamp: int
    timezone: str


class ParsedComponent(BaseModel):
    label: str
    value: str


class HealthMismatch(BaseModel):
    label: str
    expected: str
    actual: Optional[str] = None


class HealthOkResponse(BaseModel):
    status: str


class HealthErrorResponse(BaseModel):
    status: str
    message: str
    mismatches: list[HealthMismatch]


class ParseErrorResponse(BaseModel):
    error: str
