from copy import deepcopy
from unittest import TestCase

from trips.services.daily_logs import build_daily_logs
from trips.services.hos_engine import plan_hos
from .test_hos_engine import route


def event(id, start, end, status="DRIVING", reason="TRAVEL", miles=0):
    return {"id": id, "start_offset_seconds": start, "end_offset_seconds": end,
            "duration_seconds": end - start, "status": status, "reason": reason,
            "distance_miles": miles, "start_location": {"latitude": 40, "longitude": -90}}


class DailyLogTests(TestCase):
    def assert_complete(self, logs, events):
        for index, log in enumerate(logs):
            self.assertEqual(log["day"], index + 1)
            self.assertEqual(log["start_offset_seconds"], index * 86400)
            self.assertAlmostEqual(sum(log["totals_seconds"].values()), 86400)
            cursor = 0
            for entry in log["entries"]:
                self.assertEqual(entry["start_second_of_day"], cursor)
                self.assertGreater(entry["duration_seconds"], 0)
                cursor = entry["end_second_of_day"]
            self.assertEqual(cursor, 86400)
        self.assertAlmostEqual(sum(log["distance_miles"] for log in logs), sum(e["distance_miles"] for e in events))
        for source in events:
            slices = [entry for log in logs for entry in log["entries"] if entry["original_event_id"] == source["id"]]
            self.assertAlmostEqual(sum(e["duration_seconds"] for e in slices), source["duration_seconds"])
            self.assertAlmostEqual(sum(e["distance_miles"] for e in slices), source["distance_miles"])

    def test_single_day_and_source_unchanged(self):
        events = plan_hos(route(), 0)["duty_events"]
        original = deepcopy(events)
        logs = build_daily_logs(events)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["entries"][-1]["reason"], "POST_TRIP_OFF_DUTY")
        self.assertEqual(logs[0]["totals_seconds"]["DRIVING"], 14400)
        self.assertEqual(events, original)
        self.assert_complete(logs, events)

    def test_driving_crosses_midnight_and_mileage_split(self):
        events = [event("a", 0, 23*3600, "SLEEPER_BERTH", "DAILY_REST"),
                  event("b", 23*3600, 26*3600, miles=180),
                  event("c", 26*3600, 27*3600, "ON_DUTY_NOT_DRIVING", "DROPOFF")]
        logs = build_daily_logs(events)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["distance_miles"], 60)
        self.assertEqual(logs[1]["distance_miles"], 120)
        self.assertEqual(logs[1]["entries"][0]["end_second_of_day"], 7200)
        self.assert_complete(logs, events)

    def test_sleeper_crosses_midnight(self):
        events = [event("a", 0, 22*3600, miles=100),
                  event("b", 22*3600, 32*3600, "SLEEPER_BERTH", "DAILY_REST"),
                  event("c", 32*3600, 33*3600, "ON_DUTY_NOT_DRIVING", "DROPOFF")]
        logs = build_daily_logs(events)
        self.assertEqual(logs[0]["totals_seconds"]["SLEEPER_BERTH"], 7200)
        self.assertEqual(logs[1]["totals_seconds"]["SLEEPER_BERTH"], 28800)
        self.assertTrue(logs[1]["remarks"][0]["continued_from_previous_day"])
        self.assert_complete(logs, events)

    def test_long_hos_stream(self):
        events = plan_hos(route((20, 20), (1200, 1200)), 0)["duty_events"]
        logs = build_daily_logs(events)
        self.assertGreaterEqual(len(logs), 3)
        self.assert_complete(logs, events)

    def test_final_off_duty_at_1730(self):
        events = [event("a", 0, 16.5*3600, miles=900), event("b", 16.5*3600, 17.5*3600, "ON_DUTY_NOT_DRIVING", "DROPOFF")]
        logs = build_daily_logs(events)
        tail = logs[0]["entries"][-1]
        self.assertEqual(tail["start_second_of_day"], 63000)
        self.assertEqual(tail["duration_seconds"], 23400)
        self.assertEqual(tail["status"], "OFF_DUTY")
        self.assertIsNone(tail["original_event_id"])
        self.assert_complete(logs, events)

    def test_exact_midnight_has_no_extra_day(self):
        for days in (1, 2, 3):
            end = days * 86400
            events = [event("a", 0, end-3600, miles=500), event("b", end-3600, end, "ON_DUTY_NOT_DRIVING", "DROPOFF")]
            with self.subTest(days=days):
                logs = build_daily_logs(events)
                self.assertEqual(len(logs), days)
                self.assertEqual(logs[-1]["entries"][-1]["reason"], "DROPOFF")
                self.assert_complete(logs, events)

    def test_event_spans_multiple_days(self):
        events = [event("a", 0, 50*3600, "OFF_DUTY", "REQUIRED_BREAK"), event("b", 50*3600, 51*3600, "ON_DUTY_NOT_DRIVING", "DROPOFF")]
        logs = build_daily_logs(events)
        self.assertEqual(len(logs), 3)
        self.assert_complete(logs, events)

    def test_fractional_seconds_preserved(self):
        events = [event("a", 0, 86400.123, miles=100.123), event("b", 86400.123, 90000.123, "ON_DUTY_NOT_DRIVING", "DROPOFF")]
        self.assert_complete(build_daily_logs(events), events)

    def test_empty_insufficient_schedule(self):
        self.assertEqual(build_daily_logs(plan_hos(route(), 70)["duty_events"]), [])

    def test_invalid_streams_fail_without_filling(self):
        valid = [event("a", 0, 3600), event("b", 3600, 7200, "ON_DUTY_NOT_DRIVING", "DROPOFF")]
        for start in (3599, 3601):
            with self.subTest(start=start), self.assertRaises(ValueError):
                build_daily_logs([valid[0], event("b", start, 7200, "ON_DUTY_NOT_DRIVING", "DROPOFF")])
        for field, value in (("status", "UNKNOWN"), ("distance_miles", 1), ("duration_seconds", 0), ("end_offset_seconds", float("nan"))):
            events = deepcopy(valid)
            events[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_daily_logs(events)
        with self.assertRaises(ValueError):
            build_daily_logs(valid[::-1])
        with self.assertRaises(ValueError):
            build_daily_logs(valid[:1])
