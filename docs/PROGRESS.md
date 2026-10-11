# Engineering Log

Entries describe the state at the time of each task; later entries supersede earlier unfinished items. Proposed targets are not measured results.

## 2026-10-10 — S0 Project Preparation

### Completed

- Reviewed the original proposal and documented MVP scope, exclusions, and evaluation principles.
- Created the FDI workspace and moved the original proposal into it without content changes, verifying SHA256 equality.
- Created initial web/API/worker/database/evaluation/tests/docs/CI directories.
- Documented stages, S1 acceptance criteria, access policy, design rationale, and interview explanations.

### Validation

- Original proposal SHA256 before and after relocation: `b29f85d8c6ec67c58ea5528a5c05cd342b8d1b7f839a4b99f1d9c0a0b24ba8a5`.
- Verified relative Markdown targets and directory existence.
- No application, database, authentication, tests, or performance measurements existed at this stage. Structural checks did not imply functional test passes.

### Next Work at This Stage

1. Select 2–3 public PDFs and create a manifest/extraction experiment.
2. Author 12 development questions and compare them against originals.
3. Implement database migrations, access policy/RLS, and a minimal API environment.
4. Record actual runtime and security test results.

### Limitations

Codex project registration was incomplete: no local-project registration tool was available, and computer use blocked access to the Codex app. The user needed to select FDI in the app's project UI. No other projects were changed; the chat remained projectless at that time.

For each task, record the date, completed/changed files, validation commands/results, failures/limitations, design rationale, and next work.

## 2026-10-10 — S1-1 Data Acquisition and PDF Extraction

### Completed / Changed Files

- Read required design documents and the original proposal; preserved the original proposal unchanged.
- `evaluation/manifests/s1_reports.json`: two Berkshire reports (2023/2024), URLs, acquisition timestamps, hashes, page counts, and unverified redistribution permissions.
- `evaluation/tools/probe_pdf.py`: extracts text/word coordinates across 302 pages and lines/text table candidates plus PNGs on four selected pages. SHA256 is checked first; full text stays in ignored local artifacts.
- `evaluation/configs/pdf_probe.json` and `pdf_probe_expected.json`: source-compared rows and observed results for eight combinations.
- `backend/requirements-pdf-macos-arm64.lock`: PyMuPDF 1.26.7 and the macOS arm64 wheel hash.
- `backend/tests/ingestion/test_pdf_probe.py`: integration regression covering known successes/failures.
- Updated README, evaluation guide, plan status, decision notes, and `docs/archive/pdf-extraction-s1.md`.

### Actual Validation

- `.venv/bin/python evaluation/tools/probe_pdf.py`: success; four pages × two strategies = eight table candidates checked.
- lines: selected rows 8/8 pass; units omitted in 4/4 tables. text: selected rows 1/8 pass. Both strategies retain year headers in 4/4 tables.
- `.venv/bin/python -m unittest discover -s backend/tests/ingestion -p 'test_*.py' -v`: one regression test passed, comparing eight combinations and retaining known extraction failures as expected results.
- Codex visually compared four original-page PNGs; no independent human review.

### Failures / Limitations / Unfinished Work

- Initial pip/download attempts failed under sandbox DNS restrictions; approved network execution completed installation and downloads.
- A Microsoft PDF returned HTTP 403, narrowing the sample to two years from Berkshire and one company's layout.
- Currency-symbol/blank-cell splits remain; automatic unit association is absent. This is not a measurement of whole-parser or financial-fact accuracy.
- At this stage there were zero development questions and no DB/RLS/API/authentication/security tests/CI/B0 measurements. S1-wide acceptance criteria were not met. The PDF lock is platform-specific.

### Next Work at This Stage

S1-2 questions with source/version/permission fixtures, expected states, formulas, and tolerances; S1-3 composite FKs/RLS, non-owner and pooled-context tests, API/database runtime and CI; expand report diversity. Keep B0 metrics at Not measured.

## 2026-10-10 — S1-2 Development Questions

### Completed / Validation

- `evaluation/questions/s1_development.json`: **12 development-only questions**—four lookup, four calculation, two insufficient-evidence, two ambiguity.
- `evaluation/configs/s1_access.json`: fixed fictional organization/user/document ACL conditions.
- Codex compared values, rows, years, and units with four source-page images. Evidence records hashes, versions, pages, rows, and columns.
- Two tests in `backend/tests/test_questions.py` passed: contracts/Decimal answer checks and hash-pinned source-value presence.
- `docs/archive/s1-questions.md` records review methods, split rules, and limitations.

