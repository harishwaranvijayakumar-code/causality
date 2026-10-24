
import json

from django.test import TestCase
from django.urls import reverse

from webapp.models import ComparisonRun


class ComparisonPersistenceTests(TestCase):
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
                        }
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
                        }
                    ],
                }
            ]
        }

    def submit(self, baseline=None, degraded=None):
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

    def test_successful_comparison_is_persisted(self):
        response = self.submit()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(ComparisonRun.objects.count(), 1)

        run = ComparisonRun.objects.get()
        self.assertEqual(run.baseline_trace_count, 1)
        self.assertEqual(run.degraded_trace_count, 1)
        self.assertEqual(run.matched_operation_count, 1)
        self.assertEqual(run.regression_count, 1)
        self.assertEqual(run.baseline_dataset, self.baseline)
        self.assertEqual(run.degraded_dataset, self.degraded)
        self.assertEqual(len(run.results), 1)

        self.assertEqual(
            response.context["saved_comparison_id"],
            run.pk,
        )

    def test_invalid_json_does_not_create_a_record(self):
        response = self.client.post(
            self.url,
            {
                "baseline_json": "{invalid",
                "degraded_json": json.dumps(self.degraded),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["analysis_completed"])
        self.assertEqual(ComparisonRun.objects.count(), 0)

    def test_empty_valid_datasets_are_persisted(self):
        empty_dataset = {"traces": []}

        response = self.submit(empty_dataset, empty_dataset)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(ComparisonRun.objects.count(), 1)

        run = ComparisonRun.objects.get()
        self.assertEqual(run.matched_operation_count, 0)
        self.assertEqual(run.regression_count, 0)
        self.assertEqual(run.results, [])

    def test_each_successful_submission_creates_a_separate_record(self):
        self.submit()
        self.submit()

        self.assertEqual(ComparisonRun.objects.count(), 2)
