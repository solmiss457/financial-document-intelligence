"""RLS for pages/chunks/jobs: content follows document ACLs and ready status."""
import json
from uuid import UUID
import psycopg
import pytest
from fdi.db.config import dsn
from fdi.db.session import create_pool, organization_connection, request_connection


def u(n): return UUID(int=n)


ORG = {101: 1, 102: 1, 103: 2, 104: 2, 105: 1, 106: 1}


def vec(i): return '[' + ','.join('1' if k == i else '0' for k in range(384)) + ']'


@pytest.fixture
def content(database):
    admin, pool = database
    for doc, org in ORG.items():
        admin.execute('INSERT INTO fdi.document_pages VALUES (%s,%s,1,612,792,%s)', (u(org), u(doc), f'CANARY_PAGE_{doc}'))
        admin.execute('''INSERT INTO fdi.chunks (organization_id,document_id,chunker,chunk_index,page_start,page_end,
            spans,text,embedding_model,embedding) VALUES (%s,%s,'fixture',0,1,1,%s,%s,'fixture',%s)''',
            (u(org), u(doc), json.dumps([{'page': 1, 'bbox': [0, 0, 1, 1]}]), f'revenue CANARY_CHUNK_{doc}', vec(doc % 384)))
        admin.execute('INSERT INTO fdi.ingestion_jobs (organization_id,document_id,dedup_key) VALUES (%s,%s,%s)',
                      (u(org), u(doc), f'fixture:{doc}'))
    worker = create_pool(dsn(role='worker'), max_size=1, expected_role='fdi_worker')
    try:
        yield admin, pool, worker
    finally:
        worker.close()


def docs_of(conn, table):
    return sorted(r['document_id'].int for r in conn.execute(f'SELECT document_id FROM fdi.{table}').fetchall())


@pytest.mark.parametrize('user,org,expected', [(11, 1, [101, 102]), (12, 1, [101]), (13, 1, [101, 102]),
    (14, 1, []), (15, 1, []), (16, 1, []), (21, 1, []), (11, 2, []), (21, 2, [103, 104]), (17, 2, [103])])
def test_content_visible_only_for_readable_ready_documents(content, user, org, expected):
    _, pool, _ = content
    with request_connection(pool, u(user), u(org)) as conn:
        assert docs_of(conn, 'chunks') == expected
        assert docs_of(conn, 'document_pages') == expected
        # Keyword and vector retrieval run through the same policy.
        fts = conn.execute("SELECT document_id FROM fdi.chunks WHERE search_text @@ plainto_tsquery('english','revenue')").fetchall()
        assert sorted(r['document_id'].int for r in fts) == expected
        near = conn.execute('SELECT document_id FROM fdi.chunks ORDER BY embedding <=> %s::vector LIMIT 10', (vec(104),)).fetchall()
        assert sorted(r['document_id'].int for r in near) == expected


def test_no_context_sees_no_content(content):
    _, pool, _ = content
    with pool.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM fdi.chunks').fetchone()['n'] == 0
        assert conn.execute('SELECT count(*) AS n FROM fdi.document_pages').fetchone()['n'] == 0
        assert conn.execute('SELECT count(*) AS n FROM fdi.ingestion_jobs').fetchone()['n'] == 0


@pytest.mark.parametrize('change', ['grant', 'deleting', 'failed', 'membership'])
def test_content_revocation_next_transaction(content, change):
    admin, pool, _ = content
    with request_connection(pool, u(11), u(1)) as conn:
        assert 102 in docs_of(conn, 'chunks')
    if change == 'grant': admin.execute('DELETE FROM fdi.document_grants')
    elif change == 'membership': admin.execute('UPDATE fdi.memberships SET active=false WHERE user_id=%s', (u(11),))
    else: admin.execute('UPDATE fdi.documents SET status=%s WHERE id=%s', (change, u(102)))
    with request_connection(pool, u(11), u(1)) as conn:
        assert 102 not in docs_of(conn, 'chunks')
        assert 102 not in docs_of(conn, 'document_pages')


def test_deleting_document_content_hidden_even_from_admin(content):
    admin, pool, _ = content
    admin.execute("UPDATE fdi.documents SET status='deleting' WHERE id=%s", (u(101),))
    with request_connection(pool, u(13), u(1)) as conn:
        assert 101 in [r['id'].int for r in conn.execute('SELECT id FROM fdi.documents').fetchall()]
        assert docs_of(conn, 'chunks') == [102]


