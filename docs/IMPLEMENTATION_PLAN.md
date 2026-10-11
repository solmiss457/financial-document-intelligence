# Project Structure and Implementation Plan

Written on 2026-10-10. Proposed goals are distinct from completed work.

## Structure

```text
FDI/
  frontend/                 Web UI (placeholder until implementation)
  backend/
    src/fdi/api/            HTTP routes
    src/fdi/auth/           Pure authorization policies
    src/fdi/db/             Configuration and pooled DB sessions
    migrations/            Immutable SQL migrations
    scripts/               Local environment and DB management tools
    tests/                 Authorization, API, PDF and question regressions
    pytest.ini             Test discovery and import configuration
    requirements-*.lock    Existing dependency locks, unchanged versions
  evaluation/
    manifests/             Source URLs, hashes and versions
    questions/             Development and future final evaluation questions
    configs/               Fixed experiment settings and expectations
    tools/                 PDF extraction feasibility probe
    runs/                  Local results, excluded from Git
  docs/
    architecture.md        Target design and implemented boundaries
    development.md         Executable setup and verification commands
    security.md            Authorization behavior and limitations
    archive/               Original S1 extraction and question reports
    IMPLEMENTATION_PLAN.md Development plan
    PROGRESS.md            Engineering log
    DECISIONS_AND_INTERVIEW.md Design decisions and trade-offs
  .github/workflows/       Automated checks
  compose.yaml             Local services; persistent data stays in storage/
  README.md
```

At S0, Docker Compose and dependency lockfiles were deferred until runtime validation. S1 additions are recorded in the engineering log. Private planning and agent instruction files are local-only and are not required to run the public repository.

## S0: Preparation

Preserve the original proposal, create the directory structure, define the initial implementation scope, and record design rationale and validation plans. This stage did not include an application implementation or performance measurements.

## S1: Data and Security Foundations

1. Select 2–3 public annual reports and record original URLs, acquisition dates, SHA256 hashes, versions, and redistribution conditions.
2. Build a small PyMuPDF experiment extracting page text, coordinates, and table candidates. Compare representative tables against the original PDFs for preservation of years, rows, units, and parenthesized negatives. Record failures.
3. Author and review an initial target of 12 development questions covering lookup, calculation, insufficient evidence, and ambiguity. The target is not itself a completion claim. Do not use these as final evaluation questions.
4. Migrate users, organizations, memberships, documents, and document_grants, including organization consistency constraints. Plan compatible job/chunk/fact structures for later stages.
5. Implement pure authorization policies and database RLS. Verify isolation with test-only user contexts without calling this production authentication.
6. Document minimal API/health, database setup, migrations, and test commands in the development guide. Pin dependencies and the database development environment.

Acceptance criteria: successful migrations on an empty database; organization A/B and restricted ACL allow/deny checks through a non-owner API role; no pooled request-context leakage; documented PDF extraction failures; and 12 questions compared against original sources. Do not expose document APIs externally before authentication is implemented.

## Later Stages

| Stage | Implementation | Acceptance criteria |
|---|---|---|
| S2 | One OIDC provider, invitations/sessions, upload/status/delete, worker, B0 | Isolation through actual authentication and citation access; upload-to-evidence-backed answer flow |
| S3 | Evaluation tooling, B0 measurements, R1 table chunks/R2 hybrid/R3 combined | Same documents, questions, permissions, models, and context budget |
| S4 | G1 evidence-based abstention, G2 citation/claim validation | Report error rates with coverage and unnecessary abstention |
| S5 | N1 structured extraction, N2 Decimal calculations | Separate extraction, arithmetic, and end-to-end errors; compare calculations on identical inputs |
| S6 | Final evaluation, recovery/deletion regression, Docker/CI, demo | No known security test failures; reproducible commands, measured results, and limitations |

CI begins with executable tests in S1 and expands to the complete flow in S6. The original estimate of roughly six weeks is a proposal; acceptance criteria take precedence.

## Decisions Still Open

OIDC provider/library, LLM provider/model, embedding model/version, final report/company selection, and cost limit. Verify official documentation and the runtime environment before implementation, and record decisions. S1 runtime versions are documented separately.

## Progress as of 2026-10-10

S1-1: extraction experiment on two reports and four representative tables completed; see [results](archive/pdf-extraction-s1.md). S1-2: 12 questions authored and compared with sources by Codex. S1-3: DB/RLS/minimal API implemented, with 40 local tests passing. Independent human review is pending. CI configuration was written; remote execution was not verified in this implementation record. See [security validation](security.md) and [question review scope](archive/s1-questions.md).

## Repository Organization Before S2

The existing implementation is grouped into frontend, backend, evaluation, and docs. API and future worker processes can share the fdi Python package while remaining separate runtime processes. Add ingestion/retrieval/answering/calculations/worker modules when their implementations begin, rather than adding empty directories now. Existing SQL migration bytes and dependency lock versions are preserved. Dependency-tool consolidation is a separate change.

PROGRESS.md, IMPLEMENTATION_PLAN.md, and DECISIONS_AND_INTERVIEW.md retain their names because local project instructions refer to these stable entry points. One-off S1 reports live in docs/archive. Private files, storage, .env, and work artifacts remain local and ignored.
