# 진행 기록

## 2026-10-10 — S0 프로젝트 준비

### 완료

- 계획서 전체 검토, MVP/제외 범위와 평가 원칙 정리.
- /Users/solmismac/Desktop/MyCSProject/FDI 생성.
- 원본 계획서를 FDI 루트로 이동; 내용 변경 없이 SHA256 동일성 확인.
- web/API/worker/DB/eval/tests/docs/CI 초기 디렉터리 구성.
- 구현 단계, S1 완료 기준, 권한 정책, 설계 이유 및 인터뷰 설명 작성.

### 검증

- 원본 이동 전후 SHA256 일치 (아래 값 참조).
- Markdown 상대 링크 대상 및 디렉터리 존재 확인.
- 앱 코드·DB·인증·테스트·성능 측정은 미구현/미실행. 이 기록은 기능 테스트 통과를 의미하지 않는다.

### 다음 작업

1. S1: 공개 PDF 2–3개 선정·manifest 및 표 추출 실험.
2. 개발 질문 12개 작성 후 원본 대조.
3. DB 마이그레이션·권한 정책·RLS와 최소 API 실행 환경 구현.
4. 실제 실행 및 보안 테스트 결과를 이 파일에 기록.

### 미완료 및 제약

Codex Projects 등록 미완료: 제공된 도구에 로컬 프로젝트 추가 기능이 없고, Computer Use는 Codex 앱 접근을 안전상 차단했다. 사용자가 Codex의 프로젝트 추가 UI에서 FDI 폴더를 선택해야 한다. 기존 다른 프로젝트는 변경하지 않았다. 현재 채팅은 projectless 상태이며 자동 이동되지 않았다.

### 매 작업 종료 시 기록할 항목

날짜 / 완료 사항 / 변경 파일 / 검증 명령·결과 / 실패·제약 / 설계 선택 이유 / 다음 작업.

원본 SHA256: `b29f85d8c6ec67c58ea5528a5c05cd342b8d1b7f839a4b99f1d9c0a0b24ba8a5`

## 2026-10-10 — S1-1 데이터 확보와 PDF 추출 실험

### 완료 / 변경 파일

- 필수 설계 문서 및 원본 계획서 읽기 완료. 원본 계획서 내용은 변경하지 않음.
- `eval/manifests/s1_reports.json`: Berkshire 2023/2024 원본 2개, URL/취득 시각/해시/페이지 수/재배포 미확인 기록.
- `scripts/probe_pdf.py`: 전체 302쪽 text/words 좌표 추출, 지정 4쪽의 lines/text 표 후보 및 PNG 저장, SHA256 선검사. 전문은 Git 제외 경로로만 저장.
- `eval/configs/pdf_probe.json`, `pdf_probe_expected.json`: 원본 이미지와 대조한 지정 행 및 8개 조합의 관측 결과.
- `requirements-pdf-macos-arm64.lock`: PyMuPDF 1.26.7 고정 및 macOS arm64 wheel 해시.
- `tests/ingestion/test_pdf_probe.py`: 알려진 성공/실패에 대한 통합 회귀 검사.
- README/eval README/계획서 진행 표시/설계 선택 갱신. `docs/PDF_EXTRACTION_S1.md`에 방법과 한계 기록.

### 실제 검증

- `.venv/bin/python scripts/probe_pdf.py`: 정상 종료. 4쪽 × 2전략 = 8개 표 후보 검증.
- lines: 지정 행 8/8 검사 통과, 단위 문구 4/4 누락. text: 지정 행 1/8 통과. 두 전략 모두 연도 헤더 4/4 존재.
- `.venv/bin/python -m unittest discover -s tests/ingestion -p 'test_*.py' -v`: 1개 회귀 테스트 통과(8개 조합 비교). 알려진 추출 실패를 기대 결과로 포함한다.
- 원본 4쪽 PNG 시각 대조: Codex 단독 수행. 독립 사람 검수는 미완료.

### 실패 / 한계 / 미완료

