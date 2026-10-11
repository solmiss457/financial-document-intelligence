"""P1-P3 through the real authentication path: signed tokens, identity linking, invitations,
administration, uploads, citation page images, and deletion. Uses the fdi_test database."""
import hashlib
from uuid import UUID
import pymupdf
import pytest
from fastapi.testclient import TestClient
from fdi.api import document_routes
from fdi.api.main import create_app
from fdi.auth.tokens import GOOGLE_ISSUER, Identity, mint
from fdi.db.config import dsn
from fdi.db.session import create_pool
from fdi.ingestion.embedding import HashEmbedder
from fdi.storage import LocalStorage
from fdi.worker.jobs import Settings, run_once
from tests.api.test_auth_tokens import PRIVATE, PUBLIC


def u(n): return UUID(int=n)


def who(name, verified=True):
    return Identity(GOOGLE_ISSUER, f'google-{name}', f'{name}@example.com', verified)


MEMBER, OTHER_MEMBER, ADMIN, ADMIN_B = who('m11'), who('m12'), who('a13'), who('a21')


def pdf_bytes(pages=2, marker='Revenue'):
    doc = pymupdf.open()
    for p in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), 'EXAMPLE CORP. CONSOLIDATED STATEMENTS OF EARNINGS (dollars in millions)')
        page.insert_text((300, 100), '2024        2023')
        for i, (label, a, b) in enumerate([('Total revenues', '1,000', '900'), ('Net earnings', '100', '(50)'),
                                          ('Operating income', '200', '150')]):
            page.insert_text((72, 120 + 14 * i), label)
            page.insert_text((300, 120 + 14 * i), f'{a}        {b}')
        page.insert_text((72, 300), f'{marker} narrative page {p + 1}')
    return doc.tobytes()


@pytest.fixture
def api(database, tmp_path):
    admin, pool = database
    for user, ident in ((11, MEMBER), (12, OTHER_MEMBER), (13, ADMIN), (21, ADMIN_B)):
        admin.execute('INSERT INTO fdi.user_identities (issuer, subject, user_id, email) VALUES (%s,%s,%s,%s)',
                      (ident.issuer, ident.subject, u(user), ident.email))
    auth_pool = create_pool(dsn(role='auth'), max_size=1, expected_role='fdi_auth')
    worker = create_pool(dsn(role='worker'), max_size=1, expected_role='fdi_worker')
    storage = LocalStorage(tmp_path / 'documents')
    app = create_app(pool, embedder=HashEmbedder(), auth_pool=auth_pool, public_key=PUBLIC, storage=storage)
    with TestClient(app) as client:
        def call(method, path, identity=None, **kw):
            headers = kw.pop('headers', {})
            if identity:
                headers['Authorization'] = 'Bearer ' + mint(identity, PRIVATE)
            return client.request(method, path, headers=headers, **kw)
        yield call, admin, worker, storage
    auth_pool.close()
    worker.close()


def drain(worker, storage):
    while run_once(worker, 'test-worker', storage, HashEmbedder(), Settings(lease_seconds=60, extract_timeout_seconds=60)):
        pass


# ---------- P1: authentication boundary ----------

def test_requests_need_a_valid_signed_token(api):
    call, *_ = api
    docs = f'/organizations/{u(1)}/documents'
    assert call('GET', docs).status_code == 401
    assert call('GET', docs, headers={'X-User-ID': str(u(11))}).status_code == 401
    assert call('GET', docs, headers={'Authorization': 'Bearer not-a-token'}).status_code == 401
    assert call('GET', docs, headers={'Authorization': 'Basic abc'}).status_code == 401
    assert call('GET', docs, MEMBER).status_code == 200
    assert call('GET', '/health').status_code == 200


def test_me_lists_only_active_memberships(api):
    call, admin, *_ = api
    body = call('GET', '/me', MEMBER).json()
    assert body['user_id'] == str(u(11)) and [m['organization_id'] for m in body['memberships']] == [str(u(1))]
    assert body['email'] == 'm11@example.com'
    admin.execute('UPDATE fdi.users SET active=false WHERE id=%s', (u(11),))
    body = call('GET', '/me', MEMBER).json()
    assert body['user_id'] is None and body['memberships'] == []
    assert call('GET', f'/organizations/{u(1)}/documents', MEMBER).status_code == 404


