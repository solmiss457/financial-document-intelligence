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
- GitHub-hosted Linux CI runs the authorization/API and question-contract subset and has passed since publication (run 38098874459 on fbb9e93). Linux PDF dependency hashes remain unverified.
- B0 remains unmeasured. The same RLS rules must apply to B0 and all later experiments.

## Official References

[PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html), [psycopg pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html), [FastAPI dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/).

## Ingestion Tables and Worker Role (2026-10-11)

Migration 003 adds `ingestion_jobs`, `document_pages`, and `chunks` with ENABLE/FORCE RLS (eight tables total) and composite `(organization_id, document_id)` foreign keys.

- **fdi_app:** SELECT on pages/chunks only through a parent document that is `ready` and visible under the documents policy. The documents subquery is itself filtered by documents RLS, so membership, restricted ACLs, revocation, and `deleting` status apply to content as well. Same-organization admins may read and insert jobs (enqueue for future uploads); members cannot see jobs. No write access to pages/chunks or job state.
- **fdi_worker:** LOGIN, NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE/NOINHERIT; pool startup rejects any other role name or unsafe attributes. It reads and updates jobs across organizations (needed to claim work), but documents, pages, and chunks only for the organization set in the transaction (`fdi.org_id`). It can update only document `status`, cannot read users/memberships/grants, cannot change titles or visibility, and cannot delete documents or jobs.

Verified by `backend/tests/authorization/test_ingestion_rls.py` (35 tests) and `backend/tests/ingestion/test_worker.py` (18 tests) against real PostgreSQL: the A/B/restricted/inactive matrix for chunks and pages, keyword (`tsvector`) and vector (`<=>`) queries under the same policy, revocation in the next transaction, admin exclusion of `deleting` content, worker cross-organization write rejection, least privilege, concurrent claims, lease loss, and deletion during processing. Temporarily removing the `ready` condition from the chunk policy made five tests fail, and removing the final lease-owner check made one test fail; both were restored and re-verified.

Limits: the worker trusts its own organization context; a compromised worker credential can read every job row and set any organization context. Deletion cleanup (physical removal of files, pages, chunks) and in-flight permission rechecks for answers are not implemented. Extraction isolation uses a spawned process with a wall-clock timeout and CPU rlimit; memory limits are not enforced on macOS.

## Answer Path (2026-10-11)

- Retrieval runs in the caller's request transaction, so only chunks of readable, `ready` documents are ranked. The LLM receives only those excerpts; with no authorized evidence it is not called.
- After generation, all retrieved chunks are re-checked in a new transaction. If any became invisible (grant removed, membership deactivated, document deleting), the answer and citations are withheld. Verified for all three cases; removing the re-check made those three tests fail.
- Document text is placed in the user input, never in the system instructions, and the instructions say to treat excerpts as data. This reduces but does not eliminate prompt-injection risk; the model has no tools, so injected text cannot trigger actions.
- Logs contain question ID, organization, user, state, counts, tokens, and latency; tests assert that question text and evidence text are absent. LLM errors are reduced to the exception type.
- Requests use `store=false`. Only authorized excerpts of public reports are sent to OpenAI; provider retention terms were not reviewed for real internal documents, which remain out of scope.
- Limits: no OIDC yet, so the route is unreachable outside tests; no rate limiting or per-user cost limits.

## Authentication and Administration (2026-10-11)

- **Tokens.** ES256 only, `iss`/`aud` fixed, lifetime ≤ 300 s, trusted identity-provider issuers only, all claims required and typed. Tests reject expired, wrong-audience, wrong-issuer, over-long, untrusted-provider, missing-claim, wrong-key, `alg: none`, and HS256-with-public-key (algorithm confusion) tokens. FastAPI cannot mint tokens because it has no private key. `X-User-ID` and similar headers are ignored.
- **Linking.** Google `(issuer, subject)` identifies an account; email is used only to match invitations and only when `email_verified` is true. Signing in alone creates nothing.
- **SECURITY DEFINER exception.** Earlier policies avoided SECURITY DEFINER. Admin visibility of all memberships needs a check that reads memberships while a memberships policy is evaluated, which recurses under RLS. `fdi.is_org_admin(org)` is the single exception: owned by NOLOGIN `fdi_policy` (BYPASSRLS, SELECT on memberships and users only), fixed `search_path`, EXECUTE granted only to `fdi_app`, and it returns a boolean about the current request user. Replacing it with `SELECT true` made 37 tests fail.
- **Admin limits.** Admins cannot change their own membership (avoids self-lockout and self-escalation paths); `organization_id` and `user_id` of memberships are not updatable; a member cannot promote anyone; admins of one organization see 404 for another.
- **Uploads and deletion** follow the same RLS; non-admin uploads are rejected before anything is stored. Removing the invitation email check made the invitation test fail.
- **Verified.** 22 API flow tests through real signed tokens and PostgreSQL, 11 token tests, updated privilege tests (253 total). A live Uvicorn run with locally minted tokens: no token 401, invitation shown and accepted, admin views working, other organization 404, no emails in server logs.
- **Limits.** No rate limiting, no CSRF exposure yet (no browser calls the API; Next.js will handle cookies and CSRF in P4), no audit-event table, and key rotation is manual (replace the key pair and restart).
