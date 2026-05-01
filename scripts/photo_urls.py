"""
Resolve photo URLs for the API response layer.

Photo URLs in the database can be absolute (Ontario MPPs hotlinked from
ola.org) or relative paths starting with '/' (federal MPs in /mp-photos/
served by the frontend). This module prepends FRONTEND_BASE_URL to the
relative ones so clients receive complete URLs.
"""
import os

FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "").rstrip("/")


def resolve_photo_url(value):
    """Prepend FRONTEND_BASE_URL to relative photo paths.

    Returns:
      - None unchanged
      - Absolute URLs (http:// or https://) unchanged
      - Relative paths (starting with /) prefixed with FRONTEND_BASE_URL
        if it's set, otherwise returned unchanged

    The fallback (returning relative paths as-is when FRONTEND_BASE_URL
    is unset) means local development without the env var still works
    when the frontend serves both API responses and static photos from
    the same origin — which we never actually do, but the safe default
    matters more than the unreachable case.
    """
    if not value:
        return value
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("/") and FRONTEND_BASE_URL:
        return FRONTEND_BASE_URL + value
    return value
