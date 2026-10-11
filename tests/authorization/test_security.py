from uuid import UUID
import pytest
import psycopg
from fastapi.testclient import TestClient
from services.api.db import request_connection, create_pool
from services.api.main import create_app, authenticated_principal, Principal
from services.api.policy import Membership, can_read, can_manage
from scripts.local_db import dsn


def u(n): return UUID(int=n)


def visible(pool,user,org):
    with request_connection(pool,u(user),u(org)) as conn:
        return [r['id'].int for r in conn.execute('SELECT id FROM fdi.documents ORDER BY id').fetchall()]


@pytest.mark.parametrize('user,org,expected',[(11,1,[101,102,106]),(12,1,[101,106]),(13,1,[101,102,105,106]),
    (14,1,[]),(15,1,[]),(16,1,[]),(21,1,[]),(11,2,[]),(21,2,[103,104]),(17,2,[103])])
def test_rls_matrix(database,user,org,expected):
    _,pool=database
    assert visible(pool,user,org)==expected


def test_no_context_and_privileged_role_rejected(database):
    _,pool=database
    with pool.connection() as conn:
        assert conn.execute('SELECT id FROM fdi.documents').fetchall()==[]
        role=conn.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        assert not any(role.values())
        assert conn.execute("SELECT tableowner FROM pg_tables WHERE schemaname='fdi'").fetchall()==[{'tableowner':'fdi_owner'}]*5
    with pytest.raises(RuntimeError,match='Unsafe'):
        create_pool(dsn(admin=True))


@pytest.mark.parametrize('fail',[False,True])
def test_pool_context_cleared_even_on_rollback(database,fail):
    _,pool=database
    try:
        with request_connection(pool,u(11),u(1)) as conn:
            pid=conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            assert conn.execute('SELECT count(*) AS n FROM fdi.documents').fetchone()['n']==3
            if fail: conn.execute('SELECT 1/0')
    except psycopg.errors.DivisionByZero:
        assert fail
    with pool.connection() as conn:
        assert conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']==pid
        state=conn.execute('SELECT fdi.user_id() AS usr, fdi.org_id() AS org').fetchone()
        assert state=={'usr':None,'org':None}
        assert conn.execute('SELECT id FROM fdi.documents').fetchall()==[]
    assert visible(pool,21,2)==[103,104]


@pytest.mark.parametrize('change', ['grant','membership','user','deleting','visibility'])
def test_revocation_next_transaction(database,change):
    admin,pool=database
    assert 102 in visible(pool,11,1)
    if change=='grant': admin.execute('DELETE FROM fdi.document_grants')
    elif change=='membership': admin.execute('UPDATE fdi.memberships SET active=false WHERE user_id=%s',(u(11),))
    elif change=='user': admin.execute('UPDATE fdi.users SET active=false WHERE id=%s',(u(11),))
    elif change=='deleting': admin.execute("UPDATE fdi.documents SET status='deleting' WHERE id=%s",(u(102),))
    else:
        assert 101 in visible(pool,12,1)
        admin.execute("UPDATE fdi.documents SET visibility='restricted' WHERE id=%s",(u(101),))
        assert 101 not in visible(pool,12,1)
        return
    assert 102 not in visible(pool,11,1)


def test_admin_changes_acl_member_cannot(database):
    _,pool=database
    with request_connection(pool,u(13),u(1)) as conn:
        conn.execute('INSERT INTO fdi.document_grants VALUES (%s,%s,%s)',(u(1),u(102),u(12)))
    assert 102 in visible(pool,12,1)
    with request_connection(pool,u(13),u(1)) as conn:
        assert conn.execute('DELETE FROM fdi.document_grants WHERE user_id=%s',(u(12),)).rowcount==1
    assert 102 not in visible(pool,12,1)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_connection(pool,u(12),u(1)) as conn:
            conn.execute('INSERT INTO fdi.document_grants VALUES (%s,%s,%s)',(u(1),u(102),u(12)))
    with request_connection(pool,u(12),u(1)) as conn:
        assert conn.execute('DELETE FROM fdi.document_grants').rowcount==0
        assert conn.execute("UPDATE fdi.documents SET title='bad'").rowcount==0


@pytest.mark.parametrize('org,doc,user',[(1,104,11),(1,102,21)])
def test_composite_fk_blocks_cross_org_grants(database,org,doc,user):
    _,pool=database
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with request_connection(pool,u(13),u(1)) as conn:
            conn.execute('INSERT INTO fdi.document_grants VALUES (%s,%s,%s)',(u(org),u(doc),u(user)))


