# S1-3 권한 DB와 최소 API

2026-10-10. PostgreSQL 17.9, Python 3.12.14, FastAPI 0.115.12, psycopg 3.2.6으로 로컬 검증.

## 구현 경계

- `db/migrations/001_security.sql`: users, organizations, memberships, documents, document_grants. 5개 모두 ENABLE/FORCE RLS.
- `002_admin_deletion_status.sql`: 관리자 삭제 상태 메타데이터 조회 허용. 일반 멤버와 API 문서 응답에서는 deleting 제외.
- `fdi_owner`: NOLOGIN 소유자. `fdi_app`: LOGIN, NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE/NOINHERIT. API 시작 시 안전하지 않은 역할 설정이면 실패.
- grant의 `(organization_id,document_id)`와 `(organization_id,user_id)` 복합 FK로 타 조직 문서·멤버 연결 차단. 문서 조직 ID는 API 역할에 UPDATE 권한 자체를 주지 않았다.
- 사용자/멤버십/조직 관리 권한은 API 역할에 없음. OIDC/초대 관리 경로는 S2에서 설계한다.
- 메타데이터 INSERT/UPDATE 및 grant INSERT/DELETE는 같은 조직 활성 관리자만 허용. 물리 문서 삭제는 API DB 역할에 불허하고 후속 worker 책임으로 남김. HTTP 쓰기 API는 아직 없음.

## 요청 처리

실제 API 인증 의존성은 항상 401을 반환한다. 헤더의 사용자 ID나 가짜 Bearer 토큰으로 우회할 수 없다. 테스트만 FastAPI dependency override로 Principal을 주입한다. 이는 인증 구현이 아니다.

요청별 transaction에서 사용자·선택 조직을 `set_config(..., true)`로 설정한다. 신뢰 경계는 서버가 선택한 Principal이며 DB 자격 증명을 가진 공격자의 임의 SQL 실행을 방어하는 구조는 아니다. org 경로 값은 DB 멤버십 검증을 통과해야 한다.

DB는 RLS로 먼저 필터링하고 API는 별도 순수 정책으로 응답을 확인한다. 현재 반환은 문서 ID/제목/상태뿐이다. 원본 경로·본문·해시·grant 목록은 HTTP에 반환하지 않는다. 비인가/타 조직/없는 문서는 동일 404, DB 진단은 일반 503으로 바꾼다.

- `/health`: 프로세스 확인.
- `/ready`: 비소유자 역할 DB/schema 접근 확인.
- `/organizations/{organization_id}/documents`: 목록 골격.
- `/organizations/{organization_id}/documents/{document_id}`: 개별 메타데이터 골격.

현 서버는 127.0.0.1에서만 실행한다. 인증 연결 전 문서 경로는 테스트 외 사용 불가.

## 검증 결과

`.venv/bin/python -m pytest -q`: **40 passed**, 6개 dependency deprecation warnings. 구성: 권한/API 37, 질문 2, PDF 회귀 1. known test 통과이며 일반적인 보안 보장이 아니다.

- 활성/비활성 사용자·멤버십, 미가입자, A/B 관리자·멤버, 두 조직 가입자, organization/restricted 문서.
- grant 허용/거부, 관리자 쓰기/멤버 쓰기 거부, 타 조직 문서·사용자 grant FK 위반, 조직 이동 및 멤버십 자기 승격 거부.
- grant/멤버십/사용자 권한 회수 및 visibility/deleting 변경 후 다음 transaction 반영.
- 1개 연결 풀에서 동일 backend PID를 재사용해 commit/SQL 오류 rollback 모두 컨텍스트 제거 확인.
- no-context 조회 0건, table owner/superuser 접속은 API 풀에서 거부, 5개 RLS 강제, owner로 SET ROLE 거부.
- API 위조 헤더 거부, 일관된 404, 응답/캡처 로그에 타 조직 canary 미포함, DB 내부 오류 비노출.
- 실제 Uvicorn+HTTP: health 200, ready 200, 인증 없는 문서 목록 401. 검증 후 API 프로세스 종료.
- 빈 임시 DB에서 2개 migration 적용 및 동일 파일 재실행 성공, RLS 테이블 5개 확인 후 해당 임시 DB 정리. `fdi`와 `fdi_test`는 별도 보존.

## 실패에서 수정한 사항

처음에는 관리자도 deleting 행을 SELECT하지 못하게 했다. 실제 관리자 UPDATE 테스트가 `new row violates row-level security`로 실패했다(39 passed/1 failed). SELECT 정책은 UPDATE에도 영향을 주므로, 관리자에게 삭제 상태 메타데이터 조회를 허용하는 002 migration으로 수정했다. API의 순수 읽기 정책은 deleting을 계속 제외한다. 향후 chunks/facts/원본 제공은 별도의 ready/권한 검사를 유지해야 한다.

## 다음 구조와 제한

- `chunks`와 `financial_facts`: `(organization_id, document_id)` → documents 복합 FK, 문서 SHA256/버전·원본 페이지/좌표 유지. ready 문서의 권한을 따라야 한다. 아직 테이블/검색 미구현.
- `ingestion_jobs`: 같은 복합 FK, deduplication key·claim·lease 만료·retry count를 S2에 추가. worker용 역할은 API와 분리해 정의한다. 아직 미구현.
- 진행 중 긴 요청의 권한 회수와 최종 반환 직전 재검사는 Q&A 경로 구현 시 추가. 현재 다음 transaction 반영만 검증했다.
- 실제 OIDC/만료 세션/초대, PDF 다운로드·인용, keyword/vector 검색, 업로드·복구는 미구현·미검증. DB GUC는 인증 대체 수단이 아니다.
- CI workflow는 추가했지만 원격 GitHub 실행은 하지 않았다. Linux 실행/lock 이식성은 검증 전이며 로컬 macOS 결과와 구분한다.
- baseline B0는 아직 미측정. 현재 RLS 정책을 B0와 후속 실험 모두에 동일 적용한다.

## 공식 근거

[PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html), [psycopg pool](https://www.psycopg.org/psycopg3/docs/advanced/pool.html), [FastAPI test dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/).
