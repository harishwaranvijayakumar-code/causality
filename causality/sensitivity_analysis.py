from __future__ import annotations

from statistics import mean
from typing import Any, Iterable

from causality.experiment_suite import run_experiment_suite


SENSITIVITY_SCENARIOS = (
    "small_regression",
    "magnitude_10ns_noise_10pct",
    "magnitude_100ns_noise_0pct",
    "magnitude_100ns_noise_10pct",
)

ALGORITHMS = (
    "simple_ranking",
    "execution_aware_ranking",
)


def _validate_trace_counts(trace_counts: Iterable[int]) -> list[int]:
    values = list(trace_counts)

    if not values:
        raise ValueError("trace_counts must contain at least one value.")

    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Every trace count must be an integer.")
        if value < 3:
            raise ValueError("Every trace count must be at least 3.")

    return values


def _validate_seeds(seeds: Iterable[int]) -> list[int]:
    values = list(seeds)

    if not values:
        raise ValueError("seeds must contain at least one value.")

    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Every seed must be an integer.")

    return values


def _mean_defined(values: list[float | int | None]) -> float | None:
    defined = [float(value) for value in values if value is not None]
    return mean(defined) if defined else None


def run_sensitivity_experiments(
    *,
    trace_counts: Iterable[int] = (10, 25, 50),
    seeds: Iterable[int] = range(20),
) -> list[dict[str, Any]]:
    """
    Evaluate regression magnitude and noise over multiple seeds and trace counts.

    Each condition is evaluated on the same generated datasets by both
    ranking algorithms. Metrics are averaged over repeated runs. Undefined
    precision values are excluded from the precision mean rather than treated
    as zero.
    """
    validated_trace_counts = _validate_trace_counts(trace_counts)
    validated_seeds = _validate_seeds(seeds)

    observations: dict[tuple[str, int, str], list[dict[str, Any]]] = {}

    for trace_count in validated_trace_counts:
        for seed in validated_seeds:
            reports = run_experiment_suite(
                trace_count=trace_count,
                seed=seed,
            )

            for report in reports:
                scenario = report["scenario"]

                if scenario not in SENSITIVITY_SCENARIOS:
                    continue

                for algorithm in ALGORITHMS:
                    key = (scenario, trace_count, algorithm)
                    observations.setdefault(key, []).append(
                        report[algorithm]
                    )

    summary: list[dict[str, Any]] = []

    for scenario in SENSITIVITY_SCENARIOS:
        for trace_count in validated_trace_counts:
            for algorithm in ALGORITHMS:
                key = (scenario, trace_count, algorithm)
                runs = observations.get(key, [])

                if not runs:
                    continue

                summary.append(
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
                            [run["ground_truth_recall"] for run in runs]
                        ),
                        "mean_false_attributions": _mean_defined(
                            [run["false_attribution_count"] for run in runs]
                        ),
                        "runs_with_undefined_precision": sum(
                            run["precision"] is None for run in runs
                        ),
                    }
                )

    return summary