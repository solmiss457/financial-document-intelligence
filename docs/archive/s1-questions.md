# S1-2: Twelve Development Questions

Dataset: `evaluation/questions/s1_development.json`. Permission fixture: `evaluation/configs/s1_access.json`.
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

Validation: two tests in `backend/tests/test_questions.py` passed, covering the 12 question contracts, calculations, source locations, and value presence in hash-pinned PDFs. CI without original PDFs runs only the contract check.

## Revision for the Multi-Company Corpus (2026-10-11)

After ten reports from five more companies were added to organization A, seven questions (dev-02 to dev-08) no longer identified their company ("the 2024 annual report"). A B0 smoke run answered dev-06 with JPMorgan figures. The company name was added to those seven questions; `authorized_document_ids` now lists all 12 manifest reports, matching the local access setup; the dev-09 reason now names the multi-company corpus. Evidence locations, values, expected answers, formulas, tolerances, and expected states are byte-for-byte unchanged (checked by script).

`test_questions_name_their_company_in_multi_company_corpus` fails if any question omits the company of its evidence; with the original wording it failed on dev-02. Human review remains pending; `evaluation/questions/s1_review_checklist.md` lists each question's PDF page, row, column, and value for that review.

## Human Review (2026-10-11)

The project owner checked all 12 questions against the PDFs: values, rows, columns, signs (parentheses as negatives), and USD-million units for dev-01 to dev-08, and the expected behavior for dev-09 to dev-12. One reviewer, who is also the project owner; no second independent review. Decision for ambiguous questions: keep asking for clarification, but also give the answer under the most likely interpretation (dev-11: most recent year, 371,433; dev-12: attributable earnings, 88,995). Recorded as `expected_clarification` and enforced by the contract test.
