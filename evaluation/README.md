# Evaluation Data and Experiment Rules

Twelve public reports from six companies are listed in `manifests/s1_reports.json`; four representative Berkshire tables were checked (`configs/pdf_probe.json`). The ten reports added on 2026-10-11 have no probe cases or questions yet. Twelve development questions are in `questions/s1_development.json`, with Codex source comparison, a 2026-10-11 revision naming the company in each question, and automated checks. `questions/s1_review_checklist.md` records the human review: all 12 confirmed by the project owner on 2026-10-11 (single reviewer).

Clarification policy: when company, period, or metric is ambiguous, the expected response asks for it (`needs_clarification`) and also gives the answer under the most likely interpretation. `expected_clarification` records what to ask for and the provisional value; a response is correct only if its state is `needs_clarification` and it contains that value with its interpretation. Independent human review is pending; final evaluation questions and RAG evaluation runs do not yet exist. The original 10–15 reports, 160 questions, and 80/80 split are proposed targets, not completed quantities.

Manifest fields: document_id, company, fiscal_year, source_url, acquired_at, sha256, version, redistribution_notes, local_path.
Question fields: question_id, type, split, evidence_group_ids, question, organization_id, user_id, authorized_document_ids, expected_state, expected_answer, alternative_evidence_sets, inputs, formula, tolerance, reviewed_by, reviewed_at.
Evidence fields: document_id, document_version, PDF page (1-based), printed_page_label, table_id, row_label, column_label, passage/coordinates. Ground-truth evidence must not depend on chunk IDs.

Keep the same table, fact, and paraphrases in the same split. **Split by company (decided 2026-10-11):** development questions use Berkshire Hathaway, Apple, and Walmart; Coca-Cola, JPMorgan, and Nike are reserved for final evaluation questions. All 12 reports stay in the searchable corpus. Fully satisfying any predefined alternative evidence set is acceptable. Do not tune on final questions or answers. Compare ground truth with original PDFs through human review and disclose single-reviewer limitations.

For B0/R1/R2/R3/G1/G2/N1/N2/F, record the commit, model versions, prompt/retrieval settings, document hashes, context budget, timestamp, and per-question outputs and judgments. Also compare N1/N2 arithmetic using identical inputs separately.

Report Recall@5, Complete Evidence@5, Answerable Accuracy, Unsupported Answer Rate, Citation Precision/Coverage, Numerical Accuracy, Answer Coverage, False Deferral, p50/p95 latency, and API cost. A zero denominator is N/A. Numerical tolerance must not excuse period or unit errors.

Run a configuration with `.venv/bin/python -m evaluation.tools.run_eval --repeats 3` (real LLM calls; requires ingested reports and `OPENAI_API_KEY`). Scoring rules are in `tools/scoring.py` and its tests.

| Configuration | Question set | Recall@5 | Numerical Accuracy | Answer Coverage | p95 |
|---|---|---|---|---|---|
| B0 | Development, 12 questions, 3 runs | 0.0% | 0.0% | 8.3–16.7% | 2.8–3.8 s (12 samples) |
| R1 table chunks | Development, same | 56.2% | 50.0% strict, 62.5% adjudicated | 58.3–66.7% | 2.1–7.9 s |
| R2 hybrid on B0 chunks | Development, same | 0.0% | 0.0% | 8.3–16.7% | 2.2–2.6 s |
| R3 table chunks + hybrid | Development, same | 81.2% | 62.5% strict, 75.0% adjudicated | 58.3–66.7% | 1.6–2.0 s |
| B0 | Development, 28 questions (3 companies), 3 runs | 5.0% | 20–25% | 25.0–32.1% | 2.1–2.6 s (28 samples) |
| R1 | Development, 28 questions | 42.5% | 50–55% strict, 55–60% adjudicated | 57.1–60.7% | 5.1–6.8 s |
| R3 | Development, 28 questions | 57.5% | 70–75% strict, 75–80% adjudicated | 67.9–71.4% | 1.6–3.1 s |
| F | Final test (Coca-Cola, JPMorgan, Nike) | Not measured | Not measured | Not measured | Not measured |

Development results are not held-out results. See the [B0 report](../docs/experiments/b0-development-2026-10-11.md) , [R1–R3 report](../docs/experiments/r1-r3-development-2026-10-11.md), and [28-question report](../docs/experiments/retrieval-28q-2026-10-11.md), including equal-token-budget comparisons. `tools/evidence_ranks.py` measures evidence ranks without LLM calls.
