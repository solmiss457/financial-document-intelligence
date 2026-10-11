import os
from uuid import UUID
import psycopg
import pytest
from fdi.db.config import dsn
from fdi.db.session import create_pool


def uid(n): return UUID(int=n)


@pytest.fixture
def database(monkeypatch):
    monkeypatch.setenv('FDI_DB_NAME', 'fdi_test')
    admin = psycopg.connect(dsn(admin=True), autocommit=True)
    assert admin.info.dbname == 'fdi_test'  # refuse destructive fixtures elsewhere
    admin.execute('TRUNCATE fdi.document_grants,fdi.documents,fdi.memberships,fdi.organizations,fdi.users')
    for n in [11,12,13,14,15,16,17,21]:
        admin.execute('INSERT INTO fdi.users VALUES (%s,%s)', (uid(n), n != 15))
    for n in [1,2]: admin.execute('INSERT INTO fdi.organizations VALUES (%s,%s)', (uid(n),f'Organization {n}'))
    for org,user,role,active in [(1,11,'member',True),(1,12,'member',True),(1,13,'admin',True),
                                 (1,14,'member',False),(1,15,'admin',True),(1,17,'member',True),
                                 (2,17,'member',True),(2,21,'admin',True)]:
        admin.execute('INSERT INTO fdi.memberships VALUES (%s,%s,%s,%s)', (uid(org),uid(user),role,active))
    for n,org,visibility,status in [(101,1,'organization','ready'),(102,1,'restricted','ready'),
                                  (103,2,'organization','ready'),(104,2,'restricted','ready'),
                                  (105,1,'organization','deleting'),(106,1,'organization','queued')]:
        admin.execute('INSERT INTO fdi.documents VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                      (uid(n),uid(org),f'CANARY_ORG_{org}_DOC_{n}',uid(n+1000),'a'*64,'fixture-v1',visibility,status))
    admin.execute('INSERT INTO fdi.document_grants VALUES (%s,%s,%s)', (uid(1),uid(102),uid(11)))
    pool = create_pool(dsn(),max_size=1)
    try:
        yield admin,pool
    finally:
        pool.close()
        admin.close()
