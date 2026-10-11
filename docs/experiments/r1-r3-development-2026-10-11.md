# R1–R3 Retrieval Experiments on the Development Questions (2026-10-11)

**Development set only: 12 questions on Berkshire Hathaway, 8 answerable.** One answerable question is 12.5 percentage points. These results choose what to try next; they are not held-out performance.

## What Changed

| Config | Chunks | Retrieval | Everything else |
|---|---|---|---|
| B0 | `fixed_words_v1:150/30` (9,435) | exact vector top-5 | same prompt `b0-v2-4a58d1dde6ff`, `gpt-5.4-mini-2026-03-17`, bge-small, organization A member, top-5 |
| R1 | `table_rows_v1:12r1200c+150/30` (10,311) | exact vector top-5 | same |
| R2 | B0 chunks | vector top-50 + PostgreSQL full-text top-50, reciprocal rank fusion (k=60), top-5 | same |
| R3 | R1 chunks | as R2 | same |

R1 rebuilds statement rows from word coordinates and emits row groups of at most 12 rows or 1,200 characters, each repeating the document, statement title, units, and column years, for example `Total revenues: 2024 = 371,433; 2023 = 364,482; 2022 = 302,020`. Text outside detected tables is chunked exactly as in B0. 1,931 table chunks were produced; 2 chunks exceed the 512-token embedding limit, as in B0. Full-text search is PostgreSQL `ts_rank_cd`, not BM25.

Runs: B0 `20261011T022458Z-B0` (worktree `1d616c8a` on `bcf07ac`); R1/R2/R3 `20261011T0244…`–`0246…` (worktree `b2318b88` on `2924e09`). Three repeats each; retrieval is deterministic.

## Retrieval Without the LLM

Best rank of a chunk containing each evidence item's row label and value (16 items over 10 questions, from `evaluation/tools/evidence_ranks.py`):

| | B0 | R1 | R2 | R3 |
|---|---:|---:|---:|---:|
| Items in top 5 | 0/16 | 8/16 | 0/16 | 12/16 |
| Items in top 50 | 3/16 | 16/16 | 1/16 | 16/16 |
| Items covered within B0's top-5 token budget | 0/16 | 7/16 | 0/16 | 5/16 |

Example: dev-01's evidence ranked 2,359 under B0, 4 under R1, 2 under R3. Keyword search alone over B0 chunks ranked it 831.

R3 passes 28% more input tokens to the LLM than B0 (28,204 vs 21,975 per 12 questions). Under an equal token budget R1 covers more evidence than R3, so part of R3's top-5 advantage comes from larger table chunks reaching the top through keyword matches.

## End-to-End Results (mean of 3 runs; range when runs differ)

| Metric | B0 | R1 | R2 | R3 |
|---|---:|---:|---:|---:|
| Evidence Recall@5 | 0.0% | 56.2% | 0.0% | 81.2% |
| Complete Evidence@5 | 0.0% | 50.0% | 0.0% | 75.0% |
| Answerable accuracy, strict scorer | 0.0% | 50.0% | 0.0% | 62.5% |
| Answerable accuracy, after adjudication | 0.0% | 62.5% | 0.0% | 75.0% |
| Wrong substantive answers / answered answerable (per run) | 0/0 | 2/7 | 0/0, 1/1, 0/0 | 1/7 |
| False deferral rate | 100% | 12.5% | 95.8% | 12.5% |
| Out-of-scope deferral rate | 100% | 100% | 100% | 100% |
| Clarification accuracy (state + provisional value) | 0% | 16.7% (0–50) | 0% | 33.3% (0–50) |
| Answer coverage | 13.9% | 63.9% | 11.1% | 63.9% |
| Latency p50 (ms) | 1,301 | 1,445 | 1,523 | 1,368 |
| Input / output tokens per 12 questions | 21,975 / 2,350 | 25,465 / 2,514 | 21,995 / 2,197 | 28,204 / 1,962 |

Adjudication: dev-07 ("how much did operating cash flow change") was answered in every R1/R3 run as "decreased by USD 18,604 million" with a calculation result of -18,604. The strict scorer requires a signed number in the answer text and flagged it; the project owner's expected value is -18,604, so it is counted correct after adjudication. No other answer was adjudicated. Cost for all nine new runs was about $0.25.

## Errors in R1 and R3

| Question | Config | What happened | Type |
|---|---|---|---|
| dev-05, dev-06 | R1 | Answered from the "Manufacturing, Service and Retailing" segment table, whose row is also "Total revenues" | Table context (wrong table, same label) |
| dev-03 | R3 | Answered USD 7,611 million, a figure from another table | Wrong evidence used; unsupported answer |
| dev-08 | R1, R3 | Retrieved operating cash flow but not total revenues; abstained | Incomplete retrieval (correct abstention given evidence) |
| dev-11 | R1, R3 | Answered without asking for the year; once used a pro forma table (383,115) | Clarification; wrong table |
| dev-12 | R1 | Asked to clarify but chose net earnings (89,561), not attributable earnings, as "most likely" | Clarification interpretation |
| dev-02 | R1 | Correct answer while Recall@5 was 0 | Ground truth lacks an alternative evidence set (same figure appears in the cash flow statement) |

B0 abstained instead of inventing numbers. R1 and R3 answer far more questions but also produce confident wrong answers from neighboring tables. That trade-off is what G1 (evidence sufficiency) and G2 (claim/citation verification) are meant to measure.

## Decision for the Next Step

- **Keep R1 chunking.** It is the main improvement and holds under an equal token budget.
- **R2 alone does not help** on these questions; full-text search over B0 chunks cannot match a label separated from its numbers.
- **R3 vs R1 is undecided.** R3 is better at top-5 (12 vs 8 items, 62.5% vs 50% strict accuracy) but worse under an equal token budget (5 vs 7 items). Twelve questions on one company cannot settle it.
- Before choosing, add development questions for the other five companies and add the missing alternative evidence set for dev-02 (requires human review). Then G1/G2 on the chosen retrieval configuration.
