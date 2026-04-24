import pytest

from app.config import Settings


def test_settings_requires_platform_url(monkeypatch):
    monkeypatch.delenv("PLATFORM_BASE_URL", raising=False)
    with pytest.raises(Exception):
        Settings()


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("PLATFORM_BASE_URL", "http://example.svc:8000")
    monkeypatch.setenv("REQUEST_TIMEOUT_S", "7")
    s = Settings()
    assert s.platform_base_url == "http://example.svc:8000"
    assert s.request_timeout_s == 7.0


def test_settings_default_log_level(monkeypatch):
    monkeypatch.setenv("PLATFORM_BASE_URL", "http://example.svc:8000")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    s = Settings()
    assert s.log_level == "INFO"


def test_settings_default_timeout(monkeypatch):
    monkeypatch.setenv("PLATFORM_BASE_URL", "http://example.svc:8000")
    monkeypatch.delenv("REQUEST_TIMEOUT_S", raising=False)
    s = Settings()
    assert s.request_timeout_s == 5.0
