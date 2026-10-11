"""Local development config; credentials are never printed or accepted over HTTP."""
import os
from pathlib import Path
from psycopg.conninfo import make_conninfo
ROOT = Path(__file__).resolve().parents[4]
ROLES = {'admin': ('postgres', 'FDI_POSTGRES_PASSWORD'), 'app': ('fdi_app', 'FDI_APP_PASSWORD'),
         'worker': ('fdi_worker', 'FDI_WORKER_PASSWORD'), 'auth': ('fdi_auth', 'FDI_AUTH_PASSWORD')}


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


def dsn(admin=False, role='app'):
    s = settings()
    user, secret = ROLES['admin' if admin else role]
    return make_conninfo(host='127.0.0.1', port=s.get('FDI_DB_PORT', '55432'),
                         dbname=s.get('FDI_DB_NAME', 'fdi'), user=user, password=s[secret],
                         connect_timeout=5)
