import pytest

from causality.dataset_generator import generate_experiment
from causality.trace_analysis import (
    parse_traces,
    rank_latency_regressions,
    rank_slowest_spans,
)


def test_generates_requested_number_of_traces():
    experiment = generate_experiment(trace_count=5)

    assert len(experiment.baseline["traces"]) == 5
    assert len(experiment.degraded["traces"]) == 5


def test_generates_valid_trace_relationships():
    experiment = generate_experiment()

    baseline_spans = parse_traces(experiment.baseline)
    degraded_spans = parse_traces(experiment.degraded)

    assert len(baseline_spans) == 30
    assert len(degraded_spans) == 30


def test_injects_known_payment_regression():
    experiment = generate_experiment()

    assert (
        experiment.ground_truth["injected_service"]
        == "payment"
    )
    assert (
        experiment.ground_truth["expected_payment_increase_ns"]
        == 500_000_000
    )


def test_serial_operations_execute_sequentially():
    experiment = generate_experiment(execution_mode="serial")

    trace = experiment.baseline["traces"][0]
    spans = {span["span_id"]: span for span in trace["spans"]}

    inventory = spans["inventory-span"]
    payment = spans["payment-span"]
    root = spans["checkout-root"]

    assert inventory["end_time_ns"] == payment["start_time_ns"]
    assert root["start_time_ns"] == inventory["start_time_ns"]
    assert root["end_time_ns"] == payment["end_time_ns"]


def test_parallel_operations_overlap():
    experiment = generate_experiment(execution_mode="parallel")

    trace = experiment.baseline["traces"][0]
    spans = {span["span_id"]: span for span in trace["spans"]}

    inventory = spans["inventory-span"]
    payment = spans["payment-span"]
    root = spans["checkout-root"]

    assert inventory["start_time_ns"] == payment["start_time_ns"]
    assert inventory["end_time_ns"] > payment["start_time_ns"]
    assert root["end_time_ns"] == max(
        inventory["end_time_ns"],
        payment["end_time_ns"],
    )


def test_fixed_seed_produces_identical_datasets():
    first = generate_experiment(
        seed=123,
        jitter_fraction=0.1,
    )
    second = generate_experiment(
        seed=123,
        jitter_fraction=0.1,
    )

    assert first.baseline == second.baseline
    assert first.degraded == second.degraded
    assert first.ground_truth == second.ground_truth


def test_latency_regression_baseline_detects_payment_increase():
    experiment = generate_experiment()

    baseline = parse_traces(experiment.baseline)
    degraded = parse_traces(experiment.degraded)

    results = rank_latency_regressions(baseline, degraded)

    payment = next(
        result
        for result in results
        if result["service_name"] == "payment"
    )

    assert payment["delta_ns"] == 500_000_000


def test_slowest_span_baseline_ranks_checkout_root_first():
    experiment = generate_experiment(execution_mode="parallel")
    degraded = parse_traces(experiment.degraded)

    results = rank_slowest_spans(degraded)

    # The root span covers the full request duration.
    # This intentionally demonstrates a limitation of absolute-duration
    # ranking: the longest span is not necessarily the injected cause.
    assert results[0]["service_name"] == "checkout"
    assert results[0]["operation_name"] == "checkout_request"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"trace_count": 0},
        {"trace_count": -1},
        {"baseline_payment_ns": 0},
        {"degraded_payment_ns": 100, "baseline_payment_ns": 100},
        {"execution_mode": "unknown"},
        {"jitter_fraction": 1.0},
    ],
)
def test_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        generate_experiment(**kwargs)
