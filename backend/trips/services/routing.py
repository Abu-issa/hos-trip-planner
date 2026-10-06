from django.conf import settings

from .providers import ProviderError, finite_number, get_json, invalid_response

METERS_PER_MILE = 1609.344


def route_leg(start, end, from_key, to_key):
    coordinates = f"{start['longitude']},{start['latitude']};{end['longitude']},{end['latitude']}"
    data = get_json(
        f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{coordinates}",
        {"overview": "full", "geometries": "geojson", "steps": "false", "alternatives": "false"},
        "routing", allow_route_error=True,
    )
    if isinstance(data, dict) and data.get("code") in ("NoRoute", "NoSegment"):
        raise ProviderError("NO_ROUTE_FOUND", f"No road route was found from {from_key} to {to_key}. Try more specific road-accessible locations.", 422)
    try:
        if data["code"] != "Ok":
            raise ValueError("Routing failed")
        route = data["routes"][0]
        distance = finite_number(route["distance"])
        duration = finite_number(route["duration"])
        if distance > 0 and duration == 0:
            raise ValueError("Positive route distance requires driving time")
        geometry = route["geometry"]
        points = geometry["coordinates"]
        if distance < 0 or duration < 0 or geometry["type"] != "LineString" or not isinstance(points, list) or len(points) < 2:
            raise ValueError("Invalid route")
        normalized = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("Invalid point")
            lon, lat = map(finite_number, point)
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError("Invalid coordinates")
            normalized.append([lon, lat])
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        raise invalid_response("routing") from exc
    return {
        "id": f"{from_key}_to_{to_key}", "from": from_key, "to": to_key,
        "distance_miles": distance / METERS_PER_MILE,
        "duration_seconds": duration,
        "geometry": {"type": "LineString", "coordinates": normalized},
    }


def build_route(locations):
    legs = [
        route_leg(locations["current"], locations["pickup"], "current", "pickup"),
        route_leg(locations["pickup"], locations["dropoff"], "pickup", "dropoff"),
    ]
    return {
        "distance_miles": sum(leg["distance_miles"] for leg in legs),
        "estimated_driving_seconds": sum(leg["duration_seconds"] for leg in legs),
        "legs": legs,
    }
