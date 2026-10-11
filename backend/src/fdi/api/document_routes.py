"""Documents: listing, admin upload and management, deletion, and citation page images."""
import hashlib
from datetime import date
from typing import Literal
from uuid import UUID, uuid4
import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from fdi.api.deps import NOT_FOUND, Principal, authenticated_principal, member_id, require_admin, require_member
from fdi.auth.policy import Membership, can_read
from fdi.db.session import request_connection
from fdi.worker.jobs import enqueue

router = APIRouter(prefix='/organizations/{organization_id}/documents')
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PAGE_IMAGE_ZOOM = 1.5


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    visibility: Literal['organization', 'restricted'] | None = None
    fiscal_year_end: date | None = None


class GrantCreate(BaseModel):
    user_id: UUID


def _document(r):
    return {'id': str(r['id']), 'title': r['title'], 'status': r['status'], 'visibility': r['visibility'],
            'fiscal_year_end': r['fiscal_year_end'].isoformat() if r['fiscal_year_end'] else None,
            'created_at': r['created_at'].isoformat()}


def read_documents(pool, org, user_id, document_id=None):
    with request_connection(pool, user_id, org) as conn:
        row = conn.execute('SELECT role,active FROM fdi.memberships WHERE organization_id=%s AND user_id=%s',
                           (org, user_id)).fetchone()
        membership = Membership(org, row['role'], row['active'], True) if row else None
        if not membership:
            raise NOT_FOUND
        records = conn.execute('''SELECT d.id,d.organization_id,d.title,d.visibility,d.status,d.fiscal_year_end,d.created_at,
            EXISTS(SELECT 1 FROM fdi.document_grants g WHERE g.organization_id=d.organization_id
            AND g.document_id=d.id AND g.user_id=%s) AS granted FROM fdi.documents d
            WHERE d.organization_id=%s AND (%s::uuid IS NULL OR d.id=%s::uuid) ORDER BY d.created_at DESC, d.id''',
            (user_id, org, document_id, document_id)).fetchall()
        # Pure policy re-check on top of RLS (e.g. hides deleting documents from admins).
        return [_document(r) for r in records
                if can_read(membership, r['organization_id'], r['visibility'], r['granted'], r['status'])]


@router.get('')
def documents(organization_id: UUID, request: Request, principal: Principal = Depends(authenticated_principal)):
    return {'documents': read_documents(request.app.state.pool, organization_id, member_id(principal))}


@router.get('/{document_id}')
def document(organization_id: UUID, document_id: UUID, request: Request, principal: Principal = Depends(authenticated_principal)):
    rows = read_documents(request.app.state.pool, organization_id, member_id(principal), document_id)
    if not rows:
        raise NOT_FOUND
    return rows[0]


async def _read_pdf(file):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, 'File exceeds 50 MB')
    if not data.startswith(b'%PDF-'):
        raise HTTPException(415, 'Only PDF files are accepted')
    return data


@router.post('', status_code=201)
async def upload(organization_id: UUID, request: Request, file: UploadFile = File(...),
                 title: str = Form(min_length=1, max_length=300),
                 visibility: Literal['organization', 'restricted'] = Form('organization'),
                 fiscal_year_end: date = Form(...), principal: Principal = Depends(authenticated_principal)):
    """Admin upload: validate, store under a random key, register as queued, enqueue table-aware ingestion."""
    from fdi.answering.b0 import CONFIGS
    me = member_id(principal)
    data = await _read_pdf(file)
    digest = hashlib.sha256(data).hexdigest()
    state = request.app.state
    # Check role before storing anything.
    with request_connection(state.pool, me, organization_id) as conn:
        require_admin(conn, organization_id)
        existing = conn.execute("SELECT id FROM fdi.documents WHERE organization_id=%s AND sha256=%s AND status <> 'deleting'",
                                (organization_id, digest)).fetchone()
        if existing:
            raise HTTPException(409, f"This file is already uploaded as document {existing['id']}")
    key = state.storage.put(data)
    document_id = uuid4()
    try:
        with request_connection(state.pool, me, organization_id) as conn:
            require_admin(conn, organization_id)
            row = conn.execute('''INSERT INTO fdi.documents (id, organization_id, title, storage_key, sha256, source_version,
                    visibility, status, fiscal_year_end) VALUES (%s,%s,%s,%s,%s,%s,%s,'queued',%s)
                RETURNING id, title, status, visibility, fiscal_year_end, created_at''',
                (document_id, organization_id, title.strip(), key, digest, f'uploaded {date.today().isoformat()}',
                 visibility, fiscal_year_end)).fetchone()
            enqueue(conn, organization_id, document_id, digest, CONFIGS['G2'].chunker)
    except Exception:
        state.storage.path(key).unlink(missing_ok=True)  # no orphaned original if registration fails
        raise
    return _document(row)


@router.patch('/{document_id}')
def update(organization_id: UUID, document_id: UUID, body: DocumentUpdate, request: Request,
           principal: Principal = Depends(authenticated_principal)):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, 'Nothing to change')
    with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
        require_admin(conn, organization_id)
        sets = ', '.join(f'{k}=%s' for k in changes)  # keys from the validated model
        row = conn.execute(f"""UPDATE fdi.documents SET {sets} WHERE organization_id=%s AND id=%s AND status <> 'deleting'
            RETURNING id, title, status, visibility, fiscal_year_end, created_at""",
            (*changes.values(), organization_id, document_id)).fetchone()
    if not row:
        raise NOT_FOUND
    return _document(row)


