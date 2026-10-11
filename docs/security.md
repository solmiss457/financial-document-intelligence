# S1-3 Authorization Database and Minimal API

Locally verified on 2026-10-10 using PostgreSQL 17.9, Python 3.12.14, FastAPI 0.115.12, and psycopg 3.2.6.

## Implementation Boundary

- `backend/migrations/001_security.sql`: users, organizations, memberships, documents, document_grants. All five tables use ENABLE/FORCE RLS.
- `002_admin_deletion_status.sql`: permits admins to inspect deletion metadata. Members and API document responses exclude deleting documents.
- `fdi_owner`: NOLOGIN owner. `fdi_app`: LOGIN, NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE/NOINHERIT. API startup rejects unsafe role settings.
- Composite grant foreign keys `(organization_id,document_id)` and `(organization_id,user_id)` prevent references to documents/members in another organization. The API role has no UPDATE privilege on document organization IDs.
- The API role cannot administer users, memberships, or organizations. OIDC/invitation administration is deferred to S2.
- Metadata INSERT/UPDATE and grant INSERT/DELETE require an active admin of the same organization. Physical document deletion is denied to the API role and reserved for a later worker. HTTP write endpoints are not implemented.

## Request Handling

The actual authentication dependency always returns 401. User-ID headers and fake Bearer tokens cannot bypass it. Only tests inject a Principal through FastAPI dependency overrides. This is not production authentication.

Each request transaction sets user and selected organization with `set_config(..., true)`. The trust boundary is the server-selected Principal; this does not defend against arbitrary SQL executed by an attacker holding database credentials. Organization path values must pass database membership checks.

RLS filters database rows first; the API applies an additional pure policy before responding. Responses contain only document ID/title/status. Original storage paths, document bodies, hashes, and grant lists are not returned over HTTP. Unauthorized, cross-organization, and missing documents receive the same 404; database diagnostics become a generic 503.

- `/health`: process health.
- `/ready`: database/schema access through a non-owner role.
- `/organizations/{organization_id}/documents`: document-list skeleton.
- `/organizations/{organization_id}/documents/{document_id}`: individual metadata skeleton.

Run this server only on 127.0.0.1. Document routes are unavailable outside tests until authentication is connected.

## Verified Results

`.venv/bin/python -m pytest -c backend/pytest.ini -q`: **40 passed**, with six dependency deprecation warnings. Breakdown: 37 authorization/API, two question, one PDF regression test. Passing known tests is not a general security guarantee.

- Active/inactive users and memberships, nonmembers, A/B admins and members, dual-organization membership, organization/restricted documents.
- Grant allow/deny behavior, admin writes/member write denial, cross-organization document/user FK violations, organization reassignment and membership self-promotion denial.
- Grant/membership/user revocation and visibility/deleting changes take effect in the next transaction.
- A one-connection pool reuses the same backend PID and clears context after both commit and SQL-error rollback.
- Queries without context return zero rows; API pools reject owner/superuser connections; five tables enforce RLS; SET ROLE to owner is denied.
- Forged API identity headers are rejected; 404 responses are consistent; response/captured logs do not contain cross-organization canaries; internal DB errors are not exposed.
- Actual Uvicorn/HTTP: health 200, ready 200, unauthenticated document list 401. The API process was stopped after verification.
- Two migrations succeeded on an empty temporary database and on repeat execution. Five RLS tables were confirmed before that temporary database was removed. `fdi` and `fdi_test` remain separate.

## Failure Found and Fixed

Initially, SELECT policies hid deleting rows even from admins. A real admin UPDATE test failed with `new row violates row-level security` (39 passed/one failed). SELECT policies also affect UPDATE, so migration 002 allows admin access to deletion metadata. The API's pure reading policy still excludes deleting documents. Future chunks/facts/original-file paths need separate ready-state and authorization checks.

## Future Structures and Limitations

- `chunks` and `financial_facts`: composite `(organization_id, document_id)` FK to documents, retaining SHA256/version and original page/coordinates. They must follow permissions on ready documents. Tables/retrieval are not implemented.
- `ingestion_jobs`: the same composite FK, deduplication key, claim, lease expiration, and retry count are planned for S2. Define worker privileges separately from API privileges. Not implemented.
- In-flight revocation and a final permission recheck will be added with the Q&A path. Only next-transaction revocation has been verified.
- Actual OIDC, expired sessions, invitations, PDF downloads/citations, keyword/vector retrieval, uploads, and recovery are not implemented or tested. Database GUCs do not replace authentication.
- CI configuration was added, but remote GitHub execution was not verified in this implementation record. Linux runtime/lock portability remains unverified and must be distinguished from local macOS results.
- B0 remains unmeasured. The same RLS rules must apply to B0 and all later experiments.

## Official References

[PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html), [psycopg pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html), [FastAPI dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/).
