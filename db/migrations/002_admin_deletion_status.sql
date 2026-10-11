-- Administrators need deletion metadata for updates/recovery. No content lives here.
-- Members never see deleting documents. API content/list policy still excludes them.
ALTER POLICY document_read ON fdi.documents
 USING (organization_id=fdi.org_id() AND EXISTS (
   SELECT 1 FROM fdi.memberships m WHERE m.organization_id=documents.organization_id
   AND (m.role='admin' OR (status <> 'deleting' AND (visibility='organization' OR EXISTS (
     SELECT 1 FROM fdi.document_grants g WHERE g.organization_id=documents.organization_id
       AND g.document_id=documents.id AND g.user_id=fdi.user_id()))))));
