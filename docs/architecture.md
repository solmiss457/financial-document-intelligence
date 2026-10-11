# Architecture and Access Policies

This document separates the target architecture from the S1 implementation described below.

Browser → Next.js → FastAPI → PostgreSQL + pgvector.
Admin PDF upload → private storage + database job → Python worker → pages/tables/chunks/embeddings → ready.
Question → authentication and membership checks → retrieval from permitted documents → evidence assessment → LLM draft → claim/citation/numerical validation → permission recheck → response.

## Responsibilities

Next.js handles the UI and server-side sessions. FastAPI validates server-issued credentials and checks organization membership and document ACLs. Client-supplied user_id/org_id values alone are not trusted. The worker runs separately from user requests, with resource limits and retries.

## Access Policy

| User state | Read organization-wide documents | Read restricted documents | Upload, delete, or change permissions |
|---|---|---|---|
| Active admin in the same organization | Allow | Allow | Allow |
| Active member in the same organization | Allow | Explicit grant required | Deny |
| Other organization, inactive, or not a member | Deny | Deny | Deny |

Admin privileges apply only within the admin's organization. The same policy must cover original downloads, pages, citations, and keyword/vector retrieval. Unauthorized candidates must be excluded before any content is sent to an LLM.

## Database Principles

Composite keys and foreign keys enforce organization consistency for document children such as chunks, facts, and grants. The RLS execution role must not be a table owner, superuser, or BYPASSRLS role. User context is set inside each request transaction and tested for leakage through pooled connections.

Revocation and deletion must affect new requests immediately. In-flight requests require a final permission check before returning results. Answer caching and persisted conversation history are omitted from the MVP.

## Processing and Response States

Documents: queued → processing → ready/failed. Deletion first transitions a document to deleting, excludes it from retrieval, and allows retryable cleanup of files, chunks, and facts. Worker jobs require claims, leases/recovery, deduplication keys, and retry counts.

Responses: answered / needs_clarification / insufficient_evidence / processing_error. Errors must not reveal the existence of another organization's documents. Tokens are not streamed before final validation.

PDF content is data, not instructions to execute tools. Private files stay outside the web public directory and use random storage keys. Logs must not contain document bodies, complete prompts, or secrets.

## S1 Implementation (2026-10-10)

Implemented: PostgreSQL users/organizations/memberships/documents/document_grants, RLS, pure authorization policies, FastAPI health/ready endpoints, and document metadata routes with authentication denied by default. UI, OIDC, worker, chunks, facts, and pgvector are not implemented.

`fdi_app` is a non-owner role without schema modification, user/membership administration, document organization reassignment, or physical document deletion privileges. Development database `fdi` and test database `fdi_test` are separate. The migration verification task cleans up only its own temporary database.

Deletion **metadata** is visible in the database to admins of the same organization for state transitions and future recovery. Regular members and current API document responses exclude deleting documents. Future retrieval, citations, original files, and facts require separate ready-state and permission checks. See [S1 Security and API](security.md) for verified behavior and limitations.

## Ingestion Implementation (2026-10-11)

Implemented: `ingestion_jobs`, `document_pages`, and `chunks` (migration 003), a separate `fdi_worker` database role, and a polling worker (`python -m fdi.worker`). Upload HTTP endpoints, OIDC, deletion cleanup, retrieval APIs, and LLM answers are not implemented.

Flow: a document row (status `queued`) and an ingestion job are created → the worker claims the job with `FOR UPDATE SKIP LOCKED` and a lease → it sets the transaction's organization context to the job's organization, marks the document `processing`, and verifies the stored file's SHA256 against the document version → PyMuPDF extracts pages and words in a separate, time-limited process → B0 fixed-size word chunks are embedded locally → pages and chunks are replaced in one transaction and the document becomes `ready`.

Safety properties: the final write re-locks the job and confirms this worker still owns the lease and the document is not `deleting`; otherwise nothing is written. Input errors (hash mismatch, missing file, non-PDF, encryption, page/size/time limits) fail without retry; other errors are retried up to `max_attempts`, after which the document becomes `failed`. Jobs whose final lease expires are reaped as failed. Chunk rows record their chunker and embedding model so B0 and later chunkers can coexist on the same documents.

API-side, pages and chunks are readable only when the parent document is `ready` and readable under the documents policy, so keyword and vector queries over `chunks` inherit organization, ACL, revocation, and deletion rules. See [security](security.md).

## B0 Answer Path (2026-10-11)

`POST /organizations/{organization_id}/questions` (authentication still denied outside tests) → membership check → query embedding (bge with its query instruction) → exact cosine top-5 over `chunks` inside the request transaction, so RLS removes unauthorized, non-ready, and deleting content before ranking → if nothing is retrievable, `insufficient_evidence` without an LLM call → OpenAI Responses API with a strict JSON schema (`state`, `answer`, `citations`, `calculation`), `store=false` → evidence IDs mapped back to chunk, document, pages, and coordinates; unknown IDs reported as `invalid_citations` → a second transaction re-checks that every retrieved chunk is still visible; if not, the answer is withheld → response with `meta` (configuration, prompt version, chunker, k, models, tokens, latency, retrieved chunk IDs and scores).

B0 intentionally trusts the model's state, citations, and arithmetic. The response distinguishes `answered`, `needs_clarification`, `insufficient_evidence`, and `processing_error`. No streaming, caching, or conversation history.

## Retrieval Configurations (2026-10-11)

Migration 004 adds `ingestion_jobs.chunker`; the worker looks it up in `fdi/ingestion/chunkers.py` (unknown names fail permanently), so B0 and R1 chunks coexist per document version. `fdi/answering/b0.py` `CONFIGS` defines B0 (fixed chunks, vector), R1 (table chunks, vector), R2 (fixed chunks, hybrid), and R3 (table chunks, hybrid). Hybrid retrieval fuses vector and PostgreSQL full-text candidates (50 each) with reciprocal rank fusion; both run inside the request transaction, so RLS applies to each. The API currently serves B0; the default will change only after a configuration is chosen on evidence.

## Deterministic Calculation (N2, 2026-10-11)

`CONFIGS['N2']` keeps R3 retrieval but uses a prompt and schema in which the model returns an allowlisted operation, two inputs copied as printed (with unit, period, evidence ID), and the requested rounding, plus answer text containing `{{result}}`. `fdi/calculation.py` computes with Decimal and refuses unit, currency, or period mismatches, zero denominators, and negative growth baselines; a refusal becomes `insufficient_evidence` with a reason code. Model-written formulas are never evaluated. Input values are not yet checked against the cited excerpt; that belongs to G2.
