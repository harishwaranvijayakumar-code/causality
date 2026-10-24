
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


MAX_JAEGER_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_JAEGER_TRACES = 100
JAEGER_TIMEOUT_SECONDS = 8


class JaegerError(ValueError):
    """Raised when a Jaeger query fails or returns invalid trace data."""


def _get_json(url):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Causality/1.0",
        },
    )

    try:
        with urlopen(request, timeout=JAEGER_TIMEOUT_SECONDS) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_JAEGER_RESPONSE_BYTES:
                        raise JaegerError(
                            "Jaeger returned a response larger than 8 MiB."
                        )
                except ValueError as exc:
                    if isinstance(exc, JaegerError):
                        raise
                    raise JaegerError(
                        "Jaeger returned an invalid Content-Length header."
                    ) from exc

            raw = response.read(MAX_JAEGER_RESPONSE_BYTES + 1)

    except HTTPError as exc:
        raise JaegerError(
            f"Jaeger returned HTTP {exc.code} for the trace query."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise JaegerError(
            "Could not reach Jaeger. Check JAEGER_QUERY_URL and "
            "confirm that the backend can connect to the Jaeger Query service."
        ) from exc

    if len(raw) > MAX_JAEGER_RESPONSE_BYTES:
        raise JaegerError("Jaeger returned a response larger than 8 MiB.")

    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise JaegerError("Jaeger returned invalid JSON.") from exc


def _convert_legacy_traces(payload):
    data = payload.get("data")
    if not isinstance(data, list):
        raise JaegerError("Jaeger response does not contain a traces list.")

    converted = []

    for trace in data:
        if not isinstance(trace, dict):
            continue

        trace_id = str(trace.get("traceID") or "").strip()
        raw_spans = trace.get("spans", [])
        processes = trace.get("processes", {})

        if not trace_id or not isinstance(raw_spans, list):
            continue

        spans = []

        for span in raw_spans:
            if not isinstance(span, dict):
                continue

            span_id = str(span.get("spanID") or "").strip()
            operation = str(span.get("operationName") or "").strip()

            try:
                start_us = int(span["startTime"])
                duration_us = int(span["duration"])
            except (KeyError, TypeError, ValueError):
                continue

            if not span_id or not operation or duration_us < 0:
                continue

            process = processes.get(span.get("processID"), {})
            if not isinstance(process, dict):
                process = {}

            service_name = str(process.get("serviceName") or "").strip()
            if not service_name:
                service_name = "unknown-service"

            parent_span_id = None
            references = span.get("references", [])
            if isinstance(references, list):
                for reference in references:
                    if (
                        isinstance(reference, dict)
                        and reference.get("refType") == "CHILD_OF"
                    ):
                        parent_span_id = reference.get("spanID") or None
                        break

            spans.append(
                {
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "service_name": service_name,
                    "operation_name": operation,
                    "start_time_ns": start_us * 1000,
                    "end_time_ns": (start_us + duration_us) * 1000,
                }
            )

        if spans:
            converted.append({"trace_id": trace_id, "spans": spans})

    return {"traces": converted}


def _convert_otlp_traces(payload):
    resource_spans = payload.get("resourceSpans")
    if not isinstance(resource_spans, list):
        return None

    converted_by_trace = {}

    for resource in resource_spans:
        if not isinstance(resource, dict):
            continue

        service_name = "unknown-service"
        attributes = resource.get("resource", {}).get("attributes", [])
        if isinstance(attributes, list):
            for attribute in attributes:
                if (
                    isinstance(attribute, dict)
                    and attribute.get("key") == "service.name"
                ):
                    value = attribute.get("value", {})
                    service_name = str(
                        value.get("stringValue") or service_name
                    )
                    break

        scope_groups = resource.get("scopeSpans", [])
        if not isinstance(scope_groups, list):
            continue

        for scope in scope_groups:
            if not isinstance(scope, dict):
                continue

            for span in scope.get("spans", []):
                if not isinstance(span, dict):
                    continue

                trace_id = str(span.get("traceId") or "")
                span_id = str(span.get("spanId") or "")
                operation = str(span.get("name") or "")
                try:
                    start_ns = int(span["startTimeUnixNano"])
                    end_ns = int(span["endTimeUnixNano"])
                except (KeyError, TypeError, ValueError):
                    continue

                if not trace_id or not span_id or not operation:
                    continue
                if end_ns < start_ns:
                    continue

                parent_id = span.get("parentSpanId") or None
                converted_by_trace.setdefault(
                    trace_id, {"trace_id": trace_id, "spans": []}
                )["spans"].append(
                    {
                        "span_id": span_id,
                        "parent_span_id": parent_id,
                        "service_name": service_name,
                        "operation_name": operation,
                        "start_time_ns": start_ns,
                        "end_time_ns": end_ns,
                    }
                )

    return {"traces": list(converted_by_trace.values())}


def _convert_response(payload):
    if not isinstance(payload, dict):
        raise JaegerError("Jaeger returned an unexpected response format.")

    converted = _convert_otlp_traces(payload)
    if converted is None:
        converted = _convert_legacy_traces(payload)

    if not converted["traces"]:
        raise JaegerError(
            "Jaeger returned no usable spans for this service and time range."
        )

    return converted


def fetch_traces(service_name, start_time, end_time, limit=20):
    """Fetch a service's traces and convert them to Causality JSON."""

    endpoint = os.getenv("JAEGER_QUERY_URL", "").strip().rstrip("/")
    if not endpoint:
        raise JaegerError(
            "Jaeger is not configured. Set JAEGER_QUERY_URL in the "
            "backend environment."
        )

    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise JaegerError(
            "JAEGER_QUERY_URL must be a valid HTTP or HTTPS URL."
        )

    service_name = service_name.strip()
    if not service_name:
        raise JaegerError("Enter a Jaeger service name.")
    if len(service_name) > 200:
        raise JaegerError("Jaeger service names must be 200 characters or fewer.")

    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise JaegerError("Trace limit must be an integer.") from exc

    if not 1 <= limit <= MAX_JAEGER_TRACES:
        raise JaegerError(
            f"Trace limit must be between 1 and {MAX_JAEGER_TRACES}."
        )

    if end_time <= start_time:
        raise JaegerError("The Jaeger end time must be after the start time.")

    # Jaeger Query's legacy /api/traces endpoint uses epoch microseconds.
    query = urlencode(
        {
            "service": service_name,
            "start": int(start_time.timestamp() * 1_000_000),
            "end": int(end_time.timestamp() * 1_000_000),
            "limit": limit,
        }
    )
    url = f"{endpoint}/api/traces?{query}"
    return _convert_response(_get_json(url))