@router.delete('/{document_id}', status_code=202)
def delete(organization_id: UUID, document_id: UUID, request: Request, principal: Principal = Depends(authenticated_principal)):
    """Hide immediately (status deleting excludes it from reads and retrieval); a worker job removes
    the file, pages, chunks, grants, and row."""
    with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
        require_admin(conn, organization_id)
        row = conn.execute("""UPDATE fdi.documents SET status='deleting' WHERE organization_id=%s AND id=%s
            AND status <> 'deleting' RETURNING id""", (organization_id, document_id)).fetchone()
        if not row:
            raise NOT_FOUND
        conn.execute('''INSERT INTO fdi.ingestion_jobs (organization_id, document_id, dedup_key, kind)
            VALUES (%s,%s,%s,'delete') ON CONFLICT (dedup_key) DO NOTHING''',
            (organization_id, document_id, f'delete:{document_id}'))
    return {'id': str(document_id), 'status': 'deleting'}


@router.get('/{document_id}/grants')
def grants(organization_id: UUID, document_id: UUID, request: Request, principal: Principal = Depends(authenticated_principal)):
    with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
        require_admin(conn, organization_id)
        if not conn.execute("SELECT 1 FROM fdi.documents WHERE organization_id=%s AND id=%s AND status <> 'deleting'",
                            (organization_id, document_id)).fetchone():
            raise NOT_FOUND
        rows = conn.execute('''SELECT g.user_id, (SELECT string_agg(i.email, ', ') FROM fdi.user_identities i
            WHERE i.user_id=g.user_id) AS email FROM fdi.document_grants g WHERE g.organization_id=%s AND g.document_id=%s
            ORDER BY email''', (organization_id, document_id)).fetchall()
    return {'grants': [{'user_id': str(r['user_id']), 'email': r['email']} for r in rows]}


@router.post('/{document_id}/grants', status_code=201)
def add_grant(organization_id: UUID, document_id: UUID, body: GrantCreate, request: Request,
              principal: Principal = Depends(authenticated_principal)):
    try:
        with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
            require_admin(conn, organization_id)
            if not conn.execute("SELECT 1 FROM fdi.documents WHERE organization_id=%s AND id=%s AND status <> 'deleting'",
                                (organization_id, document_id)).fetchone():
                raise NOT_FOUND
            conn.execute('''INSERT INTO fdi.document_grants (organization_id, document_id, user_id) VALUES (%s,%s,%s)
                ON CONFLICT DO NOTHING''', (organization_id, document_id, body.user_id))
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(422, 'User is not a member of this organization')
    return {'user_id': str(body.user_id)}


@router.delete('/{document_id}/grants/{user_id}', status_code=204)
def remove_grant(organization_id: UUID, document_id: UUID, user_id: UUID, request: Request,
                 principal: Principal = Depends(authenticated_principal)):
    with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
        require_admin(conn, organization_id)
        removed = conn.execute('DELETE FROM fdi.document_grants WHERE organization_id=%s AND document_id=%s AND user_id=%s',
                               (organization_id, document_id, user_id)).rowcount
    if not removed:
        raise NOT_FOUND


@router.get('/{document_id}/pages/{page_number}/image')
def page_image(organization_id: UUID, document_id: UUID, page_number: int, request: Request,
               chunk_id: UUID | None = None, principal: Principal = Depends(authenticated_principal)):
    """Citation view: renders one page of a readable, ready document, optionally outlining a cited chunk.
    The original file is never served. Unreadable, missing, and other-organization pages all return 404."""
    with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
        require_member(conn, organization_id)
        # document_pages RLS: visible only for ready documents the caller may read.
        page = conn.execute('''SELECT p.page_number, d.storage_key, d.sha256 FROM fdi.document_pages p
            JOIN fdi.documents d ON d.organization_id=p.organization_id AND d.id=p.document_id
            WHERE p.organization_id=%s AND p.document_id=%s AND p.page_number=%s''',
            (organization_id, document_id, page_number)).fetchone()
        if not page:
            raise NOT_FOUND
        boxes = []
        if chunk_id:
            chunk = conn.execute('SELECT spans FROM fdi.chunks WHERE id=%s AND organization_id=%s AND document_id=%s',
                                 (chunk_id, organization_id, document_id)).fetchone()
            if not chunk:
                raise NOT_FOUND
            boxes = [s['bbox'] for s in chunk['spans'] if s['page'] == page_number]
    path = request.app.state.storage.path(page['storage_key'])
    data = path.read_bytes() if path.is_file() else b''
    if hashlib.sha256(data).hexdigest() != page['sha256']:
        raise HTTPException(503, 'Service unavailable')
    import pymupdf
    with pymupdf.open(stream=data, filetype='pdf') as pdf:
        pdf_page = pdf[page_number - 1]
        for box in boxes:
            pdf_page.draw_rect(pymupdf.Rect(*box) + (-3, -3, 3, 3), color=(0.9, 0.55, 0), width=2)
        png = pdf_page.get_pixmap(matrix=pymupdf.Matrix(PAGE_IMAGE_ZOOM, PAGE_IMAGE_ZOOM)).tobytes('png')
    return Response(png, media_type='image/png', headers={'Cache-Control': 'private, no-store',
                                                         'X-Content-Type-Options': 'nosniff'})
