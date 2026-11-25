import pytest
from pydantic import ValidationError

from fastpostal.config import Environment, Settings


def _settings(**kwargs) -> Settings:
    """Build Settings without reading any .env file."""
    return Settings(_env_file=None, **kwargs)


class TestFailFastValidation:
    def test_prod_without_access_key_raises(self):
        with pytest.raises(ValidationError, match="ACCESS_KEY"):
            _settings(environment="PROD", access_key="")

    def test_debug_without_access_key_raises(self):
        with pytest.raises(ValidationError, match="ACCESS_KEY"):
            _settings(environment="DEBUG", access_key="")

    def test_dev_without_access_key_ok(self):
        assert _settings(environment="DEV", access_key="").access_keys == []

    def test_access_key_is_csv_split(self):
        assert _settings(environment="DEV", access_key="a, b ,c").access_keys == ["a", "b", "c"]

    def test_ssl_half_configured_raises(self):
        with pytest.raises(ValidationError, match="together"):
            _settings(environment="DEV", ssl_cert="/tmp/cert.pem")

    def test_ssl_missing_file_raises(self, tmp_path):
        missing = str(tmp_path / "missing.pem")
        with pytest.raises(ValidationError, match="missing file"):
            _settings(environment="DEV", ssl_cert=missing, ssl_key=missing)

    def test_environment_is_case_insensitive(self):
        assert _settings(environment="dev").environment == Environment.DEV