def test_unlinked_google_account_gets_nothing(api):
    call, *_ = api
    stranger = who('stranger')
    body = call('GET', '/me', stranger).json()
    assert body == {'user_id': None, 'email': 'stranger@example.com', 'email_verified': True,
                    'memberships': [], 'pending_invitations': []}
    for path in (f'/organizations/{u(1)}/documents', f'/organizations/{u(1)}/members'):
        assert call('GET', path, stranger).status_code == 404
    assert call('POST', f'/organizations/{u(1)}/questions', stranger, json={'question': 'q'}).status_code == 404


# ---------- P2: invitations and membership administration ----------

def invite(call, email, role='member', identity=ADMIN, org=1):
    return call('POST', f'/organizations/{u(org)}/invitations', identity, json={'email': email, 'role': role})


def test_invitation_accepted_only_by_verified_matching_email(api):
    call, admin, *_ = api
    created = invite(call, 'New.Person@Example.com')
    assert created.status_code == 201 and created.json()['email'] == 'new.person@example.com'
    inv = created.json()['id']
    assert invite(call, 'new.person@example.com').status_code == 409          # one pending invitation per email
    impostor, unverified = who('impostor'), Identity(GOOGLE_ISSUER, 'google-np2', 'new.person@example.com', False)
    assert call('POST', f'/invitations/{inv}/accept', impostor).status_code == 404
    assert call('POST', f'/invitations/{inv}/accept', unverified).status_code == 403
    assert call('GET', '/me', unverified).json()['pending_invitations'] == []
    invitee = Identity(GOOGLE_ISSUER, 'google-np', 'new.person@example.com', True)
    pending = call('GET', '/me', invitee).json()['pending_invitations']
    assert [p['id'] for p in pending] == [inv] and pending[0]['organization_name'] == 'Organization 1'
    accepted = call('POST', f'/invitations/{inv}/accept', invitee)
    assert accepted.status_code == 200 and accepted.json()['role'] == 'member'
    assert call('POST', f'/invitations/{inv}/accept', invitee).status_code == 404   # single use
    me = call('GET', '/me', invitee).json()
    assert [m['organization_id'] for m in me['memberships']] == [str(u(1))]
    assert call('GET', f'/organizations/{u(1)}/documents', invitee).status_code == 200
    assert call('GET', f'/organizations/{u(2)}/documents', invitee).status_code == 404


def test_expired_revoked_and_deactivated_invitations(api):
    call, admin, *_ = api
    expired = invite(call, 'late@example.com').json()['id']
    admin.execute("UPDATE fdi.invitations SET created_at=now()-interval '9 days', expires_at=now()-interval '1 day' WHERE id=%s", (expired,))
    late = who('late')
    assert call('POST', f'/invitations/{expired}/accept', late).status_code == 404
    revoked = invite(call, 'gone@example.com').json()['id']
    assert call('DELETE', f'/organizations/{u(1)}/invitations/{revoked}', ADMIN).status_code == 204
    assert call('POST', f'/invitations/{revoked}/accept', who('gone')).status_code == 404
    assert call('DELETE', f'/organizations/{u(1)}/invitations/{revoked}', ADMIN).status_code == 404
    # A deactivated member is not silently reactivated by a new invitation.
    admin.execute('UPDATE fdi.memberships SET active=false WHERE user_id=%s AND organization_id=%s', (u(12), u(1)))
    again = invite(call, 'm12-new@example.com').json()['id']
    admin.execute("UPDATE fdi.invitations SET email='m12@example.com' WHERE id=%s", (again,))
    assert call('POST', f'/invitations/{again}/accept', OTHER_MEMBER).status_code == 409


