from __future__ import annotations

import json

from causality.focused_benchmark import run_focused_benchmark


def main() -> None:
    results = run_focused_benchmark(
        trace_counts=(10, 25, 50),
        seeds=tuple(range(20)),
    )

    print("CAUSALITY: FOCUSED RANKING BENCHMARK")
    print("=" * 76)
    print("Synthetic scenarios, repeated seeds, identical inputs per algorithm.")
    print()

    for result in results:
        print(
            f"{result['scenario']} | "
            f"traces={result['trace_count']} | "
            f"algorithm={result['algorithm']}"
        )
        print(json.dumps(result, indent=2))
        print()

    print("Interpretation notes:")
    print(
        "- Precision averages exclude runs where precision is undefined."
    )
    print(
        "- Checkout false-attribution rate is calculated only for runs "
        "where checkout is explicitly labelled a known negative."
    )
    print(
        "- Results are synthetic and do not establish causal proof or "
        "production accuracy."
    )


if __name__ == "__main__":
    main()