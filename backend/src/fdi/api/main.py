"""FDI API. Browsers never call it directly: the Next.js server forwards short-lived signed identity
tokens (see fdi.auth.tokens). Bind to 127.0.0.1 or a private network only."""
from contextlib import asynccontextmanager
from uuid import UUID
import psycopg
from psycopg_pool import PoolTimeout
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from fdi.answering.b0 import CONFIGS, NotMember, answer_question
from fdi.answering.llm import LLMError
from fdi.api import admin_routes, document_routes, identity_routes
from fdi.api.deps import Principal, authenticated_principal, member_id
from fdi.api.document_routes import read_documents  # noqa: F401  (kept for tests and tools)
from fdi.auth.tokens import load_public_key
from fdi.db.session import create_pool
from fdi.storage import LocalStorage

__all__ = ['create_app', 'authenticated_principal', 'Principal']


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def create_app(pool=None, embedder=None, llm=None, answer_config=CONFIGS['G2'], auth_pool=None,
               public_key=None, storage=None):
    """Owns its pools when none are passed. Tests pass pools, keys, and storage explicitly."""
    @asynccontextmanager
    async def lifespan(app):
        owned = pool is None
        if owned:
            from fdi.db.config import dsn
            app.state.pool = create_pool(dsn())
            app.state.auth_pool = create_pool(dsn(role='auth'), max_size=2, expected_role='fdi_auth')
            app.state.public_key = load_public_key()
        else:
            app.state.pool, app.state.auth_pool, app.state.public_key = pool, auth_pool, public_key
        try:
            yield
        finally:
            if owned:
                app.state.pool.close()
                app.state.auth_pool.close()

    app = FastAPI(title='FDI', lifespan=lifespan)
    app.state.embedder, app.state.llm = embedder, llm
    app.state.storage = storage or LocalStorage()

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

    app.include_router(identity_routes.router)
    app.include_router(admin_routes.router)
    app.include_router(document_routes.router)

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
    def ask(organization_id: UUID, body: QuestionRequest, request: Request,
            principal: Principal = Depends(authenticated_principal)):
        user_id = member_id(principal)
        try:
            embedder, llm = answer_dependencies()
        except LLMError:
            raise HTTPException(503, 'Service unavailable')
        try:
            return answer_question(app.state.pool, user_id, organization_id, body.question, embedder, llm, answer_config)
        except NotMember:
            raise HTTPException(404, 'Not found')
        except ValueError:
            raise HTTPException(422, 'Invalid question')

    return app


app = create_app()
