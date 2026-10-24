
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import median
from typing import Any


OperationKey = tuple[str, str]


@dataclass(frozen=True)
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    service_name: str
    operation_name: str
    start_time_ns: int
    end_time_ns: int

    @property
    def duration_ns(self) -> int:
        return self.end_time_ns - self.start_time_ns

    @property
    def operation_key(self) -> OperationKey:
        return self.service_name, self.operation_name


def parse_traces(data: dict[str, Any]) -> list[Span]:
    """Parse and validate a dataset containing a list of traces."""
    if not isinstance(data, dict):
        raise ValueError("Dataset must be a JSON object.")

    traces = data.get("traces")
    if not isinstance(traces, list):
        raise ValueError("'traces' must be a list.")

    spans: list[Span] = []
    seen_trace_ids: set[str] = set()

    for trace in traces:
        if not isinstance(trace, dict):
            raise ValueError("Each trace must be an object.")

        trace_id = trace.get("trace_id")
        raw_spans = trace.get("spans")

        if not isinstance(trace_id, str) or not trace_id:
            raise ValueError("Every trace needs a non-empty trace_id.")

        if trace_id in seen_trace_ids:
            raise ValueError(f"Duplicate trace_id: {trace_id!r}.")
        seen_trace_ids.add(trace_id)

        if not isinstance(raw_spans, list):
            raise ValueError("Each trace must contain a spans list.")

        local_ids: set[str] = set()
        parent_by_id: dict[str, str | None] = {}
        parsed_trace_spans: list[Span] = []

        for raw in raw_spans:
            if not isinstance(raw, dict):
                raise ValueError("Each span must be an object.")

            span_id = raw.get("span_id")
            parent_id = raw.get("parent_span_id")
            service = raw.get("service_name")
            operation = raw.get("operation_name")
            start = raw.get("start_time_ns")
            end = raw.get("end_time_ns")

            if not isinstance(span_id, str) or not span_id:
                raise ValueError("Every span needs a non-empty span_id.")

            if span_id in local_ids:
                raise ValueError(
                    f"Duplicate span_id {span_id!r} in trace {trace_id!r}."
                )
            local_ids.add(span_id)

            if parent_id is not None and (
                not isinstance(parent_id, str) or not parent_id
            ):
                raise ValueError(
                    "parent_span_id must be a non-empty string or null."
                )

            if not isinstance(service, str) or not service:
                raise ValueError("Every span needs a service_name.")

            if not isinstance(operation, str) or not operation:
                raise ValueError("Every span needs an operation_name.")

            if (
                isinstance(start, bool)
                or not isinstance(start, int)
                or isinstance(end, bool)
                or not isinstance(end, int)
            ):
                raise ValueError("Span timestamps must be integers.")

            if end < start:
                raise ValueError(f"Span {span_id!r} ends before it starts.")

            parent_by_id[span_id] = parent_id
            parsed_trace_spans.append(
                Span(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_id,
                    service_name=service,
                    operation_name=operation,
                    start_time_ns=start,
                    end_time_ns=end,
                )
            )

        for span_id, parent_id in parent_by_id.items():
            if parent_id is not None and parent_id not in local_ids:
                raise ValueError(
                    f"Span {span_id!r} references missing parent "
                    f"{parent_id!r} in trace {trace_id!r}."
                )

        for span_id in local_ids:
            visited: set[str] = set()
            current: str | None = span_id

            while current is not None:
                if current in visited:
                    raise ValueError(
                        f"Parent cycle detected in trace {trace_id!r}."
                    )
                visited.add(current)
                current = parent_by_id[current]

        spans.extend(parsed_trace_spans)

    return spans


def group_operations(
    spans: list[Span],
) -> dict[OperationKey, list[Span]]:
    """Group span instances by service and operation name."""
    grouped: dict[OperationKey, list[Span]] = defaultdict(list)

    for span in spans:
        grouped[span.operation_key].append(span)

    return dict(grouped)


def summarize_operations(
    spans: list[Span],
) -> dict[OperationKey, dict[str, int]]:
    """Calculate median duration and sample count per operation."""
    grouped = group_operations(spans)
    summaries: dict[OperationKey, dict[str, int]] = {}

    for key, operation_spans in grouped.items():
        durations = [span.duration_ns for span in operation_spans]
        summaries[key] = {
            "median_duration_ns": int(median(durations)),
            "sample_count": len(durations),
        }

    return summaries


def rank_slowest_spans(
    spans: list[Span],
) -> list[dict[str, Any]]:
    """Rank operations by median observed duration."""
    summaries = summarize_operations(spans)

    results = [
        {
            "service_name": service,
            "operation_name": operation,
            **summary,
        }
        for (service, operation), summary in summaries.items()
    ]

    return sorted(
        results,
        key=lambda item: (
            -item["median_duration_ns"],
            item["service_name"],
            item["operation_name"],
        ),
    )


