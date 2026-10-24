
from causality.trace_analysis import (
    classify_regression_evidence,
    parse_traces,
    rank_execution_aware_regressions,
)


def _dataset(root_duration, payment_duration, inventory_duration=20):
    return {
        "traces": [
            {
                "trace_id": "trace-1",
                "spans": [
                    {
                        "span_id": "root",
                        "parent_span_id": None,
                        "service_name": "checkout",
                        "operation_name": "checkout_request",
                        "start_time_ns": 0,
                        "end_time_ns": root_duration,
                    },
                    {
                        "span_id": "payment",
                        "parent_span_id": "root",
                        "service_name": "payment",
                        "operation_name": "authorize_payment",
                        "start_time_ns": 0,
                        "end_time_ns": payment_duration,
                    },
                    {
                        "span_id": "inventory",
                        "parent_span_id": "root",
                        "service_name": "inventory",
                        "operation_name": "reserve_inventory",
                        "start_time_ns": 0,
                        "end_time_ns": inventory_duration,
                    },
                ],
            }
        ]
    }


def test_classifies_non_positive_delta():
    assert classify_regression_evidence(0, 0) == "no_observed_regression"
    assert classify_regression_evidence(-10, 20) == "no_observed_regression"


def test_classifies_positive_delta_without_descendant_increase():
    assert (
        classify_regression_evidence(50, 0)
        == "no_descendant_regression_observed"
    )


def test_classifies_parent_symptom_as_possible_not_proven():
    assert (
        classify_regression_evidence(50, 50)
        == "possible_parent_symptom"
    )
    assert (
        classify_regression_evidence(50, 80)
        == "possible_parent_symptom"
    )


def test_classifies_mixed_parent_and_descendant_evidence():
    assert (
        classify_regression_evidence(100, 40)
        == "mixed_parent_descendant_evidence"
    )


def test_execution_aware_results_keep_measured_delta_and_classification():
    baseline = parse_traces(
        _dataset(root_duration=100, payment_duration=50)
    )
    degraded = parse_traces(
        _dataset(root_duration=150, payment_duration=100)
    )

    results = rank_execution_aware_regressions(baseline, degraded)
    by_operation = {
        (item["service_name"], item["operation_name"]): item
        for item in results
    }

    root = by_operation[("checkout", "checkout_request")]
    payment = by_operation[("payment", "authorize_payment")]

    assert root["delta_ns"] == 50
    assert root["adjusted_delta_ns"] == 0
    assert root["evidence_classification"] == "possible_parent_symptom"

    assert payment["delta_ns"] == 50
    assert payment["adjusted_delta_ns"] == 50
    assert (
        payment["evidence_classification"]
        == "no_descendant_regression_observed"
    )


def test_parent_with_larger_delta_gets_mixed_evidence():
    baseline = parse_traces(
        _dataset(root_duration=100, payment_duration=50)
    )
    degraded = parse_traces(
        _dataset(root_duration=180, payment_duration=90)
    )

    results = rank_execution_aware_regressions(baseline, degraded)
    root = next(
        item for item in results
        if item["service_name"] == "checkout"
    )

    assert root["delta_ns"] == 80
    assert root["descendant_regression_evidence_ns"] == 40
    assert (
        root["evidence_classification"]
        == "mixed_parent_descendant_evidence"
    )
    assert root["adjusted_delta_ns"] == 80
