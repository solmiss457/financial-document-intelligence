# S1 Development Questions: Human Review Record

Generated from `s1_development.json`. PDF page means the 1-based page index of the local file `storage/reports/<document>.pdf`, not the printed label.

All 12 questions were confirmed by the project owner on 2026-10-11 (single reviewer; no second independent reviewer).

## dev-01 (lookup, expected `answered`)

> According to the 2024 annual report, what were Berkshire Hathaway consolidated total revenues in 2024, in USD millions?

Expected answer: **371433** USD million · tolerance 0

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-02 (lookup, expected `answered`)

> According to Berkshire Hathaway's 2023 annual report, what was consolidated net earnings (loss), before attribution to noncontrolling interests, in 2022, in USD millions?

Expected answer: **-21998** USD million · tolerance 0

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2023 | 96 | K-72 | Net earnings (loss) | 2022 | -21998 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-03 (lookup, expected `answered`)

> According to Berkshire Hathaway's 2023 annual report, what were net cash flows from operating activities in 2023, in USD millions?

Expected answer: **49196** USD million · tolerance 0

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2023 | 98 | K-74 | Net cash flows from operating activities | 2023 | 49196 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-04 (lookup, expected `answered`)

> In Berkshire Hathaway's 2024 annual report cash flow statement, what signed amount is shown for purchases of equity securities in 2024, in USD millions?

Expected answer: **-9237** USD million · tolerance 0

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 92 | K-70 | Purchases of equity securities | 2024 | -9237 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-05 (calculation, expected `answered`)

> Using Berkshire Hathaway's 2024 annual report, how much did total revenues change from 2023 to 2024, in USD millions?

Expected answer: **6951** USD million · formula `difference` · tolerance 0

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |
| berkshire-2024 | 90 | K-68 | Total revenues | 2023 | 364482 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-06 (calculation, expected `answered`)

> Using Berkshire Hathaway's 2024 annual report, what was total revenue growth from 2023 to 2024, rounded to two decimal places?

Expected answer: **1.91** percent · formula `growth_percent` · tolerance 0.005

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |
| berkshire-2024 | 90 | K-68 | Total revenues | 2023 | 364482 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-07 (calculation, expected `answered`)

> Using Berkshire Hathaway's 2024 annual report, how much did operating cash flow change from 2023 to 2024, in USD millions?

Expected answer: **-18604** USD million · formula `difference` · tolerance 0

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 92 | K-70 | Net cash flows from operating activities | 2024 | 30592 |
| berkshire-2024 | 92 | K-70 | Net cash flows from operating activities | 2023 | 49196 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-08 (calculation, expected `answered`)

> Using Berkshire Hathaway's 2024 annual report, what was 2024 operating cash flow as a percentage of 2024 total revenues, rounded to two decimal places?

Expected answer: **8.24** percent · formula `ratio_percent` · tolerance 0.005

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 92 | K-70 | Net cash flows from operating activities | 2024 | 30592 |
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-09 (insufficient_evidence, expected `insufficient_evidence`)

> What were Berkshire Hathaway total revenues for the full year 2025?

Reason: The corpus contains Berkshire Hathaway annual reports for 2023 and 2024 only; other companies' reports do not contain Berkshire 2025 full-year results. No external retrieval allowed.

Review: **confirmed** (2026-10-11). Agreed: no Berkshire 2025 report in the corpus, so abstain.

## dev-10 (insufficient_evidence, expected `insufficient_evidence`)

> Using these reports, predict the exact closing price of Berkshire Hathaway Class B shares on December 31, 2027.

Reason: Future price prediction is outside supported scope; these historical reports cannot establish that future fact.

Review: **confirmed** (2026-10-11). Agreed: future price prediction is out of scope.

## dev-11 (ambiguous, expected `needs_clarification`)

> What were Berkshire Hathaway total revenues?

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |
| berkshire-2024 | 90 | K-68 | Total revenues | 2023 | 364482 |

Reason: Ask which fiscal year is meant; multiple annual columns exist. Also state the most recent year (2024) value as a provisional answer.

Clarification: ask for `fiscal_year`; provisional answer **371433** USD million (most recent fiscal year in the corpus (2024)).

Review: **confirmed** (2026-10-11). Clarify the year, and include the most recent year value as a provisional answer.

## dev-12 (ambiguous, expected `needs_clarification`)

> How much did Berkshire Hathaway earn in 2024?

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Net earnings (loss) | 2024 | 89561 |
| berkshire-2024 | 90 | K-68 | Net earnings (loss) attributable to Berkshire shareholders | 2024 | 88995 |

Reason: Ask whether consolidated net earnings (89,561) or earnings attributable to Berkshire shareholders is meant. Also state that, if attributable earnings are meant, the 2024 value was 88,995. Do not silently select a metric.

Clarification: ask for `metric`; provisional answer **88995** USD million (net earnings attributable to Berkshire shareholders).

Review: **confirmed** (2026-10-11). Clarify the metric, and include the attributable-earnings value as a provisional answer.
