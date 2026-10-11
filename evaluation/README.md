# Evaluation Data and Experiment Rules

Twelve public reports from six companies are listed in `manifests/s1_reports.json`; four representative Berkshire tables were checked (`configs/pdf_probe.json`). The ten reports added on 2026-10-11 have no probe cases or questions yet. Twelve development questions are in `questions/s1_development.json`, with Codex source comparison and automated checks. Independent human review is pending; final evaluation questions and RAG evaluation runs do not yet exist. The original 10–15 reports, 160 questions, and 80/80 split are proposed targets, not completed quantities.

Manifest fields: document_id, company, fiscal_year, source_url, acquired_at, sha256, version, redistribution_notes, local_path.
Question fields: question_id, type, split, evidence_group_ids, question, organization_id, user_id, authorized_document_ids, expected_state, expected_answer, alternative_evidence_sets, inputs, formula, tolerance, reviewed_by, reviewed_at.
Evidence fields: document_id, document_version, PDF page (1-based), printed_page_label, table_id, row_label, column_label, passage/coordinates. Ground-truth evidence must not depend on chunk IDs.

Keep the same table, fact, and paraphrases in the same split. Fully satisfying any predefined alternative evidence set is acceptable. Do not tune on final questions or answers. Compare ground truth with original PDFs through human review and disclose single-reviewer limitations.

For B0/R1/R2/R3/G1/G2/N1/N2/F, record the commit, model versions, prompt/retrieval settings, document hashes, context budget, timestamp, and per-question outputs and judgments. Also compare N1/N2 arithmetic using identical inputs separately.

Report Recall@5, Complete Evidence@5, Answerable Accuracy, Unsupported Answer Rate, Citation Precision/Coverage, Numerical Accuracy, Answer Coverage, False Deferral, p50/p95 latency, and API cost. A zero denominator is N/A. Numerical tolerance must not excuse period or unit errors.

| Configuration | Recall@5 | Numerical Accuracy | Answer Coverage | p95 |
|---|---|---|---|---|
| B0 | Not measured | Not measured | Not measured | Not measured |
| F | Not measured | Not measured | Not measured | Not measured |
