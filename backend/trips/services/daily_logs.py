"""Project existing duty events onto relative 24-hour days; never reschedule work."""
from math import isclose, isfinite

DAY_SECONDS = 86400
STATUSES = ("OFF_DUTY", "SLEEPER_BERTH", "DRIVING", "ON_DUTY_NOT_DRIVING")
POST_TRIP_ASSUMPTION = "After dropoff, the remainder of the final planning day is projected OFF_DUTY solely to complete the 24-hour log; it does not change the trip schedule or cycle totals."


def build_daily_logs(duty_events):
    if not duty_events:
        return []

    # Validate the whole stream before adding any projection. Do not sort or repair it.
    previous_end = 0
    for event in duty_events:
        start, end = event["start_offset_seconds"], event["end_offset_seconds"]
        duration, distance = event["duration_seconds"], event["distance_miles"]
        if not all(isfinite(value) for value in (start, end, duration, distance)):
            raise ValueError("Daily log source contains nonfinite values.")
        if start != previous_end:
            raise ValueError("Daily log source contains a gap, overlap, or out-of-order event.")
        if end <= start or not isclose(end - start, duration, rel_tol=0, abs_tol=1e-7):
            raise ValueError("Daily log source contains an invalid duration.")
        if event["status"] not in STATUSES:
            raise ValueError("Daily log source contains an unknown duty status.")
        if distance < 0 or (event["status"] != "DRIVING" and distance != 0):
            raise ValueError("Only driving events can carry nonnegative mileage.")
        previous_end = end
    if duty_events[-1]["reason"] != "DROPOFF":
        raise ValueError("Daily logs require a completed trip ending with dropoff.")

    logs = []
    for event in duty_events:
        cursor = event["start_offset_seconds"]
        while cursor < event["end_offset_seconds"]:
            day_index = int(cursor // DAY_SECONDS)
            day_start = day_index * DAY_SECONDS
            day_end = day_start + DAY_SECONDS
            if len(logs) <= day_index:
                logs.append({
                    "day": day_index + 1, "start_offset_seconds": day_start,
                    "end_offset_seconds": day_end, "entries": [],
                    "totals_seconds": dict.fromkeys(STATUSES, 0),
                    "distance_miles": 0, "remarks": [],
                })
            end = min(event["end_offset_seconds"], day_end)
            seconds = end - cursor
            distance = event["distance_miles"] * seconds / event["duration_seconds"] if event["status"] == "DRIVING" else 0
            log = logs[day_index]
            entry = {
                "status": event["status"], "reason": event["reason"],
                "start_second_of_day": cursor - day_start,
                "end_second_of_day": end - day_start,
                "duration_seconds": seconds, "distance_miles": distance,
                "original_event_id": event["id"],
            }
            log["entries"].append(entry)
            log["totals_seconds"][event["status"]] += seconds
            log["distance_miles"] += distance
            if event["status"] != "DRIVING":
                log["remarks"].append({
                    "second_of_day": entry["start_second_of_day"],
                    "reason": event["reason"], "original_event_id": event["id"],
                    "continued_from_previous_day": cursor > event["start_offset_seconds"],
                    "location": event.get("start_location"),
                })
            cursor = end

    final = logs[-1]
    final_second = previous_end - final["start_offset_seconds"]
    if final_second < DAY_SECONDS:
        seconds = DAY_SECONDS - final_second
        final["entries"].append({
            "status": "OFF_DUTY", "reason": "POST_TRIP_OFF_DUTY",
            "start_second_of_day": final_second, "end_second_of_day": DAY_SECONDS,
            "duration_seconds": seconds, "distance_miles": 0, "original_event_id": None,
        })
        final["totals_seconds"]["OFF_DUTY"] += seconds
        final["remarks"].append({
            "second_of_day": final_second, "reason": "POST_TRIP_OFF_DUTY",
            "original_event_id": None, "continued_from_previous_day": False,
            "location": None,
        })
    return logs
