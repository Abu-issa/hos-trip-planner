from copy import deepcopy
from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase

from trips.services.geocoding import geocode_location
from trips.services.providers import ProviderError
from trips.services.routing import build_route, route_leg

GEOCODE = [{"lat": "41.88", "lon": "-87.63", "display_name": "Chicago, Illinois, USA"}]
OSRM = {"code": "Ok", "routes": [{
    "distance": 1609.344, "duration": 3600,
    "geometry": {"type": "LineString", "coordinates": [[-87.63, 41.88], [-86.16, 39.77]]},
}]}


def response(data, status=200):
    result = Mock(status_code=status)
    result.json.return_value = data
    return result


def provider_fixture(url, **kwargs):
    return response(GEOCODE if "q" in kwargs.get("params", {}) else OSRM)


class ProviderTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.get = self.enterContext(patch("trips.services.providers.requests.get"))
        self.sleep = self.enterContext(patch("trips.services.geocoding.time.sleep"))
        self.start = {"latitude": 41.88, "longitude": -87.63}
        self.end = {"latitude": 39.77, "longitude": -86.16}

    def geocode(self):
        return geocode_location("Chicago, IL", "current_location")

    def route(self):
        return route_leg(self.start, self.end, "current", "pickup")

    def assert_provider_error(self, function, code, status):
        with self.assertRaises(ProviderError) as caught:
            function()
        self.assertEqual(caught.exception.payload["error"]["code"], code)
        self.assertEqual(caught.exception.status, status)
        return caught.exception

    def test_geocoding_and_cache(self):
        self.get.return_value = response(GEOCODE)
        location = self.geocode()
        self.assertEqual(location["latitude"], 41.88)
        self.assertEqual(location["longitude"], -87.63)
        self.assertEqual(location["input_text"], "Chicago, IL")
        self.assertEqual(self.get.call_args.kwargs["params"]["q"], "Chicago, IL")
        self.assertIn("User-Agent", self.get.call_args.kwargs["headers"])
        self.geocode()
        self.assertEqual(self.get.call_count, 1)

    def test_geocoding_not_found(self):
        self.get.return_value = response([])
        error = self.assert_provider_error(self.geocode, "LOCATION_NOT_FOUND", 422)
        self.assertIn("current_location", error.payload["error"]["fields"])

    def test_geocoder_timeout(self):
        self.get.side_effect = requests.Timeout()
        self.assert_provider_error(self.geocode, "PROVIDER_TIMEOUT", 504)

    def test_routing_and_miles_conversion(self):
        self.get.return_value = response(OSRM)
        leg = self.route()
        self.assertEqual(leg["distance_miles"], 1)
        self.assertEqual(leg["duration_seconds"], 3600)
        self.assertEqual(leg["id"], "current_to_pickup")
        self.assertIn("-87.63,41.88;-86.16,39.77", self.get.call_args.args[0])
        self.assertEqual(leg["geometry"]["coordinates"][0], [-87.63, 41.88])
        self.assertEqual(self.get.call_args.kwargs["params"]["geometries"], "geojson")

    def test_no_route(self):
        for code in ("NoRoute", "NoSegment"):
            for status in (200, 400):
                with self.subTest(code=code, status=status):
                    self.get.return_value = response({"code": code}, status)
                    self.assert_provider_error(self.route, "NO_ROUTE_FOUND", 422)

    def test_routing_timeout(self):
        self.get.side_effect = requests.Timeout()
        self.assert_provider_error(self.route, "PROVIDER_TIMEOUT", 504)

    def test_two_leg_totals(self):
        second = deepcopy(OSRM)
        second["routes"][0].update(distance=3218.688, duration=7200)
        self.get.side_effect = [response(OSRM), response(second)]
        route = build_route({"current": self.start, "pickup": self.end, "dropoff": self.start})
        self.assertEqual(route["distance_miles"], 3)
        self.assertEqual(route["estimated_driving_seconds"], 10800)
        self.assertEqual([leg["id"] for leg in route["legs"]], ["current_to_pickup", "pickup_to_dropoff"])
        self.assertEqual(self.get.call_count, 2)

    def test_connection_and_http_errors(self):
        for function in (self.geocode, self.route):
            with self.subTest(function=function.__name__):
                self.get.side_effect = requests.ConnectionError("private provider detail")
                self.assert_provider_error(function, "PROVIDER_UNAVAILABLE", 502)
                self.get.side_effect = None
                self.get.return_value = response({})
                self.get.return_value.raise_for_status.side_effect = requests.HTTPError()
                self.assert_provider_error(function, "PROVIDER_UNAVAILABLE", 502)

    def test_invalid_json(self):
        for function in (self.geocode, self.route):
            with self.subTest(function=function.__name__):
                self.get.return_value = response(None)
                self.get.return_value.json.side_effect = ValueError("not JSON")
                self.assert_provider_error(function, "INVALID_PROVIDER_RESPONSE", 502)

    def test_malformed_geocoder_schema(self):
        for data in ({}, [None], [{"lat": "NaN", "lon": 0, "display_name": "Bad"}], [{"lat": 91, "lon": 0, "display_name": "Bad"}]):
            with self.subTest(data=data):
                self.get.return_value = response(data)
                self.assert_provider_error(self.geocode, "INVALID_PROVIDER_RESPONSE", 502)

    def test_malformed_route_schema(self):
        bad_number = deepcopy(OSRM)
        bad_number["routes"][0]["duration"] = float("inf")
        bad_geometry = deepcopy(OSRM)
        bad_geometry["routes"][0]["geometry"]["coordinates"] = [[-87, 150], [-86, 39]]
        for data in (None, {}, {"code": "Ok", "routes": []}, bad_number, bad_geometry):
            with self.subTest(data=data):
                self.get.return_value = response(data)
                self.assert_provider_error(self.route, "INVALID_PROVIDER_RESPONSE", 502)

    def test_geocoder_spacing(self):
        self.get.return_value = response(GEOCODE)
        with patch("trips.services.geocoding._last_request", 100), patch("trips.services.geocoding.time.monotonic", return_value=100.2):
            self.geocode()
        self.assertAlmostEqual(self.sleep.call_args.args[0], 0.9)

    def test_positive_distance_requires_time(self):
        data = deepcopy(OSRM)
        data["routes"][0]["duration"] = 0
        self.get.return_value = response(data)
        self.assert_provider_error(self.route, "INVALID_PROVIDER_RESPONSE", 502)
        data["routes"][0]["distance"] = 0
        self.assertEqual(self.route()["duration_seconds"], 0)

    def test_http_400_cannot_report_success(self):
        self.get.return_value = response(OSRM, 400)
        self.assert_provider_error(self.route, "INVALID_PROVIDER_RESPONSE", 502)
