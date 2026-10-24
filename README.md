
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

The latest recorded verification completed with 97 passing tests. Re-run the commands in the Testing section to verify the current checkout.

## Technology

- Python
- Django
- PostgreSQL support, with SQLite for local development
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
python manage.py migrate
python manage.py check
```

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
5. Review matched operations, latency changes, and the evidence classifications.

The form includes example datasets. Each dataset is limited to 1 MiB, and malformed or unsupported input should be corrected before retrying.

The analysis is performed for the request. Datasets and results are not currently persisted between requests.

## Tests and checks

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

## Architecture

- `causality/` contains domain analysis and evidence logic.
- `webapp/` contains Django request handling.
- `templates/` contains the HTML interface.
- `tests/` contains automated tests.
- Experimental scripts remain outside the web request workflow.

## Interpretation and limitations

The ranking methods use operation-level latency changes and descendant-span evidence. These signals can help prioritize investigation, but correlation and trace evidence do not prove causation.

Synthetic benchmark results are not proof of production accuracy. The tool should be treated as an investigation aid, not an automatic root-cause oracle.

## Development decisions and deviations

The current implementation intentionally avoids queues, background workers, and persistent analysis records because the core comparison workflow does not currently require them.

GitHub Actions CI and an additional linting tool are not configured. These remain explicit deviations from the general development checklist, not completed tasks.
