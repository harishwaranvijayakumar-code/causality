
from causality.trace_analysis import (
    parse_traces,
    rank_execution_aware_regressions,
    rank_latency_regressions,
)


def make_dataset(
    root_duration_ns: int,
    child_duration_ns: int | None = None,
    *,
    root_operation: str = "request",
    child_operation: str = "authorize",
    child_service: str = "payment",
) -> dict:
    spans = [
        {
            "span_id": "root",
            "parent_span_id": None,
            "service_name": "checkout",
            "operation_name": root_operation,
            "start_time_ns": 0,
            "end_time_ns": root_duration_ns,
        }
    ]

    if child_duration_ns is not None:
        spans.append(
            {
                "span_id": "child",
                "parent_span_id": "root",
                "service_name": child_service,
                "operation_name": child_operation,
                "start_time_ns": 0,
                "end_time_ns": child_duration_ns,
            }
        )

    return {
        "traces": [
            {
                "trace_id": "trace-1",
                "spans": spans,
            }
        ]
    }


def parsed(dataset: dict):
    return parse_traces(dataset)


def test_no_matching_operations_returns_empty_results():
    baseline = parsed(
        make_dataset(
            100,
            root_operation="old_request",
        )
    )
    degraded = parsed(
        make_dataset(
            200,
            root_operation="new_request",
        )
    )

    results = rank_latency_regressions(baseline, degraded)

    assert results == []


def test_unchanged_latency_is_not_a_regression_candidate():
    baseline = parsed(make_dataset(100))
    degraded = parsed(make_dataset(100))

    results = rank_latency_regressions(baseline, degraded)

    assert len(results) == 1
    assert results[0]["delta_ns"] == 0
    assert results[0]["is_regression_candidate"] is False


def test_improved_latency_is_not_a_regression_candidate():
    baseline = parsed(make_dataset(200))
    degraded = parsed(make_dataset(100))

    results = rank_latency_regressions(baseline, degraded)

    assert len(results) == 1
    assert results[0]["delta_ns"] == -100
    assert results[0]["is_regression_candidate"] is False


def test_parent_regression_is_discounted_when_child_increase_accounts_for_it():
    baseline = parsed(
        make_dataset(
            root_duration_ns=100,
            child_duration_ns=10,
        )
    )
    degraded = parsed(
        make_dataset(
            root_duration_ns=600,
            child_duration_ns=510,
        )
    )

    results = rank_execution_aware_regressions(
        baseline,
        degraded,
    )

    by_operation = {
        item["operation_name"]: item
        for item in results
    }

    parent = by_operation["request"]
    child = by_operation["authorize"]

    assert parent["delta_ns"] == 500
    assert child["delta_ns"] == 500

    assert parent["discounted_as_parent_symptom"] is True
    assert parent["adjusted_delta_ns"] == 0

    assert child["discounted_as_parent_symptom"] is False
    assert child["adjusted_delta_ns"] == 500


def test_parent_without_descendant_regression_keeps_its_increase():
    baseline = parsed(
        make_dataset(
            root_duration_ns=100,
            child_duration_ns=50,
        )
    )
    degraded = parsed(
        make_dataset(
            root_duration_ns=600,
            child_duration_ns=50,
        )
    )

    results = rank_execution_aware_regressions(
        baseline,
        degraded,
    )

    parent = next(
        item for item in results
        if item["operation_name"] == "request"
    )

    assert parent["delta_ns"] == 500
    assert parent["descendant_regression_evidence_ns"] == 0
    assert parent["discounted_as_parent_symptom"] is False
    assert parent["adjusted_delta_ns"] == 500
