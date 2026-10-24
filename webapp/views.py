import json

from django.shortcuts import render

from causality.evidence_reporting import attach_evidence_reporting
from causality.trace_analysis import (
    parse_traces,
    rank_execution_aware_regressions,
)


EXAMPLE_BASELINE = json.dumps(
    {
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
    },
    indent=2,
)

EXAMPLE_DEGRADED = json.dumps(
    {
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
    },
    indent=2,
)


def _parse_dataset(raw_json: str, label: str):
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label}: invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}."
        ) from exc

    try:
        spans = parse_traces(data)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc

    return spans


def compare_traces(request):
    context = {
        "baseline_json": EXAMPLE_BASELINE,
        "degraded_json": EXAMPLE_DEGRADED,
        "analysis_completed": False,
        "results": [],
        "errors": [],
    }

    if request.method != "POST":
        return render(request, "causality/compare.html", context)

    baseline_json = request.POST.get("baseline_json", "")
    degraded_json = request.POST.get("degraded_json", "")

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

    ranked = rank_execution_aware_regressions(
        baseline_spans,
        degraded_spans,
    )
    reported = attach_evidence_reporting(ranked)

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

    context.update(
        {
            "analysis_completed": True,
            "results": results,
            "baseline_span_count": len(baseline_spans),
            "degraded_span_count": len(degraded_spans),
            "matched_operation_count": len(results),
            "regression_count": sum(
                item["delta_ns"] > 0 for item in results
            ),
        }
    )

    return render(request, "causality/compare.html", context)