from unittest.mock import patch

from fastpostal import parse_service
from fastpostal.models import HealthMismatch, ParsedComponent


def _full_parse() -> list[tuple[str, str]]:
    return [
        ("1", "house_number"),
        ("apple park way", "road"),
        ("cupertino", "city"),
        ("california", "state"),
        ("united states", "country"),
    ]


def test_parse_returns_components() -> None:
    with patch("postal.parser.parse_address", return_value=[("1", "house_number")]):
        assert parse_service.parse("1 Main St") == [ParsedComponent(label="house_number", value="1")]


def test_health_mismatches_empty_when_parse_matches() -> None:
    with patch("postal.parser.parse_address", return_value=_full_parse()):
        assert parse_service.health_mismatches() == []


def test_health_mismatches_reports_wrong_value() -> None:
    pairs = [
        ("1", "house_number"),
        ("other road", "road"),
        ("cupertino", "city"),
        ("california", "state"),
        ("united states", "country"),
    ]
    with patch("postal.parser.parse_address", return_value=pairs):
        assert parse_service.health_mismatches() == [
            HealthMismatch(label="road", expected="apple park way", actual="other road"),
        ]


def test_health_mismatches_reports_missing_label() -> None:
    with patch("postal.parser.parse_address", return_value=_full_parse()[:-1]):
        assert parse_service.health_mismatches() == [
            HealthMismatch(label="country", expected="united states", actual=None),
        ]
