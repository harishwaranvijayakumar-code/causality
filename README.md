# Causality · Distributed Trace Latency Regression Analysis

**Causality** is a distributed tracing analysis tool designed to investigate what changes when a backend system moves from a baseline execution to a degraded execution.

It compares two trace datasets, aggregates operation latency, ranks observed regressions, and presents execution-aware evidence to help engineers investigate potential performance bottlenecks.

**Live application:** [Causality](https://causality-x0qi.onrender.com)

The project is an engineering investigation tool. It does not automatically prove the root cause of a performance regression, and it does not replace distributed tracing, profiling, or production observability systems.

---

# Project Thesis

A distributed application can become slower without an obvious explanation.

A user request may pass through an API gateway, an application service, a database, and several downstream services. A regression in one component can increase the observed duration of multiple operations.

For example:

```text
Baseline execution

API Request              120 ms
    ├── User Service      25 ms
    ├── Product Service   35 ms
    └── Database Query    20 ms
```

After a deployment or infrastructure change:

```text
Degraded execution

API Request              310 ms
    ├── User Service      28 ms
    ├── Product Service  190 ms
    └── Database Query    22 ms
```

The API request became slower, but the latency increase is not distributed evenly across its descendants.

The engineering problem is to identify which operations changed, quantify those changes, and determine which operations deserve further investigation.

Causality approaches this problem through a repeatable workflow:

```text
Collect trace datasets
        ↓
Validate the inputs
        ↓
Normalize trace data
        ↓
Aggregate operation durations
        ↓
Compare baseline and degraded executions
        ↓
Rank observed latency changes
        ↓
Evaluate execution-aware evidence
        ↓
Present findings and limitations
```

The goal is to make performance regression analysis more systematic, explainable, and reproducible.

---

# What Causality Investigates

## 1. Operation Latency Regression

An operation may become significantly slower between two executions.

Causality compares the median duration of matching operations in the baseline and degraded datasets.

For an operation \(o\):

\[
\Delta_o =
M_{\text{degraded},o}
-
M_{\text{baseline},o}
\]

Where:

- \(M_{\text{baseline},o}\) is the baseline median duration.
- \(M_{\text{degraded},o}\) is the degraded median duration.
- \(\Delta_o\) is the observed change in median duration.

A positive delta indicates that the operation's median duration increased.

A negative delta indicates that it became faster.

A zero delta indicates no observed change in median duration.

Causality ranks these changes so that engineers can begin their investigation with the largest observed latency increases.

## 2. Aggregation Across Trace Samples

A single span may not represent the typical behavior of an operation.

An operation can execute multiple times across a dataset, and its duration may vary between traces.

Causality groups spans by operation identity and calculates summary statistics, including:

- Median duration.
- Number of samples.
- Baseline median.
- Degraded median.
- Difference between the two medians.

Using a median helps reduce the influence of individual extreme observations compared with using only an arithmetic mean.

However, a median alone does not describe the entire latency distribution. It does not replace percentiles, histograms, or statistical significance testing.

## 3. Matching Operations Across Datasets

The baseline and degraded datasets may contain different operations.

Causality compares matching operation identities using the service and operation names.

This makes it possible to distinguish an operation that became slower from an operation that appears only in one dataset.

The current regression-ranking workflow focuses on matched operations. An operation missing from one dataset cannot be treated as a direct latency regression without additional assumptions.

## 4. Parent and Descendant Latency Changes

Distributed traces often represent nested or connected execution.

A parent operation can become slower because one of its descendants became slower.

For example:

```text
API Request             +180 ms
    └── Product Service +165 ms
            └── Database Query  +150 ms
```

The API request, product service, and database query all exhibit increased latency.

It would be misleading to conclude that all three operations independently introduced the same amount of additional work.

Causality therefore evaluates descendant regression evidence when ranking candidate operations.

This is an execution-aware heuristic. It helps identify possible parent symptoms, but it does not establish that a particular descendant caused the observed regression.

## 5. Distinguishing Observations from Explanations

Causality deliberately separates measurable observations from interpretations.

An observed median increase is a measurement.

A possible parent symptom is an interpretation based on execution relationships and descendant regression evidence.

A root-cause claim requires additional investigation, such as examining service logs, database behavior, resource utilization, deployment changes, or controlled experiments.

The system must not silently convert a correlation into a causal conclusion.

---

# Core Design Principle

A slower operation is not automatically the root cause of a slower request.

Consider:

```text
Baseline

Request: 100 ms
    ├── Service A: 20 ms
    └── Service B: 30 ms
```

Compared with:

```text
Degraded

Request: 240 ms
    ├── Service A: 22 ms
    └── Service B: 170 ms
```

The observed data indicates that Service B became substantially slower.

That makes Service B a useful investigation target. It does not prove why the operation slowed down.

Possible explanations include:

- A slower database query.
- A downstream dependency delay.
- Resource contention.
- Increased workload.
- A code change.
- Network latency.
- A change in the workload or trace sample.

Causality is designed to narrow the investigation, not invent an explanation that the trace data cannot support.

---

# Architecture

Causality is organized around a trace comparison pipeline.

```text
                     ┌──────────────────────┐
                     │       Engineer       │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │   Django Web UI      │
                     │  Trace Input Form    │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │   Input Adapters     │
                     │                      │
                     │ JSON / File / Jaeger │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │  Input Validation   │
                     │  and Normalization  │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Trace Analysis Core │
                     │                      │
                     │ Aggregation          │
                     │ Regression Ranking   │
                     │ Descendant Evidence  │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Evidence Reporting  │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Comparison Results  │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ Database Persistence│
                     └──────────────────────┘
```

The analysis engine is kept separate from the web interface. This separation allows the core comparison logic to be tested independently of HTTP request handling and HTML rendering.

The input layer supports multiple ways to obtain trace datasets while preserving a common normalized representation for the analysis engine.

---

# Technology Stack

## Backend

- Python
- Django
- Django ORM

## Analysis

- Python dataclasses
- Trace validation and normalization
- Median-based operation aggregation
- Regression ranking
- Execution-aware descendant evidence
- Evidence reporting

## Database

- SQLite for local development by default
- PostgreSQL through `DATABASE_URL`
- Django ORM and migrations for persistence

## Application Server and Static Files

- Gunicorn
- WhiteNoise
- Django templates

## Configuration

- Environment variables
- `python-dotenv`

## Testing

- pytest
- pytest-django
- Django system checks

## Trace Ingestion

- JSON pasted into the web interface
- JSON file uploads
- Jaeger Query API integration

## Frontend

- HTML
- CSS
- JavaScript
- Django templates

The interface uses a fixed dark Spectrum visual system with restrained typography, layered dark surfaces, and pink, violet, blue, and cyan accents.

The UI is intended to present operational evidence clearly rather than behave like a generic administrative dashboard.

---

# Repository Structure

The core project is organized around the following components:

```text
causality/
│
├── causality/
│   ├── trace_analysis.py
│   └── evidence_reporting.py
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── webapp/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── jaeger_client.py
│   └── migrations/
│
├── templates/
│   └── causality/
│       └── compare.html
│
├── tests/
│   ├── test_web_workflow.py
│   ├── test_comparison_persistence.py
│   ├── test_web_limits.py
│   ├── test_evidence_reporting.py
│   └── test_trace_ingestion.py
│
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

The tree highlights the principal application components. Refer to the repository itself for the complete file listing.

The root README documents the project's purpose, architecture, operation, and limitations. The core analysis code and tests provide the implementation details.

---

# Core Analysis Model

## Span

A span represents a timed operation within a trace.

The analysis model includes:

```text
Span
    trace_id
    span_id
    parent_span_id
    service_name
    operation_name
    start_time_ns
    end_time_ns
```

Duration is calculated from the start and end timestamps:

\[
D_{\text{span}} =
T_{\text{end}} - T_{\text{start}}
\]

The canonical representation uses nanosecond timestamps.

Span duration is not necessarily equal to CPU execution time. It represents the interval between the recorded start and end timestamps.

## Operation Identity

Causality groups spans by:

```text
(service_name, operation_name)
```

This defines the operation identity used by the current comparison algorithm.

It is a practical matching key, not a universal identity across all tracing systems. If service or operation names change between datasets, an otherwise equivalent operation may not match.

## Operation Summary

For each operation, Causality calculates:

```text
service_name
operation_name
median_duration_ns
sample_count
```

These summaries provide the input to the baseline-versus-degraded comparison.

## Regression Result

A matched operation receives comparison fields including:

```text
service_name
operation_name
baseline_median_ns
degraded_median_ns
delta_ns
baseline_sample_count
degraded_sample_count
is_regression_candidate
```

Execution-aware analysis adds fields such as:

```text
descendant_regression_evidence_ns
discounted_as_parent_symptom
adjusted_delta_ns
```

These fields allow the reporting layer to distinguish observed latency changes from evidence used to interpret those changes.

---

# Trace Validation

Trace analysis is only useful when the input is structurally valid.

The parser validates the canonical trace dataset before analysis.

The validation rules include:

- Dataset structure is valid.
- Trace identifiers are unique within the dataset.
- Span identifiers are unique within each trace.
- Service and operation names are non-empty.
- Timestamp values are integers and are not booleans.
- Span end timestamps are not earlier than their start timestamps.
- Parent references point to valid spans.
- Parent relationships do not contain cycles.

Invalid input is rejected rather than silently converted into misleading analysis results.

The web workflow also handles malformed JSON, oversized datasets, invalid file input, and relevant ingestion errors through controlled error handling.

---

# Regression Ranking

Causality ranks operation latency changes using baseline and degraded summaries.

For a matched operation:

```text
Baseline median:  40 ms
Degraded median: 190 ms
Delta:           +150 ms
```

The positive delta indicates an observed increase.

The comparison engine considers matched operations and orders results by their latency changes, using deterministic tie-breaking behavior.

The result is a ranked list of investigation candidates.

Importantly, the ranking is based on the observed difference in median duration, not a direct measurement of how much application-wide latency the operation caused.

---

# Execution-Aware Evidence

## Why Descendant Evidence Matters

Suppose an API operation is slower because a downstream database operation is slower.

The parent and descendant may both exhibit positive latency deltas.

A ranking based only on parent duration could make the parent look like an independent source of regression.

Causality examines descendant operation regression evidence to help interpret this situation.

## Evidence Classifications

The evidence-reporting layer uses classifications that include:

```text
no_observed_regression
no_own_regression_descendant_regression_observed
own_regression_no_descendant_regression_observed
possible_parent_symptom
mixed_parent_descendant_evidence
```

These classifications describe patterns in the observed regression and descendant evidence.

They are not proof of causality.

## Adjusted Delta

The execution-aware ranking logic also records an adjusted delta and whether an operation has been discounted as a possible parent symptom.

These are heuristic outputs. They should be interpreted alongside the original median durations, raw delta, sample counts, and trace structure.

The adjusted value is not a replacement for the original measurement.

## Limitations of the Evidence Model

The current approach does not establish causal relationships through controlled intervention or a complete statistical model.

In particular:

- A descendant's latency increase may be correlated with a parent's increase without fully explaining it.
- Concurrent or parallel spans complicate simple additive latency reasoning.
- Missing spans can distort execution relationships.
- Different baseline and degraded workloads can produce misleading comparisons.
- A median does not capture all distribution changes.
- Sampling and instrumentation differences can affect the results.

The tool therefore presents evidence to guide investigation rather than a definitive root-cause verdict.

---

# Trace Input Sources

Causality supports three input paths.

## 1. Paste JSON

Engineers can paste baseline and degraded trace datasets directly into the comparison form.

The input is validated before it reaches the analysis engine.

## 2. Upload JSON Files

Engineers can upload JSON files for the baseline and degraded datasets.

The upload path uses the same normalized trace representation and analysis workflow as pasted JSON.

The current dataset size limit is 1 MiB per dataset.

## 3. Query Jaeger

Causality includes a Jaeger client in `webapp/jaeger_client.py`.

The integration retrieves traces from a configured Jaeger Query endpoint and converts the returned data into Causality's canonical trace representation.

The workflow accepts a service name, time range, and trace limit. The configured query limit is between 1 and 100 traces.

The integration includes response-size and timeout limits and reports connection or response errors through the input workflow.

### Jaeger Configuration

Set the `JAEGER_QUERY_URL` environment variable to the base URL of a Jaeger Query service that is reachable by the Django application.

For local development:

```dotenv
JAEGER_QUERY_URL=http://localhost:16686
```

This value works only when Jaeger is reachable from the same machine or network context as the Django application.

For the hosted application, `localhost` refers to the application container itself. It does not refer to the developer's computer.

Hosted Jaeger ingestion therefore requires a reachable Jaeger-compatible query endpoint and appropriate network access.

The application can be deployed without a hosted Jaeger service, but that does not mean its hosted Jaeger integration has been verified.

---

# Comparison Persistence

Successful comparisons are saved through the Django ORM using the `ComparisonRun` model.

The persisted information includes the input datasets and analysis results, together with comparison metadata such as:

- Creation timestamp.
- Trace counts.
- Matched operation count.
- Regression candidate count.
- Normalized input datasets.
- Ranked analysis results and evidence.

Invalid submissions are not saved as successful comparison runs.

Persistence allows the application to retain the record of an analysis rather than relying exclusively on the currently rendered page.

The application does not currently provide a complete authenticated, per-user comparison-history system. Trace datasets can contain sensitive operational information, so access to the database and application should be configured accordingly.

---

# Input Limits and Error Handling

Causality uses limits to reduce the risk of excessively large or malformed requests.

Current limits include:

| Resource | Limit |
|---|---:|
| Each normalized JSON dataset | 1 MiB |
| Jaeger response | 8 MiB |
| Jaeger trace query | 100 traces |
| Jaeger request timeout | 8 seconds |
| Multipart request body | 3 MiB |

The web application handles malformed JSON, structural validation errors, oversized requests, and Jaeger connection or response errors.

These controls are intended to keep invalid requests from reaching the core analysis logic and to return controlled errors rather than uncontrolled application failures.

They are not a complete substitute for production monitoring, rate limiting, or authentication.

---

# Reliability and Correctness Invariants

Causality is evaluated against explicit correctness expectations.

## Input Integrity

Malformed trace datasets should be rejected before analysis.

## Timestamp Integrity

A span cannot end before it starts.

## Identifier Integrity

Trace and span identifiers must satisfy the parser's uniqueness requirements.

## Parent Relationship Integrity

Parent references must be valid, and parent cycles must be rejected.

## Deterministic Comparison

The same valid datasets should produce consistent comparison results under the same implementation and configuration.

## Measurement Preservation

The original baseline and degraded medians and their delta should remain available even when execution-aware evidence is added.

## Evidence Transparency

A heuristic classification must not be presented as proof of root cause.

## Persistence Integrity

A successful comparison should be saved using the configured database backend.

## Error Isolation

Malformed input, request-size violations, and upstream ingestion errors should produce controlled failures instead of silently creating misleading analysis results.

---

# Testing Philosophy

Causality uses tests to validate the analysis engine, evidence model, web workflow, input handling, and persistence.

The objective is not merely to confirm that the homepage loads. The analysis must also behave correctly on edge cases.

## Core Analysis

Tests cover trace validation, operation aggregation, regression ranking, and execution-aware evidence.

## Evidence Reporting

Tests validate the transformation and reporting of regression evidence, including preservation of relevant fields and classifications.

## Web Workflow

Tests exercise dataset submission, result rendering, and the handling of invalid requests.

## Persistence

Tests validate the saving of successful comparison runs and the associated result data.

## Request Limits

Tests exercise oversized requests and the application's controlled error behavior.

## Trace Ingestion

Tests cover Jaeger client behavior and the conversion and handling of trace responses.

## Validation Commands

Run the Django system check:

```powershell
python manage.py check
```

Run the complete test suite:

```powershell
python -m pytest -q
```

Check dependency consistency:

```powershell
python -m pip check
```

Check whether model changes require migrations:

```powershell
python manage.py makemigrations --check --dry-run
```

Check production settings:

```powershell
python manage.py check --deploy
```

Collect static assets:

```powershell
python manage.py collectstatic --noinput
```

The test suite passed **114 tests** in the development environment during the October 24, 2026 verification session. This is a recorded local result, not a claim that all possible workloads or hosted integration paths have been tested.

---

# Local Development

## Requirements

- Python version compatible with the pinned Django release.
- Git.
- A terminal with PowerShell or equivalent shell support.
- Optional: a reachable Jaeger Query endpoint for testing Jaeger ingestion.

SQLite is the default local database when `DATABASE_URL` is empty.

PostgreSQL is supported when a valid database URL is supplied.

## 1. Clone the Repository

```powershell
git clone https://github.com/harishwaranvijayakumar-code/causality.git
cd causality
```

## 2. Create a Virtual Environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

## 4. Configure Environment Variables

Create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

The example contains local-development defaults, including a placeholder secret and the local Jaeger URL.

Review `.env` before using the application. Keep the file out of Git, and do not use its development secret in production.

For local development without Jaeger, the application can still use the paste-JSON and file-upload input paths.

## 5. Apply Database Migrations

```powershell
python manage.py migrate
```

## 6. Start the Development Server

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

The local application should now be available for trace comparisons.

---

# Production Deployment

Causality is deployed to Render.

**Live application:** [https://causality-x0qi.onrender.com](https://causality-x0qi.onrender.com)

The deployment architecture is:

```text
GitHub Repository
        ↓
Render Web Service
        ↓
Gunicorn
        ↓
Django Application
        ↓
Trace Analysis and Evidence Reporting
        ↓
PostgreSQL
```

WhiteNoise is used to serve static assets from the Django deployment.

## Build Command

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

## Start Command

```bash
python manage.py migrate && gunicorn config.wsgi:application
```

## Production Environment Variables

The deployment requires appropriately configured environment variables.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django's production secret |
| `DEBUG` | Must be `False` in production |
| `ALLOWED_HOSTS` | Permitted hostnames |
| `DATABASE_URL` | PostgreSQL connection URL |
| `JAEGER_QUERY_URL` | Reachable Jaeger Query endpoint |
| `SECURE_HSTS_SECONDS` | HSTS duration, if enabled after HTTPS verification |

Production secrets must be configured through the hosting provider rather than committed to Git.

The database URL must use a supported PostgreSQL URL scheme and must identify a reachable database.

## Deployment Validation

A successful build does not guarantee a correctly configured application.

Deployment validation should include:

- Successful dependency installation.
- Successful static-file collection.
- Successful database migrations.
- Correct hostname configuration.
- HTTPS availability.
- Database connectivity.
- Comparison submission and result rendering.
- Persistence of successful comparison records.
- File-upload validation.
- Jaeger connectivity when a reachable endpoint is configured.

The hosted homepage being available is only one part of deployment validation.

---

# Security and Data Privacy

Trace data can expose sensitive operational information.

Examples include internal service names, database operation details, URLs, identifiers, and attributes attached to spans.

Before uploading or querying trace data:

- Remove credentials and tokens.
- Avoid including personal or confidential attributes unnecessarily.
- Restrict access to the database and tracing infrastructure.
- Keep production secrets out of source control.
- Use HTTPS for public access.
- Ensure the Jaeger endpoint is reachable only through appropriately secured network paths.
- Avoid exposing an unauthenticated tracing interface containing private operational data.

Successful comparisons persist normalized input datasets and results in the configured database. Treat that data as potentially sensitive.

The project is an engineering analysis tool and does not itself guarantee that input trace data is safe to share.

---

# UI and Product Design

Causality's interface is designed as a focused engineering workspace.

The visual goals are:

- Clear information hierarchy.
- Readable operation names and latency values.
- A consistent dark Spectrum theme.
- Layered graphite surfaces.
- Restrained pink, violet, blue, and cyan accents.
- Responsive layouts.
- Clear validation and error messages.
- Direct presentation of comparison evidence.

The interface focuses on the comparison workflow rather than a generic dashboard.

The principal user task is to provide baseline and degraded trace datasets, run the analysis, and inspect the ranked results.

The design intentionally keeps the original measurement and evidence classification visible so that engineers can distinguish a latency observation from its interpretation.

---

# What Causality Does Not Claim

Causality is not:

- A universal distributed tracing backend.
- A replacement for Jaeger or other observability systems.
- A complete distributed profiler.
- A statistical causal-inference platform.
- An automatic root-cause diagnosis system.
- A guarantee that the highest-ranked operation caused the regression.
- A substitute for production monitoring and incident investigation.

The tool identifies observed changes and presents heuristics to prioritize investigation.

Its value is in making trace comparisons repeatable and making the reasoning behind the ranked output visible.

---

# Current Limitations

The current implementation has several limitations that matter when interpreting results.

## Statistical Limitations

The analysis relies on operation medians and sample counts. It does not currently establish statistical significance or model the full latency distribution.

## Matching Limitations

Operations are matched by service name and operation name. Naming changes or instrumentation differences can prevent otherwise related operations from matching.

## Execution-Aware Evidence

Descendant regression evidence is heuristic. It can help identify possible parent symptoms, but it does not prove causal relationships.

## Input Scope

Causality expects trace datasets that can be normalized into its canonical span representation. Arbitrary trace formats may require an adapter.

## Hosted Jaeger

The Jaeger integration is implemented, but hosted ingestion requires a Jaeger Query endpoint reachable from the deployed application.

A local URL such as `http://localhost:16686` does not refer to Jaeger running on a developer's computer when used by the hosted Render service.

## Production Scale

The current deployment is intended for demonstration and engineering investigation. It has not been established as a high-availability, large-scale trace analytics platform.

## Access and History

A complete authenticated, per-user comparison history and access-control model is outside the current implementation.

These limitations define the boundaries of the current system rather than implying that unimplemented capabilities already exist.

---

# Future Engineering Work

Potential next investigations include the following.

## 1. Latency Distribution Analysis

Extend median comparisons with percentile-based summaries and distribution visualizations.

## 2. Statistical Confidence

Investigate whether observed changes are robust to sample size, variance, and workload differences.

## 3. Better Operation Matching

Explore stable operation identities or additional matching strategies when names differ between datasets.

## 4. Critical-Path Analysis

Distinguish operations that contribute to end-to-end request latency from operations that execute concurrently or outside the critical path.

## 5. Richer Execution Evidence

Investigate more precise methods for relating descendant timing changes to parent operation duration.

## 6. Hosted Trace Integration

Connect Causality to a reachable Jaeger-compatible endpoint and validate the integration end to end.

## 7. Comparison History

Add a safe way to browse prior comparisons and inspect their input metadata and results.

## 8. Observability

Add structured application logs and metrics for analysis duration, ingestion failures, validation errors, and request volume.

## 9. Performance Testing

Measure analysis time and memory usage as trace count, span count, and dataset size increase.

## 10. Deployment Hardening

Continue validating production security settings, persistent storage, database behavior, and hosted error handling.

Future work should be marked complete only after implementation and validation evidence exists.

---

# Project Methodology

Causality follows an investigation-driven engineering process:

```text
1. Identify a performance investigation problem.

2. Define the baseline and degraded comparison model.

3. Establish a canonical trace representation.

4. Implement structural validation.

5. Aggregate operation durations.

6. Rank observed latency changes.

7. Add execution-aware evidence.

8. Test edge cases and malformed input.

9. Expose the workflow through a web interface.

10. Persist successful comparison results.

11. Add trace ingestion options.

12. Validate deployment behavior.

13. Document assumptions and limitations.

14. Identify the next measurable improvement.
```

The goal is not to accumulate features without a clear purpose.

Each major component exists to support the central investigation: identifying and explaining observed latency differences between two trace datasets without overstating what the evidence proves.

---

# Key Takeaway

Causality investigates a practical distributed-systems question:

> When a backend system becomes slower, which operations changed, how large were those changes, and what evidence can help an engineer decide where to investigate next?

It addresses that question through:

```text
Trace validation
        +
Operation aggregation
        +
Median-based comparison
        +
Regression ranking
        +
Execution-aware evidence
        +
Controlled error handling
        +
Database persistence
        +
Trace ingestion
        +
Automated tests
        +
Deployment validation
```

The central idea is that performance regression analysis should be systematic and evidence-driven.

A ranked operation is an investigation candidate, not a verdict. Causality aims to make the observations measurable, the reasoning inspectable, and the limitations explicit.
