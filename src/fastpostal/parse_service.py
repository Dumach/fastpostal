"""Parsing service: the single place that calls libpostal."""

from __future__ import annotations

from .models import HealthMismatch, ParsedComponent

# Address the /health endpoint parses to verify libpostal works.
HEALTH_ADDRESS = "1 Apple Park Way Cupertino, California United States"
# Expected parse result for HEALTH_ADDRESS.
HEALTH_EXPECTED: dict[str, str] = {
    "house_number": "1",
    "road": "apple park way",
    "city": "cupertino",
    "state": "california",
    "country": "united states",
}


def parse(address: str) -> list[ParsedComponent]:
    """Parse an address into labeled components using libpostal."""
    from postal import parser
    # Called through the postal.parser module (not a module-level import of
    # parse_address) so tests can patch postal.parser.parse_address.
    return [ParsedComponent(label=label, value=value) for value, label in parser.parse_address(address)]


def health_mismatches() -> list[HealthMismatch]:
    """Parse HEALTH_ADDRESS and return the labels whose value differs from HEALTH_EXPECTED."""
    actual = {component.label: component.value for component in parse(HEALTH_ADDRESS)}
    return [
        HealthMismatch(label=label, expected=expected, actual=actual.get(label))
        for label, expected in HEALTH_EXPECTED.items()
        if actual.get(label) != expected
    ]
