from __future__ import annotations

from statistics import mean
from typing import Any

from causality.experiment_suite import run_experiment_suite


SCENARIOS = (
    "parent_only_regression",
    "parallel_child_regressions",
    "multiple_regressions",
)

ALGORITHMS = (
    "simple_ranking",
    "execution_aware_ranking",
)

CHECKOUT = ("checkout", "checkout_request")


def _mean_defined(values: list[float | int | None]) -> float | None:
    defined = [float(value) for value in values if value is not None]
    return mean(defined) if defined else None


def run_focused_benchmark(
    *,
    trace_counts: tuple[int, ...] = (10, 25, 50),
    seeds: tuple[int, ...] = tuple(range(20)),
) -> list[dict[str, Any]]:
    """Compare ranking algorithms on focused synthetic scenarios."""
    if not trace_counts:
        raise ValueError("trace_counts must not be empty.")
    if not seeds:
        raise ValueError("seeds must not be empty.")

    for count in trace_counts:
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("Every trace count must be an integer.")
        if count < 3:
            raise ValueError("Every trace count must be at least 3.")

    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("Every seed must be an integer.")

    collected: dict[tuple[str, int, str], list[dict[str, Any]]] = {}

    for trace_count in trace_counts:
        for seed in seeds:
            reports = run_experiment_suite(
                trace_count=trace_count,
                seed=seed,
            )

            for report in reports:
                scenario = report["scenario"]
                if scenario not in SCENARIOS:
                    continue

                for algorithm in ALGORITHMS:
                    metrics = report[algorithm]
                    known_negatives = {
                        tuple(operation)
                        for operation in report["known_negative"]
                    }
                    ranked_operations = {
                        tuple(operation)
                        for operation in metrics["ranked_operations"]
                    }

                    parent_is_assessed_negative = CHECKOUT in known_negatives
                    parent_false_attribution = (
                        int(CHECKOUT in ranked_operations)
                        if parent_is_assessed_negative
                        else None
                    )

                    key = (scenario, trace_count, algorithm)
                    collected.setdefault(key, []).append(
                        {
                            "top1_hit": metrics["top1_hit"],
                            "top3_hit": metrics["top3_hit"],
                            "precision": metrics["precision"],
                            "recall": metrics["ground_truth_recall"],
                            "false_attributions": (
                                metrics["false_attribution_count"]
                            ),
                            "parent_false_attribution": (
                                parent_false_attribution
                            ),
                        }
                    )

    results: list[dict[str, Any]] = []

    for scenario in SCENARIOS:
        for trace_count in trace_counts:
            for algorithm in ALGORITHMS:
                runs = collected.get(
                    (scenario, trace_count, algorithm),
                    [],
                )

                if not runs:
                    continue

                parent_values = [
                    run["parent_false_attribution"]
                    for run in runs
                    if run["parent_false_attribution"] is not None
                ]

                results.append(
                    {
                        "scenario": scenario,
                        "trace_count": trace_count,
                        "algorithm": algorithm,
                        "repeat_count": len(runs),
                        "top1_hit_rate": _mean_defined(
                            [run["top1_hit"] for run in runs]
                        ),
                        "top3_hit_rate": _mean_defined(
                            [run["top3_hit"] for run in runs]
                        ),
                        "mean_precision": _mean_defined(
                            [run["precision"] for run in runs]
                        ),
                        "mean_recall": _mean_defined(
                            [run["recall"] for run in runs]
                        ),
                        "mean_false_attributions": _mean_defined(
                            [run["false_attributions"] for run in runs]
                        ),
                        "checkout_false_attribution_rate": (
                            _mean_defined(parent_values)
                        ),
                        "checkout_negative_assessed_runs": len(
                            parent_values
                        ),
                        "runs_with_undefined_precision": sum(
                            run["precision"] is None for run in runs
                        ),
                    }
                )

    return results