
import json
from datetime import datetime

from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError
from django.shortcuts import render
from django.utils import timezone

from causality.evidence_reporting import attach_evidence_reporting
from causality.trace_analysis import (
    parse_traces,
    rank_execution_aware_regressions,
)
from webapp.jaeger_client import JaegerError, fetch_traces
from webapp.models import ComparisonRun


MAX_DATASET_BYTES = 1_048_576

EXAMPLE_BASELINE = {
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
                    "end_time_ns": 300_000_000,
                },
                {
                    "span_id": "payment",
                    "parent_span_id": "root",
                    "service_name": "payment",
                    "operation_name": "authorize",
                    "start_time_ns": 50_000_000,
                    "end_time_ns": 100_000_000,
                },
            ],
        }
    ]
}

EXAMPLE_DEGRADED = {
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
                    "end_time_ns": 800_000_000,
                },
                {
                    "span_id": "payment",
                    "parent_span_id": "root",
                    "service_name": "payment",
                    "operation_name": "authorize",
                    "start_time_ns": 50_000_000,
                    "end_time_ns": 600_000_000,
                },
            ],
        }
    ]
}


def _decode_json(raw_json, label):
    if not isinstance(raw_json, str):
        raise ValueError(f"{label}: provide a JSON dataset.")

    # Check the size before checking whether the content is empty.
    # This ensures oversized whitespace-only input is rejected by size.
    if len(raw_json.encode("utf-8")) > MAX_DATASET_BYTES:
        raise ValueError(
            f"{label}: dataset exceeds the 1 MiB size limit."
        )

    if not raw_json.strip():
        raise ValueError(f"{label}: provide a JSON dataset.")

    try:
        return json.loads(raw_json)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(
            f"{label}: invalid JSON; it may be invalid or excessively nested JSON."
        ) from exc


def _validate_dataset(data, label):
    try:
        return parse_traces(data)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc
    except RecursionError as exc:
        raise ValueError(
            f"{label}: dataset is excessively nested."
        ) from exc


def _read_uploaded_json(upload, label):
    if upload is None:
        raise ValueError(
            f"{label}: choose a JSON file to upload."
        )

    if not upload.name.lower().endswith(".json"):
        raise ValueError(
            f"{label}: upload a file with a .json extension."
        )

    if upload.size > MAX_DATASET_BYTES:
        raise ValueError(
            f"{label}: file exceeds the 1 MiB size limit."
        )

    try:
        raw = upload.read(MAX_DATASET_BYTES + 1)

        if len(raw) > MAX_DATASET_BYTES:
            raise ValueError(
                f"{label}: file exceeds the 1 MiB size limit."
            )

        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{label}: file must contain UTF-8 JSON."
        ) from exc

    data = _decode_json(text, label)
    return data, text


def _parse_datetime_local(value, label):
    if not value:
        raise ValueError(
            f"{label}: enter both Jaeger start and end times."
        )

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{label}: enter a valid date and time."
        ) from exc

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(
            parsed,
            timezone.get_current_timezone(),
        )

    return parsed


def _load_dataset(request, label, prefix, default_json):
    source = request.POST.get(
        f"{prefix}_source",
        "text",
    )

    if source == "text":
        raw_json = request.POST.get(
            f"{prefix}_json",
            default_json,
        )
        data = _decode_json(raw_json, label)

        return (
            _validate_dataset(data, label),
            data,
            raw_json,
        )

    if source == "file":
        upload = request.FILES.get(f"{prefix}_file")
        data, raw_json = _read_uploaded_json(upload, label)

        return (
            _validate_dataset(data, label),
            data,
            raw_json,
        )

    if source == "jaeger":
        service = request.POST.get(
            f"{prefix}_service",
            "",
        )

        start = _parse_datetime_local(
            request.POST.get(f"{prefix}_start", ""),
            label,
        )

        end = _parse_datetime_local(
            request.POST.get(f"{prefix}_end", ""),
            label,
        )

        limit = request.POST.get(
            f"{prefix}_limit",
            "20",
        )

        data = fetch_traces(
            service,
            start,
            end,
            limit,
        )
        raw_json = json.dumps(data, indent=2)

        return (
            _validate_dataset(data, label),
            data,
            raw_json,
        )

    raise ValueError(
        f"{label}: choose text, file, or Jaeger as the source."
    )


