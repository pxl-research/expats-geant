"""Tests for m_shared.utils.startup_checks."""

import logging

import pytest

from m_shared.utils.startup_checks import check_secrets


def test_placeholder_jwt_secret_warns_in_dev(monkeypatch, caplog):
    monkeypatch.setenv("JWT_SECRET", "change-me-in-production")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "real-secret-value")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with caplog.at_level(logging.WARNING):
        check_secrets()

    assert "JWT_SECRET" in caplog.text
    assert "Placeholder value detected" in caplog.text


def test_placeholder_oidc_secret_warns_in_dev(monkeypatch, caplog):
    monkeypatch.setenv("JWT_SECRET", "real-secret-value")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "change-me")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with caplog.at_level(logging.WARNING):
        check_secrets()

    assert "OIDC_CLIENT_SECRET" in caplog.text


def test_placeholder_secret_exits_in_production(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "change-me-in-production")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "real-secret-value")
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(SystemExit):
        check_secrets()


def test_real_secrets_no_warning(monkeypatch, caplog):
    monkeypatch.setenv("JWT_SECRET", "a-real-randomly-generated-secret")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "another-real-secret")
    monkeypatch.setenv("ENVIRONMENT", "production")

    with caplog.at_level(logging.WARNING):
        check_secrets()

    assert caplog.text == ""


def test_missing_secrets_no_warning(monkeypatch, caplog):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with caplog.at_level(logging.WARNING):
        check_secrets()

    assert caplog.text == ""
