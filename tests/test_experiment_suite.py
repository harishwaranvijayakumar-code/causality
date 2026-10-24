import pytest

from causality.experiment_suite import (
    build_experiment_cases,
    evaluate_ranking,
    run_experiment_suite,
    summarize_experiment_suite,
)


PAYMENT = ("payment", "authorize_payment")
INVENTORY = ("inventory", "reserve_inventory")
CHECKOUT = ("checkout", "checkout_request")


def _result(key, delta_ns=None):
    result = {
        "service_name": key[0],
        "operation_name": key[1],
    }
    if delta_ns is not None:
        result["delta_ns"] = delta_ns
    return result


def test_builds_all_twelve_scenarios():
    cases = build_experiment_cases()

    assert len(cases) == 12
    assert {case.name for case in cases} == {
        "single_regression",
        "multiple_regressions",
        "parent_only_regression",
        "serial_execution",
        "noisy_traces",
        "incomplete_traces",
        "parallel_child_regressions",
        "small_regression",
        "child_regression_unchanged_parent",
        "magnitude_10ns_noise_10pct",
        "magnitude_100ns_noise_0pct",
        "magnitude_100ns_noise_10pct",
    }


def test_experiment_cases_are_reproducible():
    assert build_experiment_cases(seed=123) == build_experiment_cases(seed=123)


def test_evaluation_finds_ground_truth_at_rank_one():
    metrics = evaluate_ranking(
        [_result(PAYMENT), _result(CHECKOUT)],
        frozenset({PAYMENT}),
        frozenset({CHECKOUT}),
    )

    assert metrics["top1_hit"] == 1
    assert metrics["top3_hit"] == 1
    assert metrics["ground_truth_recall"] == 1.0
    assert metrics["precision"] == 0.5
    assert metrics["true_positive_count"] == 1
    assert metrics["false_positive_count"] == 1


def test_evaluation_handles_multiple_causes():
    metrics = evaluate_ranking(
        [_result(PAYMENT), _result(INVENTORY)],
        frozenset({PAYMENT, INVENTORY}),
        frozenset({CHECKOUT}),
    )

    assert metrics["top1_hit"] == 1
    assert metrics["top3_hit"] == 1
    assert metrics["ground_truth_recall"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["true_positive_count"] == 2


def test_unchanged_operations_are_not_positive_candidates():
    metrics = evaluate_ranking(
        [_result(CHECKOUT, 0), _result(INVENTORY, -10)],
        frozenset(),
        frozenset({CHECKOUT, INVENTORY}),
    )

    assert metrics["positive_candidate_count"] == 0
    assert metrics["false_positive_count"] == 0
    assert metrics["precision"] is None
    assert metrics["ranked_operations"] == []
    assert len(metrics["all_ranked_operations"]) == 2


def test_false_positives_require_explicit_negative_labels():
    metrics = evaluate_ranking(
        [_result(CHECKOUT, 10)],
        frozenset({PAYMENT}),
    )

    assert metrics["false_positive_count"] == 0
    assert metrics["unassessed_prediction_count"] == 1
    assert metrics["precision"] is None


def test_evaluation_handles_no_known_regression():
    metrics = evaluate_ranking(
        [_result(INVENTORY, 10)],
        frozenset(),
        frozenset({INVENTORY}),
    )

    assert metrics["top1_hit"] == 0
    assert metrics["top3_hit"] == 0
    assert metrics["ground_truth_recall"] is None
    assert metrics["evaluation_status"] == "not_evaluable_no_ground_truth"
    assert metrics["false_positive_count"] == 1
    assert metrics["precision"] == 0.0


def test_incomplete_scenario_reports_payment_as_unmatched():
    report = next(
        item
        for item in run_experiment_suite()
        if item["scenario"] == "incomplete_traces"
    )

    assert report["ground_truth"] == []
    assert report["comparison_coverage"]["baseline_only_operations"] == [
        PAYMENT
    ]
    assert report["simple_ranking"]["positive_candidate_count"] == 0
    assert (
        report["simple_ranking"]["evaluation_status"]
        == "not_evaluable_no_ground_truth"
    )
    assert report["simple_ranking"]["ground_truth_recall"] is None
    assert report["simple_ranking"]["precision"] is None


def test_small_regression_is_isolated_to_payment():
    report = next(
        item
        for item in run_experiment_suite()
        if item["scenario"] == "small_regression"
    )

    simple = report["simple_ranking"]
    aware = report["execution_aware_ranking"]

    assert simple["ranked_operations"] == [PAYMENT]
    assert aware["ranked_operations"] == [PAYMENT]
    assert simple["top1_hit"] == 1
    assert aware["top1_hit"] == 1
    assert simple["ground_truth_recall"] == 1.0
    assert aware["ground_truth_recall"] == 1.0


def test_magnitude_and_noise_scenarios_have_explicit_ground_truth():
    cases = {
        case.name: case
        for case in build_experiment_cases()
    }

    expected = {
        "magnitude_10ns_noise_10pct",
        "magnitude_100ns_noise_0pct",
        "magnitude_100ns_noise_10pct",
    }

    assert expected.issubset(cases)
    for name in expected:
        assert cases[name].ground_truth == frozenset({PAYMENT})
        assert cases[name].known_negative == frozenset({CHECKOUT, INVENTORY})


def test_magnitude_noise_cases_are_reproducible():
    first = build_experiment_cases(seed=77)
    second = build_experiment_cases(seed=77)

    first_cases = {case.name: case for case in first}
    second_cases = {case.name: case for case in second}

    for name in (
        "magnitude_10ns_noise_10pct",
        "magnitude_100ns_noise_0pct",
        "magnitude_100ns_noise_10pct",
    ):
        assert first_cases[name] == second_cases[name]


def test_parallel_child_scenario_has_two_injected_regressions():
    case = next(
        item
        for item in build_experiment_cases()
        if item.name == "parallel_child_regressions"
    )

    assert case.ground_truth == frozenset({PAYMENT, INVENTORY})
    assert case.known_negative == frozenset({CHECKOUT})


def test_child_regression_can_exist_without_parent_duration_change():
    report = next(
        item
        for item in run_experiment_suite()
        if item["scenario"] == "child_regression_unchanged_parent"
    )

    assert report["comparison_coverage"]["matched_operation_count"] == 3
    assert report["simple_ranking"]["top1_hit"] == 1
    assert report["execution_aware_ranking"]["top1_hit"] == 1


def test_suite_compares_both_algorithms_for_every_scenario():
    reports = run_experiment_suite()

    assert len(reports) == 12

    for report in reports:
        assert "simple_ranking" in report
        assert "execution_aware_ranking" in report
        assert "ground_truth" in report
        assert "known_negative" in report
        assert "comparison_coverage" in report
        assert "coverage_unit" in report["comparison_coverage"]


def test_summary_excludes_unevaluable_scenario_from_metric_means():
    reports = run_experiment_suite()
    summary = summarize_experiment_suite(reports)

    assert summary["scenario_count"] == 12
    assert summary["unevaluable_scenario_count"] == 1
    assert summary["evaluable_scenario_count"] == 11

    aware = summary["algorithms"]["execution_aware_ranking"]
    assert aware["evaluable_scenarios"] == 11
    assert aware["unevaluable_scenarios"] == 1
    assert aware["top1_hit_rate"] is not None
    assert aware["mean_recall"] is not None


def test_trace_count_validation():
    with pytest.raises(ValueError, match="at least 3"):
        build_experiment_cases(trace_count=2)

    with pytest.raises(ValueError, match="must be an integer"):
        build_experiment_cases(trace_count=True)