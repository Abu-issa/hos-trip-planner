"""Deterministic relative-time planning. No Django, HTTP, or prior-day history."""
from bisect import bisect_left
from math import asin, ceil, cos, radians, sin, sqrt

HOUR = 3600
EPS = 1e-7
ASSUMPTIONS = [
    "Property-carrying driver; 70-hour/8-day cycle; no adverse conditions or split-sleeper exception.",
    "Trip starts after at least 10 consecutive hours off duty, with fresh daily driving and break clocks.",
    "Supplied cycle usage remains consumed; no prior-day history, midnight recapture, or 34-hour restart is inferred.",
    "Pickup and dropoff each take one hour on duty; fueling takes 30 minutes on duty.",
    "Full fuel state at departure; maximum 1,000 miles between fuel events.",
    "Daily rests are planned as 10 consecutive hours in SLEEPER_BERTH.",
    "Driving speed is uniform within each route leg; stop coordinates follow cumulative road geometry and are estimated, not verified facilities.",
    "Day/time labels are elapsed trip offsets, not calendar dates or local clock times.",
]


class GeometryProgress:
    def __init__(self, coordinates):
        self.points = coordinates
        self.cumulative = [0.0]
        for a, b in zip(coordinates, coordinates[1:]):
            lon1, lat1, lon2, lat2 = map(radians, [*a, *b])
            hav = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
            self.cumulative.append(self.cumulative[-1] + 2 * asin(sqrt(min(1, hav))))

    def at(self, fraction):
        target = min(1, max(0, fraction)) * self.cumulative[-1]
        index = min(max(1, bisect_left(self.cumulative, target)), len(self.points) - 1)
        span = self.cumulative[index] - self.cumulative[index - 1]
        ratio = (target - self.cumulative[index - 1]) / span if span else 0
        a, b = self.points[index - 1:index + 1]
        delta = b[0] - a[0]
        if abs(delta) > 180:
            delta = (delta + 180) % 360 - 180
        longitude = a[0] + delta * ratio
        if abs(longitude) > 180:
            longitude = (longitude + 180) % 360 - 180
        return {"longitude": longitude, "latitude": a[1] + (b[1] - a[1]) * ratio}


