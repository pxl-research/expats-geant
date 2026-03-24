"""Unit and integration tests for OIDC oauth.py."""

import logging
import os
import time
from unittest.mock import patch

import httpx
import pytest
import respx

import m_shared.auth.oauth as oauth_module
from m_shared.auth.oauth import (
    OIDCConfigurationError,
    OIDCStateError,
    OIDCTokenError,
    _normalize_sub,
    exchange_code,
    get_authorization_url,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ISSUER = "http://localhost:8080/realms/expats"
CLIENT_ID = "cue-api"
CLIENT_SECRET = "change-me"
REDIRECT_URI = "http://localhost:8001/auth/callback"

OIDC_ENV = {
    "OIDC_ISSUER_URL": ISSUER,
    "OIDC_CLIENT_ID": CLIENT_ID,
    "OIDC_CLIENT_SECRET": CLIENT_SECRET,
    "OIDC_REDIRECT_URI": REDIRECT_URI,
    "JWT_SECRET": "test-secret-for-oauth-tests-minimum-32-bytes",
}

DISCOVERY_DOC = {
    "issuer": ISSUER,
    "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
    "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
    "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
}

# A minimal RS256 JWKS + corresponding signed token generated with authlib for tests.
# We use a symmetric HS256 trick via authlib's jwt to avoid needing a full RSA key pair
# in tests — we patch the JWT decode step instead.


def _clear_oauth_caches():
    """Reset module-level caches between tests."""
    oauth_module._oidc_config = None
    oauth_module._jwks_cache = None
    oauth_module._pending_states.clear()


@pytest.fixture(autouse=True)
def reset_caches():
    _clear_oauth_caches()
    yield
    _clear_oauth_caches()


# ---------------------------------------------------------------------------
# _normalize_sub
# ---------------------------------------------------------------------------


class TestNormalizeSub:
    def test_basic(self):
        result = _normalize_sub("http://localhost:8080/realms/expats", "user123")
        assert result == "localhost:8080:user123"

    def test_two_providers_produce_distinct_ids(self):
        uid1 = _normalize_sub("http://provider-a.example.com/realm", "abc")
        uid2 = _normalize_sub("http://provider-b.example.com/realm", "abc")
        assert uid1 != uid2

    def test_same_provider_same_sub_is_stable(self):
        uid1 = _normalize_sub(ISSUER, "abc")
        uid2 = _normalize_sub(ISSUER, "abc")
        assert uid1 == uid2


# ---------------------------------------------------------------------------
# Missing env vars
# ---------------------------------------------------------------------------


class TestMissingEnvVars:
    def test_missing_oidc_issuer_url(self):
        env = {k: v for k, v in OIDC_ENV.items() if k != "OIDC_ISSUER_URL"}
        with patch.dict(os.environ, env, clear=False):
            # Remove the var if it was already in the environment
            with patch.dict(os.environ, {"OIDC_ISSUER_URL": ""}, clear=False):
                os.environ.pop("OIDC_ISSUER_URL", None)
                with pytest.raises(OIDCConfigurationError, match="OIDC_ISSUER_URL"):
                    oauth_module._get_env("OIDC_ISSUER_URL")

    @pytest.mark.asyncio
    async def test_get_authorization_url_missing_env(self):
        """get_authorization_url raises OIDCConfigurationError when env vars absent."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(OIDCConfigurationError):
                await get_authorization_url()


# ---------------------------------------------------------------------------
# get_authorization_url
# ---------------------------------------------------------------------------


class TestGetAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_returns_url_and_state(self):
        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )

                url, state = await get_authorization_url()

        assert "response_type=code" in url
        assert f"client_id={CLIENT_ID}" in url
        assert f"state={state}" in url
        assert len(state) == 36  # UUID4

    @pytest.mark.asyncio
    async def test_state_stored_in_pending(self):
        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )

                _url, state = await get_authorization_url()

        assert state in oauth_module._pending_states
        assert oauth_module._pending_states[state] > time.time()


# ---------------------------------------------------------------------------
# exchange_code — state validation
# ---------------------------------------------------------------------------


class TestExchangeCodeStateValidation:
    @pytest.mark.asyncio
    async def test_invalid_state_raises(self):
        with patch.dict(os.environ, OIDC_ENV):
            with pytest.raises(OIDCStateError):
                await exchange_code(code="any", state="nonexistent-state")

    @pytest.mark.asyncio
    async def test_expired_state_raises(self):
        with patch.dict(os.environ, OIDC_ENV):
            # Insert an already-expired state
            oauth_module._pending_states["expired-state"] = time.time() - 1

            with pytest.raises(OIDCStateError):
                await exchange_code(code="any", state="expired-state")


# ---------------------------------------------------------------------------
# exchange_code — ID token validation
# ---------------------------------------------------------------------------


def _make_id_token_claims(
    *,
    iss: str = ISSUER,
    sub: str = "user-abc",
    aud: str | list = CLIENT_ID,
    exp_offset: int = 3600,
    iat_offset: int = 0,
) -> dict:
    now = int(time.time())
    return {
        "iss": iss,
        "sub": sub,
        "aud": aud,
        "exp": now + exp_offset,
        "iat": now + iat_offset,
    }


class TestExchangeCodeTokenValidation:
    @pytest.mark.asyncio
    async def test_exchange_code_success(self):
        """Valid code → platform JWT returned."""
        claims = _make_id_token_claims()

        class FakeClaims(dict):
            def validate(self):
                pass

        with patch.dict(os.environ, OIDC_ENV):
            valid_state = "valid-state-abc"
            oauth_module._pending_states[valid_state] = time.time() + 600

            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )
                respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                    return_value=httpx.Response(200, json={"keys": []})
                )
                respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
                    return_value=httpx.Response(
                        200, json={"id_token": "fake.id.token", "token_type": "Bearer"}
                    )
                )

                with patch(
                    "m_shared.auth.oauth.authlib_jwt.decode",
                    return_value=FakeClaims(claims),
                ):
                    platform_token = await exchange_code(code="auth-code-123", state=valid_state)

        assert isinstance(platform_token, str)
        assert len(platform_token.split(".")) == 3  # JWT format

    @pytest.mark.asyncio
    async def test_id_token_expired(self):
        """Expired ID token raises OIDCTokenError."""
        valid_state = "valid-state-expired-token"
        oauth_module._pending_states[valid_state] = time.time() + 600

        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )
                respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                    return_value=httpx.Response(200, json={"keys": []})
                )
                respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
                    return_value=httpx.Response(
                        200, json={"id_token": "fake.expired.token", "token_type": "Bearer"}
                    )
                )

                from authlib.jose.errors import JoseError

                with patch(
                    "m_shared.auth.oauth.authlib_jwt.decode",
                    side_effect=JoseError("Token expired"),
                ):
                    with pytest.raises(OIDCTokenError, match="validation failed"):
                        await exchange_code(code="code", state=valid_state)

    @pytest.mark.asyncio
    async def test_id_token_wrong_issuer(self):
        """ID token with wrong issuer raises OIDCTokenError."""
        valid_state = "valid-state-wrong-iss"
        oauth_module._pending_states[valid_state] = time.time() + 600

        wrong_iss_claims = _make_id_token_claims(iss="http://evil.example.com/realms/other")

        class FakeClaims(dict):
            def validate(self):
                pass

        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )
                respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                    return_value=httpx.Response(200, json={"keys": []})
                )
                respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
                    return_value=httpx.Response(
                        200, json={"id_token": "fake.token", "token_type": "Bearer"}
                    )
                )

                with patch(
                    "m_shared.auth.oauth.authlib_jwt.decode",
                    return_value=FakeClaims(wrong_iss_claims),
                ):
                    with pytest.raises(OIDCTokenError, match="issuer"):
                        await exchange_code(code="code", state=valid_state)

    @pytest.mark.asyncio
    async def test_id_token_wrong_audience(self):
        """ID token with wrong audience raises OIDCTokenError."""
        valid_state = "valid-state-wrong-aud"
        oauth_module._pending_states[valid_state] = time.time() + 600

        wrong_aud_claims = _make_id_token_claims(aud="wrong-client")

        class FakeClaims(dict):
            def validate(self):
                pass

        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )
                respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                    return_value=httpx.Response(200, json={"keys": []})
                )
                respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
                    return_value=httpx.Response(
                        200, json={"id_token": "fake.token", "token_type": "Bearer"}
                    )
                )

                with patch(
                    "m_shared.auth.oauth.authlib_jwt.decode",
                    return_value=FakeClaims(wrong_aud_claims),
                ):
                    with pytest.raises(OIDCTokenError, match="audience"):
                        await exchange_code(code="code", state=valid_state)


# ---------------------------------------------------------------------------
# Full OIDC flow integration test
# ---------------------------------------------------------------------------


class TestFullOIDCFlow:
    @pytest.mark.asyncio
    async def test_full_oidc_flow(self):
        """Integration: login → state generated → callback → valid platform JWT."""
        from m_shared.auth.jwt_handler import validate_token

        claims = _make_id_token_claims(sub="test-user-001")

        class FakeClaims(dict):
            def validate(self):
                pass

        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )
                respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                    return_value=httpx.Response(200, json={"keys": []})
                )
                respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
                    return_value=httpx.Response(
                        200, json={"id_token": "fake.id.token", "token_type": "Bearer"}
                    )
                )

                # Step 1: get authorization URL (generates state)
                auth_url, state = await get_authorization_url()
                assert state in oauth_module._pending_states

                # Step 2: simulate callback with same state
                with patch(
                    "m_shared.auth.oauth.authlib_jwt.decode",
                    return_value=FakeClaims(claims),
                ):
                    platform_token = await exchange_code(code="auth-code", state=state)

            # Step 3: validate the returned platform JWT (still inside env patch)
            token_claims = validate_token(platform_token)

        assert "user_id" in token_claims
        assert "localhost:8080" in token_claims["user_id"]
        assert "test-user-001" in token_claims["user_id"]
        assert "session_id" in token_claims

        # State should be consumed
        assert state not in oauth_module._pending_states


# ---------------------------------------------------------------------------
# Security event logging
# ---------------------------------------------------------------------------


class TestSecurityEventLogging:
    """Verify OIDC security events are logged at the correct level."""

    @pytest.mark.asyncio
    async def test_invalid_state_logs_warning(self, caplog):
        """Invalid OIDC state must emit a WARNING."""
        with patch.dict(os.environ, OIDC_ENV):
            with caplog.at_level(logging.WARNING, logger="m_shared.auth.oauth"):
                with pytest.raises(OIDCStateError):
                    await exchange_code(code="any", state="nonexistent-state")
        assert any("state" in r.message.lower() for r in caplog.records)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    async def test_id_token_failure_logs_warning(self, caplog):
        """ID token validation failure must emit a WARNING."""
        from authlib.jose.errors import JoseError

        _clear_oauth_caches()
        valid_state = "log-test-state-token-fail"
        oauth_module._pending_states[valid_state] = time.time() + 600

        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )
                respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                    return_value=httpx.Response(200, json={"keys": []})
                )
                respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
                    return_value=httpx.Response(
                        200, json={"id_token": "fake.bad.token", "token_type": "Bearer"}
                    )
                )
                with patch(
                    "m_shared.auth.oauth.authlib_jwt.decode",
                    side_effect=JoseError("bad signature"),
                ):
                    with caplog.at_level(logging.WARNING, logger="m_shared.auth.oauth"):
                        with pytest.raises(OIDCTokenError):
                            await exchange_code(code="code", state=valid_state)

        assert any("validation failed" in r.message.lower() for r in caplog.records)
        assert not any(
            "fake.bad.token" in r.message for r in caplog.records
        ), "Raw token string must not appear in log output"

    @pytest.mark.asyncio
    async def test_provider_unreachable_logs_error(self, caplog):
        """Unreachable OIDC token endpoint must emit an ERROR."""
        _clear_oauth_caches()
        valid_state = "log-test-state-unreachable"
        oauth_module._pending_states[valid_state] = time.time() + 600

        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )
                respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                    return_value=httpx.Response(200, json={"keys": []})
                )
                respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
                    side_effect=httpx.ConnectError("connection refused")
                )
                with caplog.at_level(logging.ERROR, logger="m_shared.auth.oauth"):
                    with pytest.raises(httpx.ConnectError):
                        await exchange_code(code="code", state=valid_state)

        assert any(r.levelno == logging.ERROR for r in caplog.records)
        assert any("unreachable" in r.message.lower() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_successful_login_logs_info(self, caplog):
        """Successful OIDC login must emit an INFO entry with normalized user_id."""

        class FakeClaims(dict):
            def validate(self):
                pass

        claims = _make_id_token_claims(sub="test-sub-logging")
        _clear_oauth_caches()
        valid_state = "log-test-state-success"
        oauth_module._pending_states[valid_state] = time.time() + 600

        with patch.dict(os.environ, OIDC_ENV):
            with respx.mock:
                respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
                    return_value=httpx.Response(200, json=DISCOVERY_DOC)
                )
                respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                    return_value=httpx.Response(200, json={"keys": []})
                )
                respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
                    return_value=httpx.Response(
                        200, json={"id_token": "fake.id.token", "token_type": "Bearer"}
                    )
                )
                with patch(
                    "m_shared.auth.oauth.authlib_jwt.decode",
                    return_value=FakeClaims(claims),
                ):
                    with caplog.at_level(logging.INFO, logger="m_shared.auth.oauth"):
                        await exchange_code(code="auth-code", state=valid_state)

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any("login successful" in r.message.lower() for r in info_records)
        assert any(
            "localhost:8080" in r.message for r in info_records
        ), "Normalized user_id should appear in the success log"
        assert not any(
            "fake.id.token" in r.message for r in caplog.records
        ), "Raw token string must not appear in log output"
