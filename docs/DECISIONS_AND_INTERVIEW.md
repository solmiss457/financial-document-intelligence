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
- **Baseline:** lines/text is a parser-strategy comparison, not a replacement for B0/R1 RAG evaluation. Retrievaluation/answer performance remains unmeasured.

## 2026-10-10 — S1-2 Questions and S1-3 Authorization

### Questions and Review Level

Twelve development questions link to original locations, hashes, units, and periods. Chunk IDs would change with chunking methods, so ground truth uses original tables/rows/columns. Expected calculations were independently checked using Decimal; this is not a product calculation engine. Keep all questions in development to avoid final-test leakage. Codex visual comparison and automated checks are complete; independent human review is pending.

### Two Authorization Layers

Retain both pure API policies and RLS. API-only checks are simpler but cannot defend omitted SQL checks. RLS alone does not express the distinction between product responses and database metadata access as clearly. The cost is maintaining regression checks for both. Thirty-seven authorization/API tests verified allow/deny behavior.

Helpers remain SECURITY INVOKER, with a one-way users → memberships → grants → documents dependency to avoid recursion. This avoids SECURITY DEFINER owner-bypass risks and privilege-management complexity, while leaving membership administration for separate design. Composite FKs reject organization mismatches. See `docs/security.md`.

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

## Repository Layout Before S2

**Decision:** Group code by responsibility in frontend, backend, evaluation, and docs. Keep API authorization and database code in a shared `backend/src/fdi` package. Place maintenance scripts and migrations beside that package, and evaluation tools beside their fixtures. Add future worker/retrieval/calculation modules when implemented.

**Reason and alternative:** The earlier apps/services/db/scripts/tests layout scattered one backend across several root folders. A service-per-folder layout would be useful with independently maintained services, but is unnecessary for the current project. Shared Python code can still run in separate API and worker processes later.

**Trade-offs:** Explicit `PYTHONPATH` or Uvicorn `--app-dir` is required until a separate packaging decision. Existing lockfiles and dependency versions remain unchanged to isolate structural regressions. Three planning/log entry points keep their uppercase names to preserve local instruction paths; one-off reports move into docs/archive.

**Validation:** All 40 existing tests passed after relocation; the local CI subset passed 38 tests with one deselected. Empty-database migrations and repeat application succeeded with five FORCE RLS tables. Live HTTP health/ready returned 200 and the organization document route returned 401 without authentication. SQL, lockfile, and evaluation JSON bytes match their previous versions.

**Limits:** This refactor adds no product capabilities. Remote CI and independent human question review are not established by these local checks.

## 2026-10-11 — Ingestion Foundation (Plan Steps 0–2)

**Packaging.** `backend/pyproject.toml` with an editable install replaces `PYTHONPATH`/`--app-dir`. Dependencies stay in the existing lockfiles to avoid changing two things at once; the trade-off is that `pip install -e backend` does not install runtime dependencies.

**pgvector image and new data directory.** Switched from `postgres:17.9-alpine` to `pgvector/pgvector:0.8.6-pg17-trixie` (PostgreSQL 17.11), pinned by digest. The old data directory was created under musl; reusing it under glibc risks silent collation differences in text indexes, so a new directory is mounted and the old one left untouched. Alternative: build pgvector into the alpine image; rejected for build complexity.

**Worker role scoped by organization context.** The worker must claim jobs across organizations, but writes pages/chunks for one organization at a time. Jobs are readable across organizations; documents/pages/chunks require `fdi.org_id` to match. A bug that mixes organizations then fails at RLS or the composite FK instead of silently writing. Alternative: BYPASSRLS worker; simpler, but removes the database check entirely.

**Leases instead of a broker.** `FOR UPDATE SKIP LOCKED` plus a lease and attempt counter handles concurrent workers and crashes at this scale. Leases are renewed after extraction and each embedding batch, and the final transaction re-checks ownership. Trade-off: polling latency and a fixed lease length.

**Embedding model.** `BAAI/bge-small-en-v1.5` (MIT, 384 dimensions) pinned by Hugging Face revision, run locally on CPU: no API cost, reproducible, and small enough to embed the 12 reports in about four minutes. It is not a finance-specific model; that limitation should appear in error analysis rather than be assumed away. Vector column dimension is fixed at 384, so a model change requires a migration.

**B0 chunk size from measurement.** Candidates 100–250 words were tokenized on all 12 reports. 150 words / 30 overlap keeps all but 2 of 9,435 chunks within the model's 512-token limit (p99 353 tokens); 250 words would truncate 2.5%. This selects a baseline that does not lose text to truncation; it says nothing about retrieval quality, which is unmeasured.

