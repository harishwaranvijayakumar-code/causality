from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from causality.dataset_generator import generate_experiment
from causality.trace_analysis import (
    parse_traces,
    rank_execution_aware_regressions,
    rank_latency_regressions,
)


OperationKey = tuple[str, str]

PAYMENT: OperationKey = ("payment", "authorize_payment")
INVENTORY: OperationKey = ("inventory", "reserve_inventory")
CHECKOUT: OperationKey = ("checkout", "checkout_request")


@dataclass(frozen=True)
class ExperimentCase:
    name: str
    baseline: dict[str, Any]
    degraded: dict[str, Any]
    ground_truth: frozenset[OperationKey]
    description: str
    known_negative: frozenset[OperationKey] = frozenset()


def _trace(
    trace_id: str,
    *,
    root_duration_ns: int,
    payment_duration_ns: int,
    inventory_duration_ns: int,
    include_payment: bool = True,
    include_inventory: bool = True,
) -> dict[str, Any]:
    """Build a trace with parallel child spans."""
    spans: list[dict[str, Any]] = [
        {
            "span_id": "checkout-root",
            "parent_span_id": None,
            "service_name": "checkout",
            "operation_name": "checkout_request",
            "start_time_ns": 0,
            "end_time_ns": root_duration_ns,
        }
    ]

    if include_inventory:
        spans.append(
            {
                "span_id": "inventory-span",
                "parent_span_id": "checkout-root",
                "service_name": "inventory",
                "operation_name": "reserve_inventory",
                "start_time_ns": 0,
                "end_time_ns": inventory_duration_ns,
            }
        )

    if include_payment:
        spans.append(
            {
                "span_id": "payment-span",
                "parent_span_id": "checkout-root",
                "service_name": "payment",
                "operation_name": "authorize_payment",
                "start_time_ns": 0,
                "end_time_ns": payment_duration_ns,
            }
        )

    return {"trace_id": trace_id, "spans": spans}


def _dataset(
    *,
    prefix: str,
    count: int,
    root_duration_ns: int,
    payment_duration_ns: int,
    inventory_duration_ns: int,
    include_payment: bool = True,
    include_inventory: bool = True,
) -> dict[str, Any]:
    return {
        "traces": [
            _trace(
                f"{prefix}-{index + 1}",
                root_duration_ns=root_duration_ns,
                payment_duration_ns=payment_duration_ns,
                inventory_duration_ns=inventory_duration_ns,
                include_payment=include_payment,
                include_inventory=include_inventory,
            )
            for index in range(count)
        ]
    }


def _jittered_isolated_case(
    *,
    name: str,
    trace_count: int,
    seed: int,
    regression_ns: int,
    jitter_fraction: float,
) -> ExperimentCase:
    """
    Vary regression magnitude and noise independently.

    Checkout duration remains fixed so the experiment isolates the payment
    operation rather than making checkout a second regression candidate.
    Noise is sampled independently for baseline and degraded observations.
    """
    rng = random.Random(seed)
    baseline_traces: list[dict[str, Any]] = []
    degraded_traces: list[dict[str, Any]] = []

    baseline_payment_mean = 500
    degraded_payment_mean = baseline_payment_mean + regression_ns
    inventory_mean = 200
    root_duration = 1_000

    def sample(mean: int) -> int:
        spread = round(mean * jitter_fraction)
        if spread == 0:
            return mean
        return max(1, mean + rng.randint(-spread, spread))

    for index in range(trace_count):
        baseline_payment = sample(baseline_payment_mean)
        degraded_payment = sample(degraded_payment_mean)
        baseline_inventory = sample(inventory_mean)
        degraded_inventory = sample(inventory_mean)

        baseline_traces.append(
            _trace(
                f"{name}-base-{index + 1}",
                root_duration_ns=root_duration,
                payment_duration_ns=baseline_payment,
                inventory_duration_ns=baseline_inventory,
            )
        )
        degraded_traces.append(
            _trace(
                f"{name}-degraded-{index + 1}",
                root_duration_ns=root_duration,
                payment_duration_ns=degraded_payment,
                inventory_duration_ns=degraded_inventory,
            )
        )

    return ExperimentCase(
        name=name,
        baseline={"traces": baseline_traces},
        degraded={"traces": degraded_traces},
        ground_truth=frozenset({PAYMENT}),
        known_negative=frozenset({CHECKOUT, INVENTORY}),
        description=(
            f"Payment regression magnitude is {regression_ns} ns with "
            f"{jitter_fraction:.0%} independent duration noise. "
            "Checkout duration remains fixed."
        ),
    )


