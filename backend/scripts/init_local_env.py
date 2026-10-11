"""Create local-only random DB credentials and the web-to-API signing key pair; never print secrets."""
from pathlib import Path
import os
import secrets
ROOT = Path(__file__).resolve().parents[2]
KEYS = ('FDI_POSTGRES_PASSWORD', 'FDI_APP_PASSWORD', 'FDI_WORKER_PASSWORD', 'FDI_AUTH_PASSWORD')
p = ROOT / '.env'
if not p.exists():
    os.close(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
present = {line.split('=', 1)[0] for line in p.read_text().splitlines() if '=' in line}
missing = [k for k in KEYS if k not in present]
with p.open('a') as f:
    for key in missing:
        f.write(key + '=' + secrets.token_hex(24) + '\n')
os.chmod(p, 0o600)
# ES256 key pair: the Next.js server signs short-lived tokens with the private key; FastAPI holds only
# the public key, so a compromised API cannot mint identities.
keys = ROOT / 'storage/keys'
private, public = keys / 'web-signing-private.pem', keys / 'web-signing-public.pem'
created = False
if not private.exists():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    keys.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = ec.generate_private_key(ec.SECP256R1())
    fd = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    created = True
print(f'Local .env (0600): added {len(missing)} missing credential(s); signing key pair '
      f'{"created" if created else "unchanged"} in storage/keys')
