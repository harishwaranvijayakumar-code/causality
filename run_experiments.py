from __future__ import annotations

import json
from typing import Any

from causality.experiment_suite import (
    run_experiment_suite,
    summarize_experiment_suite,
)


def _format_metric(value: Any) -> str:
    """Format optional metrics without treating undefined values as zero."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def main() -> None:
    reports = run_experiment_suite(trace_count=10, seed=42)
    summary = summarize_experiment_suite(reports)

    print("=" * 72)
    print("CAUSALITY EXPERIMENT SUMMARY")
    print("=" * 72)
    print(f"Total scenarios: {summary['scenario_count']}")
    print(f"Evaluable scenarios: {summary['evaluable_scenario_count']}")
    print(f"Unevaluable scenarios: {summary['unevaluable_scenario_count']}")

    for algorithm, metrics in summary["algorithms"].items():
        print(f"\n{algorithm}")
        print(f"  Evaluable scenarios: {metrics['evaluable_scenarios']}")
        print(f"  Unevaluable scenarios: {metrics['unevaluable_scenarios']}")
        print(f"  Top-1 hit rate: {_format_metric(metrics['top1_hit_rate'])}")
        print(f"  Top-3 hit rate: {_format_metric(metrics['top3_hit_rate'])}")
        print(f"  Mean precision: {_format_metric(metrics['mean_precision'])}")
        print(f"  Mean recall: {_format_metric(metrics['mean_recall'])}")
        print(f"  False attributions: {metrics['false_attribution_count']}")

    for report in reports:
        print(f"\n{'=' * 72}")
        print(f"Scenario: {report['scenario']}")
        print(report["description"])
        print(f"Ground truth: {report['ground_truth']}")
        print(f"Known negatives: {report['known_negative']}")

        print("\nComparison coverage")
        print(json.dumps(report["comparison_coverage"], indent=2))

        for label, key in (
            ("Simple ranking", "simple_ranking"),
            ("Execution-aware ranking", "execution_aware_ranking"),
        ):
            metrics = report[key]
            print(f"\n--- {label} ---")
            print(
                json.dumps(
                    {
                        "evaluation_status": metrics["evaluation_status"],
                        "top1_hit": metrics["top1_hit"],
                        "top3_hit": metrics["top3_hit"],
                        "ground_truth_count": metrics["ground_truth_count"],
                        "detected_ground_truth_count": (
                            metrics["detected_ground_truth_count"]
                        ),
                        "ground_truth_recall": metrics["ground_truth_recall"],
                        "precision": metrics["precision"],
                        "true_positive_count": metrics["true_positive_count"],
                        "false_positive_count": metrics["false_positive_count"],
                        "unassessed_prediction_count": (
                            metrics["unassessed_prediction_count"]
                        ),
                        "positive_candidate_count": (
                            metrics["positive_candidate_count"]
                        ),
                        "ranked_operations": metrics["ranked_operations"],
                    },
                    indent=2,
                )
            )

        print(
            "\nInterpretation note: these metrics describe synthetic scenarios. "
            "They do not establish causal proof or real-world accuracy."
        )


if __name__ == "__main__":
    main()