def test_invitation_and_member_admin_require_admin_of_that_organization(api):
    call, *_ = api
    assert invite(call, 'x@example.com', identity=MEMBER).status_code == 403
    assert invite(call, 'x@example.com', identity=ADMIN_B).status_code == 404
    assert invite(call, 'not-an-email', identity=ADMIN).status_code == 422
    assert invite(call, 'm11@example.com', identity=ADMIN).status_code == 409   # already a member
    assert call('GET', f'/organizations/{u(1)}/members', MEMBER).status_code == 403
    assert call('GET', f'/organizations/{u(1)}/invitations', ADMIN_B).status_code == 404
    members = call('GET', f'/organizations/{u(1)}/members', ADMIN).json()['members']
    emails = {m['email'] for m in members}
    assert {'m11@example.com', 'a13@example.com'} <= emails and 'a21@example.com' not in emails


def test_member_role_and_deactivation(api):
    call, *_ = api
    path = f'/organizations/{u(1)}/members'
    assert call('PATCH', f'{path}/{u(13)}', ADMIN, json={'role': 'member'}).status_code == 400   # self
    assert call('PATCH', f'{path}/{u(21)}', ADMIN, json={'role': 'admin'}).status_code == 404    # other org's user
    assert call('PATCH', f'{path}/{u(12)}', MEMBER, json={'role': 'admin'}).status_code == 403
    assert call('PATCH', f'{path}/{u(12)}', ADMIN, json={}).status_code == 422
    assert call('PATCH', f'{path}/{u(11)}', ADMIN, json={'role': 'admin'}).json()['role'] == 'admin'
    assert call('GET', f'/organizations/{u(1)}/members', MEMBER).status_code == 200            # promotion is live
    assert call('PATCH', f'{path}/{u(11)}', ADMIN, json={'active': False}).json()['active'] is False
    assert call('GET', f'/organizations/{u(1)}/documents', MEMBER).status_code == 404          # next request


# ---------- P3: documents ----------

def upload(call, data, identity=ADMIN, org=1, title='Example 2024', visibility='organization'):
    return call('POST', f'/organizations/{u(org)}/documents', identity,
                files={'file': ('report.pdf', data, 'application/pdf')},
                data={'title': title, 'visibility': visibility, 'fiscal_year_end': '2024-12-31'})


def test_upload_validates_and_registers_for_table_aware_ingestion(api, monkeypatch):
    call, admin, worker, storage = api
    data = pdf_bytes()
    assert upload(call, data, identity=MEMBER).status_code == 403
    assert upload(call, data, identity=ADMIN_B).status_code == 404                              # admin of another org
    assert upload(call, b'not a pdf').status_code == 415
    monkeypatch.setattr(document_routes, 'MAX_UPLOAD_BYTES', 100)
    assert upload(call, data).status_code == 413
    monkeypatch.undo()
    assert not storage.root.exists() or not any(storage.root.iterdir())                      # nothing stored yet
    created = upload(call, data)
    assert created.status_code == 201
    doc = created.json()
    assert (doc['status'], doc['visibility'], doc['fiscal_year_end']) == ('queued', 'organization', '2024-12-31')
    assert upload(call, data).status_code == 409                                                # same file again
    row = admin.execute('SELECT storage_key, sha256 FROM fdi.documents WHERE id=%s', (doc['id'],)).fetchone()
    assert row[1] == hashlib.sha256(data).hexdigest() and storage.path(row[0]).read_bytes() == data
    job = admin.execute('SELECT chunker, kind FROM fdi.ingestion_jobs WHERE document_id=%s', (doc['id'],)).fetchone()
    assert job == ('table_rows_v1:12r1200c+150/30', 'ingest')
    drain(worker, storage)
    assert call('GET', f"/organizations/{u(1)}/documents/{doc['id']}", MEMBER).json()['status'] == 'ready'


