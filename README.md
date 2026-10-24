# Causality

Causality is an experimental tool for investigating latency regressions in distributed traces. It compares baseline and degraded trace datasets, ranks operation-level latency changes, and presents evidence that may help engineers investigate potential contributors.

## Current status

The core trace-analysis and synthetic-experiment modules exist, and the current test suite contains 79 passing tests. The Django foundation is being established.

The product does not yet have a completed upload-to-results web workflow.

## Technology

- Python
- Django
- PostgreSQL support, with SQLite available for local development
- Django templates and static files
- Gunicorn and WhiteNoise
- pytest and pytest-django

## Prerequisites

- Python compatible with the pinned dependencies
- Git

## Local setup

Create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

For local development, the default settings use SQLite. Keep `DEBUG=True` only for local development.

Run Django checks and database migrations:

```powershell
python manage.py check
python manage.py migrate
```

Start the development server:

```powershell
python manage.py runserver
```

Visit `http://127.0.0.1:8000/health/` to verify the health endpoint.

## Tests

Run the full test suite:

```powershell
python -m pytest -q
```

Run Django's system checks:

```powershell
python manage.py check
```

## Experimental scripts

The existing analysis and benchmark scripts remain separate from the web configuration:

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
| `DATABASE_URL` | Optional database connection URL |

Never commit `.env` or production secrets.

## Interpretation and limitations

The current ranking methods use synthetic experiments and operation-level latency evidence. Correlation and trace evidence do not establish causality. Synthetic benchmark results are not proof of production accuracy.

## Development notes

The analysis package and its existing tests should remain independent of Django views and templates. Add web functionality incrementally and verify it with automated tests.

GitHub Actions CI and an additional linting tool are not currently configured. These remain explicit deviations from the general development checklist rather than completed tasks.
