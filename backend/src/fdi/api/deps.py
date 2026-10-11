"""Request authentication. Never trusts user, organization, or role values sent by clients."""
from dataclasses import dataclass
from uuid import UUID
from fastapi import HTTPException, Request
from fdi.auth import identity as identities
from fdi.auth.tokens import Identity, InvalidToken, verify


@dataclass(frozen=True)
class Principal:
    user_id: UUID | None
    identity: Identity | None = None


NOT_FOUND = HTTPException(404, 'Not found')


def authenticated_principal(request: Request) -> Principal:
    """Bearer token signed by the web server (ES256) -> Google identity -> internal user, if linked."""
    header = request.headers.get('authorization', '')
    scheme, _, token = header.partition(' ')
    state = request.app.state
    if scheme.lower() != 'bearer' or not token or state.auth_pool is None:
        raise HTTPException(401, 'Authentication required')
    try:
        identity = verify(token.strip(), state.public_key)
    except InvalidToken:
        raise HTTPException(401, 'Authentication required')
    user_id, active = identities.resolve(state.auth_pool, identity)
    return Principal(user_id if active else None, identity)


def member_id(principal: Principal) -> UUID:
    """Organization routes need a linked, active user; others get the same 404 as non-members."""
    if principal.user_id is None:
        raise NOT_FOUND
    return principal.user_id


def require_admin(conn, organization_id):
    """Inside request_connection: 404 for non-members (RLS hides the membership), 403 for members."""
    if not conn.execute('SELECT 1 FROM fdi.memberships WHERE organization_id=%s AND user_id=fdi.user_id()',
                        (organization_id,)).fetchone():
        raise NOT_FOUND
    if not conn.execute('SELECT fdi.is_org_admin(%s) AS ok', (organization_id,)).fetchone()['ok']:
        raise HTTPException(403, 'Administrator role required')


def require_member(conn, organization_id):
    if not conn.execute('SELECT 1 FROM fdi.memberships WHERE organization_id=%s AND user_id=fdi.user_id()',
                        (organization_id,)).fetchone():
        raise NOT_FOUND
