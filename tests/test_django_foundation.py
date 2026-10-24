from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok"},
        )
        self.assertEqual(
            response.headers["Content-Type"],
            "application/json",
        )

    def test_health_endpoint_accepts_get_requests(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
