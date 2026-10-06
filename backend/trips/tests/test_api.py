import json
import requests
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIClient
from .test_services import GEOCODE, provider_fixture, response


class TripAPITests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.provider = self.enterContext(patch("trips.services.providers.requests.get", side_effect=provider_fixture))
        self.enterContext(patch("trips.services.geocoding.time.sleep"))
        self.client = APIClient()
        self.body = {
            "current_location": "Chicago, IL",
            "pickup_location": "Indianapolis, IN",
            "dropoff_location": "Dallas, TX",
            "current_cycle_used": 15,
        }

    def post(self, body):
        return self.client.post("/api/trips/plan/", body, format="json")

    def test_health(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_valid_request_and_trimming(self):
        response = self.post({**self.body, "current_location": "  Chicago, IL  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["input"], self.body)
        self.assertEqual(response.json()["route"]["distance_miles"], 2)
        self.assertEqual(response.json()["summary"]["estimated_driving_hours"], 2)
        self.assertEqual(response.json()["summary"]["remaining_cycle_hours"], 55)
        self.assertEqual(len(response.json()["locations"]), 3)
        self.assertEqual(self.provider.call_count, 5)
        self.assertEqual(response.json()["hos"]["status"], "COMPLIANT_PLAN")
        self.assertEqual(len(response.json()["route"]["legs"]), 2)
        self.assertTrue(response.json()["duty_events"])
        self.assertTrue(response.json()["stops"])
        self.assertEqual(response.json()["summary"]["daily_log_count"], 1)
        self.assertEqual(sum(response.json()["daily_logs"][0]["totals_seconds"].values()), 86400)

    def test_insufficient_cycle_returns_route_without_fake_schedule(self):
        result = self.post({**self.body, "current_cycle_used": 69})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["hos"]["status"], "INSUFFICIENT_CYCLE_HOURS")
        self.assertEqual(result.json()["duty_events"], [])
        self.assertEqual(result.json()["daily_logs"], [])
        self.assertEqual(result.json()["summary"]["daily_log_count"], 0)
        self.assertEqual(len(result.json()["route"]["legs"]), 2)

    def test_unresolved_pickup(self):
        self.provider.side_effect = [response(GEOCODE), response([])]
        result = self.post(self.body)
        self.assertEqual(result.status_code, 422)
        self.assertEqual(result.json()["error"]["code"], "LOCATION_NOT_FOUND")
        self.assertIn("pickup_location", result.json()["error"]["fields"])
        self.assertEqual(self.provider.call_count, 2)

    def test_multiday_log_integration(self):
        from .test_hos_engine import route
        for hours, miles, used, count in (((3.613083333333333, 15.84338888888889), (180.743, 899.603), 15, 2), ((10.542, 39.5267777778), (534.518, 2245.315), 0, 4)):
            with self.subTest(hours=hours), patch("trips.services.trip_planner.build_route", return_value=route(hours, miles)):
                result = self.post({**self.body, "current_cycle_used": used})
                self.assertEqual(result.status_code, 200)
                data = result.json()
                self.assertEqual(data["summary"]["daily_log_count"], count)
                self.assertEqual(len(data["daily_logs"]), count)
                for log in data["daily_logs"]:
                    self.assertAlmostEqual(sum(log["totals_seconds"].values()), 86400)
                self.assertAlmostEqual(sum(log["distance_miles"] for log in data["daily_logs"]), sum(miles))

    def test_cycle_boundaries_and_fraction(self):
        for value in (0, 69.5, 70):
            with self.subTest(value=value):
                response = self.post({**self.body, "current_cycle_used": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["input"]["current_cycle_used"], value)

    def test_invalid_cycle_values(self):
        for value in (-1, 71, "abc", "15", None, True):
            with self.subTest(value=value):
                response = self.post({**self.body, "current_cycle_used": value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("current_cycle_used", response.json())

    def test_nonfinite_json(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(value=value):
                body = json.dumps({**self.body, "current_cycle_used": 0}).replace(
                    '"current_cycle_used": 0', '"current_cycle_used": ' + value,
                )
                response = self.client.post(
                    "/api/trips/plan/", body,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)

    def test_missing_fields(self):
        for field in self.body:
            with self.subTest(field=field):
                response = self.post({k: v for k, v in self.body.items() if k != field})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_invalid_locations(self):
        for field in ("current_location", "pickup_location", "dropoff_location"):
            for value in ("", "   ", None, 123, "x" * 256):
                with self.subTest(field=field, value=value):
                    response = self.post({**self.body, field: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.json())

    def test_extra_fields_rejected(self):
        response = self.post({**self.body, "extra": "unexpected"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("extra", response.json())

    def test_cors_preflight(self):
        response = self.client.options(
            "/api/trips/plan/", HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:5173")

    def test_provider_errors_are_sanitized_end_to_end(self):
        for exception, status, code in (
            (requests.Timeout("private upstream detail"), 504, "PROVIDER_TIMEOUT"),
            (requests.ConnectionError("private upstream detail"), 502, "PROVIDER_UNAVAILABLE"),
        ):
            with self.subTest(status=status):
                cache.clear()
                self.provider.side_effect = exception
                result = self.post(self.body)
                self.assertEqual(result.status_code, status)
                self.assertEqual(result.json()["error"]["code"], code)
                self.assertNotIn("private upstream detail", result.content.decode())
        self.provider.side_effect = None
        self.provider.return_value = response({"upstream": "private upstream detail"})
        result = self.post(self.body)
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json()["error"]["code"], "INVALID_PROVIDER_RESPONSE")
        self.assertNotIn("private upstream detail", result.content.decode())

    def test_malformed_json_and_unapproved_origin(self):
        result = self.client.post("/api/trips/plan/", '{"broken":', content_type="application/json")
        self.assertEqual(result.status_code, 400)
        self.assertIn("detail", result.json())
        result = self.client.options("/api/trips/plan/", HTTP_ORIGIN="https://unapproved.example",
                                     HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        self.assertNotIn("Access-Control-Allow-Origin", result)