def build_experiment_cases(
    *,
    trace_count: int = 10,
    seed: int = 42,
) -> list[ExperimentCase]:
    """Create reproducible scenarios with explicit synthetic ground truth."""
    if isinstance(trace_count, bool) or not isinstance(trace_count, int):
        raise ValueError("trace_count must be an integer.")
    if trace_count < 3:
        raise ValueError("trace_count must be at least 3.")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer.")

    cases: list[ExperimentCase] = []

    generated = generate_experiment(
        execution_mode="parallel",
        trace_count=trace_count,
        seed=seed,
    )
    cases.append(
        ExperimentCase(
            name="single_regression",
            baseline=generated.baseline,
            degraded=generated.degraded,
            ground_truth=frozenset({PAYMENT}),
            known_negative=frozenset({INVENTORY, CHECKOUT}),
            description=(
                "Payment is the only injected regression source; "
                "parent latency may increase as a consequence."
            ),
        )
    )

    cases.append(
        ExperimentCase(
            name="multiple_regressions",
            baseline=_dataset(
                prefix="multi-base",
                count=trace_count,
                root_duration_ns=200,
                payment_duration_ns=100,
                inventory_duration_ns=80,
            ),
            degraded=_dataset(
                prefix="multi-degraded",
                count=trace_count,
                root_duration_ns=700,
                payment_duration_ns=600,
                inventory_duration_ns=500,
            ),
            ground_truth=frozenset({PAYMENT, INVENTORY}),
            known_negative=frozenset({CHECKOUT}),
            description=(
                "Payment and inventory are injected regression sources; "
                "checkout latency is a parent symptom."
            ),
        )
    )

    cases.append(
        ExperimentCase(
            name="parent_only_regression",
            baseline=_dataset(
                prefix="parent-base",
                count=trace_count,
                root_duration_ns=200,
                payment_duration_ns=100,
                inventory_duration_ns=80,
            ),
            degraded=_dataset(
                prefix="parent-degraded",
                count=trace_count,
                root_duration_ns=700,
                payment_duration_ns=100,
                inventory_duration_ns=80,
            ),
            ground_truth=frozenset({CHECKOUT}),
            known_negative=frozenset({PAYMENT, INVENTORY}),
            description=(
                "Checkout latency increases while both child durations "
                "remain unchanged."
            ),
        )
    )

    serial = generate_experiment(
        execution_mode="serial",
        trace_count=trace_count,
        seed=seed,
    )
    cases.append(
        ExperimentCase(
            name="serial_execution",
            baseline=serial.baseline,
            degraded=serial.degraded,
            ground_truth=frozenset({PAYMENT}),
            known_negative=frozenset({INVENTORY, CHECKOUT}),
            description="Payment becomes slower in a serial execution path.",
        )
    )

    noisy = generate_experiment(
        execution_mode="parallel",
        trace_count=trace_count,
        seed=seed,
        jitter_fraction=0.10,
    )
    cases.append(
        ExperimentCase(
            name="noisy_traces",
            baseline=noisy.baseline,
            degraded=noisy.degraded,
            ground_truth=frozenset({PAYMENT}),
            known_negative=frozenset({INVENTORY, CHECKOUT}),
            description=(
                "Durations vary around configured values while payment "
                "remains the only injected source."
            ),
        )
    )

    cases.append(
        ExperimentCase(
            name="incomplete_traces",
            baseline=_dataset(
                prefix="incomplete-base",
                count=trace_count,
                root_duration_ns=200,
                payment_duration_ns=100,
                inventory_duration_ns=80,
            ),
            degraded=_dataset(
                prefix="incomplete-degraded",
                count=trace_count,
                root_duration_ns=200,
                payment_duration_ns=100,
                inventory_duration_ns=80,
                include_payment=False,
            ),
            ground_truth=frozenset(),
            known_negative=frozenset({CHECKOUT, INVENTORY}),
            description=(
                "Payment is missing from degraded data. Its regression "
                "status is unknown, not negative."
            ),
        )
    )

    cases.append(
        ExperimentCase(
            name="parallel_child_regressions",
            baseline=_dataset(
                prefix="parallel-base",
                count=trace_count,
                root_duration_ns=100,
                payment_duration_ns=100,
                inventory_duration_ns=80,
            ),
            degraded=_dataset(
                prefix="parallel-degraded",
                count=trace_count,
                root_duration_ns=200,
                payment_duration_ns=200,
                inventory_duration_ns=180,
            ),
            ground_truth=frozenset({PAYMENT, INVENTORY}),
            known_negative=frozenset({CHECKOUT}),
            description=(
                "Both parallel children increase by 100 ns, while the "
                "parent increases by only 100 ns. Child deltas must not "
                "be summed as if both necessarily add to elapsed time."
            ),
        )
    )

    # A genuinely isolated small regression: checkout and inventory do not
    # change, so only payment is a positive latency-regression candidate.
    cases.append(
        _jittered_isolated_case(
            name="small_regression",
            trace_count=trace_count,
            seed=seed + 100,
            regression_ns=10,
            jitter_fraction=0.0,
        )
    )

    cases.append(
        ExperimentCase(
            name="child_regression_unchanged_parent",
            baseline=_dataset(
                prefix="child-base",
                count=trace_count,
                root_duration_ns=1_000,
                payment_duration_ns=500,
                inventory_duration_ns=200,
            ),
            degraded=_dataset(
                prefix="child-degraded",
                count=trace_count,
                root_duration_ns=1_000,
                payment_duration_ns=600,
                inventory_duration_ns=200,
            ),
            ground_truth=frozenset({PAYMENT}),
            known_negative=frozenset({CHECKOUT, INVENTORY}),
            description=(
                "Payment increases by 100 ns while checkout duration is "
                "unchanged. The operation regresses, but observed request "
                "duration does not increase in this constructed dataset."
            ),
        )
    )

    # A small 2-by-2 experiment varies regression magnitude and noise
    # independently. small_regression above is the 10 ns, 0% noise cell.
    cases.extend(
        [
            _jittered_isolated_case(
                name="magnitude_10ns_noise_10pct",
                trace_count=trace_count,
                seed=seed + 110,
                regression_ns=10,
                jitter_fraction=0.10,
            ),
            _jittered_isolated_case(
                name="magnitude_100ns_noise_0pct",
                trace_count=trace_count,
                seed=seed + 120,
                regression_ns=100,
                jitter_fraction=0.0,
            ),
            _jittered_isolated_case(
                name="magnitude_100ns_noise_10pct",
                trace_count=trace_count,
                seed=seed + 130,
                regression_ns=100,
                jitter_fraction=0.10,
            ),
        ]
    )

    return cases