def test_admin_cannot_move_document_or_escalate_membership(database):
    _,pool=database
    for statement in ['UPDATE fdi.documents SET organization_id=%s WHERE id=%s',
                      "UPDATE fdi.memberships SET role='admin' WHERE organization_id=%s AND user_id=%s"]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with request_connection(pool,u(13),u(1)) as conn:
                conn.execute(statement,(u(2),u(101)))
    with request_connection(pool,u(13),u(1)) as conn:
        assert conn.execute("UPDATE fdi.documents SET title='bad' WHERE id=%s",(u(104),)).rowcount==0
        assert conn.execute("UPDATE fdi.documents SET title='updated' WHERE id=%s",(u(101),)).rowcount==1


@pytest.mark.parametrize('role,active,user_active,org,visibility,grant,expected',[
    ('member',True,True,1,'organization',False,True),('member',True,True,1,'restricted',False,False),
    ('member',True,True,1,'restricted',True,True),('admin',True,True,1,'restricted',False,True),
    ('admin',True,True,2,'organization',True,False),('admin',False,True,1,'organization',True,False),
    ('member',True,False,1,'organization',True,False)])
def test_pure_policy(role,active,user_active,org,visibility,grant,expected):
    m=Membership(u(org),role,active,user_active)
    assert can_read(m,u(1),visibility,grant,'ready')==expected
    assert not can_read(m,u(1),visibility,grant,'deleting')
    assert can_manage(m,u(1))==(role=='admin' and active and user_active and org==1)


def test_api_no_identity_backdoor(database):
    _,pool=database
    with TestClient(create_app(pool)) as client:
        assert client.get('/health').json()=={'status':'ok'}
        assert client.get('/ready').status_code==200
        for headers in [{},{'X-User-ID':str(u(13))},{'Authorization':'Bearer fake'}]:
            assert client.get(f'/organizations/{u(1)}/documents',headers=headers).status_code==401


def test_api_acl_404_and_canary_isolation(database,caplog):
    admin,pool=database
    app=create_app(pool)
    app.dependency_overrides[authenticated_principal]=lambda: Principal(u(12))
    with TestClient(app) as client:
        listing=client.get(f'/organizations/{u(1)}/documents')
        assert listing.status_code==200
        assert [r['id'] for r in listing.json()['documents']]==[str(u(101)),str(u(106))]
        assert 'CANARY_ORG_2' not in listing.text
        assert 'DOC_102' not in listing.text
        for org,doc in [(1,102),(1,104),(2,104),(1,999)]:
            response=client.get(f'/organizations/{u(org)}/documents/{u(doc)}')
            assert response.status_code==404 and response.json()=={'detail':'Not found'}
        admin.execute('UPDATE fdi.memberships SET active=false WHERE user_id=%s',(u(12),))
        assert client.get(f'/organizations/{u(1)}/documents/{u(101)}').status_code==404
    assert 'CANARY_' not in caplog.text


@pytest.mark.parametrize('user,org,allowed',[(13,1,True),(12,1,False),(21,1,False)])
def test_document_insert_requires_same_org_admin(database,user,org,allowed):
    _,pool=database
    def insert():
        with request_connection(pool,u(user),u(org)) as conn:
            conn.execute('INSERT INTO fdi.documents VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                         (u(200),u(1),'new',u(1200),'b'*64,'v1','organization','queued'))
    if allowed:
        insert()
        assert 200 in visible(pool,user,org)
    else:
        with pytest.raises(psycopg.errors.InsufficientPrivilege): insert()


def test_rls_enabled_for_all_tables_and_no_role_escalation(database):
    _,pool=database
    with pool.connection() as conn:
        rows=conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='fdi' AND relkind='r'").fetchall()
        assert len(rows)==5 and all(all(r.values()) for r in rows)
        assert conn.execute("SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)").fetchall()==[]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with pool.connection() as conn: conn.execute('SET ROLE fdi_owner')


def test_admin_soft_delete_keeps_admin_metadata_hides_member_content(database):
    _,pool=database
    with request_connection(pool,u(13),u(1)) as conn:
        assert conn.execute("UPDATE fdi.documents SET status='deleting' WHERE id=%s",(u(101),)).rowcount==1
    assert 101 in visible(pool,13,1)  # deletion status is admin-only metadata
    assert 101 not in visible(pool,11,1)
    app=create_app(pool)
    app.dependency_overrides[authenticated_principal]=lambda: Principal(u(13))
    with TestClient(app) as client:
        assert client.get(f'/organizations/{u(1)}/documents/{u(101)}').status_code==404
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_connection(pool,u(13),u(1)) as conn:
            conn.execute('DELETE FROM fdi.documents WHERE id=%s',(u(101),))


def test_api_db_error_does_not_expose_details(database):
    _,pool=database
    app=create_app(pool)
    with TestClient(app) as client:
        original=pool.connection
        def fail(*args,**kwargs):
            raise psycopg.OperationalError('SECRET_DATABASE_DIAGNOSTIC')
        pool.connection=fail
        try:
            response=client.get('/ready')
            assert response.status_code==503
            assert response.json()=={'detail':'Service unavailable'}
            assert 'SECRET_' not in response.text
        finally:
            pool.connection=original
