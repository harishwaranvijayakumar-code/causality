
# Causality

Causality is an experimental tool for investigating latency regressions in distributed traces. It compares baseline and degraded trace datasets, ranks operation-level latency changes, and presents evidence that may help engineers investigate potential contributors.

## Current status

The project includes:

- A trace-analysis package that operates independently of Django.
- Execution-aware regression ranking and evidence reporting.
- A Django web workflow for comparing baseline and degraded JSON datasets.
- Input validation and dataset-size limits.
- Automated tests for analysis behavior, edge cases, and the web workflow.
- Synthetic experiments and benchmark scripts.
- A database model for storing successful comparison runs, including their input datasets, summary metrics, and ranked results.

The last verified state before the persistence changes completed with 103 passing tests. The persistence changes must be verified with the commands in the Testing section before they can be considered complete.

## Technology

- Python
- Django
- PostgreSQL support, with SQLite for local development
- Django ORM and migrations
- Django templates and static files
- Gunicorn and WhiteNoise
- `python-dotenv`
- pytest and pytest-django

## Prerequisites

- A Python version compatible with the pinned dependencies
- Git

## Local setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

The default local configuration uses SQLite. Keep `DEBUG=True` only for local development. Do not commit `.env` or production secrets.

Apply database migrations and check the configuration:

```powershell
python manage.py makemigrations webapp
python manage.py migrate
python manage.py check
```

If Django reports that no model changes are detected, confirm that `webapp/models.py` exists and defines `ComparisonRun`.

Start the development server:

```powershell
python manage.py runserver
```

Open `http://127.0.0.1:8000/` to use the trace comparison workflow.

The health endpoint is available at `http://127.0.0.1:8000/health/`.

## Using the comparison workflow

1. Open the home page.
2. Provide a baseline trace dataset as JSON.
3. Provide a degraded trace dataset using the supported trace structure.
4. Submit the comparison.
5. Review matched operations, latency changes, and evidence classifications.
6. If the comparison succeeds and the database save completes, note the saved comparison record ID displayed with the results.

The form includes example datasets. Each dataset is limited to 1 MiB. Malformed or unsupported input must be corrected before retrying.

## Persistence

Successful comparisons are stored in the configured database using the Django ORM.

Each saved comparison contains:

- Creation timestamp.
- Baseline and degraded trace counts.
- Matched operation count.
- Regression candidate count.
- Baseline input dataset.
- Degraded input dataset.
- Ranked analysis results and evidence reporting.

Invalid submissions are not saved. If the analysis succeeds but the database save fails, the workflow reports a save error rather than presenting the comparison as successfully persisted.

The current workflow displays the saved record ID but does not yet provide a user-facing history or retrieval page. There is also no user authentication or per-user separation of saved records.

**Data handling:** raw trace datasets can contain service names, operation names, identifiers, and other operational details. Treat the configured database as sensitive, restrict database access, and define a retention policy before using real production traces. Do not deploy this version as a multi-user service without reviewing authentication and authorization.

## Tests and checks

Run the persistence tests:

```powershell
python -m pytest tests\test_comparison_persistence.py -q
```

Run the complete test suite:

```powershell
python -m pytest -q
```

Run Django's system checks:

```powershell
python manage.py check
```

Check installed dependency consistency:

```powershell
python -m pip check
```

Check the current Git diff for whitespace errors:

```powershell
git diff --check
```

Collect static files when preparing a deployment:

```powershell
python manage.py collectstatic --noinput
```

Do not consider persistence complete until the migration succeeds and all relevant tests pass.

## Experimental scripts

The analysis and benchmark scripts remain separate from Django views and templates:

```powershell
python run_experiments.py
python run_sensitivity_experiments.py
python run_focused_benchmark.py
python run_evidence_report.py
```

## Environment variables

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django signing and security secret |
| `DEBUG` | Enables or disables Django debug mode |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames |
| `DATABASE_URL` | Optional SQLite or PostgreSQL connection URL |

Production deployments must set a secure `SECRET_KEY`, set `DEBUG=False`, configure `ALLOWED_HOSTS`, and provide an appropriate database configuration.

Never commit `.env` or production secrets.

## Architecture

- `causality/` contains domain analysis and evidence logic.
- `webapp/` contains Django request handling and persistence models.
- `templates/` contains the HTML interface.
- `tests/` contains automated tests.
- `config/` contains Django project settings and URL configuration.
- Experimental scripts remain outside the web request workflow.

The domain analysis layer should remain independent of Django views and database persistence. The web layer validates requests, invokes the analysis functions, prepares display results, and stores successful comparisons.

## Interpretation and limitations

The ranking methods use operation-level latency changes and descendant-span evidence. These signals can help prioritize investigation, but correlation and trace evidence do not prove causation.

Execution-aware classifications are heuristics. They are not proof that a particular operation caused the observed latency regression.

Synthetic benchmark results are not proof of production accuracy. Causality should be treated as an investigation aid, not an automatic root-cause oracle.

## Development decisions and deviations

The implementation avoids queues and background workers because the current synchronous comparison workflow does not establish a need for them.

GitHub Actions CI and an additional linting tool are not configured. These remain explicit deviations from the general development checklist, not completed tasks.

The persistence implementation, database migration, and related tests must be verified before the project status is updated to mark persistence complete.
