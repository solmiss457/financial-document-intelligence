"""Local development config; credentials are never printed or accepted over HTTP."""
import os
from pathlib import Path
from psycopg.conninfo import make_conninfo
ROOT = Path(__file__).resolve().parents[1]


def settings():
    result = {}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.startswith('#'):
                k, v = line.split('=', 1)
                result[k] = v
    result.update({k: v for k, v in os.environ.items() if k.startswith('FDI_')})
    return result


def dsn(admin=False):
    s = settings()
    return make_conninfo(host='127.0.0.1', port=s.get('FDI_DB_PORT', '55432'),
                         dbname=s.get('FDI_DB_NAME', 'fdi'), user='postgres' if admin else 'fdi_app',
                         password=s['FDI_POSTGRES_PASSWORD' if admin else 'FDI_APP_PASSWORD'],
                         connect_timeout=5)
