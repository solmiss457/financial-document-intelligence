# 로컬 개발과 검증

## 실행

PDF 실험 및 DB/API 실행 명령은 아래에 있다. 문서 HTTP API는 인증 미구현으로 기본 401이며, 테스트에서만 신원을 주입한다. 웹 UI·OIDC·RAG는 아직 없다.

## S1-1 PDF 추출 실험 (2026-10-10)

공개 보고서 2개와 대표 표 4개를 검증했다. [실측 및 실패 기록](../docs/PDF_EXTRACTION_S1.md)을 참고한다. 이어서 개발 질문 12개와 DB/RLS/최소 API를 구현했다(아래).

검증 환경: Python 3.12.14, macOS arm64. Python 3.12가 설치된 환경에서 루트에서 실행한다. lock은 macOS arm64 전용이며 다른 OS는 별도 검증이 필요하다.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --cache-dir work/pip-cache --require-hashes -r requirements-pdf-macos-arm64.lock
mkdir -p storage/reports
curl --fail --location --silent --show-error 'https://www.berkshirehathaway.com/2023ar/2023ar.pdf' -o storage/reports/berkshire-2023.pdf
curl --fail --location --silent --show-error 'https://www.berkshirehathaway.com/2024ar/2024ar.pdf' -o storage/reports/berkshire-2024.pdf
.venv/bin/python scripts/probe_pdf.py
.venv/bin/python -m unittest discover -s tests/ingestion -p 'test_*.py' -v
```

이 작업에서는 Codex 번들 Python 3.12.14로 `.venv`를 생성했다. 원본 다운로드가 바뀌면 해시 오류를 조사하고 manifest를 무조건 덮어쓰지 않는다. 원본·페이지 이미지·추출 전문은 Git 제외 `storage/`, `work/`에만 보관한다. 테스트 1건은 8개 표/전략 조합의 결과(알려진 실패 포함) 회귀 확인이며, 전체 표 정확도나 보안 검증 결과가 아니다.

## S1-2 / S1-3: 개발 질문·DB·API

[개발 질문과 검토 한계](../docs/S1_QUESTIONS.md), [권한 구현·실제 검증](../docs/S1_SECURITY_AND_API.md).

준비: Python 3.12 및 실행 중인 Docker Desktop. 루트에서 실행한다. API lock은 직접/간접 버전을 고정하며, PDF 해시 lock과 달리 wheel 해시 lock은 아니다. Linux CI는 아직 원격 실행 전이다.

```sh
# .venv가 없으면 먼저 Python 3.12로 생성
.venv/bin/python -m pip install --cache-dir work/pip-cache -r requirements-api.lock
.venv/bin/python scripts/init_local_env.py
# .env.example을 .env로 복사하지 않는다. 위 명령이 랜덤 자격 증명을 생성한다.
docker compose up -d --wait db
.venv/bin/python -m scripts.migrate
.venv/bin/python -m scripts.prepare_test_db
.venv/bin/python -m scripts.check_clean_migrations
# 원본 PDF 없이 실행 가능한 DB/API + 질문 계약 검사
.venv/bin/python -m pytest tests/authorization tests/test_questions.py -k 'not source_values' -q
# 위 PDF 설치/다운로드까지 완료했을 때 전체 40개 검사
.venv/bin/python -m pytest -q
# 로컬 API 실행
.venv/bin/python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

`/health`, `/ready`는 200, 문서 API는 기본 401이다. X-User-ID 같은 테스트 헤더는 지원하지 않는다. 개발 DB `fdi`는 자동 샘플 데이터 없이 생성된다. 테스트는 `fdi_test`의 테스트 데이터만 초기화하며 실제 보고서를 업로드한 것이 아니다. `check_clean_migrations`는 새 임시 DB 생성·마이그레이션·재실행 검증 후 자신이 생성한 DB만 삭제한다.

현재 DB: `127.0.0.1:55432`, 데이터: Git 제외 `storage/postgres`. API를 끝내려면 Ctrl-C, DB를 멈추려면 `docker compose stop db`. DB 볼륨 파일을 직접 삭제하지 않는다. 비밀 값은 로컬 `.env`(0600)에만 보관하고 출력/커밋하지 않는다. 기본값 변경이 필요하면 `FDI_DB_PORT`, `FDI_DB_NAME`을 사용하되 compose 포트와 일치시킨다.

`.github/workflows/s1.yml`은 원본 PDF 다운로드 없이 보안/API/질문 계약을 검사한다. workflow 작성 완료와 원격 CI 통과는 구분한다. 공개 데모·실제 인증·검색·인용·다운로드 검증은 S2 이후다.
