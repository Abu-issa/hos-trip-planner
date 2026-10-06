import json
import os
import subprocess
import sys

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient


class DeploymentTests(SimpleTestCase):
    def test_production_defaults_and_required_secret(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("DJANGO_")}
        env["DJANGO_DEBUG"] = "false"
        result = subprocess.run([sys.executable, "-c", "import config.settings"], env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set DJANGO_SECRET_KEY", result.stderr)
        env["DJANGO_SECRET_KEY"] = "test-only-not-a-deployment-secret"
        script = "import json; from config import settings as s; print(json.dumps([s.DEBUG, s.SECURE_SSL_REDIRECT, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.SECURE_PROXY_SSL_HEADER, s.SECURE_HSTS_SECONDS, s.SECURE_HSTS_INCLUDE_SUBDOMAINS, s.SECURE_HSTS_PRELOAD]))"
        result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), [False, True, True, True, None, 0, False, False])

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["api.example.com"], SECURE_SSL_REDIRECT=True,
                       SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
                       CORS_ALLOWED_ORIGINS=["https://app.example.com"], SECURE_HSTS_SECONDS=3600)
    def test_trusted_proxy_health_and_cors(self):
        client = APIClient()
        response = client.get("/api/health/", HTTP_HOST="api.example.com", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Strict-Transport-Security"], "max-age=3600")
        response = client.options("/api/trips/plan/", HTTP_HOST="api.example.com",
                                  HTTP_X_FORWARDED_PROTO="https", HTTP_ORIGIN="https://app.example.com",
                                  HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
                                  HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "https://app.example.com")

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["api.example.com"], SECURE_SSL_REDIRECT=True,
                       SECURE_PROXY_SSL_HEADER=None)
    def test_untrusted_forwarded_header_does_not_bypass_redirect(self):
        response = APIClient().get("/api/health/", HTTP_HOST="api.example.com", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://api.example.com/api/health/")

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["api.example.com"], SECURE_SSL_REDIRECT=True)
    def test_unknown_host_is_rejected(self):
        response = APIClient().get("/api/health/", HTTP_HOST="unapproved.example")
        self.assertEqual(response.status_code, 400)