- 초기 pip 및 다운로드는 샌드박스 DNS 제한으로 실패; 승인된 네트워크 실행으로 설치/다운로드 완료.
- Microsoft 후보 PDF 다운로드 HTTP 403. Berkshire의 두 연도로 범위 축소: 한 회사의 레이아웃에 한정.
- 표 후보에는 통화기호/빈 셀 분할이 남고 단위 자동 결합도 없다. 파서 전체 정확도·금융 사실 추출 완료로 해석하지 않는다.
- 개발 질문은 아직 0개. DB/RLS/API/실제 인증/보안 테스트/CI/B0 비교 및 성능 측정은 미구현·미실행.
- S1 전체 완료 기준 미충족. Python lock은 현 검증 환경 한정.

### 다음 작업

1. S1-2: 개발 질문 12개를 조회/계산/근거 부족/모호함으로 작성. 원본 위치·버전·권한 fixture·기대 상태·계산식·허용오차를 기록하고 원본 검토 수행.
2. S1-3: 조직·문서·grant 복합 FK 및 RLS, 비소유자 역할/풀 컨텍스트 테스트, 최소 API/DB 런타임·CI 구현.
3. 다른 회사 보고서로 레이아웃 다양성 확대. B0 성능은 실제 실행 전까지 Not measured 유지.

## 2026-10-10 — S1-2 개발 질문

### 완료 / 검증

- `eval/questions/s1_development.json`: 조회 4, 계산 4, 근거 부족 2, 모호함 2 = **12개** 작성. 모두 development.
- `eval/configs/s1_access.json`: 가상 조직/사용자/문서 ACL 조건 고정.
- 원본 4쪽 이미지와 수치·행·연도·단위 대조(Codex). 질문마다 원본 해시·버전·페이지·행/열을 기록.
- `tests/test_questions.py`: 계약/Decimal 정답 검산 및 원본 해시/수치 존재 2개 테스트 통과.
- `docs/S1_QUESTIONS.md`에 검토 방법/분할/한계 기록.

### 미완료 / 다음

독립 **사람 검수 pending**. 12개를 최종 gold/holdout 완료로 부르지 않는다. 다음은 S1-3 DB/RLS/API(아래 기록).

## 2026-10-10 — S1-3 권한 DB·최소 API

### 완료 / 변경 파일

- `compose.yaml`: PostgreSQL 17.9-alpine + digest 고정. 127.0.0.1:55432 바인딩, 데이터 `storage/postgres`.
- `scripts/init_local_env.py`, `local_db.py`, `migrate.py`, `prepare_test_db.py`, `check_clean_migrations.py`: 비밀 값 비출력, 로컬 랜덤 .env, 마이그레이션 체크섬, 테스트 DB 분리.
- `db/migrations/001_security.sql`, `002_admin_deletion_status.sql`: 5개 테이블, 복합 FK, 역할 최소 권한, ENABLE/FORCE RLS.
- `services/api/{policy,db,main}.py`: 순수 정책·transaction-local context·풀·역할 검사·최소 API. 인증 기본 거부.
- `tests/authorization/`: 실제 PostgreSQL 기반 **37개** 테스트.
- `requirements-api.lock`: 실제 설치한 직접/간접 의존성 버전 고정. `pytest.ini`, `.env.example`, `.github/workflows/s1.yml` 추가.
- README/아키텍처/결정 기록 및 `docs/S1_SECURITY_AND_API.md` 갱신.

### 실제 검증

- 전용 개발 DB/테스트 DB 마이그레이션 성공.
- `.venv/bin/python -m scripts.check_clean_migrations`: 새 빈 DB에 2개 migration 성공, 동일 migration 재실행 성공, FORCE RLS 테이블 5개 확인. 임시 DB 정리 완료.
- `.venv/bin/python -m pytest -q`: **40 passed, 6 warnings (5.51s)**. 권한/API 37 + 질문 2 + PDF 회귀 1. 경고는 Starlette/AnyIO와 PyMuPDF deprecation.
- commit/rollback 뒤 같은 pooled backend PID의 user/org context null 확인. A/B·restricted·비활성·권한 회수·복합 FK·권한 승격/조직 이동 거부·오류 비노출 검증.
- 실제 Uvicorn localhost HTTP: health 200, ready 200, 미인증 문서 목록 401. 점검 후 API 정상 종료.
- Python compileall 성공. 원격 GitHub CI는 **작성만 완료, 미실행**.

### 실패·수정·한계

