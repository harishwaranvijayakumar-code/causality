
from __future__ import annotations

from typing import Any

from causality.trace_analysis import (
    parse_traces,
    rank_execution_aware_regressions,
    rank_latency_regressions,
)


CHECKOUT = ("checkout", "checkout_request")
PAYMENT = ("payment", "authorize_payment")
INVENTORY = ("inventory", "reserve_inventory")


def make_dataset(
    prefix: str,
    *,
    root_durations: list[int],
    payment_durations: list[int],
    inventory_durations: list[int],
    execution_mode: str = "parallel",
) -> dict[str, Any]:
    """Build a deterministic dataset for ranking edge-case tests."""
    if not (
        len(root_durations)
        == len(payment_durations)
        == len(inventory_durations)
    ):
        raise ValueError("All duration lists must have the same length.")

    traces = []

    for index, (root_duration, payment_duration, inventory_duration) in enumerate(
        zip(root_durations, payment_durations, inventory_durations)
    ):
        if execution_mode == "serial":
            inventory_start = 0
            inventory_end = inventory_duration
            payment_start = inventory_end
            payment_end = payment_start + payment_duration
        else:
            inventory_start = 0
            inventory_end = inventory_duration
            payment_start = 0
            payment_end = payment_duration

        spans = [
            {
                "span_id": "checkout-root",
                "parent_span_id": None,
                "service_name": CHECKOUT[0],
                "operation_name": CHECKOUT[1],
                "start_time_ns": 0,
                "end_time_ns": root_duration,
            },
            {
                "span_id": "inventory-span",
                "parent_span_id": "checkout-root",
                "service_name": INVENTORY[0],
                "operation_name": INVENTORY[1],
                "start_time_ns": inventory_start,
                "end_time_ns": inventory_end,
            },
            {
                "span_id": "payment-span",
                "parent_span_id": "checkout-root",
                "service_name": PAYMENT[0],
                "operation_name": PAYMENT[1],
                "start_time_ns": payment_start,
                "end_time_ns": payment_end,
            },
        ]

        traces.append(
            {
                "trace_id": f"{prefix}-{index + 1}",
                "spans": spans,
            }
        )

    return {"traces": traces}


def result_for(results: list[dict[str, Any]], key: tuple[str, str]) -> dict[str, Any]:
    """Find one operation in a ranking result."""
    return next(
        item
        for item in results
        if (item["service_name"], item["operation_name"]) == key
    )


def test_parent_only_regression_is_not_discounted_without_child_evidence():
    baseline = parse_traces(
        make_dataset(
            "baseline",
            root_durations=[200, 200, 200],
            payment_durations=[100, 100, 100],
            inventory_durations=[80, 80, 80],
        )
    )
    degraded = parse_traces(
        make_dataset(
            "degraded",
            root_durations=[300, 300, 300],
            payment_durations=[100, 100, 100],
            inventory_durations=[80, 80, 80],
        )
    )

    results = rank_execution_aware_regressions(baseline, degraded)
    checkout = result_for(results, CHECKOUT)

    assert checkout["delta_ns"] == 100
    assert checkout["descendant_regression_evidence_ns"] == 0
    assert checkout["discounted_as_parent_symptom"] is False
    assert checkout["adjusted_delta_ns"] == 100


def test_parallel_child_deltas_are_not_summed_for_parent_discount():
    baseline = parse_traces(
        make_dataset(
            "baseline",
            root_durations=[100, 100, 100],
            payment_durations=[100, 100, 100],
            inventory_durations=[80, 80, 80],
        )
    )
    degraded = parse_traces(
        make_dataset(
            "degraded",
            root_durations=[200, 200, 200],
            payment_durations=[200, 200, 200],
            inventory_durations=[180, 180, 180],
        )
    )

    results = rank_execution_aware_regressions(baseline, degraded)
    checkout = result_for(results, CHECKOUT)

    assert result_for(results, PAYMENT)["delta_ns"] == 100
    assert result_for(results, INVENTORY)["delta_ns"] == 100
    assert checkout["delta_ns"] == 100

    # Maximum descendant increase is 100 ns, not the sum of 200 ns.
    assert checkout["descendant_regression_evidence_ns"] == 100
    assert checkout["discounted_as_parent_symptom"] is True
    assert checkout["adjusted_delta_ns"] == 0


def test_serial_payment_regression_has_matching_parent_delta():
    baseline = parse_traces(
        make_dataset(
            "baseline",
            root_durations=[180, 180, 180],
            payment_durations=[100, 100, 100],
            inventory_durations=[80, 80, 80],
            execution_mode="serial",
        )
    )
    degraded = parse_traces(
        make_dataset(
            "degraded",
            root_durations=[680, 680, 680],
            payment_durations=[600, 600, 600],
            inventory_durations=[80, 80, 80],
            execution_mode="serial",
        )
    )

    results = rank_execution_aware_regressions(baseline, degraded)
    checkout = result_for(results, CHECKOUT)
    payment = result_for(results, PAYMENT)
    inventory = result_for(results, INVENTORY)

    assert payment["delta_ns"] == 500
    assert checkout["delta_ns"] == 500
    assert checkout["descendant_regression_evidence_ns"] == 500
    assert checkout["discounted_as_parent_symptom"] is True
    assert checkout["adjusted_delta_ns"] == 0
    assert inventory["delta_ns"] == 0


def test_single_outlier_does_not_change_median_duration():
    baseline = parse_traces(
        make_dataset(
            "baseline",
            root_durations=[100, 100, 100],
            payment_durations=[100, 100, 100],
            inventory_durations=[80, 80, 80],
        )
    )
    degraded = parse_traces(
        make_dataset(
            "degraded",
            root_durations=[100, 100, 101],
            payment_durations=[100, 100, 101],
            inventory_durations=[80, 80, 80],
        )
    )

    results = rank_latency_regressions(baseline, degraded)
    payment = result_for(results, PAYMENT)

    assert payment["baseline_median_ns"] == 100
    assert payment["degraded_median_ns"] == 100
    assert payment["delta_ns"] == 0
    assert payment["is_regression_candidate"] is False


def test_negative_delta_is_preserved_but_not_a_regression_candidate():
    baseline = parse_traces(
        make_dataset(
            "baseline",
            root_durations=[200, 200, 200],
            payment_durations=[200, 200, 200],
            inventory_durations=[80, 80, 80],
        )
    )
    degraded = parse_traces(
        make_dataset(
            "degraded",
            root_durations=[150, 150, 150],
            payment_durations=[150, 150, 150],
            inventory_durations=[80, 80, 80],
        )
    )

    results = rank_latency_regressions(baseline, degraded)
    payment = result_for(results, PAYMENT)

    assert payment["delta_ns"] == -50
    assert payment["is_regression_candidate"] is False
