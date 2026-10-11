# Development Questions: Human Review Record

Generated from `s1_development.json`. PDF page = 1-based page index of `storage/reports/<document>.pdf`, not the printed label.

All 28 questions confirmed by the project owner on 2026-10-11 (single reviewer; no second independent review). Development companies: Berkshire Hathaway, Apple, Walmart.

## dev-01 (lookup, expected `answered`)

> According to the 2024 annual report, what were Berkshire Hathaway consolidated total revenues in 2024, in USD millions?

Expected answer: **371433** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-02 (lookup, expected `answered`)

> According to Berkshire Hathaway's 2023 annual report, what was consolidated net earnings (loss), before attribution to noncontrolling interests, in 2022, in USD millions?

Expected answer: **-21998** USD million · tolerance 0

Evidence set 1:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2023 | 96 | K-72 | Net earnings (loss) | 2022 | -21998 |

Evidence set 2:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2023 | 98 | K-74 | Net earnings (loss) | 2022 | -21998 |

Review: **confirmed** (2026-10-11). Income statement evidence confirmed; cash-flow alternative (PDF page 98) confirmed as the same pre-attribution net earnings row: all three columns (97,147 / (21,998) / 90,949) match.

## dev-03 (lookup, expected `answered`)

> According to Berkshire Hathaway's 2023 annual report, what were net cash flows from operating activities in 2023, in USD millions?

Expected answer: **49196** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2023 | 98 | K-74 | Net cash flows from operating activities | 2023 | 49196 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-04 (lookup, expected `answered`)

> In Berkshire Hathaway's 2024 annual report cash flow statement, what signed amount is shown for purchases of equity securities in 2024, in USD millions?

Expected answer: **-9237** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 92 | K-70 | Purchases of equity securities | 2024 | -9237 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-05 (calculation, expected `answered`)

> Using Berkshire Hathaway's 2024 annual report, how much did total revenues change from 2023 to 2024, in USD millions?

Expected answer: **6951** USD million · formula `difference` · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |
| berkshire-2024 | 90 | K-68 | Total revenues | 2023 | 364482 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-06 (calculation, expected `answered`)

> Using Berkshire Hathaway's 2024 annual report, what was total revenue growth from 2023 to 2024, rounded to two decimal places?

Expected answer: **1.91** percent · formula `growth_percent` · tolerance 0.005

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |
| berkshire-2024 | 90 | K-68 | Total revenues | 2023 | 364482 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-07 (calculation, expected `answered`)

> Using Berkshire Hathaway's 2024 annual report, how much did operating cash flow change from 2023 to 2024, in USD millions?

Expected answer: **-18604** USD million · formula `difference` · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 92 | K-70 | Net cash flows from operating activities | 2024 | 30592 |
| berkshire-2024 | 92 | K-70 | Net cash flows from operating activities | 2023 | 49196 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and USD-million units checked against the PDF pages.

## dev-08 (calculation, expected `answered`)

> Using Berkshire Hathaway's 2024 annual report, what was 2024 operating cash flow as a percentage of 2024 total revenues, rounded to two decimal places?

Expected answer: **8.24** percent · formula `ratio_percent` · tolerance 0.005

Evidence:

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

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Total revenues | 2024 | 371433 |
| berkshire-2024 | 90 | K-68 | Total revenues | 2023 | 364482 |

Reason: Ask which fiscal year is meant; multiple annual columns exist. Also state the most recent year (2024) value as a provisional answer.

Clarification: ask for `fiscal_year`; also give **371433** USD million (most recent fiscal year in the corpus (2024)).

Review: **confirmed** (2026-10-11). Clarify the year, and include the most recent year value as a provisional answer.

## dev-12 (ambiguous, expected `needs_clarification`)

> How much did Berkshire Hathaway earn in 2024?

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| berkshire-2024 | 90 | K-68 | Net earnings (loss) | 2024 | 89561 |
| berkshire-2024 | 90 | K-68 | Net earnings (loss) attributable to Berkshire shareholders | 2024 | 88995 |

Reason: Ask whether consolidated net earnings (89,561) or earnings attributable to Berkshire shareholders is meant. Also state that, if attributable earnings are meant, the 2024 value was 88,995. Do not silently select a metric.

Clarification: ask for `metric`; also give **88995** USD million (net earnings attributable to Berkshire shareholders).

Review: **confirmed** (2026-10-11). Clarify the metric, and include the attributable-earnings value as a provisional answer.

## dev-13 (lookup, expected `answered`)

> According to Apple's fiscal 2025 Form 10-K, what were total net sales for fiscal 2025, in USD millions?

Expected answer: **416161** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| apple-fy2025 | 32 | 29 | Total net sales | 2025 | 416161 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-14 (lookup, expected `answered`)

> According to Apple's fiscal 2025 Form 10-K, what were Services net sales in fiscal 2025, in USD millions?

Expected answer: **109158** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| apple-fy2025 | 32 | 29 | Services | 2025 | 109158 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-15 (lookup, expected `answered`)

> According to Apple's fiscal 2025 Form 10-K, how much cash was generated by operating activities in fiscal 2025, in USD millions?

Expected answer: **111482** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| apple-fy2025 | 36 | 33 | Cash generated by operating activities | 2025 | 111482 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-16 (lookup, expected `answered`)

> According to Apple's fiscal 2024 Form 10-K, what were total net sales in fiscal 2022, in USD millions?

Expected answer: **394328** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| apple-fy2024 | 32 | 29 | Total net sales | 2022 | 394328 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-17 (calculation, expected `answered`)

> Using Apple's fiscal 2025 Form 10-K, what was total net sales growth from fiscal 2024 to fiscal 2025, rounded to two decimal places?

