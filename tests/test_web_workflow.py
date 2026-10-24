
import json

from django.test import TestCase, override_settings
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

    def post_datasets(self, baseline=None, degraded=None):
        return self.client.post(
            self.url,
            {
                "baseline_json": json.dumps(
                    self.baseline if baseline is None else baseline
                ),
                "degraded_json": json.dumps(
                    self.degraded if degraded is None else degraded
                ),
            },
        )

    def test_homepage_displays_comparison_form(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Baseline dataset")
        self.assertContains(response, "Degraded dataset")
        self.assertContains(response, "Compare datasets")

    def test_valid_datasets_return_ranked_results(self):
        response = self.post_datasets()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(response.context["matched_operation_count"], 2)
        self.assertEqual(response.context["regression_count"], 2)
        self.assertContains(response, "payment")
        self.assertContains(response, "Evidence is not proof")

    def test_summary_displays_trace_counts_not_span_counts(self):
        response = self.post_datasets()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Baseline / degraded traces")
        self.assertContains(response, "1 / 1")

    def test_results_display_operation_sample_counts(self):
        response = self.post_datasets()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 / 1")

        results = response.context["results"]
        self.assertEqual(len(results), 2)

        for item in results:
            self.assertEqual(item["baseline_samples"], 1)
            self.assertEqual(item["degraded_samples"], 1)

    def test_multiple_traces_are_counted_and_samples_are_aggregated(self):
        baseline = {
            "traces": [
                {
                    "trace_id": "baseline-1",
                    "spans": [
                        {
                            "span_id": "span-1",
                            "parent_span_id": None,
                            "service_name": "payment",
                            "operation_name": "authorize",
                            "start_time_ns": 0,
                            "end_time_ns": 100_000_000,
                        }
                    ],
                },
                {
                    "trace_id": "baseline-2",
                    "spans": [
                        {
                            "span_id": "span-2",
                            "parent_span_id": None,
                            "service_name": "payment",
                            "operation_name": "authorize",
                            "start_time_ns": 0,
                            "end_time_ns": 200_000_000,
                        }
                    ],
                },
            ]
        }

        degraded = {
            "traces": [
                {
                    "trace_id": "degraded-1",
                    "spans": [
                        {
                            "span_id": "span-3",
                            "parent_span_id": None,
                            "service_name": "payment",
                            "operation_name": "authorize",
                            "start_time_ns": 0,
                            "end_time_ns": 300_000_000,
                        }
                    ],
                },
                {
                    "trace_id": "degraded-2",
                    "spans": [
                        {
                            "span_id": "span-4",
                            "parent_span_id": None,
                            "service_name": "payment",
                            "operation_name": "authorize",
                            "start_time_ns": 0,
                            "end_time_ns": 500_000_000,
                        }
                    ],
                },
            ]
        }

        response = self.post_datasets(baseline, degraded)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(response.context["baseline_trace_count"], 2)
        self.assertEqual(response.context["degraded_trace_count"], 2)
        self.assertEqual(response.context["matched_operation_count"], 1)
        self.assertEqual(response.context["regression_count"], 1)

        result = response.context["results"][0]
        self.assertEqual(result["baseline_samples"], 2)
        self.assertEqual(result["degraded_samples"], 2)
        self.assertEqual(result["baseline_median_ns"], 150_000_000)
        self.assertEqual(result["degraded_median_ns"], 400_000_000)
        self.assertEqual(result["delta_ns"], 250_000_000)

        self.assertContains(response, "2 / 2")
        self.assertContains(response, "2 / 2")

    def test_improved_latency_is_displayed_as_negative_delta(self):
        baseline = {
            "traces": [
                {
                    "trace_id": "baseline-1",
                    "spans": [
                        {
                            "span_id": "span-1",
                            "parent_span_id": None,
                            "service_name": "payment",
                            "operation_name": "authorize",
                            "start_time_ns": 0,
                            "end_time_ns": 500_000_000,
                        }
                    ],
                }
            ]
        }

        degraded = {
            "traces": [
                {
                    "trace_id": "degraded-1",
                    "spans": [
                        {
                            "span_id": "span-2",
                            "parent_span_id": None,
                            "service_name": "payment",
                            "operation_name": "authorize",
                            "start_time_ns": 0,
                            "end_time_ns": 200_000_000,
                        }
                    ],
                }
            ]
        }

        response = self.post_datasets(baseline, degraded)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(response.context["regression_count"], 0)

        result = response.context["results"][0]
        self.assertEqual(result["delta_ns"], -300_000_000)
        self.assertFalse(result["is_regression_candidate"])
        self.assertEqual(result["delta_ms"], -300.0)

        self.assertContains(response, "-300.000 ms")

    def test_unmatched_operations_render_empty_state(self):
        baseline = {
            "traces": [
                {
                    "trace_id": "baseline-1",
                    "spans": [
                        {
                            "span_id": "span-1",
                            "parent_span_id": None,
                            "service_name": "checkout",
                            "operation_name": "old_operation",
                            "start_time_ns": 0,
                            "end_time_ns": 100_000_000,
                        }
                    ],
                }
            ]
        }

        degraded = {
            "traces": [
                {
                    "trace_id": "degraded-1",
                    "spans": [
                        {
                            "span_id": "span-2",
                            "parent_span_id": None,
                            "service_name": "payment",
                            "operation_name": "new_operation",
                            "start_time_ns": 0,
                            "end_time_ns": 200_000_000,
                        }
                    ],
                }
            ]
        }

        response = self.post_datasets(baseline, degraded)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(response.context["matched_operation_count"], 0)
        self.assertEqual(response.context["regression_count"], 0)
        self.assertEqual(response.context["results"], [])
        self.assertContains(response, "No matched operations found.")

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

        response = self.post_datasets(empty_dataset, empty_dataset)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(response.context["matched_operation_count"], 0)
        self.assertContains(response, "No matched operations found.")

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1024)
    def test_oversized_request_returns_controlled_error(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": json.dumps(
                    {"traces": [], "padding": "x" * 2048}
                ),
                "degraded_json": json.dumps(self.degraded),
            },
        )

        self.assertEqual(response.status_code, 413)
        self.assertFalse(response.context["analysis_completed"])
        self.assertIn(
            "The submitted request is too large. "
            "Reduce the dataset sizes and try again.",
            response.context["errors"],
        )
        self.assertContains(
            response,
            "The submitted request is too large.",
            status_code=413,
        )