def test_citation_page_images_follow_document_permissions(api):
    call, admin, worker, storage = api
    doc = upload(call, pdf_bytes()).json()['id']
    drain(worker, storage)
    chunk = admin.execute('SELECT id FROM fdi.chunks WHERE document_id=%s ORDER BY chunk_index LIMIT 1', (doc,)).fetchone()[0]
    image = f'/organizations/{u(1)}/documents/{doc}/pages/1/image'
    ok = call('GET', image, MEMBER, params={'chunk_id': str(chunk)})
    assert ok.status_code == 200 and ok.headers['content-type'] == 'image/png' and ok.content.startswith(b'\x89PNG')
    assert ok.headers['cache-control'] == 'private, no-store'
    assert call('GET', image, ADMIN_B).status_code == 404                                       # other organization
    assert call('GET', f'/organizations/{u(2)}/documents/{doc}/pages/1/image', ADMIN_B).status_code == 404
    assert call('GET', f'/organizations/{u(1)}/documents/{doc}/pages/99/image', MEMBER).status_code == 404
    other_chunk = admin.execute('INSERT INTO fdi.chunks (organization_id,document_id,chunker,chunk_index,page_start,page_end,'
                                "spans,text,embedding_model,embedding) VALUES (%s,%s,'x',0,1,1,'[]','x','h',array_fill(0,array[384])::vector) RETURNING id",
                                (u(1), u(101))).fetchone()[0]
    assert call('GET', image, MEMBER, params={'chunk_id': str(other_chunk)}).status_code == 404  # chunk of another document
    # Restrict, then grant and revoke access for one member.
    assert call('PATCH', f'/organizations/{u(1)}/documents/{doc}', ADMIN, json={'visibility': 'restricted'}).status_code == 200
    assert call('GET', image, MEMBER).status_code == 404
    assert call('POST', f'/organizations/{u(1)}/documents/{doc}/grants', ADMIN, json={'user_id': str(u(11))}).status_code == 201
    assert call('GET', image, MEMBER).status_code == 200 and call('GET', image, OTHER_MEMBER).status_code == 404
    assert call('POST', f'/organizations/{u(1)}/documents/{doc}/grants', ADMIN, json={'user_id': str(u(21))}).status_code == 422
    assert [g['email'] for g in call('GET', f'/organizations/{u(1)}/documents/{doc}/grants', ADMIN).json()['grants']] == ['m11@example.com']
    assert call('DELETE', f'/organizations/{u(1)}/documents/{doc}/grants/{u(11)}', ADMIN).status_code == 204
    assert call('GET', image, MEMBER).status_code == 404


def test_delete_hides_immediately_then_worker_removes_everything(api):
    call, admin, worker, storage = api
    doc = upload(call, pdf_bytes()).json()['id']
    drain(worker, storage)
    key = admin.execute('SELECT storage_key FROM fdi.documents WHERE id=%s', (doc,)).fetchone()[0]
    assert call('DELETE', f'/organizations/{u(1)}/documents/{doc}', MEMBER).status_code == 403
    assert call('DELETE', f'/organizations/{u(1)}/documents/{doc}', ADMIN).status_code == 202
    for identity in (MEMBER, ADMIN):
        listing = [d['id'] for d in call('GET', f'/organizations/{u(1)}/documents', identity).json()['documents']]
        assert doc not in listing
    assert call('GET', f'/organizations/{u(1)}/documents/{doc}/pages/1/image', ADMIN).status_code == 404
    assert call('DELETE', f'/organizations/{u(1)}/documents/{doc}', ADMIN).status_code == 404
    assert storage.path(key).exists()
    drain(worker, storage)
    assert not storage.path(key).exists()
    for table in ('documents', 'document_pages', 'chunks', 'ingestion_jobs', 'document_grants'):
        column = 'id' if table == 'documents' else 'document_id'
        assert admin.execute(f'SELECT count(*) FROM fdi.{table} WHERE {column}=%s', (doc,)).fetchone()[0] == 0


def test_deletion_during_ingestion_wins(api):
    call, admin, worker, storage = api
    doc = upload(call, pdf_bytes()).json()['id']
    assert call('DELETE', f'/organizations/{u(1)}/documents/{doc}', ADMIN).status_code == 202
    drain(worker, storage)
    assert admin.execute('SELECT count(*) FROM fdi.documents WHERE id=%s', (doc,)).fetchone()[0] == 0
    assert admin.execute('SELECT count(*) FROM fdi.chunks WHERE document_id=%s', (doc,)).fetchone()[0] == 0
