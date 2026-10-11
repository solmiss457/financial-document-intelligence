# Design Decisions and Interview Notes

The initial rationale below is a set of design hypotheses, not measured achievements. Implemented decisions and observations follow in dated entries.

| Decision | Rationale and trade-offs | Validation |
|---|---|---|
| One repository, separate web/API/worker | Track types, documentation, and experiments together while separating runtime responsibilities; more deployment components | UI-to-job-completion integration tests |
| PostgreSQL + pgvector | Keep permissions, metadata, and retrieval together; simpler operations than a separate search engine is a hypothesis | ACL-aware Recall@5/latency and SQL/vector isolation tests |
| Database jobs + one worker | Persist state/retries without a broker at initial scale; limited throughput | Duplicate claims, crash recovery, retries, deletion during processing |
| API policy + RLS | Database defense against API mistakes; duplicated policy maintenance | Non-owner organization/restricted/pool-context tests |
| Fixed-size vector B0 first | Establish a comparison baseline; lost table evidence is an error to measure | Separate R1/R2/R3 comparisons on identical questions and source evidence |
| Repeat headers/units in table chunks | Preserve meaning at additional token cost | Recall@5 and equal context-token-budget evaluation |
| PostgreSQL FTS + RRF | Hypothesis: company/year keywords complement semantic retrieval | Vector/keyword/hybrid comparison; do not label FTS as BM25 |
| Decimal calculations | Reproducible allowlisted arithmetic and decimal precision | Zero denominators, negative-baseline growth abstention, scale, rounding, period/currency mismatch |
| Validate before responding | Separate citation existence from actual support; extra latency/cost | Claim–citation precision, numerical agreement, coverage, p95, API cost |

## Interview Explanation Structure

Problem → design choice → alternatives and costs → validation method → observed results → limitations.

Example: “Separating a financial number from its row, year, or unit can lead to a wrong interpretation even when retrieval finds the number. I therefore designed a comparison using chunks with repeated headers and units, under the same document, question, and token budget. The improvement has not yet been measured.”

## Common Questions

- Why not begin with advanced RAG? First establish the baseline error distribution to isolate improvement effects.
- Does a citation prove correctness? No. Check access, document version, source location, and whether the source actually supports the claim.
- Do passing arithmetic tests prove numerical answer accuracy? No. Correct arithmetic can use incorrectly extracted inputs; distinguish extraction, arithmetic, and end-to-end evaluation.
- Can abstaining more make accuracy appear higher? Include abstentions in answerable accuracy and report coverage and false deferral.
- Is an organization-ID filter sufficient? No. Validate authenticated membership, document ACLs, citation/download paths, RLS, and revocation.

Record failures, commands, result artifacts, and limitations for each stage. Known test passes must not be presented as security guarantees.

## 2026-10-10 — S1-1 Extraction Experiment

- **Choice:** Start with Berkshire 2023/2024 reports. A Microsoft candidate returned 403. Another company would improve layout diversity but broaden the initial validation scope; disclose the single-company limitation and expand later.
- **Choice:** Pin PyMuPDF 1.26.7 and retain both lines/text results, favoring reproducibility over following the latest release. Use the strategies in the [official API](https://pymupdf.readthedocs.io/en/latest/page.html#Page.find_tables). The wheel-hash lock is macOS arm64-specific; no Linux PDF hash lock exists.
- **Observed:** Across four tables, lines passed 8/8 selected-row checks but omitted units in 4/4 tables. text passed 1/8 selected-row checks. Table detection and verified fact extraction are different. Preserve source-page text/coordinates without automatically approving them as facts; unit/header association remains future work.
- **Alternatives/costs:** OCR is unnecessary for these text PDFs and outside scope. Other parsers or manual coordinate corrections may help, but fitting these specific tables would not establish generalization. Record failures first.
- **Validation:** Visual comparison of four source-page images and regression against hash-pinned PDFs, including known failures. Codex-only comparison; independent human review and whole-table accuracy measurement remain pending.
- **Interview framing:** “The parser found the tables but dropped their units. I separated table candidates from verified financial facts and retained original pages and coordinates. These are selected-row checks on a small sample, not a demonstrated RAG improvement.”
- **Baseline:** lines/text is a parser-strategy comparison, not a replacement for B0/R1 RAG evaluation. Retrieval/answer performance remains unmeasured.

## 2026-10-10 — S1-2 Questions and S1-3 Authorization

### Questions and Review Level

Twelve development questions link to original locations, hashes, units, and periods. Chunk IDs would change with chunking methods, so ground truth uses original tables/rows/columns. Expected calculations were independently checked using Decimal; this is not a product calculation engine. Keep all questions in development to avoid final-test leakage. Codex visual comparison and automated checks are complete; independent human review is pending.

### Two Authorization Layers

Retain both pure API policies and RLS. API-only checks are simpler but cannot defend omitted SQL checks. RLS alone does not express the distinction between product responses and database metadata access as clearly. The cost is maintaining regression checks for both. Thirty-seven authorization/API tests verified allow/deny behavior.

Helpers remain SECURITY INVOKER, with a one-way users → memberships → grants → documents dependency to avoid recursion. This avoids SECURITY DEFINER owner-bypass risks and privilege-management complexity, while leaving membership administration for separate design. Composite FKs reject organization mismatches. See `docs/S1_SECURITY_AND_API.md`.

### Test Boundary Before Real Authentication

Use an always-denying authentication dependency with test-only overrides instead of development X-User-ID headers. Headers simplify manual demos but risk remaining in production paths. Actual document HTTP requests return 401. Injecting test identities does not complete authentication; OIDC belongs to S2.

### Transactions and the Deletion Failure

User context uses transaction-local GUCs. The same backend PID was verified to return null context after commit and rollback. Session-level SET could persist into another pooled request. Only trusted servers should hold DB credentials; GUCs do not prevent identity forgery by a holder of those credentials.

The first deletion test failed because SELECT RLS also blocked transition to deleting. Migration 002 permits same-organization admins to inspect deletion metadata while the API still hides deleting documents. This is simpler than a privileged deletion function, but future originals/chunks/facts require their own ready filters. The failing run (39 passed/one failed) was followed by all 40 tests passing after the fix.

### Verified Interview Claims

“I tested two organizations and document ACLs through a non-owner PostgreSQL role, and confirmed that the same pooled connection clears request context after commit and rollback. I have not yet validated the complete OIDC, retrieval, and download paths.”

“I linked 12 development questions to version-pinned sources and checked their arithmetic. I do not describe them as independently human-reviewed or as a completed final holdout evaluation.”

## 2026-10-10 — Public Documentation Boundary

Keep personal planning and agent instructions on the local machine and exclude them from future commits. Publish reproducible implementation, architecture, evaluation, and decision documentation in English. The user authorized removing the two private files from historical commits as well. History rewriting changes commit IDs and requires existing clones to resynchronize; third-party copies and cached objects are outside the scope of a Git push.
