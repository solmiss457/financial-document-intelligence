-- Sign-in identities, email-bound invitations, admin management, and deletion jobs.
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='fdi_auth') THEN
  CREATE ROLE fdi_auth LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
 -- Owns only fdi.is_org_admin(). BYPASSRLS so that the function can read memberships while
 -- a memberships policy is being evaluated (a policy that queried memberships directly would recurse).
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='fdi_policy') THEN
  CREATE ROLE fdi_policy NOLOGIN NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
END $$;
GRANT USAGE ON SCHEMA fdi TO fdi_policy, fdi_auth;
SET LOCAL ROLE fdi_owner;
-- Google (or another OIDC issuer) account -> internal user. Email is informational; authorization
-- uses (issuer, subject), and invitations additionally require a provider-verified email.
CREATE TABLE fdi.user_identities (
 issuer text NOT NULL,
 subject text NOT NULL,
 user_id uuid NOT NULL REFERENCES fdi.users(id) ON DELETE CASCADE,
 email text NOT NULL CHECK (email = lower(email)),
 created_at timestamptz NOT NULL DEFAULT now(),
 last_seen_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (issuer, subject),
 UNIQUE (user_id, issuer)
);
CREATE TABLE fdi.invitations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 organization_id uuid NOT NULL REFERENCES fdi.organizations(id),
 email text NOT NULL CHECK (email = lower(email) AND email LIKE '%_@_%'),
 role text NOT NULL CHECK (role IN ('admin','member')),
 invited_by uuid REFERENCES fdi.users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 accepted_at timestamptz,
 accepted_by uuid REFERENCES fdi.users(id),
 revoked_at timestamptz,
 CHECK (expires_at > created_at),
 CHECK ((accepted_at IS NULL) = (accepted_by IS NULL)),
 CHECK (accepted_at IS NULL OR revoked_at IS NULL)
);
CREATE UNIQUE INDEX invitations_one_pending ON fdi.invitations(organization_id, email)
 WHERE accepted_at IS NULL AND revoked_at IS NULL;
CREATE INDEX invitations_email ON fdi.invitations(email) WHERE accepted_at IS NULL AND revoked_at IS NULL;
ALTER TABLE fdi.documents ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE fdi.ingestion_jobs ADD COLUMN kind text NOT NULL DEFAULT 'ingest' CHECK (kind IN ('ingest','delete'));
ALTER TABLE fdi.user_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.user_identities FORCE ROW LEVEL SECURITY;
ALTER TABLE fdi.invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.invitations FORCE ROW LEVEL SECURITY;
RESET ROLE;
-- Created as superuser, then owned by fdi_policy (owner changes need membership in the new owner).
CREATE FUNCTION fdi.is_org_admin(org uuid) RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS
$$ SELECT EXISTS (SELECT 1 FROM fdi.memberships m JOIN fdi.users u ON u.id = m.user_id
   WHERE m.organization_id = org AND m.user_id = fdi.user_id() AND m.role = 'admin' AND m.active AND u.active) $$;
ALTER FUNCTION fdi.is_org_admin(uuid) OWNER TO fdi_policy;
GRANT SELECT ON fdi.memberships, fdi.users TO fdi_policy;
GRANT EXECUTE ON FUNCTION fdi.user_id() TO fdi_policy;
REVOKE ALL ON FUNCTION fdi.is_org_admin(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fdi.is_org_admin(uuid) TO fdi_app;
SET LOCAL ROLE fdi_owner;
-- fdi_auth: identity resolution, the signed-in user's organizations and pending invitations, and
-- invitation acceptance. It is used only before an organization context exists and never reads documents.
CREATE POLICY identity_auth ON fdi.user_identities FOR ALL TO fdi_auth USING (true) WITH CHECK (true);
CREATE POLICY user_auth ON fdi.users FOR ALL TO fdi_auth USING (true) WITH CHECK (true);
CREATE POLICY membership_auth ON fdi.memberships FOR ALL TO fdi_auth USING (true) WITH CHECK (true);
CREATE POLICY organization_auth ON fdi.organizations FOR SELECT TO fdi_auth USING (true);
CREATE POLICY invitation_auth ON fdi.invitations FOR ALL TO fdi_auth USING (true) WITH CHECK (true);
GRANT SELECT, INSERT ON fdi.user_identities, fdi.users TO fdi_auth;
GRANT UPDATE (last_seen_at, email) ON fdi.user_identities TO fdi_auth;
GRANT SELECT, INSERT ON fdi.memberships TO fdi_auth;
GRANT SELECT ON fdi.organizations, fdi.invitations TO fdi_auth;
GRANT UPDATE (accepted_at, accepted_by) ON fdi.invitations TO fdi_auth;
GRANT EXECUTE ON FUNCTION fdi.user_id(), fdi.org_id() TO fdi_auth;
-- fdi_app admin management within the request's organization.
CREATE POLICY membership_admin_read ON fdi.memberships FOR SELECT TO fdi_app
 USING (organization_id = fdi.org_id() AND fdi.is_org_admin(organization_id));
CREATE POLICY membership_admin_update ON fdi.memberships FOR UPDATE TO fdi_app
 USING (organization_id = fdi.org_id() AND fdi.is_org_admin(organization_id) AND user_id <> fdi.user_id())
 WITH CHECK (organization_id = fdi.org_id() AND user_id <> fdi.user_id());
-- No users policy referencing memberships: membership_self already reads users (users -> memberships order).
CREATE POLICY identity_admin_read ON fdi.user_identities FOR SELECT TO fdi_app
 USING (fdi.is_org_admin(fdi.org_id()) AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.user_id = user_identities.user_id AND m.organization_id = fdi.org_id()));
CREATE POLICY invitation_admin_read ON fdi.invitations FOR SELECT TO fdi_app
 USING (organization_id = fdi.org_id() AND fdi.is_org_admin(organization_id));
CREATE POLICY invitation_admin_insert ON fdi.invitations FOR INSERT TO fdi_app
 WITH CHECK (organization_id = fdi.org_id() AND fdi.is_org_admin(organization_id) AND invited_by = fdi.user_id());
CREATE POLICY invitation_admin_revoke ON fdi.invitations FOR UPDATE TO fdi_app
 USING (organization_id = fdi.org_id() AND fdi.is_org_admin(organization_id))
 WITH CHECK (organization_id = fdi.org_id() AND fdi.is_org_admin(organization_id));
GRANT UPDATE (role, active) ON fdi.memberships TO fdi_app;
GRANT SELECT ON fdi.user_identities, fdi.invitations TO fdi_app;
GRANT INSERT (organization_id, email, role, invited_by, expires_at) ON fdi.invitations TO fdi_app;
GRANT UPDATE (revoked_at) ON fdi.invitations TO fdi_app;
GRANT INSERT (chunker, kind) ON fdi.ingestion_jobs TO fdi_app;
GRANT UPDATE (fiscal_year_end) ON fdi.documents TO fdi_app;
-- Worker: deletion jobs remove the document row after files, pages, and chunks.
CREATE POLICY document_worker_delete ON fdi.documents FOR DELETE TO fdi_worker
 USING (organization_id = fdi.org_id() AND status = 'deleting');
GRANT DELETE ON fdi.documents TO fdi_worker;
