from __future__ import annotations

import json

from causality.sensitivity_analysis import run_sensitivity_experiments


def main() -> None:
    results = run_sensitivity_experiments(
        trace_counts=(10, 25, 50),
        seeds=range(20),
    )

    print("CAUSALITY: REGRESSION MAGNITUDE AND NOISE SENSITIVITY")
    print("=" * 76)
    print("Metrics are averaged over repeated synthetic runs.")
    print("Undefined precision values are excluded from mean precision.")
    print()

    for result in results:
        print(
            f"{result['scenario']} | "
            f"traces={result['trace_count']} | "
            f"algorithm={result['algorithm']}"
        )
        print(
            json.dumps(
                {
                    "repeat_count": result["repeat_count"],
                    "top1_hit_rate": result["top1_hit_rate"],
                    "top3_hit_rate": result["top3_hit_rate"],
                    "mean_precision": result["mean_precision"],
                    "mean_recall": result["mean_recall"],
                    "mean_false_attributions": (
                        result["mean_false_attributions"]
                    ),
                    "runs_with_undefined_precision": (
                        result["runs_with_undefined_precision"]
                    ),
                },
                indent=2,
            )
        )
        print()

    print("Interpretation limitation:")
    print(
        "These results measure performance on constructed synthetic data. "
        "They do not prove causality or establish accuracy on production traces."
    )


if __name__ == "__main__":
    main()