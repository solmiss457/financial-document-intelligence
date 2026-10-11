-- Ingestion jobs, extracted pages, and retrievable chunks. Children of documents
-- carry organization_id and use composite FKs so they cannot cross organizations.
CREATE EXTENSION IF NOT EXISTS vector;
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='fdi_worker') THEN
  CREATE ROLE fdi_worker LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
END $$;
SET LOCAL ROLE fdi_owner;
CREATE TABLE fdi.ingestion_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 organization_id uuid NOT NULL,
 document_id uuid NOT NULL,
 dedup_key text NOT NULL UNIQUE,
 status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
 attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
 max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
 lease_owner text,
 lease_expires_at timestamptz,
 last_error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK ((status = 'running') = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)),
 FOREIGN KEY (organization_id,document_id) REFERENCES fdi.documents(organization_id,id) ON DELETE CASCADE
);
CREATE INDEX ingestion_jobs_claimable ON fdi.ingestion_jobs(created_at) WHERE status IN ('queued','running');
CREATE TABLE fdi.document_pages (
 organization_id uuid NOT NULL,
 document_id uuid NOT NULL,
 page_number integer NOT NULL CHECK (page_number >= 1),
 width real NOT NULL,
 height real NOT NULL,
 text text NOT NULL,
 PRIMARY KEY (organization_id,document_id,page_number),
 FOREIGN KEY (organization_id,document_id) REFERENCES fdi.documents(organization_id,id) ON DELETE CASCADE
);
-- chunker names the strategy and parameters so B0 and later chunkers can coexist.
-- spans: [{"page": n, "bbox": [x0,y0,x1,y1]}] in PDF points for citation display.
CREATE TABLE fdi.chunks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 organization_id uuid NOT NULL,
 document_id uuid NOT NULL,
 chunker text NOT NULL,
 chunk_index integer NOT NULL CHECK (chunk_index >= 0),
 page_start integer NOT NULL,
 page_end integer NOT NULL,
 spans jsonb NOT NULL,
 text text NOT NULL,
 embedding_model text NOT NULL,
 embedding vector(384) NOT NULL,
 search_text tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
 CHECK (1 <= page_start AND page_start <= page_end),
 UNIQUE (organization_id,document_id,chunker,chunk_index),
 FOREIGN KEY (organization_id,document_id) REFERENCES fdi.documents(organization_id,id) ON DELETE CASCADE
);
CREATE INDEX chunks_document ON fdi.chunks(organization_id,document_id);
CREATE INDEX chunks_search_text ON fdi.chunks USING gin(search_text);
ALTER TABLE fdi.ingestion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.ingestion_jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE fdi.document_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.document_pages FORCE ROW LEVEL SECURITY;
ALTER TABLE fdi.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE fdi.chunks FORCE ROW LEVEL SECURITY;
-- API: content is readable only through a ready document the user can already read.
-- The documents subquery is itself filtered by documents RLS (membership, ACL).
CREATE POLICY page_read ON fdi.document_pages FOR SELECT TO fdi_app
 USING (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.documents d WHERE d.organization_id=document_pages.organization_id
   AND d.id=document_pages.document_id AND d.status='ready'));
CREATE POLICY chunk_read ON fdi.chunks FOR SELECT TO fdi_app
 USING (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.documents d WHERE d.organization_id=chunks.organization_id
   AND d.id=chunks.document_id AND d.status='ready'));
CREATE POLICY job_admin_read ON fdi.ingestion_jobs FOR SELECT TO fdi_app
 USING (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=ingestion_jobs.organization_id AND m.role='admin'));
CREATE POLICY job_admin_insert ON fdi.ingestion_jobs FOR INSERT TO fdi_app
 WITH CHECK (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=ingestion_jobs.organization_id AND m.role='admin'));
-- Worker: claims jobs across organizations, then sets fdi.org_id to the job's
-- organization so document/page/chunk access is limited to that organization.
CREATE POLICY job_worker_read ON fdi.ingestion_jobs FOR SELECT TO fdi_worker USING (true);
CREATE POLICY job_worker_update ON fdi.ingestion_jobs FOR UPDATE TO fdi_worker USING (true) WITH CHECK (true);
CREATE POLICY document_worker_read ON fdi.documents FOR SELECT TO fdi_worker
 USING (organization_id=fdi.org_id());
CREATE POLICY document_worker_update ON fdi.documents FOR UPDATE TO fdi_worker
 USING (organization_id=fdi.org_id()) WITH CHECK (organization_id=fdi.org_id());
CREATE POLICY page_worker ON fdi.document_pages FOR ALL TO fdi_worker
 USING (organization_id=fdi.org_id()) WITH CHECK (organization_id=fdi.org_id());
CREATE POLICY chunk_worker ON fdi.chunks FOR ALL TO fdi_worker
 USING (organization_id=fdi.org_id()) WITH CHECK (organization_id=fdi.org_id());
GRANT SELECT ON fdi.document_pages, fdi.chunks, fdi.ingestion_jobs TO fdi_app;
GRANT INSERT (organization_id,document_id,dedup_key) ON fdi.ingestion_jobs TO fdi_app;
GRANT USAGE ON SCHEMA fdi TO fdi_worker;
GRANT EXECUTE ON FUNCTION fdi.user_id(), fdi.org_id() TO fdi_worker;
GRANT SELECT ON fdi.ingestion_jobs, fdi.documents TO fdi_worker;
GRANT UPDATE (status,attempts,lease_owner,lease_expires_at,last_error,updated_at) ON fdi.ingestion_jobs TO fdi_worker;
GRANT UPDATE (status) ON fdi.documents TO fdi_worker;
GRANT SELECT, INSERT, DELETE ON fdi.document_pages, fdi.chunks TO fdi_worker;
