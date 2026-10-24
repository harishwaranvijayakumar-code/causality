
import pytest

from causality.evidence_reporting import (
    EVIDENCE_DESCRIPTIONS,
    attach_evidence_reporting,
    classify_operation_evidence,
    describe_operation_evidence,
)


@pytest.mark.parametrize(
    ("delta_ns", "descendant_ns", "expected"),
    [
        (0, 0, "no_observed_regression"),
        (-10, 0, "no_observed_regression"),
        (
            0,
            100,
            "no_own_regression_descendant_regression_observed",
        ),
        (
            -10,
            100,
            "no_own_regression_descendant_regression_observed",
        ),
        (
            100,
            0,
            "own_regression_no_descendant_regression_observed",
        ),
        (100, 50, "mixed_parent_descendant_evidence"),
        (100, 100, "possible_parent_symptom"),
        (100, 150, "possible_parent_symptom"),
    ],
)
def test_classify_operation_evidence(
    delta_ns,
    descendant_ns,
    expected,
):
    assert classify_operation_evidence(
        delta_ns=delta_ns,
        descendant_regression_evidence_ns=descendant_ns,
    ) == expected


@pytest.mark.parametrize(
    "classification",
    list(EVIDENCE_DESCRIPTIONS),
)
def test_every_classification_has_a_description(classification):
    description = describe_operation_evidence(classification)

    assert isinstance(description, str)
    assert description.strip()


def test_unknown_classification_raises_value_error():
    with pytest.raises(ValueError, match="Unknown evidence classification"):
        describe_operation_evidence("unknown_classification")


def test_attach_reporting_preserves_ranking_order_and_scores():
    ranked_results = [
        {
            "service_name": "payment",
            "operation_name": "authorize",
            "delta_ns": 100,
            "adjusted_delta_ns": 100,
            "descendant_regression_evidence_ns": 0,
        },
        {
            "service_name": "checkout",
            "operation_name": "request",
            "delta_ns": 200,
            "adjusted_delta_ns": 0,
            "descendant_regression_evidence_ns": 250,
        },
    ]
    original_results = [dict(item) for item in ranked_results]

    reported = attach_evidence_reporting(ranked_results)

    assert [
        (item["service_name"], item["operation_name"])
        for item in reported
    ] == [
        (item["service_name"], item["operation_name"])
        for item in ranked_results
    ]

    for original, result in zip(ranked_results, reported):
        for key, value in original.items():
            assert result[key] == value

    assert reported[0]["evidence_classification"] == (
        "own_regression_no_descendant_regression_observed"
    )
    assert reported[1]["evidence_classification"] == (
        "possible_parent_symptom"
    )

    assert ranked_results == original_results


@pytest.mark.parametrize(
    ("result", "missing_field"),
    [
        (
            {"descendant_regression_evidence_ns": 0},
            "delta_ns",
        ),
        (
            {"delta_ns": 100},
            "descendant_regression_evidence_ns",
        ),
    ],
)
def test_attach_reporting_rejects_missing_required_fields(
    result,
    missing_field,
):
    with pytest.raises(ValueError, match=missing_field):
        attach_evidence_reporting([result])


def test_attach_reporting_handles_empty_results():
    assert attach_evidence_reporting([]) == []
