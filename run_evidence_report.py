
from causality.evidence_reporting import (
    attach_evidence_reporting,
    describe_operation_evidence,
)
from causality.experiment_suite import build_experiment_cases
from causality.trace_analysis import (
    parse_traces,
    rank_execution_aware_regressions,
)


def main():
    cases = build_experiment_cases()

    for case in cases:
        baseline_spans = parse_traces(case.baseline)
        degraded_spans = parse_traces(case.degraded)

        ranked_results = rank_execution_aware_regressions(
            baseline_spans,
            degraded_spans,
        )

        # Keep the original ranking output for comparison.
        original_results = [dict(item) for item in ranked_results]

        # Add reporting classifications without changing ranking order or scores.
        reported_results = attach_evidence_reporting(ranked_results)

        print("\n" + "=" * 90)
        print(f"Scenario: {case.name}")
        print("=" * 90)
        print(f"Ground truth: {case.ground_truth}")

        if not reported_results:
            print("No matched operations found.")
            continue

        for rank, (original, reported) in enumerate(
            zip(original_results, reported_results),
            start=1,
        ):
            delta_ns = reported["delta_ns"]
            descendant_ns = reported["descendant_regression_evidence_ns"]
            reporting_classification = reported["evidence_classification"]

            explanation = describe_operation_evidence(
                reporting_classification
            )

            print(
                f"\n#{rank} "
                f"{reported['service_name']}."
                f"{reported['operation_name']}"
            )
            print(f"  Own latency delta: {delta_ns} ns")
            print(f"  Descendant evidence: {descendant_ns} ns")
            print(
                "  Existing classification: "
                f"{original['evidence_classification']}"
            )
            print(
                "  Reporting classification: "
                f"{reporting_classification}"
            )
            print(f"  Explanation: {explanation}")
            print(
                "  Ranking adjusted delta: "
                f"{reported['adjusted_delta_ns']} ns"
            )

        print(
            "\nInterpretation note: these labels describe observed "
            "measurements and do not establish causal proof."
        )


if __name__ == "__main__":
    main()
