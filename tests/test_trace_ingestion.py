
import json
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from webapp.jaeger_client import JaegerError, fetch_traces
from webapp.models import ComparisonRun


BASELINE = {
    "traces": [
        {
            "trace_id": "baseline-1",
            "spans": [
                {
                    "span_id": "root",
                    "parent_span_id": None,
                    "service_name": "checkout",
                    "operation_name": "POST /checkout",
                    "start_time_ns": 0,
                    "end_time_ns": 100_000_000,
                }
            ],
        }
    ]
}

DEGRADED = {
    "traces": [
        {
            "trace_id": "degraded-1",
            "spans": [
                {
                    "span_id": "root",
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


class TraceFileUploadTests(TestCase):
    def test_valid_baseline_file_is_compared_and_saved(self):
        baseline_file = SimpleUploadedFile(
            "baseline.json",
            json.dumps(BASELINE).encode("utf-8"),
            content_type="application/json",
        )

        response = self.client.post(
            "/",
            {
                "baseline_source": "file",
                "baseline_file": baseline_file,
                "degraded_source": "text",
                "degraded_json": json.dumps(DEGRADED),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["analysis_completed"])
        self.assertEqual(ComparisonRun.objects.count(), 1)

    def test_non_json_extension_is_rejected(self):
        baseline_file = SimpleUploadedFile(
            "baseline.txt",
            json.dumps(BASELINE).encode("utf-8"),
            content_type="text/plain",
        )

        response = self.client.post(
            "/",
            {
                "baseline_source": "file",
                "baseline_file": baseline_file,
                "degraded_source": "text",
                "degraded_json": json.dumps(DEGRADED),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["analysis_completed"])
        self.assertContains(response, ".json extension")
        self.assertEqual(ComparisonRun.objects.count(), 0)

    def test_oversized_json_file_is_rejected(self):
        large_content = (
            b'{"traces":[]}' + b" " * (1_048_576 - len(b'{"traces":[]}') + 1)
        )
        upload = SimpleUploadedFile(
            "large.json",
            large_content,
            content_type="application/json",
        )

        response = self.client.post(
            "/",
            {
                "baseline_source": "file",
                "baseline_file": upload,
                "degraded_source": "text",
                "degraded_json": json.dumps(DEGRADED),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["analysis_completed"])
        self.assertContains(response, "1 MiB size limit")
        self.assertEqual(ComparisonRun.objects.count(), 0)

    def test_invalid_json_file_is_rejected(self):
        upload = SimpleUploadedFile(
            "baseline.json",
            b"{invalid json",
            content_type="application/json",
        )

        response = self.client.post(
            "/",
            {
                "baseline_source": "file",
                "baseline_file": upload,
                "degraded_source": "text",
                "degraded_json": json.dumps(DEGRADED),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["analysis_completed"])
        self.assertContains(response, "invalid JSON")
        self.assertEqual(ComparisonRun.objects.count(), 0)


class JaegerClientTests(TestCase):
    @override_settings(USE_TZ=True, TIME_ZONE="UTC")
    @patch("webapp.jaeger_client._get_json")
    def test_legacy_jaeger_trace_is_converted(self, mock_get_json):
        mock_get_json.return_value = {
            "data": [
                {
                    "traceID": "abc123",
                    "spans": [
                        {
                            "traceID": "abc123",
                            "spanID": "span1",
                            "operationName": "GET /items",
                            "startTime": 1_000_000,
                            "duration": 500_000,
                            "processID": "p1",
                            "references": [],
                        }
                    ],
                    "processes": {
                        "p1": {"serviceName": "inventory"}
                    },
                }
            ]
        }

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)

        with patch.dict(
            "os.environ", {"JAEGER_QUERY_URL": "http://jaeger:16686"}
        ):
            result = fetch_traces("inventory", start, end, 10)

        span = result["traces"][0]["spans"][0]
        self.assertEqual(span["service_name"], "inventory")
        self.assertEqual(span["operation_name"], "GET /items")
        self.assertEqual(span["start_time_ns"], 1_000_000_000)
        self.assertEqual(span["end_time_ns"], 1_500_000_000)

        request_url = mock_get_json.call_args.args[0]
        parsed_query = parse_qs(urlparse(request_url).query)
        self.assertEqual(parsed_query["service"], ["inventory"])
        self.assertEqual(parsed_query["limit"], ["10"])

    def test_missing_jaeger_configuration_is_reported(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesMessage(JaegerError, "Jaeger is not configured"):
                fetch_traces("inventory", start, end)

    @patch("webapp.jaeger_client._get_json")
    def test_empty_jaeger_result_is_rejected(self, mock_get_json):
        mock_get_json.return_value = {"data": []}
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)

        with patch.dict(
            "os.environ", {"JAEGER_QUERY_URL": "http://jaeger:16686"}
        ):
            with self.assertRaisesMessage(
                JaegerError, "no usable spans"
            ):
                fetch_traces("inventory", start, end)
