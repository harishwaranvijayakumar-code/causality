
"""Canonical evidence reporting for latency regression analysis.

Evidence labels describe observed measurements. They do not prove causality.
Ranking behavior is intentionally kept separate from reporting.
"""


EVIDENCE_DESCRIPTIONS = {
    "no_observed_regression": (
        "Neither this operation nor its measured descendant evidence "
        "shows a positive regression increase."
    ),
    "no_own_regression_descendant_regression_observed": (
        "This operation has no observed latency increase, but at least "
        "one descendant operation shows a positive latency increase."
    ),
    "own_regression_no_descendant_regression_observed": (
        "This operation shows a positive latency increase, but no "
        "positive descendant regression increase was observed."
    ),
    "possible_parent_symptom": (
        "The descendant regression evidence is at least as large as "
        "this operation's latency increase. The parent may be reflecting "
        "downstream latency."
    ),
    "mixed_parent_descendant_evidence": (
        "This operation and its descendants show positive latency "
        "increases, but the descendant evidence is smaller than the "
        "operation's own increase."
    ),
}


def classify_operation_evidence(
    delta_ns: int,
    descendant_regression_evidence_ns: int,
) -> str:
    """Classify own and descendant latency evidence."""

    if delta_ns <= 0:
        if descendant_regression_evidence_ns > 0:
            return "no_own_regression_descendant_regression_observed"

        return "no_observed_regression"

    if descendant_regression_evidence_ns <= 0:
        return "own_regression_no_descendant_regression_observed"

    if descendant_regression_evidence_ns >= delta_ns:
        return "possible_parent_symptom"

    return "mixed_parent_descendant_evidence"


def describe_operation_evidence(classification: str) -> str:
    """Return the explanation for a canonical evidence label."""

    try:
        return EVIDENCE_DESCRIPTIONS[classification]
    except KeyError as exc:
        raise ValueError(
            f"Unknown evidence classification: {classification!r}"
        ) from exc


def attach_evidence_reporting(
    ranked_results: list[dict],
) -> list[dict]:
    """Add canonical evidence fields without changing ranking or inputs.

    Each result must contain:
    - delta_ns
    - descendant_regression_evidence_ns

    The returned list preserves the input order. Original dictionaries
    are copied so this function does not mutate the caller's results.
    """

    reported_results = []

    for item in ranked_results:
        if "delta_ns" not in item:
            raise ValueError("Ranked result is missing 'delta_ns'")

        if "descendant_regression_evidence_ns" not in item:
            raise ValueError(
                "Ranked result is missing "
                "'descendant_regression_evidence_ns'"
            )

        classification = classify_operation_evidence(
            delta_ns=item["delta_ns"],
            descendant_regression_evidence_ns=(
                item["descendant_regression_evidence_ns"]
            ),
        )

        reported_item = dict(item)
        reported_item["evidence_classification"] = classification
        reported_item["evidence_description"] = (
            describe_operation_evidence(classification)
        )

        reported_results.append(reported_item)

    return reported_results
