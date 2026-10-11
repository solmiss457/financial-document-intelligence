"""Organization administration: members and invitations. RLS enforces the same rules."""
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from fdi.api.deps import NOT_FOUND, Principal, authenticated_principal, member_id, require_admin
from fdi.db.session import request_connection

router = APIRouter(prefix='/organizations/{organization_id}')
EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class MemberUpdate(BaseModel):
    role: Literal['admin', 'member'] | None = None
    active: bool | None = None


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: Literal['admin', 'member'] = 'member'
    expires_in_days: int = Field(default=7, ge=1, le=30)


@router.get('/members')
def members(organization_id: UUID, request: Request, principal: Principal = Depends(authenticated_principal)):
    with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
        require_admin(conn, organization_id)
        rows = conn.execute('''SELECT m.user_id, m.role, m.active,
                (SELECT string_agg(i.email, ', ' ORDER BY i.email) FROM fdi.user_identities i WHERE i.user_id=m.user_id) AS email
            FROM fdi.memberships m WHERE m.organization_id=%s ORDER BY email NULLS LAST, m.user_id''', (organization_id,)).fetchall()
    return {'members': [{'user_id': str(r['user_id']), 'email': r['email'], 'role': r['role'], 'active': r['active'],
                         'is_you': r['user_id'] == principal.user_id} for r in rows]}


@router.patch('/members/{user_id}')
def update_member(organization_id: UUID, user_id: UUID, body: MemberUpdate, request: Request,
                  principal: Principal = Depends(authenticated_principal)):
    me = member_id(principal)
    if user_id == me:
        raise HTTPException(400, 'Administrators cannot change their own membership')
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, 'Nothing to change')
    with request_connection(request.app.state.pool, me, organization_id) as conn:
        require_admin(conn, organization_id)
        sets = ', '.join(f'{k}=%s' for k in changes)  # keys come from the validated model, not the client
        row = conn.execute(f'UPDATE fdi.memberships SET {sets} WHERE organization_id=%s AND user_id=%s RETURNING user_id, role, active',
                           (*changes.values(), organization_id, user_id)).fetchone()
    if not row:
        raise NOT_FOUND
    return {'user_id': str(row['user_id']), 'role': row['role'], 'active': row['active']}


def _invitation(r):
    status = ('accepted' if r['accepted_at'] else 'revoked' if r['revoked_at']
              else 'expired' if r['expires_at'] <= datetime.now(timezone.utc) else 'pending')
    return {'id': str(r['id']), 'email': r['email'], 'role': r['role'], 'status': status,
            'created_at': r['created_at'].isoformat(), 'expires_at': r['expires_at'].isoformat()}


@router.get('/invitations')
def invitations(organization_id: UUID, request: Request, principal: Principal = Depends(authenticated_principal)):
    with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
        require_admin(conn, organization_id)
        rows = conn.execute('SELECT * FROM fdi.invitations WHERE organization_id=%s ORDER BY created_at DESC LIMIT 200',
                            (organization_id,)).fetchall()
    return {'invitations': [_invitation(r) for r in rows]}


@router.post('/invitations', status_code=201)
def invite(organization_id: UUID, body: InvitationCreate, request: Request, principal: Principal = Depends(authenticated_principal)):
    email = body.email.strip().lower()
    if not EMAIL.match(email):
        raise HTTPException(422, 'Invalid email address')
    me = member_id(principal)
    expires = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
    try:
        with request_connection(request.app.state.pool, me, organization_id) as conn:
            require_admin(conn, organization_id)
            if conn.execute('''SELECT 1 FROM fdi.user_identities i JOIN fdi.memberships m ON m.user_id=i.user_id
                    WHERE m.organization_id=%s AND i.email=%s''', (organization_id, email)).fetchone():
                raise HTTPException(409, 'This person is already a member')
            row = conn.execute('''INSERT INTO fdi.invitations (organization_id, email, role, invited_by, expires_at)
                VALUES (%s,%s,%s,%s,%s) RETURNING *''', (organization_id, email, body.role, me, expires)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, 'A pending invitation already exists for this email')
    return _invitation(row)


@router.delete('/invitations/{invitation_id}', status_code=204)
def revoke(organization_id: UUID, invitation_id: UUID, request: Request, principal: Principal = Depends(authenticated_principal)):
    with request_connection(request.app.state.pool, member_id(principal), organization_id) as conn:
        require_admin(conn, organization_id)
        updated = conn.execute('''UPDATE fdi.invitations SET revoked_at=now() WHERE id=%s AND organization_id=%s
            AND accepted_at IS NULL AND revoked_at IS NULL''', (invitation_id, organization_id)).rowcount
    if not updated:
        raise NOT_FOUND