@pytest.mark.parametrize('user,org,expected', [(13, 1, [101, 102, 105, 106]), (11, 1, []), (21, 2, [103, 104]), (13, 2, [])])
def test_jobs_visible_to_same_org_admins_only(content, user, org, expected):
    _, pool, _ = content
    with request_connection(pool, u(user), u(org)) as conn:
        assert docs_of(conn, 'ingestion_jobs') == expected


@pytest.mark.parametrize('user,org,doc,allowed', [(13, 1, 101, True), (11, 1, 101, False), (13, 1, 103, False), (21, 2, 101, False)])
def test_job_enqueue_admin_same_org(content, user, org, doc, allowed):
    _, pool, _ = content
    def enqueue():
        with request_connection(pool, u(user), u(org)) as conn:
            conn.execute('INSERT INTO fdi.ingestion_jobs (organization_id,document_id,dedup_key) VALUES (%s,%s,%s)',
                         (u(org), u(doc), f'new:{doc}:{user}'))
    if allowed:
        enqueue()
    else:
        with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.ForeignKeyViolation)):
            enqueue()


def test_app_cannot_write_content_or_job_state(content):
    _, pool, _ = content
    for sql in ["DELETE FROM fdi.chunks", "UPDATE fdi.ingestion_jobs SET status='succeeded'",
                "INSERT INTO fdi.document_pages VALUES (%s,%s,2,1,1,'x')"]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with request_connection(pool, u(13), u(1)) as conn:
                conn.execute(sql, (u(1), u(101)) if '%s' in sql else None)


def test_worker_scoped_to_context_organization(content):
    _, _, worker = content
    with worker.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM fdi.documents').fetchone()['n'] == 0
        assert conn.execute('SELECT count(*) AS n FROM fdi.chunks').fetchone()['n'] == 0
        assert conn.execute('SELECT count(*) AS n FROM fdi.ingestion_jobs').fetchone()['n'] == 6  # claims across orgs
    with organization_connection(worker, u(1)) as conn:
        # Worker sees all org-1 statuses (it must process queued and skip deleting documents).
        assert sorted(r['id'].int for r in conn.execute('SELECT id FROM fdi.documents').fetchall()) == [101, 102, 105, 106]
        assert docs_of(conn, 'chunks') == [101, 102, 105, 106]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with organization_connection(worker, u(1)) as conn:
            conn.execute("INSERT INTO fdi.document_pages VALUES (%s,%s,2,1,1,'x')", (u(2), u(103)))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with organization_connection(worker, u(1)) as conn:
            conn.execute("INSERT INTO fdi.document_pages VALUES (%s,%s,2,1,1,'x')", (u(1), u(103)))
    with organization_connection(worker, u(1)) as conn:
        assert conn.execute("UPDATE fdi.documents SET status='ready' WHERE id=%s", (u(103),)).rowcount == 0


@pytest.mark.parametrize('sql', ['SELECT * FROM fdi.memberships', 'SELECT * FROM fdi.users',
    'SELECT * FROM fdi.document_grants', "UPDATE fdi.documents SET title='x'", "UPDATE fdi.documents SET visibility='organization'",
    'DELETE FROM fdi.ingestion_jobs', "INSERT INTO fdi.ingestion_jobs (organization_id,document_id,dedup_key) VALUES (gen_random_uuid(),gen_random_uuid(),'x')"])
def test_worker_least_privilege(content, sql):
    _, _, worker = content
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with organization_connection(worker, u(1)) as conn:
            conn.execute(sql)


def test_worker_deletes_only_deleting_documents_of_its_context(content):
    admin, _, worker = content
    with organization_connection(worker, u(1)) as conn:
        assert conn.execute('DELETE FROM fdi.documents WHERE id=%s', (u(101),)).rowcount == 0   # ready
        assert conn.execute('DELETE FROM fdi.documents WHERE id=%s', (u(103),)).rowcount == 0   # other organization
        assert conn.execute('DELETE FROM fdi.documents WHERE id=%s', (u(105),)).rowcount == 1   # deleting
    assert admin.execute('SELECT count(*) FROM fdi.chunks WHERE document_id=%s', (u(105),)).fetchone()[0] == 0


def test_worker_role_attributes(content):
    _, _, worker = content
    with worker.connection() as conn:
        role = conn.execute('SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolinherit FROM pg_roles WHERE rolname=current_user').fetchone()
        assert not any(role.values())
    with pytest.raises(RuntimeError, match='Unsafe'):
        create_pool(dsn(role='worker'), expected_role='fdi_app')
