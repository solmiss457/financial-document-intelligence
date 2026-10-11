"""Verify migrations on a disposable empty local database, then remove only it."""
import os
from uuid import uuid4
import psycopg
from psycopg import sql
from fdi.db.config import ROOT, dsn
from backend.scripts.migrate import migrate


def main():
    name = 'fdi_verify_' + uuid4().hex
    previous = os.environ.get('FDI_DB_NAME')
    with psycopg.connect(dsn(admin=True), autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            os.environ['FDI_DB_NAME'] = name
            migrate()
            migrate()
            with psycopg.connect(dsn(admin=True)) as conn:
                expected = len(list((ROOT / 'backend/migrations').glob('*.sql')))
                assert conn.execute('SELECT count(*) FROM public.fdi_migrations').fetchone()[0] == expected
                tables, forced = conn.execute("SELECT count(*), count(*) FILTER (WHERE c.relrowsecurity AND c.relforcerowsecurity) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='fdi' AND c.relkind='r'").fetchone()
                assert tables == forced == 10
            print(f'Empty database: {expected} migrations applied, repeat verified, {forced}/{tables} tables FORCE RLS')
        finally:
            if previous is None: os.environ.pop('FDI_DB_NAME', None)
            else: os.environ['FDI_DB_NAME'] = previous
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


if __name__ == '__main__':
    main()
