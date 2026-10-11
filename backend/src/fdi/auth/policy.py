"""Pure policy: DB rows must be from the authenticated user, not HTTP claims."""
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Membership:
    organization_id: UUID
    role: str
    active: bool
    user_active: bool


def can_read(membership, organization_id, visibility, granted, status):
    return bool(membership and membership.active and membership.user_active
                and membership.organization_id == organization_id
                and membership.role in ('admin', 'member')
                and visibility in ('organization', 'restricted')
                and status in ('queued', 'processing', 'ready', 'failed')
                and (membership.role == 'admin' or visibility == 'organization' or granted))


def can_manage(membership, organization_id):
    return bool(membership and membership.active and membership.user_active
                and membership.organization_id == organization_id and membership.role == 'admin')
