"""Create only the dedicated fdi_test database; never drop databases."""
import os
import psycopg
from fdi.db.config import dsn
from backend.scripts.migrate import migrate

if __name__ == '__main__':
    with psycopg.connect(dsn(admin=True), autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname='fdi_test'").fetchone():
            conn.execute('CREATE DATABASE fdi_test')
    os.environ['FDI_DB_NAME'] = 'fdi_test'
    migrate()
    print('Dedicated fdi_test database ready')
