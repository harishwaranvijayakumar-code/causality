import json

from django.test import TestCase
from django.urls import reverse


class TraceComparisonWorkflowTests(TestCase):
    def setUp(self):
        self.url = reverse("webapp:compare")

        self.baseline = {
            "traces": [
                {
                    "trace_id": "baseline-1",
                    "spans": [
                        {
                            "span_id": "root-1",
                            "parent_span_id": None,
                            "service_name": "checkout",
                            "operation_name": "POST /checkout",
                            "start_time_ns": 0,
                            "end_time_ns": 300_000_000,
                        },
                        {
                            "span_id": "payment-1",
                            "parent_span_id": "root-1",
                            "service_name": "payment",
                            "operation_name": "charge",
                            "start_time_ns": 100_000_000,
                            "end_time_ns": 200_000_000,
                        },
                    ],
                }
            ]
        }

        self.degraded = {
            "traces": [
                {
                    "trace_id": "degraded-1",
                    "spans": [
                        {
                            "span_id": "root-1",
                            "parent_span_id": None,
                            "service_name": "checkout",
                            "operation_name": "POST /checkout",
                            "start_time_ns": 0,
                            "end_time_ns": 800_000_000,
                        },
                        {
                            "span_id": "payment-1",
                            "parent_span_id": "root-1",
                            "service_name": "payment",
                            "operation_name": "charge",
                            "start_time_ns": 100_000_000,
                            "end_time_ns": 700_000_000,
                        },
                    ],
                }
            ]
        }

    def test_homepage_displays_comparison_form(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Baseline dataset")
        self.assertContains(response, "Degraded dataset")
        self.assertContains(response, "Compare datasets")

    def test_valid_datasets_return_ranked_results(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": json.dumps(self.baseline),
                "degraded_json": json.dumps(self.degraded),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(response.context["matched_operation_count"], 2)
        self.assertEqual(response.context["regression_count"], 2)
        self.assertContains(response, "payment")
        self.assertContains(response, "Evidence is not proof")

    def test_invalid_json_shows_validation_error(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": "{not valid json",
                "degraded_json": json.dumps(self.degraded),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["analysis_completed"])
        self.assertTrue(
            any(
                "invalid JSON" in error
                for error in response.context["errors"]
            )
        )

    def test_invalid_trace_structure_shows_validation_error(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": json.dumps({"wrong_key": []}),
                "degraded_json": json.dumps(self.degraded),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["analysis_completed"])
        self.assertIn(
            "'traces' must be a list.",
            response.context["errors"][0],
        )

    def test_empty_datasets_show_empty_state(self):
        empty_dataset = {"traces": []}

        response = self.client.post(
            self.url,
            {
                "baseline_json": json.dumps(empty_dataset),
                "degraded_json": json.dumps(empty_dataset),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(response.context["matched_operation_count"], 0)
        self.assertContains(response, "No matched operations found.")
