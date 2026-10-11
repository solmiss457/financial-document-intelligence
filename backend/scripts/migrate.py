"""Checksum-verified SQL migrations. Restricted to dedicated local fdi database."""
import hashlib
import psycopg
from psycopg import sql
from fdi.db.config import ROOT, dsn, settings


def migrate():
    with psycopg.connect(dsn(admin=True)) as conn:
        conn.execute('SELECT pg_advisory_xact_lock(884213)')
        conn.execute('CREATE TABLE IF NOT EXISTS public.fdi_migrations (name text PRIMARY KEY, sha256 text NOT NULL)')
        conn.execute('REVOKE ALL ON public.fdi_migrations FROM PUBLIC')
        for file in sorted((ROOT / 'backend/migrations').glob('*.sql')):
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            existing = conn.execute('SELECT sha256 FROM public.fdi_migrations WHERE name=%s', (file.name,)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise RuntimeError('Applied migration checksum changed')
                continue
            conn.execute(file.read_text())
            conn.execute('RESET ROLE')
            conn.execute('INSERT INTO public.fdi_migrations VALUES (%s,%s)', (file.name,digest))
        # psycopg safely quotes value; never print the query or password.
        conn.execute(sql.SQL('ALTER ROLE fdi_app PASSWORD {}').format(sql.Literal(settings()['FDI_APP_PASSWORD'])))
    print('Migrations verified and applied')


if __name__ == '__main__':
    migrate()
