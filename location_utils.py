"""Lightweight helpers for geo lookups used by the attendance app.

The functions here keep all location logic in one place so the main
Flask app remains clean and modular. They attempt to:
- use provided GPS coordinates when present (preferred)
- otherwise fall back to IP-based geolocation
- optionally reverse geocode coordinates to a human‑readable address

All network calls are wrapped with timeouts and broad exception handling
so a failed lookup never blocks the face-recognition workflow.
"""

from __future__ import annotations

from typing import Optional, Tuple

import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable

# Keep requests snappy—location lookups should not slow attendance capture.
GEO_TIMEOUT = 4

# A single geocoder instance is fine for this lightweight app.
_geocoder = Nominatim(user_agent="smart-attendance-geo")


def get_client_ip(flask_request) -> str:
    """Best-effort client IP extraction behind proxies/load balancers."""
    forwarded = flask_request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # RFC 7239 first entry is the original client
        return forwarded.split(",")[0].strip()
    return flask_request.remote_addr or ""


def ip_lookup(ip: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Resolve an IP address to (lat, lon, label) using ipapi.co.

    Returns (None, None, None) if anything fails so callers can fall back
    without raising.
    """

    if not ip or ip.startswith("127.") or ip == "::1":
        return None, None, None

    try:
        res = requests.get(f"https://ipapi.co/{ip}/json/", timeout=GEO_TIMEOUT)
        if not res.ok:
            return None, None, None
        data = res.json()
        lat = data.get("latitude")
        lon = data.get("longitude")
        city = data.get("city")
        region = data.get("region")
        country = data.get("country_name") or data.get("country")
        parts = [p for p in (city, region, country) if p]
        label = ", ".join(parts) + " (IP)" if parts else None
        return lat, lon, label
    except Exception:
        return None, None, None


def reverse_lookup(lat: float, lon: float) -> Optional[str]:
    """Reverse geocode coordinates to a readable address (best effort)."""

    try:
        loc = _geocoder.reverse((lat, lon), language="en", timeout=GEO_TIMEOUT)
        if loc and loc.address:
            return loc.address
    except (GeocoderUnavailable, GeocoderTimedOut, GeocoderServiceError, ValueError):
        return None
    except Exception:
        return None
    return None


def resolve_location(payload: dict, flask_request) -> Tuple[str, Optional[float], Optional[float]]:
    """Combine client-supplied data with server fallbacks.

    Priority order:
    1. Use provided lat/lon; reverse geocode if no friendly text supplied.
    2. If no coords, use IP-based lookup.
    3. Fall back to any provided `location` text or "Unknown Location".
    """

    location_text = payload.get("location") or None
    lat = payload.get("lat")
    lon = payload.get("lon")

    lat = float(lat) if lat not in (None, "") else None
    lon = float(lon) if lon not in (None, "") else None

    if lat is not None and lon is not None:
        # Prefer client GPS; fill in text if missing
        if not location_text:
            location_text = reverse_lookup(lat, lon) or f"{lat:.4f}, {lon:.4f}"
        return location_text, lat, lon

    # No coordinates—fallback to IP-based city/region
    client_ip = get_client_ip(flask_request)
    ip_lat, ip_lon, ip_label = ip_lookup(client_ip)
    if ip_lat is not None and ip_lon is not None:
        return ip_label or "IP-based Location", ip_lat, ip_lon

    # Final fallback; keep the workflow running
    return location_text or "Unknown Location", lat, lon
