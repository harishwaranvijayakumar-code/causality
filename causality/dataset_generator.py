from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Literal


ExecutionMode = Literal["serial", "parallel"]


@dataclass(frozen=True)
class GeneratedExperiment:
    """Trace datasets plus ground truth for a controlled experiment."""

    baseline: dict[str, Any]
    degraded: dict[str, Any]
    ground_truth: dict[str, Any]


def _build_trace(
    *,
    trace_id: str,
    execution_mode: ExecutionMode,
    payment_duration_ns: int,
    inventory_duration_ns: int,
) -> dict[str, Any]:
    """Build one trace with consistent root and child intervals."""

    if execution_mode not in ("serial", "parallel"):
        raise ValueError(
            "execution_mode must be 'serial' or 'parallel'."
        )

    if payment_duration_ns <= 0 or inventory_duration_ns <= 0:
        raise ValueError("Operation durations must be positive.")

    root_start = 0

    if execution_mode == "serial":
        inventory_start = root_start
        inventory_end = inventory_start + inventory_duration_ns

        payment_start = inventory_end
        payment_end = payment_start + payment_duration_ns

    else:
        inventory_start = root_start
        inventory_end = inventory_start + inventory_duration_ns

        payment_start = root_start
        payment_end = payment_start + payment_duration_ns

    root_end = max(inventory_end, payment_end)

    return {
        "trace_id": trace_id,
        "spans": [
            {
                "span_id": "checkout-root",
                "parent_span_id": None,
                "service_name": "checkout",
                "operation_name": "checkout_request",
                "start_time_ns": root_start,
                "end_time_ns": root_end,
                "status": "ok",
            },
            {
                "span_id": "inventory-span",
                "parent_span_id": "checkout-root",
                "service_name": "inventory",
                "operation_name": "reserve_inventory",
                "start_time_ns": inventory_start,
                "end_time_ns": inventory_end,
                "status": "ok",
            },
            {
                "span_id": "payment-span",
                "parent_span_id": "checkout-root",
                "service_name": "payment",
                "operation_name": "authorize_payment",
                "start_time_ns": payment_start,
                "end_time_ns": payment_end,
                "status": "ok",
            },
        ],
    }


def generate_experiment(
    *,
    execution_mode: ExecutionMode = "parallel",
    trace_count: int = 10,
    baseline_payment_ns: int = 200_000_000,
    degraded_payment_ns: int = 700_000_000,
    inventory_duration_ns: int = 150_000_000,
    seed: int = 42,
    jitter_fraction: float = 0.0,
) -> GeneratedExperiment:
    """
    Generate comparable baseline and degraded trace datasets.

    The known regression is injected into payment.authorize_payment.
    Ground truth is returned separately from the trace datasets.

    Jitter is disabled by default. When enabled, each operation duration
    varies by a reproducible random fraction around its configured value.
    """

    if execution_mode not in ("serial", "parallel"):
        raise ValueError(
            "execution_mode must be 'serial' or 'parallel'."
        )

    if isinstance(trace_count, bool) or not isinstance(trace_count, int):
        raise ValueError("trace_count must be an integer.")

    if trace_count < 1:
        raise ValueError("trace_count must be at least 1.")

    durations = (
        baseline_payment_ns,
        degraded_payment_ns,
        inventory_duration_ns,
    )

    if any(
        isinstance(duration, bool)
        or not isinstance(duration, int)
        or duration <= 0
        for duration in durations
    ):
        raise ValueError("All configured durations must be positive integers.")

    if (
        isinstance(jitter_fraction, bool)
        or not isinstance(jitter_fraction, (int, float))
        or not 0 <= jitter_fraction < 1
    ):
        raise ValueError("jitter_fraction must be in the range [0, 1).")

    if degraded_payment_ns <= baseline_payment_ns:
        raise ValueError(
            "degraded_payment_ns must exceed baseline_payment_ns."
        )

    rng = random.Random(seed)

    def vary_duration(duration_ns: int) -> int:
        if jitter_fraction == 0:
            return duration_ns

        lower = 1.0 - jitter_fraction
        upper = 1.0 + jitter_fraction

        varied = int(duration_ns * rng.uniform(lower, upper))
        return max(1, varied)

    baseline_traces: list[dict[str, Any]] = []
    degraded_traces: list[dict[str, Any]] = []

    for index in range(trace_count):
        baseline_traces.append(
            _build_trace(
                trace_id=f"baseline-{index + 1}",
                execution_mode=execution_mode,
                payment_duration_ns=vary_duration(
                    baseline_payment_ns
                ),
                inventory_duration_ns=vary_duration(
                    inventory_duration_ns
                ),
            )
        )

        degraded_traces.append(
            _build_trace(
                trace_id=f"degraded-{index + 1}",
                execution_mode=execution_mode,
                payment_duration_ns=vary_duration(
                    degraded_payment_ns
                ),
                inventory_duration_ns=vary_duration(
                    inventory_duration_ns
                ),
            )
        )

    baseline = {"traces": baseline_traces}
    degraded = {"traces": degraded_traces}

    ground_truth = {
        "injected_service": "payment",
        "injected_operation": "authorize_payment",
        "execution_mode": execution_mode,
        "baseline_payment_duration_ns": baseline_payment_ns,
        "degraded_payment_duration_ns": degraded_payment_ns,
        "expected_payment_increase_ns": (
            degraded_payment_ns - baseline_payment_ns
        ),
        "trace_count_per_dataset": trace_count,
        "seed": seed,
        "jitter_fraction": jitter_fraction,
    }

    return GeneratedExperiment(
        baseline=baseline,
        degraded=degraded,
        ground_truth=ground_truth,
    )
