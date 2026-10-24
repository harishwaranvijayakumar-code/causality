import pytest

from causality.focused_benchmark import run_focused_benchmark


def test_benchmark_covers_all_scenarios_and_algorithms():
    results = run_focused_benchmark(
        trace_counts=(3,),
        seeds=(1,),
    )

    assert len(results) == 6
    assert {result["scenario"] for result in results} == {
        "parent_only_regression",
        "parallel_child_regressions",
        "multiple_regressions",
    }
    assert {result["algorithm"] for result in results} == {
        "simple_ranking",
        "execution_aware_ranking",
    }


def test_benchmark_is_reproducible():
    arguments = {
        "trace_counts": (3,),
        "seeds": (5, 6),
    }

    assert run_focused_benchmark(**arguments) == (
        run_focused_benchmark(**arguments)
    )


def test_parent_false_attribution_metric_is_scoped():
    results = run_focused_benchmark(
        trace_counts=(3,),
        seeds=(1,),
    )

    parent_only = next(
        result
        for result in results
        if result["scenario"] == "parent_only_regression"
        and result["algorithm"] == "simple_ranking"
    )
    parallel = next(
        result
        for result in results
        if result["scenario"] == "parallel_child_regressions"
        and result["algorithm"] == "simple_ranking"
    )

    assert parent_only["checkout_negative_assessed_runs"] == 0
    assert parent_only["checkout_false_attribution_rate"] is None
    assert parallel["checkout_negative_assessed_runs"] == 1
    assert parallel["checkout_false_attribution_rate"] in (0.0, 1.0)


def test_benchmark_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="must not be empty"):
        run_focused_benchmark(trace_counts=())

    with pytest.raises(ValueError, match="at least 3"):
        run_focused_benchmark(trace_counts=(2,))

    with pytest.raises(ValueError, match="must not be empty"):
        run_focused_benchmark(seeds=())

    with pytest.raises(ValueError, match="seed must be an integer"):
        run_focused_benchmark(seeds=(True,))