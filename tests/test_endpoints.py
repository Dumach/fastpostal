import os
import sys
from unittest.mock import patch
from typing import Any

import pytest
from fastapi.testclient import TestClient
from _pytest.fixtures import FixtureRequest


def _get_app(mode: str = "PROD"):
    """Import app with specific ENVIRONMENT mode."""
    # Clear cached modules
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.") or mod == "main":
            del sys.modules[mod]

    # Set environment before importing
    os.environ["ENVIRONMENT"] = mode
    os.environ["ACCESS_KEY"] = "test-key-123"

    from src.app import app

    return app


@pytest.fixture()
def client_prod() -> TestClient:
    return TestClient(_get_app("PROD"))


@pytest.fixture()
def client_dev() -> TestClient:
    return TestClient(_get_app("DEV"))


@pytest.fixture()
def mock_parse() -> Any:
    with patch("postal.parser.parse_address") as m:
        m.return_value = [
            ("1", "house_number"),
            ("apple park way", "road"),
            ("cupertino", "city"),
            ("california", "state"),
            ("united states", "country"),
        ]
        yield m


class TestRoot:
    def test_returns_200(self, client_prod: TestClient) -> None:
        response = client_prod.get("/")
        assert response.status_code == 200

    def test_returns_server_time_fields(self, client_prod: TestClient) -> None:
        data = client_prod.get("/").json()
        assert "server_time" in data
        assert "timestamp" in data
        assert "timezone" in data

    def test_timezone_is_utc(self, client_prod: TestClient) -> None:
        data = client_prod.get("/").json()
        assert data["timezone"] == "UTC"


class TestHealth:
    def test_returns_200_when_parse_works(self, client_prod: TestClient, mock_parse: Any) -> None:
        response = client_prod.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_returns_503_on_mismatch(self, client_prod: TestClient) -> None:
        with patch("postal.parser.parse_address", return_value=[]):
            response = client_prod.get("/health")
        assert response.status_code == 503
        assert response.json()["status"] == "unhealthy"

    def test_returns_500_on_exception(self, client_prod: TestClient) -> None:
        with patch("postal.parser.parse_address", side_effect=RuntimeError("libpostal error")):
            response = client_prod.get("/health")
        assert response.status_code == 500
        assert "error" in response.json()


class TestParseProd:
    def test_no_auth_returns_401(self, client_prod: TestClient) -> None:
        response = client_prod.get("/parse?address=test")
        assert response.status_code == 401

    def test_wrong_key_returns_401(self, client_prod: TestClient) -> None:
        response = client_prod.get("/parse?address=test", headers={"X-API-KEY": "wrong-key"})
        assert response.status_code == 401

    def test_valid_header_key(self, client_prod: TestClient, mock_parse: Any) -> None:
        response = client_prod.get("/parse?address=test", headers={"X-API-KEY": "test-key-123"})
        assert response.status_code == 200

    def test_valid_query_token(self, client_prod: TestClient, mock_parse: Any) -> None:
        response = client_prod.get("/parse?address=test&token=test-key-123")
        assert response.status_code == 200


class TestParseDev:
    def test_dev_mode_skips_auth(self, client_dev: TestClient, mock_parse: Any) -> None:
        response = client_dev.get("/parse?address=test")
        assert response.status_code == 200

    def test_returns_parsed_components(self, client_dev: TestClient, mock_parse: Any) -> None:
        data = client_dev.get("/parse?address=test").json()
        assert isinstance(data, list)
        assert all("label" in c and "value" in c for c in data)

    def test_missing_address_returns_422(self, client_dev: TestClient) -> None:
        response = client_dev.get("/parse")
        assert response.status_code == 422

    def test_parse_exception_returns_500(self, client_dev: TestClient) -> None:
        with patch("postal.parser.parse_address", side_effect=RuntimeError("fail")):
            response = client_dev.get("/parse?address=test")
        assert response.status_code == 500
        assert "error" in response.json()
