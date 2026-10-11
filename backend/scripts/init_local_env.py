"""Create local-only random DB credentials, never print their values."""
from pathlib import Path
import secrets
import os
p = Path(__file__).resolve().parents[2] / '.env'
if p.exists():
    print('.env already exists; unchanged')
else:
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write('FDI_POSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n')
        f.write('FDI_APP_PASSWORD=' + secrets.token_hex(24) + '\n')
    print('Created local .env (0600)')
