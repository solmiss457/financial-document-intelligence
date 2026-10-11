-- Executed transactionally by a migration administrator; API never owns tables.
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='fdi_owner') THEN
  CREATE ROLE fdi_owner NOLOGIN NOSUPERUSER NOBYPASSRLS;
 END IF;
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='fdi_app') THEN
  CREATE ROLE fdi_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
END $$;
CREATE SCHEMA fdi AUTHORIZATION fdi_owner;
REVOKE ALL ON SCHEMA fdi FROM PUBLIC;
SET LOCAL ROLE fdi_owner;
CREATE FUNCTION fdi.user_id() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('fdi.user_id', true), '')::uuid $$;
CREATE FUNCTION fdi.org_id() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('fdi.org_id', true), '')::uuid $$;
CREATE TABLE fdi.users (
 id uuid PRIMARY KEY, active boolean NOT NULL DEFAULT true
);
CREATE TABLE fdi.organizations (id uuid PRIMARY KEY, name text NOT NULL);
CREATE TABLE fdi.memberships (
 organization_id uuid NOT NULL REFERENCES fdi.organizations(id),
 user_id uuid NOT NULL REFERENCES fdi.users(id),
 role text NOT NULL CHECK (role IN ('admin','member')),
 active boolean NOT NULL DEFAULT true,
 PRIMARY KEY (organization_id,user_id)
);
CREATE TABLE fdi.documents (
 id uuid PRIMARY KEY,
 organization_id uuid NOT NULL REFERENCES fdi.organizations(id),
 title text NOT NULL,
 storage_key uuid NOT NULL UNIQUE,
 sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
 source_version text NOT NULL,
 visibility text NOT NULL CHECK (visibility IN ('organization','restricted')),
 status text NOT NULL CHECK (status IN ('queued','processing','ready','failed','deleting')),
 UNIQUE (organization_id,id)
);
CREATE TABLE fdi.document_grants (
 organization_id uuid NOT NULL,
 document_id uuid NOT NULL,
 user_id uuid NOT NULL,
 PRIMARY KEY (organization_id,document_id,user_id),
 FOREIGN KEY (organization_id,document_id) REFERENCES fdi.documents(organization_id,id) ON DELETE CASCADE,
 FOREIGN KEY (organization_id,user_id) REFERENCES fdi.memberships(organization_id,user_id) ON DELETE CASCADE
);
CREATE INDEX documents_org ON fdi.documents(organization_id);
CREATE INDEX grants_user ON fdi.document_grants(organization_id,user_id,document_id);
ALTER TABLE fdi.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.users FORCE ROW LEVEL SECURITY;
ALTER TABLE fdi.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.organizations FORCE ROW LEVEL SECURITY;
ALTER TABLE fdi.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE fdi.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.documents FORCE ROW LEVEL SECURITY;
ALTER TABLE fdi.document_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.document_grants FORCE ROW LEVEL SECURITY;
-- Dependency graph avoids recursion: users -> memberships -> grants -> documents.
CREATE POLICY user_self ON fdi.users FOR SELECT TO fdi_app
 USING (id=fdi.user_id() AND active);
CREATE POLICY membership_self ON fdi.memberships FOR SELECT TO fdi_app
 USING (user_id=fdi.user_id() AND organization_id=fdi.org_id() AND active
   AND EXISTS (SELECT 1 FROM fdi.users u WHERE u.id=user_id));
CREATE POLICY organization_member ON fdi.organizations FOR SELECT TO fdi_app
 USING (id=fdi.org_id() AND EXISTS (SELECT 1 FROM fdi.memberships m WHERE m.organization_id=id));
CREATE POLICY grant_read ON fdi.document_grants FOR SELECT TO fdi_app
 USING (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=document_grants.organization_id
   AND (m.role='admin' OR document_grants.user_id=fdi.user_id())));
CREATE POLICY document_read ON fdi.documents FOR SELECT TO fdi_app
 USING (organization_id=fdi.org_id() AND status <> 'deleting' AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=documents.organization_id
   AND (m.role='admin' OR visibility='organization' OR EXISTS (
     SELECT 1 FROM fdi.document_grants g WHERE g.organization_id=documents.organization_id
       AND g.document_id=documents.id AND g.user_id=fdi.user_id()))));
CREATE POLICY document_insert ON fdi.documents FOR INSERT TO fdi_app
 WITH CHECK (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=documents.organization_id AND m.role='admin'));
CREATE POLICY document_update ON fdi.documents FOR UPDATE TO fdi_app
 USING (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=documents.organization_id AND m.role='admin'))
 WITH CHECK (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=documents.organization_id AND m.role='admin'));
-- Physical deletion belongs to a later worker; API can only mark deleting.
CREATE POLICY grant_insert ON fdi.document_grants FOR INSERT TO fdi_app
 WITH CHECK (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=document_grants.organization_id AND m.role='admin'));
CREATE POLICY grant_delete ON fdi.document_grants FOR DELETE TO fdi_app
 USING (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=document_grants.organization_id AND m.role='admin'));
GRANT USAGE ON SCHEMA fdi TO fdi_app;
REVOKE ALL ON FUNCTION fdi.user_id(), fdi.org_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fdi.user_id(), fdi.org_id() TO fdi_app;
GRANT SELECT ON ALL TABLES IN SCHEMA fdi TO fdi_app;
GRANT INSERT ON fdi.documents, fdi.document_grants TO fdi_app;
GRANT UPDATE(title,visibility,status) ON fdi.documents TO fdi_app;
GRANT DELETE ON fdi.document_grants TO fdi_app;
