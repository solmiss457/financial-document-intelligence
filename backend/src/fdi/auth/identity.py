"""Identity resolution and invitation acceptance through the fdi_auth database role.

This path runs before any organization context exists and never touches documents. Signing in
alone grants nothing: an internal user and membership are created only when the holder of a
provider-verified email accepts a pending invitation addressed to that email.
"""
from uuid import uuid4


class InvitationError(Exception):
    """code: not_found (also used for other people's invitations), email_not_verified, already_member."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def resolve(pool, identity):
    """(user_id, active) for a linked identity, or (None, False). Records the last sign-in."""
    with pool.connection() as conn, conn.transaction():
        row = conn.execute('''SELECT i.user_id, u.active FROM fdi.user_identities i JOIN fdi.users u ON u.id=i.user_id
            WHERE i.issuer=%s AND i.subject=%s''', (identity.issuer, identity.subject)).fetchone()
        if not row:
            return None, False
        conn.execute('UPDATE fdi.user_identities SET last_seen_at=now(), email=%s WHERE issuer=%s AND subject=%s',
                     (identity.email, identity.issuer, identity.subject))
        return row['user_id'], row['active']


def pending_invitations(conn, identity):
    if not identity.email_verified:
        return []
    return conn.execute('''SELECT i.id, i.organization_id, o.name AS organization_name, i.role, i.expires_at
        FROM fdi.invitations i JOIN fdi.organizations o ON o.id=i.organization_id
        WHERE i.email=%s AND i.accepted_at IS NULL AND i.revoked_at IS NULL AND i.expires_at > now()
        ORDER BY i.created_at''', (identity.email,)).fetchall()


def me(pool, identity):
    user_id, active = resolve(pool, identity)
    with pool.connection() as conn, conn.transaction():
        memberships = []
        if user_id and active:
            memberships = conn.execute('''SELECT m.organization_id, o.name AS organization_name, m.role
                FROM fdi.memberships m JOIN fdi.organizations o ON o.id=m.organization_id
                WHERE m.user_id=%s AND m.active ORDER BY o.name''', (user_id,)).fetchall()
        invitations = pending_invitations(conn, identity) if (user_id is None or active) else []
    return {'user_id': str(user_id) if user_id and active else None, 'email': identity.email,
            'email_verified': identity.email_verified,
            'memberships': [{'organization_id': str(m['organization_id']), 'organization_name': m['organization_name'],
                             'role': m['role']} for m in memberships],
            'pending_invitations': [{'id': str(i['id']), 'organization_id': str(i['organization_id']),
                                     'organization_name': i['organization_name'], 'role': i['role'],
                                     'expires_at': i['expires_at'].isoformat()} for i in invitations]}


def accept_invitation(pool, identity, invitation_id):
    if not identity.email_verified:
        raise InvitationError('email_not_verified')
    with pool.connection() as conn, conn.transaction():
        inv = conn.execute('''SELECT id, organization_id, email, role FROM fdi.invitations WHERE id=%s
            AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > now() FOR UPDATE''', (invitation_id,)).fetchone()
        if not inv or inv['email'] != identity.email:
            raise InvitationError('not_found')
        row = conn.execute('''SELECT i.user_id, u.active FROM fdi.user_identities i JOIN fdi.users u ON u.id=i.user_id
            WHERE i.issuer=%s AND i.subject=%s FOR UPDATE OF i''', (identity.issuer, identity.subject)).fetchone()
        if row and not row['active']:
            raise InvitationError('not_found')
        user_id = row['user_id'] if row else uuid4()
        if not row:
            conn.execute('INSERT INTO fdi.users (id, active) VALUES (%s, true)', (user_id,))
            conn.execute('INSERT INTO fdi.user_identities (issuer, subject, user_id, email) VALUES (%s,%s,%s,%s)',
                         (identity.issuer, identity.subject, user_id, identity.email))
        if conn.execute('SELECT 1 FROM fdi.memberships WHERE organization_id=%s AND user_id=%s',
                        (inv['organization_id'], user_id)).fetchone():
            # Includes deactivated memberships: an admin must reactivate them explicitly.
            raise InvitationError('already_member')
        conn.execute('INSERT INTO fdi.memberships (organization_id, user_id, role, active) VALUES (%s,%s,%s,true)',
                     (inv['organization_id'], user_id, inv['role']))
        conn.execute('UPDATE fdi.invitations SET accepted_at=now(), accepted_by=%s WHERE id=%s', (user_id, inv['id']))
        return {'organization_id': str(inv['organization_id']), 'user_id': str(user_id), 'role': inv['role']}
