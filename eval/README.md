# 평가 데이터와 실험 규칙

공개 보고서 2개를 확보하고 대표 표 4개를 추출 검증했다(`manifests/s1_reports.json`, `configs/pdf_probe.json`). 개발 질문 12개는 `questions/s1_development.json`에 작성했고 Codex 원본 대조/자동 검사를 수행했다. 독립 사람 검수는 pending이며 최종 질문 세트와 RAG 평가 실행은 아직 없다. 원안의 10–15 보고서, 160 질문, 80/80 분할은 목표이며 완료 수량이 아니다.

manifest 필드: document_id, company, fiscal_year, source_url, acquired_at, sha256, version, redistribution_notes, local_path.
질문 필드: question_id, type, split, evidence_group_id, question, organization_id, user_id, authorized_document_ids, expected_state, expected_answer, alternative_evidence_sets, inputs, formula, tolerance, reviewed_by, reviewed_at.
근거 필드: document_id, document_version, PDF page(1-based), printed_page_label, table_id, row_label, column_label, passage/coordinates. chunk ID를 정답 근거로 사용하지 않는다.

같은 표/사실/패러프레이즈는 같은 split으로 묶는다. 대안 근거 세트 중 하나를 완전히 충족하면 정답으로 인정한다. 최종 질문·정답으로 튜닝하지 않는다. 원본 PDF와 사람이 대조하고 1인 검토이면 제한을 명시한다.

B0/R1/R2/R3/G1/G2/N1/N2/F 설정마다 commit, 모델 버전, 프롬프트/검색 설정, 문서 hash, context budget, 시각, 질문별 결과와 판단을 저장한다. N1/N2는 동일 입력 계산 비교도 따로 수행한다.

Recall@5, Complete Evidence@5, Answerable Accuracy, Unsupported Answer Rate, Citation Precision/Coverage, Numerical Accuracy, Answer Coverage, False Deferral, p50/p95 지연, API 비용을 기록한다. 분모 0은 N/A. 기간·단위 오류를 숫자 tolerance로 허용하지 않는다.

| 설정 | Recall@5 | Numerical Accuracy | Answer Coverage | p95 |
|---|---|---|---|---|
| B0 | Not measured | Not measured | Not measured | Not measured |
| F | Not measured | Not measured | Not measured | Not measured |
