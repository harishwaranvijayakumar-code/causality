
import json

from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError
from django.shortcuts import render

from causality.evidence_reporting import attach_evidence_reporting
from causality.trace_analysis import (
    parse_traces,
    rank_execution_aware_regressions,
)
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


def _parse_dataset(raw_json: str, label: str):
    if len(raw_json.encode("utf-8")) > MAX_DATASET_BYTES:
        raise ValueError(
            f"{label}: dataset exceeds the 1 MiB size limit."
        )

    if not raw_json.strip():
        raise ValueError(f"{label}: provide a JSON dataset.")

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(
            f"{label}: invalid JSON; it may be invalid or excessively nested JSON."
        ) from exc

    try:
        return parse_traces(data)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc
    except RecursionError as exc:
        raise ValueError(
            f"{label}: dataset is excessively nested."
        ) from exc


def _count_traces(spans):
    return len({span.trace_id for span in spans})


def compare_traces(request):
    context = {
        "baseline_json": json.dumps(EXAMPLE_BASELINE, indent=2),
        "degraded_json": json.dumps(EXAMPLE_DEGRADED, indent=2),
        "errors": [],
        "results": [],
        "analysis_completed": False,
        "baseline_trace_count": 0,
        "degraded_trace_count": 0,
        "matched_operation_count": 0,
        "regression_count": 0,
        "saved_comparison_id": None,
    }

    if request.method != "POST":
        return render(request, "causality/compare.html", context)

    try:
        baseline_json = request.POST.get("baseline_json", "")
        degraded_json = request.POST.get("degraded_json", "")
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

    context["baseline_json"] = baseline_json
    context["degraded_json"] = degraded_json

    try:
        baseline_spans = _parse_dataset(
            baseline_json,
            "Baseline dataset",
        )
        degraded_spans = _parse_dataset(
            degraded_json,
            "Degraded dataset",
        )
    except ValueError as exc:
        context["errors"].append(str(exc))
        return render(request, "causality/compare.html", context)

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
        return render(request, "causality/compare.html", context)

    results = []

    for item in reported:
        result = dict(item)
        result["baseline_median_ms"] = (
            item["baseline_median_ns"] / 1_000_000
        )
        result["degraded_median_ms"] = (
            item["degraded_median_ns"] / 1_000_000
        )
        result["delta_ms"] = item["delta_ns"] / 1_000_000
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
            baseline_dataset=json.loads(baseline_json),
            degraded_dataset=json.loads(degraded_json),
            results=results,
        )
    except (DatabaseError, ValueError, TypeError):
        context["errors"].append(
            "The comparison was analyzed but could not be saved. "
            "Check the database configuration and try again."
        )
        return render(request, "causality/compare.html", context)

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

    return render(request, "causality/compare.html", context)