**Validation.** 100 local tests pass; deliberate policy and lease-check removals were caught by tests. All 12 reports were ingested by the real worker. A single manual query returned only Apple chunks for an Apple question, and organization B users saw zero chunks; this is a smoke check, not an evaluation.

## 2026-10-11 — B0 Answering (Plan Step 3)

**LLM provider and model.** OpenAI Responses API (the user's available credit), dated snapshot `gpt-5.4-mini-2026-03-17` so results stay reproducible; a mini tier keeps repeated experiments cheap. Strict JSON-schema output so evaluation can parse state, citations, and calculation without heuristics. SDK `openai==3.19.2` (released more than two weeks before adoption). `store=false`.

**What B0 includes and excludes.** Vector-only top-5, prompt-only grounding, and model-performed arithmetic, matching the plan's B0. Evidence sufficiency, claim verification, and Decimal calculation are left out so later experiments have something to improve. Invalid citation IDs are reported rather than silently dropped, so evaluation can count them.

**Security is not part of the baseline trade-off.** RLS-filtered retrieval, skipping the LLM without authorized evidence, and the final visibility re-check apply to B0 and every later configuration, so security never explains a quality difference.

**Withhold on revocation.** If any retrieved chunk is no longer visible after generation, the whole answer is withheld, not just the affected citations, because uncited text could still derive from revoked evidence. Cost: an occasional answer lost to a concurrent unrelated permission change.

**Exact search.** No ANN index: about 9.4k chunks make exact search fast enough and avoid approximate-recall effects under RLS filtering.

**Smoke observation (not a metric).** Four development questions through the real stack: one retrieval miss (the income-statement chunk was not in the top 5, so the model abstained), one correct abstention, one ambiguous question answered instead of clarified, and one calculation answered from JPMorgan. That last case exposed a data issue: S1 questions say "the 2024 annual report" without naming Berkshire because the corpus then had one company. With 12 reports in the same organization those questions are ambiguous. They need revision, with human review, before B0 is measured.

## 2026-10-11 — Clarify, but Answer the Most Likely Interpretation

**Decision (project owner).** The rule stays "ask when period or metric is ambiguous", but the response also states the answer under the most likely interpretation, named explicitly, with its source. A bare question back is less useful when one reading is far more common; silently picking a reading hides the ambiguity.

**Applied to.** The dev-11/dev-12 expectations (`expected_clarification`) and the B0 instructions (prompt `b0-v2-4a58d1dde6ff`), changed before any B0 measurement so all configurations share the same behavior spec. The prompt states the rule generically and does not name the dev-12 metric, to avoid fitting the prompt to development answers.

**Evaluation consequence.** A clarification response counts as correct only with the right state and the provisional value and interpretation. Values offered as provisional must still be supported by evidence, so this does not relax unsupported-answer metrics.

## 2026-10-11 — Evaluation Scoring Rules and First B0 Result

**Evidence coverage.** A retrieved chunk covers an evidence item only if it is from the right document, spans the evidence page, and contains both the row label and the printed value. Requiring the label prevents counting a number separated from its meaning, which is the failure this project targets. Cost: a chunk that splits a label and its value across a boundary counts as a miss even if a model could reconstruct it.

**Strict answer matching.** Exact value in the requested unit after scale conversion. A rounded "$89.0 billion" for a USD-million question is wrong, and a sign implied only by wording is flagged for a person rather than accepted. Alternative considered: an LLM judge; rejected as the sole ground truth by the plan.

**Result and how it was checked.** B0 scored 0/8 on answerable development questions with Recall@5 of 0 in all three runs. Because a zero can come from a scorer bug, the scorer was checked against the whole index first: every evidence item has a covering chunk, ranked 15th to 2,873rd by the B0 query embedding. The zero is a retrieval result, not a scoring artifact.

**Interview framing.** "My baseline answered none of the answerable development questions. Before trusting that, I checked that the evidence existed in the index and measured where it ranked. The model abstained instead of inventing numbers, so the problem was retrieval of number-dense statement chunks, which is what the table-aware chunking and hybrid search experiments test next. These are 12 development questions on one company, not a held-out result."

## 2026-10-11 — R1 Table Rows from Coordinates; R1–R3 Results

**Row reconstruction instead of `find_tables`.** S1 showed PyMuPDF table detection keeps rows but drops units. Clustering words by baseline rebuilt statement rows for all six companies, and the statement title and units line sit directly above each table. Chunks repeat document, title, units, and column years in every row group. Detected tables are retrieval units, not verified facts. Caps (12 rows, 1,200 characters) were chosen by measuring token lengths: 1,400 characters left 16 table chunks over the 512-token limit, 1,200 left 2.

**Text outside tables unchanged.** Non-table text uses B0's 150/30 windows so that R1 differs from B0 only in table handling.

**Results (development, 12 questions).** Evidence in top 5: B0 0/16, R1 8/16, R2 0/16, R3 12/16. Strict answerable accuracy 0%, 50%, 0%, 62.5%. R2 alone does nothing here because keyword search cannot reunite labels and numbers that B0 split apart.

**Equal-budget check changed the conclusion.** With each configuration limited to B0's top-5 token total, R1 covers 7/16 items and R3 5/16. R3's top-5 advantage partly reflects 28% more context. R1 is kept; R3 vs R1 stays open until more questions exist.

**New failure mode.** B0 abstained when unsure. R1/R3 answer more and sometimes answer confidently from the wrong table (segment totals, pro forma figures). Better retrieval exposes answer-verification needs; this motivates G1/G2 rather than declaring success.

**Interview framing.** "Table-aware chunking moved the evidence for 'Berkshire total revenues 2024' from rank 2,359 to rank 4. Adding keyword search helped at top-5, but when I equalized the context budget the advantage shrank, so I kept the simpler improvement and left the combination undecided. Better retrieval also produced confident answers from the wrong table, which is why the next step is verification, not more retrieval tuning."

## 2026-10-11 — Company-Level Development/Final Split

**Decision (project owner).** Development questions: Berkshire Hathaway, Apple, Walmart. Final evaluation questions: Coca-Cola, JPMorgan, Nike. All 12 reports remain searchable for every configuration.

**Why.** Chunking was just tuned on statement layouts (row reconstruction, character caps). A table-level split inside the same companies would let layout-specific tuning leak into the final score. A company-level split makes the final test a new layout as well as new questions. Cost: only three companies inform development choices such as R1 vs R3.

**New development questions.** 16 questions on Apple and Walmart (lookups, a negative value shown in parentheses, growth, difference, ratio, missing future periods, and fiscal-vs-calendar ambiguity), plus a second evidence set for dev-02 (the same 2022 figure in the 2023 cash flow statement). Values were read from rebuilt rows and compared with rendered page images; every evidence item has a covering chunk in both the B0 and R1 indexes. Human review is pending, so these are not yet used for decisions.

## 2026-10-11 — R3 Chosen After Expanding to 28 Questions

**Decision.** R3 (table chunks + hybrid retrieval) becomes the retrieval configuration for G and N experiments. On 28 reviewed development questions: Recall@5 B0 5.0%, R1 42.5%, R3 57.5%; strict answerable accuracy 20–25%, 50–55%, 70–75%; evidence within B0's token budget 1, 9, 11 of 35.

**Why not decide earlier.** On the first 12 Berkshire questions R1 beat R3 under the equal token budget. With Apple and Walmart added, R3 leads on every retrieval and answer measure, including the equal budget. Holding the decision until more questions existed avoided choosing on one company's layout.

**What the larger set revealed.** R3 found the right inputs for Apple and Walmart growth questions but computed 6.42% and 4.72% instead of 6.43% and 4.73%. These are arithmetic errors on correct inputs, which the plan's N2 (deterministic calculation) addresses. Wrong-table answers (dev-03) and missed clarifications remain for G1/G2.

**Limits.** 20 answerable questions, three companies, three runs, one reviewer. These are development results used for choices, not performance claims.

## 2026-10-11 — N2: Deterministic Calculation

**Decision.** The model selects an allowlisted operation and copies inputs; Decimal code computes, checks units and periods, and rounds half-up once. Adopted for subsequent experiments.

**Evidence.** On identical reviewed inputs the model was right 37/40 times; all misses were half-up rounding at a boundary (6.4255 → 6.42, 4.7252 → 4.72). Decimal was 40/40. End to end, R3 produced 5 wrong calculation results on correctly retrieved inputs across six runs; N2 produced none in three, and strict answerable accuracy was 85% in every N2 run versus 75–80% for R3 in the same session.

**Why the identical-input test matters.** The end-to-end gain is one question out of 20 per run, within run-to-run noise. Holding inputs fixed isolates arithmetic from retrieval and shows the error class directly, as the plan requires.

**Trade-offs.** A longer instruction (+5% input tokens) and slightly higher latency. The model must still order inputs correctly (current before previous); ordering mistakes would be extraction errors, not arithmetic. Inputs are not yet verified against the cited text.

**Unplanned benefit.** When an input was missing, the model wrote "[missing]" into the value; the parser refused it and the system abstained instead of reporting a guessed ratio.

**Interview framing.** "Once retrieval found the right numbers, some answers were still wrong in the second decimal. Giving the model the exact reviewed inputs showed it misrounded 3 of 40 times, always at a rounding boundary, and the same question could come out 6.43% in one run and 6.42% in the next. I moved arithmetic into Decimal code with unit and period checks, so those errors went to zero and missing inputs became abstentions."

## 2026-10-11 — G1/G2: Code Checks Instead of a Second LLM Judge

**Decision.** Evidence assessment and claim verification run in code over structured output (`facts`, calculation inputs) and the R1 table rows, not as a second LLM call. Cheaper, deterministic, and explainable per rejection; limited to what rows and metadata can express (metric ambiguity such as "earn" is not detected).

**Root cause first.** The recurring wrong answer (dev-03, 7,611) was textually supported: label, year, and value all matched the cited excerpt, which was the parent-only Schedule I. A citation-existence check would have passed it. The fix had to be scope (consolidated vs parent-only vs pro forma), which the plan already names as a numeric-interpretation risk.

**Fiscal year end as metadata.** Inferring it from retrieved headers missed Apple and Walmart and mis-flagged Berkshire. Recording it per document (an upload field in the product) made the period check flag exactly the three ambiguous development questions.

**Narrow scope rule.** Requiring consolidated tables for every figure would reject correct answers from MD&A narrative and summary tables. The rule rejects only parent-only and pro forma sources and figures that contradict a consolidated row for the same label and year.

**Repair before reject.** In verified runs the model sometimes cited a neighbouring excerpt for a correct figure. G2 re-attributes the citation when another retrieved excerpt contains the figure in the right row and column, and withholds the answer only when no excerpt supports it.

**Results (development).** Wrong figures stated as answers: N2 1 per run (dev-03), G1 0, G2 0; accuracy 85% for all three; false deferral 10% → 15%. Costs: dev-11 lost its correct clarification state when the pro forma figure was blocked; G2 adds about 300 ms at p50.

**Risk recorded.** G2's first runs over-rejected because of verifier defects (string comparison, label ratio, years followed by punctuation, placeholders). They were found by reading development rejections and fixed with tests; the final test must show whether G2 over-rejects on new companies.

**Interview framing.** "The wrong answer wasn't a hallucination: the number, label, and year were all in the cited table, but that table was the parent company alone. So citation checks weren't enough; I added scope rules and row-and-column verification in code. Wrong figures went to zero on the development set with one extra deferral. My first verifier rejected correct answers for trivial reasons like '2024,' being read as an amount, which I only found by reading every rejection."

## 2026-10-11 — Product Backend: Google Sign-In Boundary, Invitations, Uploads (P1–P3)

**Google via the web server, verified by the API.** The project owner chose Google. Next.js (Auth.js) will hold the Google session in an HttpOnly cookie and sign a 5-minute ES256 token per API call. Alternatives: forwarding Google ID tokens to FastAPI (no extra key, but 1-hour tokens and refresh handling in the browser session) or FastAPI running the OIDC flow itself (one more public endpoint). Asymmetric keys mean a compromised API cannot impersonate users.

**Identity, not email, is the account key.** `(issuer, subject)` links accounts; email matters only for accepting invitations, and only when Google marks it verified. Microsoft Entra ID was considered; its email claim is not guaranteed verified, so invitation matching would need tenant/object IDs. The design allows adding it as a second issuer.

**A separate auth role.** Before a user is known there is no organization context for RLS. Rather than widen `fdi_app`, `fdi_auth` handles exactly identity resolution, `/me`, and acceptance, with no document access.

**One SECURITY DEFINER function.** Recorded in security.md: admins listing all memberships cannot be expressed without a policy reading memberships during memberships' own policy. A boolean-only definer function owned by a NOLOGIN BYPASSRLS role is the smallest exception; the alternative of trusting an app-set "is admin" setting would move the check out of the database.

**Deletion as a job.** `deleting` takes effect in the same request; physical removal happens in the worker with retries, so a crash cannot leave content readable.

**Interview framing.** "Sign-in proves who you are, not what you can see. The API trusts only a short-lived token signed by the web server, maps the Google subject to a user, and everything else, including admin checks, is decided in PostgreSQL. I had to make one SECURITY DEFINER exception to let admins see their members without recursive policies, and I verified it by replacing it with 'always true' and watching 37 tests fail."