def _operation_key(item: dict[str, Any]) -> OperationKey:
    return item["service_name"], item["operation_name"]


def _ranked_keys(results: list[dict[str, Any]]) -> list[OperationKey]:
    return [_operation_key(item) for item in results]


def _positive_candidates(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter non-positive deltas while supporting key-only test fixtures."""
    return [
        item
        for item in results
        if "delta_ns" not in item or item["delta_ns"] > 0
    ]


def evaluate_ranking(
    results: list[dict[str, Any]],
    ground_truth: frozenset[OperationKey],
    known_negative: frozenset[OperationKey] = frozenset(),
) -> dict[str, Any]:
    """
    Evaluate candidates against explicit synthetic labels.

    Unlabelled predictions remain unassessed. Empty ground truth means recall
    cannot be evaluated. Precision uses only predictions with explicit labels.
    """
    all_ranked = _ranked_keys(results)
    candidates = _ranked_keys(_positive_candidates(results))
    candidate_set = set(candidates)

    true_positives = candidate_set & set(ground_truth)
    false_positives = candidate_set & set(known_negative)
    unassessed = candidate_set - set(ground_truth) - set(known_negative)
    detected = candidate_set & set(ground_truth)

    assessed_count = len(true_positives) + len(false_positives)
    precision = (
        len(true_positives) / assessed_count if assessed_count else None
    )
    recall = len(detected) / len(ground_truth) if ground_truth else None

    if not ground_truth:
        status = "not_evaluable_no_ground_truth"
    elif not detected:
        status = "no_ground_truth_regressions_detected"
    else:
        status = "evaluated"

    return {
        "evaluation_status": status,
        "top1_hit": int(bool(candidates) and candidates[0] in ground_truth),
        "top3_hit": int(bool(set(candidates[:3]) & set(ground_truth))),
        "ground_truth_count": len(ground_truth),
        "detected_ground_truth_count": len(detected),
        "ground_truth_recall": recall,
        "true_positive_count": len(true_positives),
        "false_positive_count": len(false_positives),
        "false_attribution_count": len(false_positives),
        "unassessed_prediction_count": len(unassessed),
        "unassessed_predictions": sorted(unassessed),
        "precision": precision,
        "known_negative_count": len(known_negative),
        "positive_candidate_count": len(candidates),
        "ranked_operations": candidates,
        "all_ranked_operations": all_ranked,
    }


def _operation_keys(spans: list[Any]) -> set[OperationKey]:
    return {span.operation_key for span in spans}


def run_experiment_suite(
    *,
    trace_count: int = 10,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Run both ranking algorithms and report coverage and labelled metrics."""
    reports: list[dict[str, Any]] = []

    for case in build_experiment_cases(trace_count=trace_count, seed=seed):
        baseline_spans = parse_traces(case.baseline)
        degraded_spans = parse_traces(case.degraded)

        baseline_keys = _operation_keys(baseline_spans)
        degraded_keys = _operation_keys(degraded_spans)
        matched_keys = baseline_keys & degraded_keys
        baseline_only = baseline_keys - degraded_keys
        degraded_only = degraded_keys - baseline_keys
        union_keys = baseline_keys | degraded_keys

        simple_results = rank_latency_regressions(
            baseline_spans, degraded_spans
        )
        aware_results = rank_execution_aware_regressions(
            baseline_spans, degraded_spans
        )

        reports.append(
            {
                "scenario": case.name,
                "description": case.description,
                "ground_truth": sorted(case.ground_truth),
                "known_negative": sorted(case.known_negative),
                "comparison_coverage": {
                    "baseline_operation_count": len(baseline_keys),
                    "degraded_operation_count": len(degraded_keys),
                    "matched_operation_count": len(matched_keys),
                    "baseline_only_operations": sorted(baseline_only),
                    "degraded_only_operations": sorted(degraded_only),
                    "matched_operation_fraction": (
                        len(matched_keys) / len(union_keys)
                        if union_keys
                        else 1.0
                    ),
                    "coverage_unit": "distinct operation keys, not spans",
                },
                "simple_ranking": evaluate_ranking(
                    simple_results, case.ground_truth, case.known_negative
                ),
                "execution_aware_ranking": evaluate_ranking(
                    aware_results, case.ground_truth, case.known_negative
                ),
            }
        )

    return reports


def summarize_experiment_suite(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate metrics across scenarios without treating undefined values as 0."""
    summary: dict[str, Any] = {
        "scenario_count": len(reports),
        "evaluable_scenario_count": 0,
        "unevaluable_scenario_count": 0,
        "algorithms": {},
    }

    for algorithm_key in ("simple_ranking", "execution_aware_ranking"):
        evaluable = [
            report[algorithm_key]
            for report in reports
            if report[algorithm_key]["ground_truth_count"] > 0
        ]
        unevaluable_count = len(reports) - len(evaluable)

        def mean_defined(metric: str) -> float | None:
            values = [
                item[metric]
                for item in evaluable
                if item[metric] is not None
            ]
            return sum(values) / len(values) if values else None

        summary["algorithms"][algorithm_key] = {
            "evaluable_scenarios": len(evaluable),
            "unevaluable_scenarios": unevaluable_count,
            "top1_hit_rate": mean_defined("top1_hit"),
            "top3_hit_rate": mean_defined("top3_hit"),
            "mean_precision": mean_defined("precision"),
            "mean_recall": mean_defined("ground_truth_recall"),
            "false_attribution_count": sum(
                item["false_positive_count"] for item in evaluable
            ),
        }

    if reports:
        summary["evaluable_scenario_count"] = sum(
            report["execution_aware_ranking"]["ground_truth_count"] > 0
            for report in reports
        )
        summary["unevaluable_scenario_count"] = (
            len(reports) - summary["evaluable_scenario_count"]
        )

    return summary