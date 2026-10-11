"""Signed-in user's own state: organizations and invitations. Uses the fdi_auth pool."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from fdi.api.deps import Principal, authenticated_principal
from fdi.auth import identity as identities

router = APIRouter()


@router.get('/me')
def me(request: Request, principal: Principal = Depends(authenticated_principal)):
    return identities.me(request.app.state.auth_pool, principal.identity)


@router.post('/invitations/{invitation_id}/accept')
def accept(invitation_id: UUID, request: Request, principal: Principal = Depends(authenticated_principal)):
    try:
        return identities.accept_invitation(request.app.state.auth_pool, principal.identity, invitation_id)
    except identities.InvitationError as exc:
        if exc.code == 'email_not_verified':
            raise HTTPException(403, 'A verified email address is required')
        if exc.code == 'already_member':
            raise HTTPException(409, 'Already a member of this organization')
        raise HTTPException(404, 'Not found')
