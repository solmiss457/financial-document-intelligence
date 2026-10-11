"""Identity token verification: only short-lived ES256 tokens from the web server are accepted."""
import hashlib
import hmac
import json
import time
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fdi.auth.tokens import GOOGLE_ISSUER, Identity, InvalidToken, mint, verify


def keypair():
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, public.decode()


PRIVATE, PUBLIC = keypair()
ALICE = Identity(GOOGLE_ISSUER, 'google-sub-1', 'alice@example.com', True)


def claims(**overrides):
    now = int(time.time())
    base = {'iss': 'fdi-web', 'aud': 'fdi-api', 'iat': now, 'exp': now + 60, 'sub': 'google-sub-1',
            'idp_iss': GOOGLE_ISSUER, 'email': 'Alice@Example.com', 'email_verified': True}
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def test_valid_token_and_email_normalization():
    assert verify(mint(ALICE, PRIVATE), PUBLIC) == ALICE
    assert verify(jwt.encode(claims(), PRIVATE, algorithm='ES256'), PUBLIC).email == 'alice@example.com'


@pytest.mark.parametrize('token_claims', [
    claims(exp=int(time.time()) - 120, iat=int(time.time()) - 180),   # expired beyond leeway
    claims(aud='other-api'), claims(iss='someone-else'),
    claims(exp=int(time.time()) + 3600),                              # lifetime above 5 minutes
    claims(idp_iss='https://evil.example'),                           # untrusted identity provider
    claims(email=None), claims(email_verified=None), claims(sub=None),
    claims(email_verified='true'),                                    # wrong type
])
def test_rejects_invalid_claims(token_claims):
    with pytest.raises(InvalidToken):
        verify(jwt.encode(token_claims, PRIVATE, algorithm='ES256'), PUBLIC)


def test_rejects_other_keys_and_algorithm_confusion():
    other_private, _ = keypair()
    with pytest.raises(InvalidToken):
        verify(jwt.encode(claims(), other_private, algorithm='ES256'), PUBLIC)
    # Algorithm confusion: HS256 signed with the public key (known to everyone) as the HMAC secret.
    def raw(header):
        part = lambda obj: jwt.utils.base64url_encode(json.dumps(obj).encode()).decode()
        return part(header) + '.' + part(claims())
    signing_input = raw({'alg': 'HS256', 'typ': 'JWT'})
    signature = jwt.utils.base64url_encode(hmac.new(PUBLIC.encode(), signing_input.encode(), hashlib.sha256).digest()).decode()
    with pytest.raises(InvalidToken):
        verify(signing_input + '.' + signature, PUBLIC)
    with pytest.raises(InvalidToken):
        verify(raw({'alg': 'none', 'typ': 'JWT'}) + '.', PUBLIC)
    with pytest.raises(InvalidToken):
        verify('not-a-token', PUBLIC)
    with pytest.raises(InvalidToken):
        verify(mint(ALICE, PRIVATE), None)
