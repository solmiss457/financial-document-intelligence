# S1-2: Twelve Development Questions

Dataset: `eval/questions/s1_development.json`. Permission fixture: `eval/configs/s1_access.json`.
Authored and compared against source images by Codex on 2026-10-10. Independent human review is **pending**. Do not describe this as a finalized gold set or a human-reviewed dataset based on automated authoring alone.

| Type | Count | Coverage |
|---|---:|---|
| Lookup | 4 | Total revenues, negative net earnings, operating cash flow, signed equity purchases |
| Calculation | 4 | Revenue difference/growth, operating cash-flow difference, cash-flow/revenue ratio |
| Insufficient evidence | 2 | Unavailable 2025 annual results, future stock-price prediction |
| Ambiguity | 2 | Missing year, unspecified earnings definition |

Each numerical evidence item records document hash/version, 1-based PDF page, printed label, table, row, year column, currency, scale, and period. Values were compared with previously rendered 2023 PDF pages 96/98 and 2024 pages 90/92. Only necessary values and source locations are recorded in Git, not entire tables.

Inputs and expected answers were checked using Decimal. Percentages use ROUND_HALF_UP to two decimal places at the final step, with a tolerance of 0.005 percentage point. Differences and lookups have zero tolerance in the stated units. Numerical tolerance does not excuse currency, period, or unit errors. This is evaluation-answer verification, not completion of the S5 product calculation engine.

Insufficient-evidence questions do not invent citations. Their reasons identify corpus period limits or out-of-scope prediction. Ambiguous questions record the fields requiring clarification. Page-level presence of a row string/value does not prove semantic row-column alignment; Codex visual comparison and independent human review are distinct.

The access fixture represents an active member of fictional organization A with access to the organization-wide 2024 report and an explicit grant to the restricted 2023 report. UUIDs match the database test convention, but actual report upload/indexing is not implemented. The company publishing a report is distinct from the fictional organization assigned that report.

All questions are development-only. Questions sharing tables/facts are linked through evidence_group_ids and must remain separate from final evaluation questions. There are zero final evaluation questions and zero B0/improvement evaluation runs. Broader data selection must address the bias toward simple representative tables from one company.

Validation: two tests in `tests/test_questions.py` passed, covering the 12 question contracts, calculations, source locations, and value presence in hash-pinned PDFs. CI without original PDFs runs only the contract check.
