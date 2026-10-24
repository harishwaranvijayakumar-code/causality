import pytest

from causality.sensitivity_analysis import (
    run_sensitivity_experiments,
)


def test_sensitivity_runner_returns_both_algorithms():
    results = run_sensitivity_experiments(
        trace_counts=(3,),
        seeds=(1,),
    )

    assert len(results) == 8

    for result in results:
        assert result["repeat_count"] == 1
        assert result["algorithm"] in {
            "simple_ranking",
            "execution_aware_ranking",
        }
        assert result["scenario"] in {
            "small_regression",
            "magnitude_10ns_noise_10pct",
            "magnitude_100ns_noise_0pct",
            "magnitude_100ns_noise_10pct",
        }


def test_sensitivity_runner_is_reproducible():
    first = run_sensitivity_experiments(
        trace_counts=(3,),
        seeds=(7, 8),
    )
    second = run_sensitivity_experiments(
        trace_counts=(3,),
        seeds=(7, 8),
    )

    assert first == second


def test_sensitivity_runner_rejects_invalid_trace_counts():
    with pytest.raises(ValueError, match="at least 3"):
        run_sensitivity_experiments(trace_counts=(2,), seeds=(1,))


def test_sensitivity_runner_rejects_empty_inputs():
    with pytest.raises(ValueError, match="at least one"):
        run_sensitivity_experiments(trace_counts=(), seeds=(1,))

    with pytest.raises(ValueError, match="at least one"):
        run_sensitivity_experiments(trace_counts=(3,), seeds=())


def test_sensitivity_runner_rejects_boolean_seed():
    with pytest.raises(ValueError, match="seed must be an integer"):
        run_sensitivity_experiments(trace_counts=(3,), seeds=(True,))