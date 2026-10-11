# S1-1 Public Report Table Extraction Experiment

2026-10-10. Scope: acquiring data and testing extraction feasibility. This experiment alone does not complete an application, question set, or database.

## Sources and Selection

- Berkshire Hathaway [2023 Annual Report](https://www.berkshirehathaway.com/2023ar/2023ar.pdf): 152 pages.
- Berkshire Hathaway [2024 Annual Report](https://www.berkshirehathaway.com/2024ar/2024ar.pdf): 150 pages.
- These reports support comparisons across periods, multiple year columns, parenthesized negatives, and per-share unit exceptions.
- A Microsoft 2024 PDF candidate returned HTTP 403 and was excluded. The sample lacks company diversity; results do not generalize to scans, multiple companies, or complex merged tables.
- Source URL, acquisition time, SHA256, and version are in `eval/manifests/s1_reports.json`. Public availability was not treated as redistribution permission. Original PDFs and extracted full text are not distributed without verifying permission.

## Environment and Observed Results

Python 3.12.14, PyMuPDF 1.26.7, macOS 15.7.9 arm64. Text and word coordinates were extracted locally from all 302 pages. Table detection was limited to the four pages below.

| Report | PDF page (1-based) / printed label | Statement | lines shape | text shape |
|---|---|---|---|---|
| 2023 | 96 / K-72 | Earnings | 46×13 | 57×7 |
| 2023 | 98 / K-74 | Cash flows | 46×13 | 49×12 |
| 2024 | 90 / K-68 | Earnings | 46×12 | 56×11 |
| 2024 | 92 / K-70 | Cash flows | 47×13 | 50×12 |

Each strategy found four table candidates. Currency symbols and blank cells split the original three year columns into additional extracted columns; the shapes above are not counts of financial periods.

- Page text: expected years, unit wording, and printed labels were present on all four pages.
- lines: year headers appeared in all four tables. All eight selected rows passed checks for row label, three values, value order, and parenthesized negatives. **Unit wording appeared in 0/4 extracted tables**, demonstrating context loss.
- text: year headers and units appeared in all four tables. The same selected-row checks produced **1/8 passes and 7/8 failures**. Only the 2024 cash-flow row for equity-security purchases passed. This is not whole-table or financial-fact extraction accuracy.
- Selected rows: total revenues/net earnings in the earnings statements and operating cash flow/equity-security purchases in the cash-flow statements. Source-comparison values are in `eval/configs/pdf_probe.json`.
- Codex visually compared PNG renders of all four original pages. No independent human review has been completed. This does not establish human review of the 12 development questions.

Checks remove whitespace and test value presence/order within the same extracted row. They do not guarantee year-to-cell mapping, every row, automatic title association, normalized units, per-share exceptions, or the meaning of restated figures. Bounding boxes, cells, and words were retained, but coordinate accuracy was not quantified across the full documents.

## Reproduction

Download the reports and set up the environment using the [development guide](DEVELOPMENT.md), then run:

```sh
.venv/bin/python scripts/probe_pdf.py
.venv/bin/python -m unittest discover -s tests/ingestion -p 'test_*.py' -v
```

Outputs in `work/pdf-probe/`: page text/words JSONL, table bbox/cells/rows JSON, PNGs, and summary JSON. Standard output contains check results rather than document bodies. A SHA256 mismatch stops processing before extraction. Regression tests retain known failures as well as successes; passing does not mean the parser reads every table correctly.

## Follow-up Defined by This Experiment

S1-2 links 12 development questions to original source locations. Specify document versions because the same period may be presented differently across reports, and inspect relevant notes when needed. Keep source-value verification separate from Decimal arithmetic checks. All questions are development-only, and B0/later experiments must use the same source hashes. DB/RLS/API implementation is a separate S1-3 unit; subsequent completion is recorded in the engineering log.