### Unfinished / Next

Independent **human review is pending**. Do not call these finalized gold/holdout data. S1-3 followed, as recorded below.

## 2026-10-10 — S1-3 Authorization Database and Minimal API

### Completed / Changed Files

- `compose.yaml`: PostgreSQL 17.9-alpine pinned by digest, bound to 127.0.0.1:55432, data in `storage/postgres`.
- `backend/scripts/init_local_env.py`, `backend/src/fdi/db/config.py`, `migrate.py`, `prepare_test_db.py`, `check_clean_migrations.py`: random local credentials without printing secrets, checksum-verified migrations, and isolated test databases.
- `backend/migrations/001_security.sql`, `002_admin_deletion_status.sql`: five tables, composite FKs, least-privilege roles, ENABLE/FORCE RLS.
- `backend/src/fdi/{auth/policy,db/session,api/main}.py`: pure policies, transaction-local context, pooling, role checks, minimal API with authentication denied by default.
- `backend/tests/authorization/`: **37 tests** against real PostgreSQL.
- `backend/requirements-api.lock`: installed direct/transitive dependency versions. Added `backend/pytest.ini`, `.env.example`, `.github/workflows/s1.yml`.
- Updated README, architecture, decisions, and `docs/security.md`.

### Actual Validation

- Development and test database migrations succeeded.
- `PYTHONPATH=backend/src .venv/bin/python -m backend.scripts.check_clean_migrations`: two migrations applied to a newly created empty database, repeat execution succeeded, five FORCE RLS tables confirmed, temporary database removed.
- `.venv/bin/python -m pytest -c backend/pytest.ini -q`: **40 passed, 6 warnings (5.51s)**: 37 authorization/API + two question + one PDF regression. Warnings originate from Starlette/AnyIO and PyMuPDF deprecations.
- Verified null user/org context after commit and rollback on the same pooled backend PID; A/B isolation, restricted ACLs, inactive identities, revocation, composite FKs, promotion/reassignment denial, and diagnostic non-disclosure.
- Actual Uvicorn/localhost HTTP: health 200, ready 200, unauthenticated document list 401. The API was stopped cleanly after verification.
- Python compileall passed. Remote GitHub CI execution was not verified in this implementation record.

### Failures / Fixes / Limitations

- Docker was initially stopped and the sandbox blocked localhost access. Approved execution enabled testing; the container was restarted after one shutdown.
- Initial expanded run: 39 passed/one failed because SELECT RLS blocked an admin's transition to deleting. Migration 002 allows admin deletion metadata; all tests passed afterward. API document responses still exclude deleting documents.
- Actual OIDC/invitations/expired sessions/uploads/worker/retrieval/citations/original downloads are not implemented. Tests cover metadata and next-transaction revocation only.
- DB state remains inside the FDI workspace. Secrets, source PDFs, full extraction artifacts, and database files are Git-ignored. No Git repository existed at the time of the S1 implementation tests.
- S1 implementation and automated checks are complete only within the stated scope. Independent human source review remains required; this is not a claim of complete S1 human acceptance review.

### Next Work

1. Independent human review of all 12 questions, recording the reviewer.
2. S2-1: choose an OIDC provider/session boundary, implement invitations and authenticated organization/document access.
3. S2-2: admin upload/status/delete, worker/recovery, and B0 integration; preserve composite FKs and ready-state filtering for chunks/facts/jobs.
4. Extend security regressions to actual authentication/retrieval/citation/download paths, then measure B0. Performance remains Not measured.

Additional checks: `docker compose config --quiet` passed. The CI-equivalent local command (`pytest -c backend/pytest.ini backend/tests/authorization backend/tests/test_questions.py -k 'not source_values' -q`) produced **38 passed, 1 deselected**. Relative Markdown links and evaluation JSON syntax were valid. These are not remote Linux CI results.

## 2026-10-10 — Initial GitHub Publication