def plan_hos(route, current_cycle_used):
    legs = route["legs"]
    distance = sum(leg["distance_miles"] for leg in legs)
    driving = sum(leg["duration_seconds"] for leg in legs)
    # Use the same mileage tolerance for preflight and scheduling at fuel boundaries.
    fuel_count = max(0, ceil((distance - EPS) / 1000) - 1)
    fuels_remaining = fuel_count
    required_work = driving + 2 * HOUR + fuel_count * 1800
    summary = {
        "estimated_driving_seconds": driving,
        "cycle_hours_available_at_start": 70 - current_cycle_used,
        "cycle_work_required_seconds": required_work,
        "required_cycle_used_if_completed": current_cycle_used + required_work / HOUR,
    }
    if required_work > (70 - current_cycle_used) * HOUR + EPS:
        return {
            "hos": {"status": "INSUFFICIENT_CYCLE_HOURS", "message": "The supplied cycle usage leaves insufficient known 70-hour-cycle capacity to complete driving, pickup, dropoff, and fueling. No recapture or 34-hour restart has been assumed.", "assumptions": ASSUMPTIONS},
            "summary": {**summary, "planned_elapsed_seconds": None, "projected_cycle_used": None},
            "duty_events": [], "stops": [],
        }

    events, stops = [], []
    now = daily_driving = since_break = miles_since_fuel = total_miles = 0.0
    window_start = None

    def emit(status, reason, seconds, start, end, leg_id, miles=0):
        nonlocal now, daily_driving, since_break, window_start, miles_since_fuel, total_miles, fuels_remaining
        if window_start is None and status in ("DRIVING", "ON_DUTY_NOT_DRIVING"):
            window_start = now
        qualifies = status != "DRIVING" and seconds >= 1800
        break_due = since_break >= 8 * HOUR - EPS
        event = {
            "id": f"event-{len(events) + 1}", "status": status, "reason": reason,
            "start_offset_seconds": now, "end_offset_seconds": now + seconds,
            "duration_seconds": seconds, "distance_miles": miles,
            "start_location": start, "end_location": end, "leg_id": leg_id,
        }
        events.append(event)
        now += seconds
        if status == "DRIVING":
            daily_driving += seconds
            since_break += seconds
            miles_since_fuel += miles
            total_miles += miles
        else:
            kinds = [reason]
            if qualifies and break_due and reason != "REQUIRED_BREAK":
                kinds.append("REQUIRED_BREAK")
            stop = {
                "id": f"stop-{len(stops) + 1}", "kinds": kinds,
                "start_offset_seconds": event["start_offset_seconds"], "end_offset_seconds": now,
                "duration_seconds": seconds, "location": start,
                "location_is_estimated": True, "cumulative_route_miles": total_miles,
                "duty_event_ids": [event["id"]],
            }
            # Adjacent stationary activities at the same point share one map marker.
            if stops and events[-2]["status"] != "DRIVING" and stops[-1]["location"] == start:
                previous = stops[-1]
                previous["kinds"] = list(dict.fromkeys(previous["kinds"] + kinds))
                previous["end_offset_seconds"] = now
                previous["duration_seconds"] += seconds
                previous["duty_event_ids"].append(event["id"])
            else:
                stops.append(stop)
            if qualifies:
                since_break = 0
            if reason == "DAILY_REST":
                daily_driving = 0
                window_start = None
            if reason == "FUEL":
                miles_since_fuel = 0
                fuels_remaining -= 1

    for leg_index, leg in enumerate(legs):
        geometry = GeometryProgress(leg["geometry"]["coordinates"])
        duration, miles = leg["duration_seconds"], leg["distance_miles"]
        progress = 0.0
        while progress < duration - EPS:
            point = geometry.at(progress / duration)
            if fuels_remaining and miles_since_fuel >= 1000 - EPS:
                emit("ON_DUTY_NOT_DRIVING", "FUEL", 1800, point, point, leg["id"])
                continue
            window_left = 14 * HOUR - (now - window_start) if window_start is not None else 14 * HOUR
            if daily_driving >= 11 * HOUR - EPS or window_left <= EPS:
                emit("SLEEPER_BERTH", "DAILY_REST", 10 * HOUR, point, point, leg["id"])
                continue
            if since_break >= 8 * HOUR - EPS:
                emit("OFF_DUTY", "REQUIRED_BREAK", 1800, point, point, leg["id"])
                continue
            fuel_time = (1000 - miles_since_fuel) * duration / miles if miles > 0 and fuels_remaining else float("inf")
            seconds = min(duration - progress, 11 * HOUR - daily_driving, 8 * HOUR - since_break, window_left, fuel_time)
            end = geometry.at((progress + seconds) / duration)
            emit("DRIVING", "TRAVEL", seconds, point, end, leg["id"], miles * seconds / duration)
            progress += seconds
        point = geometry.at(1)
        emit("ON_DUTY_NOT_DRIVING", "PICKUP" if leg_index == 0 else "DROPOFF", HOUR, point, point, leg["id"])

    totals = {status: sum(e["duration_seconds"] for e in events if e["status"] == status)
              for status in ("DRIVING", "ON_DUTY_NOT_DRIVING", "OFF_DUTY", "SLEEPER_BERTH")}
    on_duty = totals["DRIVING"] + totals["ON_DUTY_NOT_DRIVING"]
    summary.update({
        "planned_driving_seconds": totals["DRIVING"],
        "planned_on_duty_not_driving_seconds": totals["ON_DUTY_NOT_DRIVING"],
        "planned_on_duty_seconds": on_duty,
        "planned_off_duty_seconds": totals["OFF_DUTY"],
        "planned_sleeper_berth_seconds": totals["SLEEPER_BERTH"],
        "planned_elapsed_seconds": now,
        "projected_cycle_used": current_cycle_used + on_duty / HOUR,
        "fuel_stop_count": sum(e["reason"] == "FUEL" for e in events),
        "required_break_count": sum(e["reason"] == "REQUIRED_BREAK" for e in events),
        "daily_rest_count": sum(e["reason"] == "DAILY_REST" for e in events),
    })
    return {"hos": {"status": "COMPLIANT_PLAN", "assumptions": ASSUMPTIONS}, "summary": summary, "duty_events": events, "stops": stops}
