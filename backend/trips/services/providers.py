"""Shared provider error handling; never send upstream bodies to the client."""
import math

import requests
from django.conf import settings


class ProviderError(Exception):
    def __init__(self, code, message, status=502, fields=None):
        super().__init__(message)
        self.status = status
        self.payload = {"error": {"code": code, "message": message, "fields": fields or {}}}


def invalid_response(provider):
    return ProviderError("INVALID_PROVIDER_RESPONSE", f"The {provider} service returned an invalid response. Please try again.")


def get_json(url, params, provider, allow_route_error=False):
    try:
        response = requests.get(
            url, params=params,
            headers={"User-Agent": settings.PROVIDER_USER_AGENT, "Accept": "application/json"},
            timeout=(3.05, settings.PROVIDER_TIMEOUT_SECONDS),
        )
        if not (allow_route_error and response.status_code == 400):
            response.raise_for_status()
    except requests.Timeout as exc:
        raise ProviderError("PROVIDER_TIMEOUT", f"The {provider} service took too long to respond. Please try again.", 504) from exc
    except requests.RequestException as exc:
        raise ProviderError("PROVIDER_UNAVAILABLE", f"The {provider} service is temporarily unavailable. Please try again later.") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise invalid_response(provider) from exc
    if response.status_code == 400 and not (
        isinstance(data, dict) and data.get("code") in ("NoRoute", "NoSegment")
    ):
        raise invalid_response(provider)
    return data


def finite_number(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a coordinate or measurement")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Nonfinite measurement")
    return value
