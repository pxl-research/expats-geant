"""URL and identifier validation for external platform APIs."""

import ipaddress
import logging
import os
import re
import socket
from urllib.parse import urlparse

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    """Read ``ENVIRONMENT`` env var. ``production`` enables strict SSRF guards.

    Treated as production only when set to the exact string ``production``;
    any other value (including unset / ``development`` / ``test``) is treated
    as a non-production environment, where ``validate_api_url`` allows http
    schemes and localhost / RFC1918 targets with a logged warning.
    """
    return os.getenv("ENVIRONMENT") == "production"


def _is_internal_address(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True if the address is loopback/private/link-local/etc. (SSRF-unsafe).

    Unwraps IPv4-mapped IPv6 (e.g. ``::ffff:127.0.0.1``) so that a mapped
    loopback/private address cannot slip past the v6 checks.
    """
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_unspecified
        or addr.is_multicast
        or addr.is_reserved
    )


def _assert_safe_host(hostname: str, detail: str) -> None:
    """Resolve ``hostname`` and reject if any resolved address is internal.

    Resolving (rather than only string-matching a few literals) is what makes
    this effective: it catches DNS names that resolve to private space, plus
    integer/hex/octal IP encodings (e.g. ``2130706433``) which ``getaddrinfo``
    normalises. Note: this does not pin the connection, so a hostname that
    re-resolves to a different address after this check (DNS rebinding) remains
    a residual risk; acceptable for the PoC's authenticated, consent-gated path.
    """
    # Literal IP address: validate directly.
    try:
        _addr = ipaddress.ip_address(hostname)
        if _is_internal_address(_addr):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
        return
    except ValueError:
        pass

    # DNS name: resolve and validate every address it maps to. If the host does
    # not resolve, there is no internal target to protect against, so allow it and
    # let the subsequent fetch fail naturally — this avoids coupling validation to
    # live DNS for unresolvable/offline hosts.
    try:
        # type=SOCK_STREAM collapses the result to one row per address instead of
        # the cartesian product over socket types. This call is blocking; async
        # callers must offload it (see fetch_url / the web route).
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return
    for info in infos:
        if _is_internal_address(ipaddress.ip_address(info[4][0])):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def validate_api_url(url: str) -> None:
    """Validate that a URL is a safe API endpoint URL.

    In production (``ENVIRONMENT=production``) this enforces HTTPS-only and
    rejects loopback / RFC1918 / link-local / multicast / reserved targets,
    mitigating SSRF against internal services.

    Outside production (dev/test) the HTTPS requirement is relaxed to allow
    http (so a local LimeSurvey or Qualtrics-like service can be tested), and
    internal addresses are allowed with a logged warning so the relaxation is
    visible in the application logs. Credentials embedded in the URL remain
    rejected everywhere — they leak into logs and are never the right thing.

    Raises:
        HTTPException: 400 if the URL is unsafe for the current environment.
    """
    parsed = urlparse(url)
    production = _is_production()

    if production:
        if parsed.scheme != "https":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="api_url must use HTTPS",
            )
    elif parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_url must use http or https",
        )

    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_url must not include credentials",
        )
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_url must include a valid hostname",
        )

    if production:
        _assert_safe_host(hostname, "api_url must not point to internal addresses")
    elif _hostname_resolves_to_internal(hostname):
        logger.warning(
            "Allowing api_url to internal address %r because ENVIRONMENT is %r "
            "(this URL would be rejected in production)",
            hostname,
            os.getenv("ENVIRONMENT", "<unset>"),
        )


def _hostname_resolves_to_internal(hostname: str) -> bool:
    """Return True if ``hostname`` resolves to any internal address.

    Mirrors ``_assert_safe_host``'s resolution logic but reports instead of
    raising, so the dev/test path can log a warning without blocking.
    Unresolvable hostnames return False (consistent with the strict guard,
    which also treats unresolved hosts as non-internal).
    """
    try:
        return _is_internal_address(ipaddress.ip_address(hostname))
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    return any(_is_internal_address(ipaddress.ip_address(info[4][0])) for info in infos)


def validate_web_url(url: str) -> None:
    """Validate that a user-supplied URL is safe to fetch for web ingestion.

    Allows both http and https (web ingestion is broader than the API import
    path which is HTTPS-only). Blocks credentials, loopback, and private/
    reserved address ranges to mitigate SSRF.

    Raises:
        HTTPException: 400 if the URL is unsafe.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must use http or https",
        )
    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must not include credentials",
        )
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must include a valid hostname",
        )
    _assert_safe_host(hostname, "URL must not point to internal addresses")


def validate_datacenter_id(datacenter_id: str) -> None:
    """Validate Qualtrics datacenter ID is a simple alphanumeric string.

    Raises:
        HTTPException: 400 if the datacenter ID contains non-alphanumeric characters.
    """
    if not re.match(r"^[a-zA-Z0-9]+$", datacenter_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid datacenter_id: must be alphanumeric",
        )