def rank_latency_regressions(
    baseline_spans: list[Span],
    degraded_spans: list[Span],
) -> list[dict[str, Any]]:
    """
    Rank matched operations by median-duration increase.

    All matched operations are returned, including unchanged or faster
    operations. Positive deltas are measured regressions, not proof
    that an operation caused the overall request slowdown.
    """
    baseline = summarize_operations(baseline_spans)
    degraded = summarize_operations(degraded_spans)

    results: list[dict[str, Any]] = []

    for key, degraded_summary in degraded.items():
        baseline_summary = baseline.get(key)
        if baseline_summary is None:
            continue

        baseline_duration = baseline_summary["median_duration_ns"]
        degraded_duration = degraded_summary["median_duration_ns"]
        delta = degraded_duration - baseline_duration

        results.append(
            {
                "service_name": key[0],
                "operation_name": key[1],
                "baseline_median_ns": baseline_duration,
                "degraded_median_ns": degraded_duration,
                "delta_ns": delta,
                "baseline_samples": baseline_summary["sample_count"],
                "degraded_samples": degraded_summary["sample_count"],
                "is_regression_candidate": delta > 0,
            }
        )

    return sorted(
        results,
        key=lambda item: (
            -item["delta_ns"],
            item["service_name"],
            item["operation_name"],
        ),
    )


def _operation_descendants(
    spans: list[Span],
) -> dict[OperationKey, set[OperationKey]]:
    """Return structurally observed descendant operation types."""
    by_trace: dict[str, dict[str, Span]] = defaultdict(dict)

    for span in spans:
        by_trace[span.trace_id][span.span_id] = span

    descendants: dict[OperationKey, set[OperationKey]] = defaultdict(set)

    for trace_spans in by_trace.values():
        children: dict[str, list[Span]] = defaultdict(list)

        for span in trace_spans.values():
            if span.parent_span_id is not None:
                children[span.parent_span_id].append(span)

        for parent in trace_spans.values():
            pending = list(children[parent.span_id])
            visited: set[str] = set()

            while pending:
                child = pending.pop()

                if child.span_id in visited:
                    continue
                visited.add(child.span_id)

                if child.operation_key != parent.operation_key:
                    descendants[parent.operation_key].add(
                        child.operation_key
                    )

                pending.extend(children[child.span_id])

    return dict(descendants)


def classify_regression_evidence(
    delta_ns: int,
    descendant_regression_evidence_ns: int,
) -> str:
    """
    Classify observed evidence without claiming causal certainty.

    Descendant evidence is the maximum positive descendant operation
    delta, not the sum. The comparison is heuristic and does not establish
    critical-path membership or independent causation.
    """
    if delta_ns <= 0:
        return "no_observed_regression"

    if descendant_regression_evidence_ns <= 0:
        return "no_descendant_regression_observed"

    if descendant_regression_evidence_ns >= delta_ns:
        return "possible_parent_symptom"

    return "mixed_parent_descendant_evidence"


def rank_execution_aware_regressions(
    baseline_spans: list[Span],
    degraded_spans: list[Span],
) -> list[dict[str, Any]]:
    """
    Rank latency regressions using structural descendant evidence.

    All matched operations remain visible. The heuristic adjusts ranking
    priority but does not remove candidates or prove causal attribution.
    """
    regression_results = rank_latency_regressions(
        baseline_spans,
        degraded_spans,
    )

    deltas: dict[OperationKey, int] = {
        (item["service_name"], item["operation_name"]): item["delta_ns"]
        for item in regression_results
    }

    descendants = _operation_descendants(degraded_spans)
    results: list[dict[str, Any]] = []

    for item in regression_results:
        key = (item["service_name"], item["operation_name"])
        delta = item["delta_ns"]

        positive_descendant_deltas = [
            deltas.get(child_key, 0)
            for child_key in descendants.get(key, set())
            if deltas.get(child_key, 0) > 0
        ]

        # Do not sum parallel child deltas as if they were sequential.
        max_descendant_delta = max(positive_descendant_deltas, default=0)

        evidence_classification = classify_regression_evidence(
            delta,
            max_descendant_delta,
        )

        discounted = evidence_classification == "possible_parent_symptom"

        result = dict(item)
        result["descendant_regression_evidence_ns"] = max_descendant_delta
        result["evidence_classification"] = evidence_classification
        result["discounted_as_parent_symptom"] = discounted

        # Preserve measured delta separately from adjusted ranking priority.
        result["adjusted_delta_ns"] = 0 if discounted else delta

        results.append(result)

    return sorted(
        results,
        key=lambda item: (
            -item["adjusted_delta_ns"],
            -item["delta_ns"],
            item["service_name"],
            item["operation_name"],
        ),
    )
