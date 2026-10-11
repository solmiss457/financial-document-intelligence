# Local Development and Validation

Run all commands from the repository root. Use `-c backend/pytest.ini` for tests; API and maintenance commands explicitly load the Python package from `backend/src`.

## Runtime Scope

The commands below cover PDF experiments and the database/API. Document HTTP routes return 401 by default because authentication is not implemented; identities are injected only in tests. There is no web UI, OIDC integration, or RAG answer flow yet.

## PDF Extraction Experiment

Two public reports and four representative tables were checked. See [measured results and failures](archive/pdf-extraction-s1.md). The development questions and DB/RLS/minimal API are documented below.

Verified environment: Python 3.12.14, macOS arm64. Run from the repository root with Python 3.12 installed. The PDF lock is specific to macOS arm64; other operating systems need separate validation.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --cache-dir work/pip-cache --require-hashes -r backend/requirements-pdf-macos-arm64.lock
mkdir -p storage/reports
curl --fail --location --silent --show-error 'https://www.berkshirehathaway.com/2023ar/2023ar.pdf' -o storage/reports/berkshire-2023.pdf
curl --fail --location --silent --show-error 'https://www.berkshirehathaway.com/2024ar/2024ar.pdf' -o storage/reports/berkshire-2024.pdf
.venv/bin/python evaluation/tools/probe_pdf.py
.venv/bin/python -m unittest discover -s backend/tests/ingestion -p 'test_*.py' -v
```

The original local run created `.venv` using Codex's bundled Python 3.12.14. Investigate hash mismatches if a publisher changes a download; do not overwrite the manifest blindly. Original PDFs, page images, and extracted full text stay in Git-ignored `storage/` and `work/`. The single regression test compares eight table/strategy combinations, including known failures; it does not measure whole-table accuracy or security.

## Database, API, and Ingestion Worker

See [question review limitations](archive/s1-questions.md) and [authorization implementation and validation](security.md).

Prerequisites: Python 3.12 and running Docker Desktop. Execute from the repository root. The API and worker locks pin direct and transitive versions but, unlike the PDF lock, not wheel hashes.

```sh
# Create .venv with Python 3.12 first if it does not exist.
.venv/bin/python -m pip install --cache-dir work/pip-cache -r backend/requirements-api.lock
.venv/bin/python -m pip install --cache-dir work/pip-cache --require-hashes -r backend/requirements-pdf-macos-arm64.lock
.venv/bin/python -m pip install --cache-dir work/pip-cache -r backend/requirements-worker.lock
.venv/bin/python -m pip install --cache-dir work/pip-cache -r backend/requirements-answer.lock
.venv/bin/python -m pip install --cache-dir work/pip-cache --no-deps -e backend
# Generates random credentials for postgres, fdi_app, and fdi_worker; adds missing keys only.
.venv/bin/python backend/scripts/init_local_env.py
docker compose up -d --wait db
.venv/bin/python -m backend.scripts.migrate
.venv/bin/python -m backend.scripts.prepare_test_db
.venv/bin/python -m backend.scripts.check_clean_migrations
# Everything except checks that need the original PDFs (this is what CI runs).
.venv/bin/python -m pytest -c backend/pytest.ini backend/tests -q -k 'not source_values' --ignore=backend/tests/ingestion/test_pdf_probe.py
# Full suite after downloading the reports listed in the manifest.
.venv/bin/python -m pytest -c backend/pytest.ini backend/tests -q
# Register manifest reports for fictional organizations A/B and enqueue ingestion jobs.
.venv/bin/python -m backend.scripts.register_reports
# Process queued jobs, then exit. Omit --drain to keep polling.
.venv/bin/python -m fdi.worker --drain
# Start the local API.
.venv/bin/python -m uvicorn fdi.api.main:app --host 127.0.0.1 --port 8000
```

`/health` and `/ready` return 200; document and question routes return 401 by default because authentication is not implemented. `POST /organizations/{id}/questions` with `{"question": ...}` runs B0 (see `evaluation/configs/b0_answer.json`) and needs `OPENAI_API_KEY` in the local `.env`; add it by editing the file yourself and do not print or commit it. Without a key the route returns 503. Tests use a fake LLM and never call the network. Test identity headers such as X-User-ID are not supported. Tests reset only fixtures in `fdi_test`. `check_clean_migrations` creates a temporary database, applies and repeats migrations, then deletes only the database it created.

The worker downloads the pinned embedding model into ignored `work/models` on first use and copies registered PDFs into ignored `storage/documents` under random keys. It logs IDs, counts, and outcomes, not document text. B0 ingestion settings are recorded in `evaluation/configs/b0_ingestion.json`.

Database address: `127.0.0.1:55432`, image PostgreSQL 17.11 + pgvector 0.8.6. Data directory: Git-ignored `storage/postgres-pgvector`. The earlier alpine-based `storage/postgres` is no longer mounted; it was left in place rather than deleted. Stop the API with Ctrl-C and the database with `docker compose stop db`. Do not directly delete database volume files. Secrets remain in local `.env` (0600) and must not be printed or committed. Optional `FDI_DB_PORT`/`FDI_DB_NAME` overrides must match the Compose configuration where applicable.

`.github/workflows/s1.yml` runs migrations and every test that does not need the original PDFs on GitHub-hosted Ubuntu. PyMuPDF is installed there by version without a hash. The PDF regression and source-value checks run only locally because original PDFs are not distributed.
