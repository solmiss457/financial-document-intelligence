# 아키텍처와 권한 정책 (목표 설계 및 S1 구현 현황)

Browser → Next.js → FastAPI → PostgreSQL + pgvector.
관리자 PDF 업로드 → 비공개 저장소 + DB job → Python worker → 페이지/표/청크/임베딩 → ready.
질문 → 인증·멤버십 확인 → 허용된 문서 내 검색 → 근거 판단 → LLM 초안 → 주장·인용·숫자 검증 → 권한 재확인 → 응답.

## 책임 경계

Next.js는 UI와 서버 세션을 담당한다. FastAPI는 서버 발급 자격 증명을 검증하고 조직 멤버십 및 문서 ACL을 판단한다. 클라이언트의 user_id/org_id만 신뢰하지 않는다. worker는 사용자 요청과 분리하여 자원 제한과 재시도를 적용한다.

## 접근 정책

| 상태 | 조직 공개 문서 읽기 | restricted 읽기 | 업로드·삭제·권한 변경 |
|---|---|---|---|
| 같은 조직의 활성 admin | 허용 | 허용 | 허용 |
| 같은 조직의 활성 member | 허용 | 명시적 grant가 있을 때 | 거부 |
| 다른 조직/비활성/미가입 | 거부 | 거부 | 거부 |

admin도 자기 조직에서만 권한을 가진다. 원본 다운로드, 페이지, 인용, keyword/vector 검색에도 동일 정책을 적용한다. 검색 후보 단계에서 차단하며 LLM에 전송한 뒤 숨기는 방식은 사용하지 않는다.

## DB 원칙

문서 하위 chunks/facts/grants는 복합 키 및 외래 키로 조직 일치를 강제한다. RLS 실행 역할은 table owner/superuser/BYPASSRLS가 아니어야 한다. 사용자 컨텍스트는 요청별 transaction 안에 설정한다. 연결 풀에서 다른 요청으로 유출되지 않는지 검증한다.

권한 회수와 삭제는 새 요청에 즉시 반영한다. 진행 중 요청은 최종 반환 전에 재검사한다. MVP에서 답변 캐시와 저장된 대화 기록을 생략한다.

## 처리 및 응답 상태

문서: queued → processing → ready/failed. 삭제 시 deleting으로 먼저 전환해 검색에서 제외하고 파일·청크·facts 정리를 재시도 가능하게 한다. worker job에는 claim, lease/recovery, deduplication key, retry count를 둔다.

응답: answered / needs_clarification / insufficient_evidence / processing_error. 타 조직 문서 존재를 추측하게 하는 오류 메시지를 보내지 않는다. 최종 검증 전 토큰 스트리밍은 하지 않는다.

PDF 내용은 데이터이며 도구 실행 지시가 아니다. 비공개 파일은 웹 public 폴더 밖에 두고 임의 storage key를 사용한다. 로그에 원문·전체 프롬프트·비밀 값을 남기지 않는다.

## S1 구현 현황 (2026-10-10)

위 내용은 목표 아키텍처다. 현재 구현은 PostgreSQL users/organizations/memberships/documents/document_grants, RLS, 순수 정책, FastAPI health/ready 및 인증 차단된 문서 메타데이터 경로까지다. UI/OIDC/worker/chunks/facts/pgvector는 아직 없다.

`fdi_app`은 비소유자이며 스키마 변경/사용자·멤버십 관리/문서 조직 이동/물리 삭제 권한이 없다. 테스트 DB `fdi_test`와 개발 DB `fdi`를 분리한다. 임시 migration 검증 DB는 생성한 작업이 직접 정리한다.

삭제 상태의 **메타데이터**는 같은 조직 관리자에게 DB에서 보인다(상태 전환/후속 복구 목적). 일반 멤버와 현재 API 문서 응답은 deleting을 제외한다. 추후 검색·인용·원본·facts는 ready 상태 및 권한 검사를 별도 적용한다. 현재 구현과 제한은 [S1 보안/API](S1_SECURITY_AND_API.md)를 참고한다.
