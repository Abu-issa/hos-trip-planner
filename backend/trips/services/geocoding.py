import hashlib
import threading
import time

from django.conf import settings
from django.core.cache import cache

from .providers import ProviderError, finite_number, get_json, invalid_response

_lock = threading.Lock()
_last_request = 0.0


def geocode_location(input_text, field):
    """Submit-only geocoding, cached and serialized within the demo process."""
    global _last_request
    key = "geocode:" + hashlib.sha256(
        (settings.NOMINATIM_URL + input_text.strip().casefold()).encode()
    ).hexdigest()
    with _lock:
        result = cache.get(key)
        if result is None:
            delay = 1.1 - (time.monotonic() - _last_request)
            if delay > 0:
                time.sleep(delay)
            _last_request = time.monotonic()
            data = get_json(settings.NOMINATIM_URL, {
                "q": input_text, "format": "jsonv2", "limit": 1,
                "accept-language": "en",
            }, "geocoding")
            if not isinstance(data, list):
                raise invalid_response("geocoding")
            if not data:
                result = {}
            else:
                try:
                    item = data[0]
                    lat, lon = finite_number(item["lat"]), finite_number(item["lon"])
                    name = item["display_name"]
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        raise ValueError("Invalid coordinates")
                    if not isinstance(name, str) or not name.strip():
                        raise ValueError("Missing name")
                    result = {"display_name": name, "latitude": lat, "longitude": lon}
                except (KeyError, TypeError, ValueError, OverflowError) as exc:
                    raise invalid_response("geocoding") from exc
            cache.set(key, result, 86400)
    if not result:
        label = field.replace("_", " ")
        raise ProviderError("LOCATION_NOT_FOUND", f"Could not resolve the {label}.", 422, {
            field: ["Use a more specific city, state, or address."],
        })
    return {"input_text": input_text, **result}
