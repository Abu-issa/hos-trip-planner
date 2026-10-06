from unittest import TestCase

from trips.services.hos_engine import GeometryProgress, plan_hos


def route(hours=(2, 2), miles=(100, 100)):
    legs = [{"id": name, "duration_seconds": hours[i] * 3600, "distance_miles": miles[i],
             "geometry": {"type": "LineString", "coordinates": [[-90 + i, 40], [-89 + i, 41], [-89 + i, 40]]}}
            for i, name in enumerate(("current_to_pickup", "pickup_to_dropoff"))]
    return {"legs": legs, "distance_miles": sum(miles), "estimated_driving_seconds": sum(hours) * 3600}


class HOSTests(TestCase):
    def check_invariants(self, plan, source, used=0):
        events = plan["duty_events"]
        self.assertEqual(sum(e["reason"] == "PICKUP" for e in events), 1)
        self.assertEqual(sum(e["reason"] == "DROPOFF" for e in events), 1)
        self.assertEqual(events[-1]["reason"], "DROPOFF")
        pickup_index = next(i for i, e in enumerate(events) if e["reason"] == "PICKUP")
        self.assertTrue(all(e["leg_id"] == "current_to_pickup" for e in events[:pickup_index + 1]))
        self.assertTrue(all(e["leg_id"] == "pickup_to_dropoff" for e in events[pickup_index + 1:]))
        end = driving = work = daily = since_break = fuel_miles = 0
        window = None
        for event in events:
            duration = event["duration_seconds"]
            self.assertGreater(duration, 0)
            self.assertAlmostEqual(event["start_offset_seconds"], end)
            self.assertAlmostEqual(event["end_offset_seconds"] - end, duration)
            if event["status"] in ("DRIVING", "ON_DUTY_NOT_DRIVING"):
                work += duration
                if window is None:
                    window = end
            end = event["end_offset_seconds"]
            if event["status"] == "DRIVING":
                driving += duration
                daily += duration
                since_break += duration
                fuel_miles += event["distance_miles"]
                self.assertLessEqual(daily, 11 * 3600 + 1e-6)
                self.assertLessEqual(since_break, 8 * 3600 + 1e-6)
                self.assertLessEqual(end - window, 14 * 3600 + 1e-6)
                self.assertLessEqual(fuel_miles, 1000 + 1e-6)
            elif duration >= 1800:
                since_break = 0
            if event["reason"] == "FUEL":
                self.assertEqual(duration, 1800)
                fuel_miles = 0
            if event["reason"] == "DAILY_REST":
                self.assertEqual(duration, 36000)
                daily = 0
                window = None
        self.assertAlmostEqual(driving, source["estimated_driving_seconds"])
        self.assertAlmostEqual(sum(e["distance_miles"] for e in events), source["distance_miles"])
        self.assertAlmostEqual(work, plan["summary"]["cycle_work_required_seconds"])
        self.assertAlmostEqual(used + work / 3600, plan["summary"]["projected_cycle_used"])
        self.assertLessEqual(used + work / 3600, 70 + 1e-9)
        self.assertAlmostEqual(end, plan["summary"]["planned_elapsed_seconds"])

    def test_short_trip(self):
        source = route()
        plan = plan_hos(source, 15)
        self.assertEqual([e["reason"] for e in plan["duty_events"]], ["TRAVEL", "PICKUP", "TRAVEL", "DROPOFF"])
        self.assertEqual(plan["summary"]["projected_cycle_used"], 21)
        self.check_invariants(plan, source, 15)

    def test_required_break(self):
        plan = plan_hos(route((9, 1)), 0)
        self.assertEqual(plan["duty_events"][1]["reason"], "REQUIRED_BREAK")
        self.assertEqual(plan["summary"]["required_break_count"], 1)
        self.check_invariants(plan, route((9, 1)))

    def test_pickup_qualifies(self):
        plan = plan_hos(route((8, 2)), 0)
        self.assertEqual(plan["summary"]["required_break_count"], 0)
        self.assertIn("REQUIRED_BREAK", plan["stops"][0]["kinds"])

    def test_fuel_qualifies_without_duplicate_break(self):
        source = route((10, 0), (1250, 0))
        plan = plan_hos(source, 0)
        self.assertEqual(plan["summary"]["required_break_count"], 0)
        fuel = next(s for s in plan["stops"] if "FUEL" in s["kinds"])
        self.assertEqual(fuel["kinds"], ["FUEL", "REQUIRED_BREAK"])
        self.assertEqual(fuel["duration_seconds"], 1800)
        self.check_invariants(plan, source)

    def test_daily_limit(self):
        source = route((12, 1))
        plan = plan_hos(source, 0)
        self.assertEqual(plan["summary"]["daily_rest_count"], 1)
        self.check_invariants(plan, source)

    def test_window_limited_by_fueling_work(self):
        # Synthetic high mileage isolates the elapsed-window rule before 11h driving.
        source = route((10, 1), (10000, 100))
        plan = plan_hos(source, 0)
        rest = next(e for e in plan["duty_events"] if e["reason"] == "DAILY_REST")
        self.assertLess(sum(e["duration_seconds"] for e in plan["duty_events"] if e["status"] == "DRIVING" and e["end_offset_seconds"] <= rest["start_offset_seconds"]), 11 * 3600)
        self.check_invariants(plan, source)

    def test_break_does_not_extend_window(self):
        source = route((8, 4), (500, 8000))
        plan = plan_hos(source, 0)
        self.check_invariants(plan, source)
        # Explicit ordinary break followed by enough fuel work to exhaust the window.
        source = route((9, 3), (500, 8000))
        plan = plan_hos(source, 0)
        self.assertGreater(plan["summary"]["required_break_count"], 0)
        self.check_invariants(plan, source)

    def test_long_trip_counters_and_cycle(self):
        source = route((20, 20), (1200, 1200))
        plan = plan_hos(source, 10)
        self.assertEqual(plan["summary"]["daily_rest_count"], 3)
        self.assertEqual(plan["summary"]["projected_cycle_used"], 53)
        self.check_invariants(plan, source, 10)

    def test_fuel_boundaries(self):
        for miles, count in ((999, 0), (1000, 0), (1001, 1), (2000, 1), (2001, 2)):
            with self.subTest(miles=miles):
                source = route((5, 5), (miles / 2, miles / 2))
                plan = plan_hos(source, 0)
                self.assertEqual(plan["summary"]["fuel_stop_count"], count)
                self.check_invariants(plan, source)

    def test_cycle_insufficient(self):
        for used in (65, 70):
            plan = plan_hos(route(), used)
            self.assertEqual(plan["hos"]["status"], "INSUFFICIENT_CYCLE_HOURS")
            self.assertEqual(plan["duty_events"], [])
            self.assertIsNone(plan["summary"]["projected_cycle_used"])

    def test_cycle_exact_limit(self):
        plan = plan_hos(route(), 64)
        self.assertEqual(plan["summary"]["projected_cycle_used"], 70)
        self.check_invariants(plan, route(), 64)
        self.assertEqual(plan_hos(route(), 64.0001)["hos"]["status"], "INSUFFICIENT_CYCLE_HOURS")

    def test_zero_distance_trip_still_has_two_operations(self):
        plan = plan_hos(route((0, 0), (0, 0)), 68)
        self.assertEqual([e["reason"] for e in plan["duty_events"]], ["PICKUP", "DROPOFF"])
        self.assertEqual(plan["summary"]["projected_cycle_used"], 70)

    def test_geometry_interpolation_follows_bend(self):
        geometry = GeometryProgress([[0, 0], [0, 1], [1, 1]])
        point = geometry.at(.25)
        self.assertEqual(point["longitude"], 0)
        self.assertAlmostEqual(point["latitude"], .5, places=3)

    def test_geometry_crossing_antimeridian_stays_near_route(self):
        geometry = GeometryProgress([[179, 40], [-179, 40]])
        self.assertAlmostEqual(abs(geometry.at(.5)["longitude"]), 180)
        self.assertAlmostEqual(geometry.at(.75)["longitude"], -179.5)
        self.assertEqual(geometry.at(1), {"longitude": -179, "latitude": 40})

    def test_no_unnecessary_rest_after_final_driving(self):
        plan = plan_hos(route((5, 6)), 0)
        self.assertEqual(plan["summary"]["daily_rest_count"], 0)
        self.assertEqual(plan["duty_events"][-1]["reason"], "DROPOFF")

    def test_dropoff_can_finish_after_driving_window(self):
        source = route((0, 9), (0, 8100))
        plan = plan_hos(source, 0)
        # 1h pickup + 9h driving + 4h fuel = arrival at hour 14.
        self.assertEqual(plan["duty_events"][-1]["start_offset_seconds"], 14 * 3600)
        self.assertEqual(plan["summary"]["planned_elapsed_seconds"], 15 * 3600)
        self.assertEqual(plan["summary"]["daily_rest_count"], 0)
        self.check_invariants(plan, source)

    def test_fuel_at_pickup_merges_stationary_stop(self):
        source = route((8, 1), (1000, 100))
        plan = plan_hos(source, 0)
        stop = next(s for s in plan["stops"] if "PICKUP" in s["kinds"])
        self.assertIn("FUEL", stop["kinds"])
        self.assertEqual(stop["duration_seconds"], 5400)
        self.assertEqual(len(stop["duty_event_ids"]), 2)
        self.assertEqual(plan["summary"]["required_break_count"], 0)
        self.check_invariants(plan, source)

    def test_fractional_fuel_boundaries_match_cycle_preflight(self):
        for miles in ((999.99999995, .00000003), (1000.00000005, 0),
                      (999.99999995, 1000.00000005), (1000.0001, 1000.0001)):
            source = route((5, 5), miles)
            required = plan_hos(source, 0)["summary"]["cycle_work_required_seconds"]
            used = 70 - required / 3600
            with self.subTest(miles=miles):
                self.check_invariants(plan_hos(source, used), source, used)

    def test_deterministic_schedule_matrix(self):
        from random import Random
        from trips.services.daily_logs import build_daily_logs
        random = Random(6)
        for case in range(200):
            hours = (random.uniform(.01, 28), random.uniform(.01, 28))
            source = route(hours, tuple(h * random.uniform(10, 100) for h in hours))
            used = random.choice((0, 5, 15, 65, 70))
            plan = plan_hos(source, used)
            with self.subTest(case=case):
                if plan["hos"]["status"] == "COMPLIANT_PLAN":
                    self.check_invariants(plan, source, used)
                    logs = build_daily_logs(plan["duty_events"])
                    for log in logs:
                        self.assertAlmostEqual(sum(log["totals_seconds"].values()), 86400)
                    self.assertAlmostEqual(sum(log["distance_miles"] for log in logs), source["distance_miles"])
                else:
                    self.assertEqual(plan["duty_events"], [])
                    self.assertEqual(plan["stops"], [])
                    self.assertGreater(plan["summary"]["cycle_work_required_seconds"], (70-used)*3600)