- Initialized local main and connected origin to `https://github.com/solmiss457/financial-document-intelligence.git`.
- Inspected 50 initial files: local secret values, source PDFs, database data, work files, and virtual environment were excluded. No local credential or token/private-key pattern matches were found; this is not a guarantee of comprehensive secret detection.
- Preserved the original proposal's Markdown line-break whitespace to retain its SHA256.
- The initial commit and push to origin/main succeeded, upstream tracking was configured, and the working tree was clean.
- The first GitHub Actions query returned no runs yet. Remote CI success was not claimed.
- Historical commit IDs may change when private files are removed from history; publication outcomes above describe the original event.

## 2026-10-10 — README Project Overview

- Replaced stage progress and completed quantities in README with purpose, problems, intended experience, technology structure, and data scope.
- Preserved setup/testing instructions in `docs/development.md`. Intended features were not described as completed.
- Documentation-only change; checked relative links and diff whitespace without rerunning functional tests. Existing unfinished work and next stages remained unchanged.

## 2026-10-10 — English README Presentation

- Used the supplied examples as visual references for emoji headings, numbered feature sections, and categorized technology badges. Wrote README in English.
- Added problem statement, features, example questions, stack, Mermaid target architecture, evaluation, data, and documentation sections.
- Kept stage status/counts out of README. Labeled intended experience/target architecture and linked separate verification records.
- Checked relative links, English prose, fenced blocks, badge URL syntax, and diff whitespace. No functional code changed or functional tests rerun.

## 2026-10-10 — English Public Documentation and Local-Only Files

### Work

- Translated all eight documents under `docs/` and `evaluation/README.md` to English, preserving commands, results, failure cases, and pending human-review/CI limitations.
- Updated README's documentation-language note and kept its project overview free of stage progress.
- Preserve personal planning and agent instructions locally, remove them from Git tracking, and ignore future additions. The user also explicitly authorized removal from historical commits.
- Create an ignored local Git bundle before rewriting history; retain original local files byte-for-byte. A rewritten history does not revoke copies already downloaded by others or necessarily remove cached GitHub objects.

### Validation and Follow-up

Check public text for remaining Korean, relative links against the published file set, unchanged functional code, preserved local file hashes, and absence of the two private paths from rewritten reachable history. Functional tests are not rerun for documentation-only changes. Record the actual history/push verification after execution; do not interpret this plan as proof of completion. Previously listed S2 work and independent human review remain pending.

### Executed Results

- Created a local ignored backup at `work/privacy-backup/before-rewrite.bundle` and rewrote main in an isolated bare copy inside the same ignored directory.
- Confirmed neither private file exists in any rewritten main commit and that the current public tree was identical before/after rewriting.
- Published rewritten main using an explicit expected-SHA force-with-lease; the push succeeded. Synchronized local main/origin/main without changing working files.
- Verified both local originals still exist with their saved SHA256 hashes and are ignored. Public branch/remote histories no longer contain the private paths. All tracked text is English and public Markdown links resolve.
- This verifies reachable branch history, not erasure from third-party clones, forks, or GitHub's cached objects. Keep the backup local; do not push it. Existing other clones should be replaced or carefully rebased before further pushes.

## 2026-10-10 — Repository Structure Before S2

### Completed

- Consolidated Python runtime, migrations, maintenance tools, locks, and tests under backend; moved the web placeholder to frontend and eval to evaluation.
- Moved the PDF experiment tool into evaluation/tools. Grouped one-off reports under docs/archive and updated documentation links, commands, CI, Compose hints, and imports.
- Preserved the three stable planning/log filenames and local-only file exclusions. Moved obsolete local bytecode directories into ignored work/restructure/legacy-caches.
- Kept SQL migrations, dependency locks, and evaluation JSON byte-identical. No new feature implementation or dependency changes.

### Actual Validation

- Full suite: **40 passed, 6 existing deprecation warnings (5.26s)**.
- Local CI subset: **38 passed, 1 deselected, 1 existing warning (1.83s)**.
- Empty database: both migrations applied and repeat-verified; five FORCE RLS tables confirmed and temporary database removed.
- Live Uvicorn: health 200, ready 200, organization document listing 401 without authentication; stopped after checks. An initial check used the nonexistent /documents route and correctly returned 404; validation was repeated on the actual organization-scoped route.

### Unfinished / Next

- Independent human review, real authentication, uploads, worker processing, and B0 remain pending; this reorganization does not advance feature acceptance.
- Remote CI success is not claimed. Next implement the S2 authentication boundary in the new structure, then ingestion and baseline flow in small verified increments.