- Docker 엔진 미실행 및 샌드박스 localhost 접근 제한을 확인하고 승인된 실행으로 진행. 컨테이너 한 차례 종료 후 재시작.
- 최초 확장 테스트 39 passed/1 failed: 관리자 deleting 전환이 SELECT RLS로 거부됨. 002 migration으로 관리자 삭제 메타데이터 조회 허용 후 전체 통과. API 문서 응답에서는 deleting 계속 제외.
- 실제 OIDC/초대/만료 세션·업로드·worker·검색·인용·원본 다운로드는 미구현. 현재는 메타데이터 및 다음 transaction 권한 회수만 검증.
- DB 상태는 FDI 내부 저장소에 유지. .env/PDF 원문/추출 전문/DB 데이터는 Git 제외. 이 폴더에는 아직 Git 저장소가 없어 커밋/원격 CI 실행은 하지 않음.
- S1 구현/자동 검증은 위 범위까지 완료. 독립 사람 원본 검수는 아직 필요하며 이를 생략한 S1 전체 검수 완료로 표현하지 않는다.

### 다음 작업

1. 질문 12개의 사람 독립 검수(검토자를 별도로 기록).
2. S2-1: OIDC 제공자·세션 경계 선정, 초대 및 인증된 조직/문서 접근을 연결.
3. S2-2: 관리자 업로드/상태/삭제, worker·복구 및 B0 연결. chunks/facts/jobs 복합 FK와 ready 필터 유지.
4. 실제 인증/검색/인용/다운로드 경로에 보안 회귀를 확장한 다음 B0를 측정. 성능은 계속 Not measured.

추가 마무리 검증: `docker compose config --quiet` 성공. CI와 같은 명령(`pytest tests/authorization tests/test_questions.py -k 'not source_values' -q`)은 로컬에서 **38 passed, 1 deselected**. Markdown 상대 링크와 평가 JSON 구문 검사 성공. 이는 원격 Linux CI 실행 결과가 아니다.

## 2026-10-10 — GitHub 첫 공개 준비

- 로컬 Git main 초기화, origin을 `https://github.com/solmiss457/financial-document-intelligence.git`으로 연결.
- 첫 커밋 대상 50개 파일 점검: .env 실제 값·원본 PDF·DB 데이터·work·가상환경은 제외. 로컬 비밀 값 및 token/private-key 패턴 검사에서 탐지 없음(완전한 비밀 탐지 보장은 아님).
- 원본 계획서의 Markdown 줄바꿈용 trailing spaces는 원본 SHA256 보존을 위해 유지.
- 이 기록 시점에는 커밋/업로드 결과 및 원격 CI는 아직 확인 전. 이후 확인 결과를 추가 기록한다.

### 첫 업로드 결과

- 첫 커밋 `3e77cef` 생성 후 origin/main push 성공, 로컬 main의 upstream 연결 완료.
- 코드·문서 50개 업로드. 업로드 직후 작업 트리 변경 없음 확인.
- GitHub Actions 최초 조회에는 실행 목록이 아직 없었음. 원격 CI 통과를 주장하지 않으며 후속 확인 대상.

## 2026-10-10 — README 프로젝트 소개 개편

- README의 단계별 진행 현황·완료 수량을 제거하고 목적/문제/서비스 설계 목표/기술 구조/데이터 범위 중심으로 개편.
- 기존 실행·검증 안내는 `docs/DEVELOPMENT.md`로 이동해 보존. 목표 기능을 구현 완료로 표현하지 않음.
- 문서 변경만 수행. 상대 링크와 diff 공백 검사로 검증하며 기능 테스트는 재실행하지 않음.
- 미완료 개발 사항과 다음 단계는 기존 진행 기록 유지.

## 2026-10-10 — 영문 README 시각 구성

- 첨부 예시의 이모지 제목·번호별 기능 설명·분류별 기술 배지 구성을 참고해 README 전체를 영어로 작성.
- Problem Statement, Key Features, Example Questions, Tech Stack, System Design, Evaluation, Data, Documentation 구성. Mermaid로 목표 흐름 표시.
- 단계별 진행 현황과 완료 수량은 README에 넣지 않음. 미구현 기능은 intended experience/target architecture로 명시하고 실제 검증 기록은 별도 문서로 연결.
- 상대 링크, 영어 본문, 코드 블록/배지 URL 구문, diff 공백 검사 수행. 문서만 변경하여 기능 테스트는 재실행하지 않음.
- 다음 개발 작업과 기존 검증 한계는 이전 기록 유지.
