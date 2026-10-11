"""Create local-only random DB credentials, never print their values."""
from pathlib import Path
import secrets
import os
KEYS = ('FDI_POSTGRES_PASSWORD', 'FDI_APP_PASSWORD', 'FDI_WORKER_PASSWORD')
p = Path(__file__).resolve().parents[2] / '.env'
if not p.exists():
    os.close(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
present = {line.split('=', 1)[0] for line in p.read_text().splitlines() if '=' in line}
missing = [k for k in KEYS if k not in present]
with p.open('a') as f:
    for key in missing:
        f.write(key + '=' + secrets.token_hex(24) + '\n')
os.chmod(p, 0o600)
print(f'Local .env (0600): added {len(missing)} missing credential(s); existing values unchanged')
