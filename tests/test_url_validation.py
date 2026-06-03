"""Unit tests for the SSRF guards in m_shared/utils/url_validation.py.

These pin the security-critical branches directly (literal-IP blocking, DNS
resolution to a private address, IPv4-mapped unwrap, and the deliberate
allow-on-unresolvable behaviour) so a future refactor cannot silently re-open
them. DNS-dependent cases mock socket.getaddrinfo for determinism.
"""

import socket

import pytest
from fastapi import HTTPException

from m_shared.utils import url_validation
from m_shared.utils.url_validation import validate_api_url, validate_web_url


def _addrinfo(ip: str):
    """Build a getaddrinfo()-shaped result for a single address."""
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sockaddr = (ip, 0, 0, 0) if family == socket.AF_INET6 else (ip, 0)
    return [(family, socket.SOCK_STREAM, 6, "", sockaddr)]


def _resolves_to(monkeypatch, ip: str):
    monkeypatch.setattr(url_validation.socket, "getaddrinfo", lambda *a, **k: _addrinfo(ip))


class TestValidateWebUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://10.0.0.1/x",
            "http://127.0.0.1/x",
            "http://169.254.169.254/latest/meta-data/",
            "http://192.168.1.1/x",
        ],
    )
    def test_literal_internal_ip_blocked(self, url):
        with pytest.raises(HTTPException):
            validate_web_url(url)

    def test_ipv4_mapped_loopback_blocked(self):
        # ::ffff:127.0.0.1 must be unwrapped to 127.0.0.1 and rejected.
        with pytest.raises(HTTPException):
            validate_web_url("http://[::ffff:127.0.0.1]/")

    def test_credentials_blocked(self):
        with pytest.raises(HTTPException):
            validate_web_url("http://user:pw@example.com/")

    def test_non_http_scheme_blocked(self):
        with pytest.raises(HTTPException):
            validate_web_url("ftp://example.com/")

    def test_dns_resolving_to_private_blocked(self, monkeypatch):
        _resolves_to(monkeypatch, "10.1.2.3")
        with pytest.raises(HTTPException):
            validate_web_url("http://internal.example.com/")

    def test_dns_resolving_to_public_allowed(self, monkeypatch):
        _resolves_to(monkeypatch, "93.184.216.34")
        validate_web_url("http://example.com/")  # must not raise

    def test_unresolvable_host_allowed(self, monkeypatch):
        def boom(*a, **k):
            raise socket.gaierror("name resolution failed")

        monkeypatch.setattr(url_validation.socket, "getaddrinfo", boom)
        validate_web_url("http://does-not-exist.invalid/")  # gaierror -> allow


class TestValidateApiUrlProduction:
    """``validate_api_url`` is strict when ENVIRONMENT=production."""

    @pytest.fixture(autouse=True)
    def _force_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")

    def test_requires_https(self):
        with pytest.raises(HTTPException, match="HTTPS"):
            validate_api_url("http://example.com/")

    def test_credentials_blocked(self):
        with pytest.raises(HTTPException, match="credentials"):
            validate_api_url("https://user:pw@example.com/")

    def test_resolving_to_private_blocked(self, monkeypatch):
        _resolves_to(monkeypatch, "10.0.0.5")
        with pytest.raises(HTTPException, match="internal"):
            validate_api_url("https://internal.example.com/")

    def test_public_https_allowed(self, monkeypatch):
        _resolves_to(monkeypatch, "93.184.216.34")
        validate_api_url("https://example.com/")  # must not raise


class TestValidateApiUrlDevelopment:
    """Outside production the guard relaxes: http allowed, internal targets
    allowed (with a logged warning), credentials still rejected."""

    @pytest.fixture(autouse=True)
    def _force_development(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")

    def test_http_localhost_allowed_when_not_production(self, monkeypatch):
        _resolves_to(monkeypatch, "127.0.0.1")
        validate_api_url("http://localhost:7080/index.php/admin/remotecontrol")

    def test_http_rfc1918_allowed_when_not_production(self, monkeypatch):
        _resolves_to(monkeypatch, "10.0.0.5")
        validate_api_url("http://internal.lab.example.com/")

    def test_internal_warning_logged(self, monkeypatch, caplog):
        _resolves_to(monkeypatch, "127.0.0.1")
        with caplog.at_level("WARNING", logger="m_shared.utils.url_validation"):
            validate_api_url("http://localhost:7080/")
        assert any(
            "internal address" in rec.message and "ENVIRONMENT" in rec.message
            for rec in caplog.records
        )

    def test_credentials_still_blocked(self):
        with pytest.raises(HTTPException, match="credentials"):
            validate_api_url("http://user:pw@localhost:7080/")

    def test_unknown_scheme_still_blocked(self):
        with pytest.raises(HTTPException, match="http or https"):
            validate_api_url("ftp://localhost:21/")

    def test_missing_hostname_still_blocked(self):
        with pytest.raises(HTTPException, match="hostname"):
            validate_api_url("http:///path-only")

    def test_public_https_still_works(self, monkeypatch):
        _resolves_to(monkeypatch, "93.184.216.34")
        validate_api_url("https://example.com/")  # must not raise


class TestValidateApiUrlUnsetEnvironment:
    """When ENVIRONMENT is unset, behaviour matches development (lenient)."""

    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)

    def test_http_localhost_allowed(self, monkeypatch):
        _resolves_to(monkeypatch, "127.0.0.1")
        validate_api_url("http://localhost:7080/")

    def test_credentials_still_blocked(self):
        with pytest.raises(HTTPException, match="credentials"):
            validate_api_url("https://user:pw@example.com/")
