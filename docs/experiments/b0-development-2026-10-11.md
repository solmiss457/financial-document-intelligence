# B0 on the Development Questions (2026-10-11)

First measurement of the baseline. **Development set only (12 questions, all on Berkshire Hathaway reports); not a held-out result.** Small denominators: one answerable question is 12.5 percentage points.

## Conditions

| Item | Value |
|---|---|
| Configuration | B0: fixed 150-word chunks (30 overlap), exact vector top-5, prompt-only grounding, LLM arithmetic |
| Corpus | 12 reports, 6 companies, 9,435 chunks; all readable by the evaluating member of organization A |
| Questions | `s1_development.json`, 12 questions, human-confirmed by the project owner (single reviewer) |
| Models | `BAAI/bge-small-en-v1.5@5c38ec7c405e` (local CPU); `gpt-5.4-mini-2026-03-17`, reasoning effort low, strict JSON schema |
| Prompt | `b0-v2-4a58d1dde6ff` |
| Code | commit `bcf07ac` plus uncommitted evaluation tooling (worktree hash `1d616c8a…`), committed afterwards |
| Repeats | 3 runs of all 12 questions; retrieval is deterministic, generation varies |
| Run | `evaluation/runs/20261011T022458Z-B0` (local, Git-ignored) |

Scoring (`evaluation/tools/scoring.py`): evidence is covered only by a top-5 chunk from the right document whose page range includes the evidence page and which contains both the row label and the printed value. Answers count only with the expected state and an exact value in the requested unit after scale conversion; a value that matches only by wording ("net loss of 21,998") is flagged for manual adjudication, and none occurred. Clarifications must include the provisional value.

## Results

| Metric | Run 1 | Run 2 | Run 3 | Denominator |
|---|---:|---:|---:|---:|
| Evidence Recall@5 | 0.0% | 0.0% | 0.0% | 8 answerable |
| Complete Evidence@5 | 0.0% | 0.0% | 0.0% | 8 |
| Answerable accuracy (= numerical accuracy; all 8 are numeric) | 0.0% | 0.0% | 0.0% | 8 |
| False deferral rate | 100% | 100% | 100% | 8 |
| Out-of-scope deferral rate | 100% | 100% | 100% | 2 |
| Clarification accuracy (state and provisional value) | 0% | 0% | 0% | 2 |
| Clarification state only | 0% | 0% | 50% | 2 |
| Answer coverage (state `answered`) | 16.7% | 16.7% | 8.3% | 12 |
| Responses with invalid citation IDs | 0 | 0 | 0 | 12 |
| Latency p50 / max-like p95 (ms) | 1,480 / 2,768 | 1,196 / 3,825 | 1,228 / 2,812 | 12 |
| Input / output tokens | 21,975 / 2,085 | 21,975 / 2,660 | 21,975 / 2,306 | 12 |

Cost at the published $0.75 / $4.50 per million input/output tokens: about $0.027 per 12-question run, $0.08 for all three. End-to-end latency includes local query embedding and two database transactions. Unsupported Answer Rate and Citation Support Precision were not measured; they need claim-level judgment.

## Error Analysis

**Retrieval (8 of 8 answerable questions).** No top-5 chunk covered any required evidence, and the expected values did not appear anywhere in the top-5 text except one prior-year figure for dev-06. The covering chunks exist: for every evidence item a chunk with the label and value is in the index. Under the same query embeddings their best ranks were:

| Question | Best rank of a covering chunk (of 9,435) |
|---|---|
| dev-01 | 2,359 |
| dev-02 | 15 |
| dev-03 | 1,444 |
| dev-04 | 427 |
| dev-05 / dev-06 | 1,907 / 2,290 |
| dev-07 | 33 |
| dev-08 | 207 and 2,873 (two inputs) |

Top results were mostly narrative pages (cover letter, MD&A, notes) and, for some questions, the other year's statement or other companies. Statement chunks are dense number sequences without the question's wording, which a general-purpose sentence embedding ranks low.

**Evidence assessment.** Given those excerpts, the model abstained on all 8 answerable questions rather than inventing numbers, and correctly abstained on dev-09/dev-10. This is grounding behavior, not accuracy: the system answered nothing it was supposed to answer.

**Clarification (dev-11, dev-12).** dev-12 was answered as "$89.0 billion ... attributable to Berkshire shareholders" in all runs: no clarification, and rounded below the question's USD-million precision. dev-11 was answered with the 2023 figure in two runs; in the third it asked for the year but called 2023 "the most recent fiscal year shown", because the 2024 statement was not retrieved.

**Calculation.** Not reached; no answerable question had its inputs retrieved.

## Interpretation and Next Steps

B0's failure is retrieval, before generation. Improvements should be judged first by Evidence Recall@5 and the rank of covering chunks, then by answers. Candidates already in the plan:

- R1 table-aware chunks: keep row labels, column years, units, and statement titles with numbers.
- R2 hybrid search: PostgreSQL full-text matching of "Total revenues", "Berkshire", "2024" alongside vectors.

Both must be compared on these same 12 questions, permissions, models, and top-5 budget. Twelve questions on one company cannot show generalization; more questions on the other five companies are needed before any final test.
