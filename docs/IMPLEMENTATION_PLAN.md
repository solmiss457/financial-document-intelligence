# 초기 구조와 단계별 구현 범위

작성일: 2026-10-10. 계획서의 제안과 완료 사실을 구분한다.

## 구조

```text
FDI/
  Financial_Document_Intelligence_Project_Plan_EN.md
  README.md
  AGENTS.md
  apps/web/                 Next.js·TypeScript UI, 서버 세션
  services/api/             FastAPI, 권한·검색·검증·계산
  services/worker/          PDF 추출, 청크, 임베딩, 작업 복구
  db/migrations/           테이블·제약·RLS 마이그레이션
  eval/manifests/           문서 URL·취득일·SHA256·버전
  eval/questions/          개발/최종 평가 질문과 원본 근거
  eval/configs/            B0 및 실험별 고정 설정
  eval/runs/               실행별 결과 (로컬, Git 제외)
  tests/authorization/     조직·문서 접근 및 권한 취소
  tests/calculation/       Decimal 및 기간·단위 검증
  tests/ingestion/         처리·재시도·삭제·복구
  docs/                    설계·인터뷰·진행 기록
  .github/workflows/       실제 실행 명령 확정 후 CI 추가
```

Docker Compose와 의존성 lockfile은 다음 단계에서 실제 구동 검증 후 추가한다.

## 이번 작업 (S0)

원본 보존 및 이동, 폴더 구조, 첫 구현 범위, 설계 이유, 검증 계획, 진행 기록 작성. 앱 구현이나 성능 측정은 포함하지 않는다.

## 첫 구현 (S1): 데이터·보안 기반

1. 공개 annual report 2–3개를 선정한다. 원본 URL, 취득일, SHA256, 보고서 버전, 배포 조건을 기록한다.
2. PyMuPDF로 페이지 텍스트·좌표·표 후보를 추출하는 작은 실험을 만든다. 각 PDF의 대표 표에서 연도/행/단위/괄호 음수 보존 여부를 원본과 대조한다. 실패 표도 기록한다.
3. 조회·계산·근거 부족·모호함 유형의 초기 개발 질문 12개를 목표로 직접 검토한다. 숫자 목표는 제안이며 생성 완료가 아니다. 최종 평가 세트로 사용하지 않는다.
4. users, organizations, memberships, documents, document_grants 및 조직 일치 제약을 마이그레이션한다. job/chunk/fact 구조는 뒤 단계와 연결 가능한 형태로 설계한다.
5. 순수 권한 정책과 DB RLS를 구현한다. 테스트 전용 사용자 컨텍스트로 DB 격리를 검증하되, 이를 실제 인증 완료로 부르지 않는다.
6. API 최소 실행/health, DB 연결, 마이그레이션 및 테스트 명령을 README에 기록한다. 버전·lockfile과 DB 개발 환경을 고정한다.

완료 기준: 깨끗한 DB에 마이그레이션 성공, 비소유자 API DB 역할에서 A/B 조직과 restricted ACL 허용/거부 검증, 연결 풀 컨텍스트 잔류 없음, PDF 추출 실패 사례 기록, 질문 12개 원본 대조 완료. 인증 전에는 실제 문서 API를 외부에 노출하지 않는다.

## 후속 단계

| 단계 | 구현 | 통과 기준 |
|---|---|---|
| S2 | 단일 OIDC 제공자, 초대·세션, 업로드/상태/삭제, worker, B0 | 실제 인증 경로와 인용 접근까지 조직 격리; 업로드부터 근거 답변까지 연결 |
| S3 | 평가 도구, B0 측정, R1 표 청크/R2 hybrid/R3 결합 | 같은 문서·질문·권한·모델·context budget에서 비교 |
| S4 | G1 근거 부족 보류, G2 인용/주장 검증 | 오류율과 응답률·불필요 보류율 함께 보고 |
| S5 | N1 구조화 추출, N2 Decimal 계산 | 추출·계산·end-to-end 오류 구분; 동일 입력 계산 비교 |
| S6 | 최종 평가, 복구·삭제 회귀, Docker/CI, 데모 | 보안 실패 없음, 재현 명령·실측 결과·제한사항 기록 |

CI는 실행 가능한 테스트가 생기는 S1부터 시작하고 S6에서 전체 흐름을 완성한다. 약 6주는 원안의 제안으로, 완료 조건을 우선한다.

## 아직 결정하지 않은 사항

OIDC 제공자/라이브러리, LLM 제공자/모델, 임베딩 모델/버전, 개발 환경 버전, 최종 회사·보고서, 비용 한도. 해당 구현 직전에 공식 문서·실행 환경을 확인하고 결정 기록을 갱신한다.

## 현재 진행 (2026-10-10)

S1-1: 공개 보고서 2개, 대표 표 4개의 추출 실험 완료. 상세 결과는 [실험 기록](PDF_EXTRACTION_S1.md). S1-2 질문 12개 작성·Codex 원본 대조, S1-3 DB/RLS/최소 API 및 로컬 40개 테스트를 완료했다. 독립 사람 검수는 pending. CI 파일은 작성했으나 원격 실행은 하지 않았다. [권한 구현 검증](S1_SECURITY_AND_API.md), [질문 검토 수준](S1_QUESTIONS.md)을 참고한다.
