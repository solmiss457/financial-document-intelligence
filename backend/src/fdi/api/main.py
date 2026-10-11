"""S1 API skeleton. No production identity provider is configured yet."""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID
import psycopg
from psycopg_pool import PoolTimeout
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from fdi.db.session import create_pool, request_connection
from fdi.auth.policy import Membership, can_read
from fdi.answering.b0 import B0Config, NotMember, answer_question
from fdi.answering.llm import LLMError


@dataclass(frozen=True)
class Principal:
    user_id: UUID


def authenticated_principal() -> Principal:
    # Only tests override this dependency. Never trust X-User-ID or org claims.
    raise HTTPException(401, 'Authentication required')


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def create_app(pool=None, embedder=None, llm=None, answer_config=B0Config()):
    @asynccontextmanager
    async def lifespan(app):
        owned = pool is None
        if owned:
            from fdi.db.config import dsn
            app.state.pool = create_pool(dsn())
        else:
            app.state.pool = pool
        try:
            yield
        finally:
            if owned:
                app.state.pool.close()

    app = FastAPI(title='FDI', lifespan=lifespan)
    app.state.embedder, app.state.llm = embedder, llm

    @app.exception_handler(psycopg.Error)
    @app.exception_handler(PoolTimeout)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={'detail': 'Service unavailable'})

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.get('/ready')
    def ready():
        with app.state.pool.connection() as conn:
            conn.execute('SELECT 1 FROM fdi.documents LIMIT 0')
        return {'status': 'ready'}

    def read_documents(org, principal, document_id=None):
        with request_connection(app.state.pool, principal.user_id, org) as conn:
            row = conn.execute('SELECT role,active FROM fdi.memberships WHERE organization_id=%s AND user_id=%s',
                               (org, principal.user_id)).fetchone()
            membership = Membership(org, row['role'], row['active'], True) if row else None
            if not membership:
                raise HTTPException(404, 'Not found')
            records = conn.execute('''SELECT d.id,d.organization_id,d.title,d.visibility,d.status,
                EXISTS(SELECT 1 FROM fdi.document_grants g WHERE g.organization_id=d.organization_id
                AND g.document_id=d.id AND g.user_id=%s) AS granted FROM fdi.documents d
                WHERE d.organization_id=%s AND (%s::uuid IS NULL OR d.id=%s::uuid) ORDER BY d.id''',
                (principal.user_id, org, document_id, document_id)).fetchall()
            return [dict(id=str(r['id']), title=r['title'], status=r['status']) for r in records
                    if can_read(membership, r['organization_id'], r['visibility'], r['granted'], r['status'])]

    @app.get('/organizations/{organization_id}/documents')
    def documents(organization_id: UUID, principal: Principal = Depends(authenticated_principal)):
        return {'documents': read_documents(organization_id, principal)}

    @app.get('/organizations/{organization_id}/documents/{document_id}')
    def document(organization_id: UUID, document_id: UUID, principal: Principal = Depends(authenticated_principal)):
        rows = read_documents(organization_id, principal, document_id)
        if not rows:
            raise HTTPException(404, 'Not found')
        return rows[0]

    def answer_dependencies():
        # Loaded on first use so the API starts without the model or an LLM key.
        if app.state.embedder is None:
            from fdi.ingestion.embedding import SentenceTransformerEmbedder
            app.state.embedder = SentenceTransformerEmbedder()
        if app.state.llm is None:
            from fdi.answering.llm import OpenAIResponsesLLM
            app.state.llm = OpenAIResponsesLLM(answer_config.llm_model, answer_config.reasoning_effort)
        return app.state.embedder, app.state.llm

    @app.post('/organizations/{organization_id}/questions')
    def ask(organization_id: UUID, body: QuestionRequest, principal: Principal = Depends(authenticated_principal)):
        try:
            embedder, llm = answer_dependencies()
        except LLMError:
            raise HTTPException(503, 'Service unavailable')
        try:
            return answer_question(app.state.pool, principal.user_id, organization_id, body.question,
                                   embedder, llm, answer_config)
        except NotMember:
            raise HTTPException(404, 'Not found')
        except ValueError:
            raise HTTPException(422, 'Invalid question')

    return app


app = create_app()
