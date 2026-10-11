# N2: Deterministic Calculation on the 28 Development Questions (2026-10-11)

Development set only (28 questions, 20 answerable, 8 of them calculations). Not a held-out result.

## Change

N2 = R3 retrieval and evidence, with one change: the model no longer computes. It chooses an allowlisted operation (`difference`, `growth_percent`, `ratio_percent`), copies two input values as printed with unit, period, and evidence ID, and states the requested rounding. `fdi/calculation.py` parses the values (commas, `$`, parentheses as negatives), refuses incompatible or undefined cases (unit or currency mismatch, same period for growth, different periods for a ratio, zero denominator, negative growth baseline), computes with `Decimal`, and rounds half-up only at the end. The answer text carries a `{{result}}` placeholder that the system fills.

The plan's N1 (structured extraction with LLM arithmetic) is not a separate run: the B0/R3 prompt already requires inputs with value, unit, period, and evidence ID, so R3 serves as the N1 comparison point. Prompts: R3 `b0-v2-4a58d1dde6ff`, N2 `n2-v1-74d64c6b66b9`.

## 1. Arithmetic on Identical Inputs (no retrieval)

`evaluation/tools/arithmetic_check.py` gave the model the reviewed ground-truth inputs for all 8 calculation questions, 5 times each (`20261011T040927Z-arithmetic`).

| | Correct |
|---|---:|
| `gpt-5.4-mini-2026-03-17` | 37/40 (92.5%) |
| `fdi.calculation` (Decimal) | 40/40 |

All three model errors were rounding at a half-cent boundary: 6.4255… → 6.42 (twice) and 4.7252… → 4.72. Lookups, differences, and ratios away from a boundary were always right.

## 2. End to End (R3 vs N2, same session, worktree `b736174e` on `1a6e4fc`, 3 runs each)

| Metric | R3 | N2 |
|---|---|---|
| Evidence Recall@5 | 57.5% | 57.5% (retrieval unchanged) |
| Answerable accuracy, strict | 80 / 80 / 75% | **85 / 85 / 85%** |
| Answerable accuracy, dev-07 adjudicated | 85 / 85 / 80% | 85 / 85 / 85% |
| Calculation questions correct (24 attempts) | 20 (with adjudication) | 21 |
| Wrong numbers on calculation questions | 1 (dev-25: 4.72%) | 0 |
| False deferral | 10% | 10% |
| Out-of-scope deferral | 100% | 100% |
| Clarification accuracy | 0 / 25 / 0% | 25 / 25 / 0% |
| Latency p50 (ms) | 1,310–1,393 | 1,480–1,591 |
| Input tokens per 28 questions | 59,204 | 62,228 (+5%, longer instruction) |

Counting the earlier R3 session on commit `29e704c` as well, R3 produced 5 wrong calculation results on correctly retrieved inputs across 6 runs (dev-17 twice, dev-25 three times). N2 produced none in 3 runs. The R3 error rate varies by run, which is itself the problem: the same question and evidence gave 6.43% in one run and 6.42% in another.

Two side effects:

- **Explicit signs.** dev-07 is now "-18,604" instead of "decreased by 18,604", so it no longer needs adjudication.
- **Missing inputs become abstentions.** In two dev-08 runs the model filled the unretrieved revenue input with "[missing]"; the calculator refused it (`unparseable_value`) and the response became `insufficient_evidence` instead of a guessed ratio.

## Interpretation

Deterministic calculation removes a small but real error class: on correct inputs the model missed half-up rounding at boundaries in 3 of 40 identical-input trials and in 5 end-to-end answers across six R3 runs. The end-to-end accuracy gain on 20 answerable questions is one question (5 percentage points) per run, within run-to-run variation, so the stronger evidence is the identical-input comparison and the per-question consistency. Remaining calculation failures are retrieval (dev-08 lacks one input), not arithmetic.

N2 is adopted as the configuration for G1/G2. Next: wrong-table answers (dev-03), clarification (dev-11, dev-20, dev-28), and the Services lookup (dev-14).

Record note: `run.json` for the N2 run first stored the B0 prompt version because of a runner bug; the per-question records were correct. The header was corrected and annotated, and the runner fixed.
