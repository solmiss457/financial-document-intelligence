"""Web-to-API identity tokens.

The Next.js server signs in users with Google (OIDC) and, for each API call, signs a short-lived
ES256 token describing the Google identity. FastAPI holds only the public key. Organization IDs and
roles are never taken from the token; they come from the database.
"""
import time
from dataclasses import dataclass
from pathlib import Path
import jwt
from fdi.db.config import ROOT, settings

ISSUER = 'fdi-web'
AUDIENCE = 'fdi-api'
ALGORITHM = 'ES256'
MAX_LIFETIME_SECONDS = 300
LEEWAY_SECONDS = 30
GOOGLE_ISSUER = 'https://accounts.google.com'
REQUIRED = ['exp', 'iat', 'iss', 'aud', 'sub', 'idp_iss', 'email', 'email_verified']


class InvalidToken(Exception):
    """Reason codes only; never echo token contents."""


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str
    email: str
    email_verified: bool


def allowed_issuers():
    extra = settings().get('FDI_ALLOWED_IDP_ISSUERS', '')
    return {GOOGLE_ISSUER} | {i.strip() for i in extra.split(',') if i.strip()}


def load_public_key(path=None):
    path = Path(path or settings().get('FDI_WEB_PUBLIC_KEY_PATH') or ROOT / 'storage/keys/web-signing-public.pem')
    return path.read_text() if path.is_file() else None


def verify(token, public_key, issuers=None):
    if not public_key:
        raise InvalidToken('no_verification_key')
    try:
        claims = jwt.decode(token, public_key, algorithms=[ALGORITHM], audience=AUDIENCE, issuer=ISSUER,
                            leeway=LEEWAY_SECONDS, options={'require': REQUIRED})
    except jwt.PyJWTError as exc:
        raise InvalidToken(type(exc).__name__) from exc
    if claims['exp'] - claims['iat'] > MAX_LIFETIME_SECONDS:
        raise InvalidToken('lifetime_too_long')
    if claims['idp_iss'] not in (issuers or allowed_issuers()):
        raise InvalidToken('untrusted_identity_provider')
    if not all(isinstance(claims[k], str) and claims[k] for k in ('sub', 'idp_iss', 'email')) \
            or not isinstance(claims['email_verified'], bool):
        raise InvalidToken('malformed_claims')
    return Identity(claims['idp_iss'], claims['sub'], claims['email'].strip().lower(), claims['email_verified'])


def mint(identity, private_key, lifetime=60, now=None):
    """Reference implementation of the Next.js side, used by tests and local tools."""
    now = int(now if now is not None else time.time())
    return jwt.encode({'iss': ISSUER, 'aud': AUDIENCE, 'iat': now, 'exp': now + lifetime, 'sub': identity.subject,
                       'idp_iss': identity.issuer, 'email': identity.email, 'email_verified': identity.email_verified},
                      private_key, algorithm=ALGORITHM)

