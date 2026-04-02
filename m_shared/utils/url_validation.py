"""URL and identifier validation for external platform APIs."""

import ipaddress
import re
from urllib.parse import urlparse

from fastapi import HTTPException, status


def validate_api_url(url: str) -> None:
    """Validate that a URL is a safe HTTPS URL (not internal/loopback).

    Raises:
        HTTPException: 400 if the URL is unsafe.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_url must use HTTPS",
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
    try:
        addr = ipaddress.ip_address(hostname)
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_unspecified
            or addr.is_multicast
            or addr.is_reserved
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="api_url must not point to internal addresses",
            )
    except ValueError:
        if hostname in ("localhost", "127.0.0.1", "::1"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="api_url must not point to internal addresses",
            )


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
