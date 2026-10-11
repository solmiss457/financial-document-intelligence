# Local Development and Validation

## Runtime Scope

The commands below cover PDF experiments and the database/API. Document HTTP routes return 401 by default because authentication is not implemented; identities are injected only in tests. There is no web UI, OIDC integration, or RAG answer flow yet.

## PDF Extraction Experiment

Two public reports and four representative tables were checked. See [measured results and failures](PDF_EXTRACTION_S1.md). The development questions and DB/RLS/minimal API are documented below.

Verified environment: Python 3.12.14, macOS arm64. Run from the repository root with Python 3.12 installed. The PDF lock is specific to macOS arm64; other operating systems need separate validation.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --cache-dir work/pip-cache --require-hashes -r requirements-pdf-macos-arm64.lock
mkdir -p storage/reports
curl --fail --location --silent --show-error 'https://www.berkshirehathaway.com/2023ar/2023ar.pdf' -o storage/reports/berkshire-2023.pdf
curl --fail --location --silent --show-error 'https://www.berkshirehathaway.com/2024ar/2024ar.pdf' -o storage/reports/berkshire-2024.pdf
.venv/bin/python scripts/probe_pdf.py
.venv/bin/python -m unittest discover -s tests/ingestion -p 'test_*.py' -v
```

The original local run created `.venv` using Codex's bundled Python 3.12.14. Investigate hash mismatches if a publisher changes a download; do not overwrite the manifest blindly. Original PDFs, page images, and extracted full text stay in Git-ignored `storage/` and `work/`. The single regression test compares eight table/strategy combinations, including known failures; it does not measure whole-table accuracy or security.

## Development Questions, Database, and API

See [question review limitations](S1_QUESTIONS.md) and [authorization implementation and validation](S1_SECURITY_AND_API.md).

Prerequisites: Python 3.12 and running Docker Desktop. Execute from the repository root. The API lock pins direct and transitive versions but, unlike the PDF lock, does not pin wheel hashes. Remote Linux CI execution has not been verified in the implementation record.

```sh
# Create .venv with Python 3.12 first if it does not exist.
.venv/bin/python -m pip install --cache-dir work/pip-cache -r requirements-api.lock
.venv/bin/python scripts/init_local_env.py
# Do not copy .env.example to .env; the command above generates random credentials.
docker compose up -d --wait db
.venv/bin/python -m scripts.migrate
.venv/bin/python -m scripts.prepare_test_db
.venv/bin/python -m scripts.check_clean_migrations
# Database/API and question-contract checks without original PDFs.
.venv/bin/python -m pytest tests/authorization tests/test_questions.py -k 'not source_values' -q
# All 40 tests after installing PDF dependencies and downloading the reports.
.venv/bin/python -m pytest -q
# Start the local API.
.venv/bin/python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

`/health` and `/ready` return 200; document routes return 401 by default. Test identity headers such as X-User-ID are not supported. Development database `fdi` starts without automatic sample data. Tests reset only fixtures in `fdi_test`; they do not upload actual reports. `check_clean_migrations` creates a temporary database, applies and repeats migrations, then deletes only the database it created.

Database address: `127.0.0.1:55432`. Data directory: Git-ignored `storage/postgres`. Stop the API with Ctrl-C and the database with `docker compose stop db`. Do not directly delete database volume files. Secrets remain in local `.env` (0600) and must not be printed or committed. Optional `FDI_DB_PORT`/`FDI_DB_NAME` overrides must match the Compose configuration where applicable.

`.github/workflows/s1.yml` checks authorization/API behavior and question contracts without downloading the original PDFs. Writing a workflow is distinct from a verified remote CI pass. Public-demo, actual-authentication, retrieval, citation, and download checks belong to S2 and later stages.
