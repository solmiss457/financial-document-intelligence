from contextlib import contextmanager
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def create_pool(dsn, max_size=4, expected_role='fdi_app'):
    pool = ConnectionPool(dsn, min_size=1, max_size=max_size, open=False,
                          kwargs={'row_factory': dict_row}, timeout=5)
    pool.open(wait=True, timeout=10)
    try:
        with pool.connection() as conn:
            role = conn.execute('SELECT current_user AS name, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolinherit FROM pg_roles WHERE rolname=current_user').fetchone()
            owns = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='fdi' AND tableowner=current_user) AS owns").fetchone()
            if role['name'] != expected_role or role['rolsuper'] or role['rolbypassrls'] or role['rolcreaterole'] or role['rolcreatedb'] or role['rolinherit'] or owns['owns']:
                raise RuntimeError('Unsafe API database role')
    except Exception:
        pool.close()
        raise
    return pool


@contextmanager
def request_connection(pool, user_id, organization_id):
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('fdi.user_id', %s, true), set_config('fdi.org_id', %s, true)",
                         (str(user_id), str(organization_id)))
            yield conn


@contextmanager
def organization_connection(pool, organization_id):
    """Worker context: no user identity, access limited to one organization by RLS."""
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('fdi.org_id', %s, true)", (str(organization_id),))
            yield conn