Expected answer: **6.43** percent · formula `growth_percent` · tolerance 0.005

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| apple-fy2025 | 32 | 29 | Total net sales | 2025 | 416161 |
| apple-fy2025 | 32 | 29 | Total net sales | 2024 | 391035 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-18 (calculation, expected `answered`)

> Using Apple's fiscal 2025 Form 10-K, how much did net income change from fiscal 2024 to fiscal 2025, in USD millions?

Expected answer: **18274** USD million · formula `difference` · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| apple-fy2025 | 32 | 29 | Net income | 2025 | 112010 |
| apple-fy2025 | 32 | 29 | Net income | 2024 | 93736 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-19 (insufficient_evidence, expected `insufficient_evidence`)

> What were Apple's total net sales for fiscal 2026?

Reason: The corpus contains Apple's fiscal 2024 and fiscal 2025 Form 10-K filings only; fiscal 2026 results are not in it. No external retrieval allowed.

Review: **confirmed** (2026-10-11). Agreed: Apple fiscal 2026 is not in the corpus, so abstain.

## dev-20 (ambiguous, expected `needs_clarification`)

> What were Apple's total net sales in 2024?

Evidence set 1:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| apple-fy2025 | 32 | 29 | Total net sales | 2024 | 391035 |

Evidence set 2:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| apple-fy2024 | 32 | 29 | Total net sales | 2024 | 391035 |

Reason: Apple's fiscal 2024 ended September 28, 2024, so '2024' may mean fiscal or calendar 2024; the reports do not give calendar-year totals. Ask which is meant and give fiscal 2024 as the provisional answer.

Clarification: ask for `fiscal_year`; also give **391035** USD million (fiscal 2024 (ended September 28, 2024)).

Review: **confirmed** (2026-10-11). Agreed: ask fiscal vs calendar 2024 and give fiscal 2024 (391,035).

## dev-21 (lookup, expected `answered`)

> According to Walmart's fiscal 2026 annual report, what were total revenues for the fiscal year ended January 31, 2026, in USD millions?

Expected answer: **713163** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| walmart-fy2026 | 54 | 52 | Total revenues | 2026 | 713163 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-22 (lookup, expected `answered`)

> According to Walmart's fiscal 2026 annual report, what was consolidated net income attributable to Walmart for fiscal 2026, in USD millions?

Expected answer: **21893** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| walmart-fy2026 | 54 | 52 | Consolidated net income attributable to Walmart | 2026 | 21893 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-23 (lookup, expected `answered`)

> According to Walmart's fiscal 2026 annual report, what was net cash provided by operating activities in fiscal 2026, in USD millions?

Expected answer: **41565** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| walmart-fy2026 | 58 | 56 | Net cash provided by operating activities | 2026 | 41565 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-24 (lookup, expected `answered`)

> In Walmart's fiscal 2026 consolidated statement of income, what signed amount is shown for interest income in fiscal 2026, in USD millions?

Expected answer: **-368** USD million · tolerance 0

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| walmart-fy2026 | 54 | 52 | Interest income | 2026 | -368 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-25 (calculation, expected `answered`)

> Using Walmart's fiscal 2026 annual report, what was total revenue growth from fiscal 2025 to fiscal 2026, rounded to two decimal places?

Expected answer: **4.73** percent · formula `growth_percent` · tolerance 0.005

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| walmart-fy2026 | 54 | 52 | Total revenues | 2026 | 713163 |
| walmart-fy2026 | 54 | 52 | Total revenues | 2025 | 680985 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-26 (calculation, expected `answered`)

> Using Walmart's fiscal 2026 annual report, what was fiscal 2026 operating income as a percentage of fiscal 2026 total revenues, rounded to two decimal places?

Expected answer: **4.18** percent · formula `ratio_percent` · tolerance 0.005

Evidence:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| walmart-fy2026 | 54 | 52 | Operating income | 2026 | 29825 |
| walmart-fy2026 | 54 | 52 | Total revenues | 2026 | 713163 |

Review: **confirmed** (2026-10-11). Values, rows, columns, signs, and units checked against the PDF pages.

## dev-27 (insufficient_evidence, expected `insufficient_evidence`)

> What were Walmart's total revenues for the fiscal year ending January 31, 2027?

Reason: The corpus contains Walmart's fiscal 2025 and fiscal 2026 annual reports only; the fiscal year ending January 31, 2027 is not covered. No external retrieval allowed.

Review: **confirmed** (2026-10-11). Agreed: the fiscal year ending January 31, 2027 is not covered, so abstain.

## dev-28 (ambiguous, expected `needs_clarification`)

> What were Walmart's total revenues in 2025?

Evidence set 1:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| walmart-fy2026 | 54 | 52 | Total revenues | 2025 | 680985 |
| walmart-fy2026 | 54 | 52 | Total revenues | 2026 | 713163 |

Evidence set 2:

| Document | PDF page | Printed page | Row | Column | Value |
|---|---:|---|---|---|---:|
| walmart-fy2025 | 55 | 53 | Total revenues | 2025 | 680985 |
| walmart-fy2026 | 54 | 52 | Total revenues | 2026 | 713163 |

Reason: Walmart's fiscal 2025 ended January 31, 2025, while most of calendar 2025 falls in fiscal 2026. Ask which is meant and give both: fiscal 2025 as labeled (680,985) and fiscal 2026 as the closest match to calendar 2025 (713,163).

Clarification: ask for `fiscal_year`; also give **680985** USD million (fiscal 2025 as Walmart labels it (ended January 31, 2025)); **713163** USD million (fiscal 2026 (February 2025 to January 31, 2026), covering most of calendar 2025).

Review: **confirmed** (2026-10-11). Decided: ask, and give both fiscal 2025 (680,985) and fiscal 2026 (713,163).
