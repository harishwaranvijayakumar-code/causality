import pytest

from causality.trace_analysis import (
    parse_traces,
    rank_execution_aware_regressions,
    rank_latency_regressions,
    rank_slowest_spans,
)


def make_dataset(payment_duration: int) -> dict:
    return {
        "traces": [
            {
                "trace_id": "trace-1",
                "spans": [
                    {
                        "span_id": "root",
                        "parent_span_id": None,
                        "service_name": "checkout",
                        "operation_name": "request",
                        "start_time_ns": 0,
                        "end_time_ns": 100,
                    },
                    {
                        "span_id": "payment",
                        "parent_span_id": "root",
                        "service_name": "payment",
                        "operation_name": "authorize",
                        "start_time_ns": 100,
                        "end_time_ns": 100 + payment_duration,
                    },
                    {
                        "span_id": "inventory",
                        "parent_span_id": "root",
                        "service_name": "inventory",
                        "operation_name": "reserve",
                        "start_time_ns": 100,
                        "end_time_ns": 300,
                    },
                ],
            }
        ]
    }


def test_parse_traces_calculates_span_duration():
    spans = parse_traces(make_dataset(400))
    payment = next(span for span in spans if span.span_id == "payment")

    assert payment.duration_ns == 400
    assert payment.operation_key == ("payment", "authorize")


def test_slowest_span_ranking():
    spans = parse_traces(make_dataset(700))
    results = rank_slowest_spans(spans)

    assert results[0]["service_name"] == "payment"
    assert results[0]["median_duration_ns"] == 700


def test_latency_regression_ranking():
    baseline = parse_traces(make_dataset(200))
    degraded = parse_traces(make_dataset(700))
    results = rank_latency_regressions(baseline, degraded)

    assert results[0]["service_name"] == "payment"
    assert results[0]["delta_ns"] == 500


def test_rejects_duplicate_span_ids():
    dataset = make_dataset(400)
    dataset["traces"][0]["spans"].append(
        dataset["traces"][0]["spans"][0].copy()
    )

    with pytest.raises(ValueError, match="Duplicate span_id"):
        parse_traces(dataset)


def test_rejects_missing_parent():
    dataset = make_dataset(400)
    dataset["traces"][0]["spans"][1]["parent_span_id"] = "missing"

    with pytest.raises(ValueError, match="missing parent"):
        parse_traces(dataset)


def test_rejects_negative_duration():
    dataset = make_dataset(400)
    dataset["traces"][0]["spans"][1]["end_time_ns"] = 50

    with pytest.raises(ValueError, match="ends before it starts"):
        parse_traces(dataset)


def test_rejects_parent_cycle():
    dataset = make_dataset(400)
    dataset["traces"][0]["spans"][0]["parent_span_id"] = "payment"

    with pytest.raises(ValueError, match="Parent cycle"):
        parse_traces(dataset)


def test_rejects_duplicate_trace_ids():
    dataset = make_dataset(400)
    duplicate = dataset["traces"][0].copy()
    duplicate["spans"] = [
        span.copy() for span in duplicate["spans"]
    ]
    dataset["traces"].append(duplicate)

    with pytest.raises(ValueError, match="Duplicate trace_id"):
        parse_traces(dataset)


def test_latency_regression_excludes_unmatched_operations():
    baseline = parse_traces(make_dataset(200))
    degraded_data = make_dataset(700)
    degraded_data["traces"][0]["spans"][1]["service_name"] = "new-payment"
    degraded = parse_traces(degraded_data)

    results = rank_latency_regressions(baseline, degraded)

    assert all(
        item["service_name"] != "new-payment"
        for item in results
    )


def test_execution_aware_ranking_discounts_parent_symptom():
    from causality.dataset_generator import generate_experiment

    experiment = generate_experiment(execution_mode="parallel")
    baseline = parse_traces(experiment.baseline)
    degraded = parse_traces(experiment.degraded)

    results = rank_execution_aware_regressions(baseline, degraded)

    assert results[0]["service_name"] == "payment"
    assert results[0]["operation_name"] == "authorize_payment"

    checkout = next(
        item for item in results
        if item["service_name"] == "checkout"
    )
    assert checkout["discounted_as_parent_symptom"] is True


def test_execution_aware_ranking_preserves_unchanged_operation():
    from causality.dataset_generator import generate_experiment

    experiment = generate_experiment(execution_mode="parallel")
    baseline = parse_traces(experiment.baseline)
    degraded = parse_traces(experiment.degraded)

    results = rank_execution_aware_regressions(baseline, degraded)

    inventory = next(
        item for item in results
        if item["service_name"] == "inventory"
    )
    assert inventory["delta_ns"] == 0
    assert inventory["adjusted_delta_ns"] == 0
