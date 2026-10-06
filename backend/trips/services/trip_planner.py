from .geocoding import geocode_location
from .routing import build_route
from .hos_engine import plan_hos
from .daily_logs import POST_TRIP_ASSUMPTION, build_daily_logs


def plan_trip(data):
    locations = {key: geocode_location(data[f"{key}_location"], f"{key}_location")
                 for key in ("current", "pickup", "dropoff")}
    route = build_route(locations)
    schedule = plan_hos(route, data["current_cycle_used"])
    daily_logs = build_daily_logs(schedule["duty_events"]) if schedule["hos"]["status"] == "COMPLIANT_PLAN" else []
    if daily_logs:
        schedule["hos"] = {**schedule["hos"], "assumptions": [*schedule["hos"]["assumptions"], POST_TRIP_ASSUMPTION]}
    return {
        "input": data, "locations": locations, "route": route, **schedule,
        "daily_logs": daily_logs,
        "summary": {
            "distance_miles": route["distance_miles"],
            "estimated_driving_hours": route["estimated_driving_seconds"] / 3600,
            "current_cycle_used": data["current_cycle_used"],
            "remaining_cycle_hours": 70 - data["current_cycle_used"],
            **schedule["summary"],
            "daily_log_count": len(daily_logs),
        },
    }
