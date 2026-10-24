import json

from django.test import TestCase, override_settings
from django.urls import reverse

from webapp.views import MAX_DATASET_BYTES


class TraceInputLimitTests(TestCase):
    def setUp(self):
        self.url = reverse("webapp:compare")
        self.valid_dataset = json.dumps({"traces": []})

    def test_empty_baseline_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": "",
                "degraded_json": self.valid_dataset,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                "provide a JSON dataset" in error
                for error in response.context["errors"]
            )
        )

    def test_empty_degraded_dataset_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": self.valid_dataset,
                "degraded_json": "   ",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                "provide a JSON dataset" in error
                for error in response.context["errors"]
            )
        )

    def test_dataset_over_size_limit_is_rejected(self):
        oversized = " " * (MAX_DATASET_BYTES + 1)

        response = self.client.post(
            self.url,
            {
                "baseline_json": oversized,
                "degraded_json": self.valid_dataset,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                "exceeds the 1 MiB size limit" in error
                for error in response.context["errors"]
            )
        )

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1024)
    def test_request_body_limit_is_enforced(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": " " * 2048,
                "degraded_json": self.valid_dataset,
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_malformed_json_returns_validation_message(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": "{invalid",
                "degraded_json": self.valid_dataset,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["analysis_completed"])
        self.assertTrue(
            any(
                "invalid or excessively nested JSON" in error
                for error in response.context["errors"]
            )
        )