def _count_traces(spans):
    return len({span.trace_id for span in spans})


def _base_context():
    return {
        "baseline_json": json.dumps(
            EXAMPLE_BASELINE,
            indent=2,
        ),
        "degraded_json": json.dumps(
            EXAMPLE_DEGRADED,
            indent=2,
        ),
        "errors": [],
        "results": [],
        "analysis_completed": False,
        "baseline_trace_count": 0,
        "degraded_trace_count": 0,
        "matched_operation_count": 0,
        "regression_count": 0,
        "saved_comparison_id": None,
        "baseline_source": "text",
        "degraded_source": "text",
    }


def compare_traces(request):
    context = _base_context()

    if request.method != "POST":
        return render(
            request,
            "causality/compare.html",
            context,
        )

    try:
        # Django may raise RequestDataTooBig while parsing POST or FILES.
        baseline_source = request.POST.get(
            "baseline_source",
            "text",
        )
        degraded_source = request.POST.get(
            "degraded_source",
            "text",
        )

        context["baseline_source"] = baseline_source
        context["degraded_source"] = degraded_source

        baseline_spans, baseline_data, baseline_json = (
            _load_dataset(
                request,
                "Baseline dataset",
                "baseline",
                context["baseline_json"],
            )
        )

        degraded_spans, degraded_data, degraded_json = (
            _load_dataset(
                request,
                "Degraded dataset",
                "degraded",
                context["degraded_json"],
            )
        )

    except RequestDataTooBig:
        context["errors"].append(
            "The submitted request is too large. "
            "Reduce the dataset sizes and try again."
        )

        return render(
            request,
            "causality/compare.html",
            context,
            status=413,
        )

    except (ValueError, JaegerError) as exc:
        context["errors"].append(str(exc))

        context["baseline_json"] = request.POST.get(
            "baseline_json",
            context["baseline_json"],
        )
        context["degraded_json"] = request.POST.get(
            "degraded_json",
            context["degraded_json"],
        )

        return render(
            request,
            "causality/compare.html",
            context,
        )

    context["baseline_json"] = baseline_json
    context["degraded_json"] = degraded_json

    try:
        ranked = rank_execution_aware_regressions(
            baseline_spans,
            degraded_spans,
        )

        reported = attach_evidence_reporting(ranked)

    except (ValueError, TypeError, KeyError):
        context["errors"].append(
            "The datasets could not be analyzed. "
            "Check their structure and try again."
        )

        return render(
            request,
            "causality/compare.html",
            context,
        )

    results = []

    for item in reported:
        result = dict(item)

        result["baseline_median_ms"] = (
            item["baseline_median_ns"] / 1_000_000
        )
        result["degraded_median_ms"] = (
            item["degraded_median_ns"] / 1_000_000
        )
        result["delta_ms"] = (
            item["delta_ns"] / 1_000_000
        )
        result["evidence_label"] = (
            item["evidence_classification"]
            .replace("_", " ")
            .title()
        )

        results.append(result)

    baseline_trace_count = _count_traces(baseline_spans)
    degraded_trace_count = _count_traces(degraded_spans)
    matched_operation_count = len(results)

    regression_count = sum(
        1
        for item in results
        if item["is_regression_candidate"]
    )

    try:
        saved_run = ComparisonRun.objects.create(
            baseline_trace_count=baseline_trace_count,
            degraded_trace_count=degraded_trace_count,
            matched_operation_count=matched_operation_count,
            regression_count=regression_count,
            baseline_dataset=baseline_data,
            degraded_dataset=degraded_data,
            results=results,
        )

    except (DatabaseError, ValueError, TypeError):
        context["errors"].append(
            "The comparison was analyzed but could not be saved. "
            "Check the database configuration and try again."
        )

        return render(
            request,
            "causality/compare.html",
            context,
        )

    context.update(
        {
            "results": results,
            "analysis_completed": True,
            "baseline_trace_count": baseline_trace_count,
            "degraded_trace_count": degraded_trace_count,
            "matched_operation_count": matched_operation_count,
            "regression_count": regression_count,
            "saved_comparison_id": saved_run.pk,
        }
    )

    return render(
        request,
        "causality/compare.html",
        context,
    )
