"""Local development only: register manifest reports for fictional organizations and enqueue ingestion.

Organization A follows evaluation/configs/s1_access.json (Berkshire 2023 restricted with a grant);
the other reports are organization-wide. Organization B has members but no documents, so
isolation can be checked against real chunks. Re-running is idempotent.
"""
import hashlib
import json
import uuid
import psycopg
from fdi.db.config import ROOT, dsn
from fdi.storage import LocalStorage
from fdi.worker.jobs import Settings, enqueue
from fdi.ingestion.chunking import chunker_name

ORG_A, ORG_B = uuid.UUID(int=1), uuid.UUID(int=2)
ADMIN_A, ADMIN_B, MEMBER_B = uuid.UUID(int=0xa), uuid.UUID(int=0xc), uuid.UUID(int=0xd)
NAMESPACE = uuid.UUID('6f1c1d9e-3c55-4a59-9c1f-6a1f4d0c2b11')


def main():
    access = json.loads((ROOT / 'evaluation/configs/s1_access.json').read_text())
    assert uuid.UUID(access['organization_id']) == ORG_A
    member_a = uuid.UUID(access['user_id'])
    fixed = {d['document_id']: d for d in access['documents']}
    manifest = json.loads((ROOT / 'evaluation/manifests/s1_reports.json').read_text())
    settings = Settings()
    chunker = chunker_name(settings.chunk_size, settings.chunk_overlap)
    storage = LocalStorage()
    added = queued = 0
    with psycopg.connect(dsn(admin=True)) as conn:
        for user in (ADMIN_A, member_a, ADMIN_B, MEMBER_B):
            conn.execute('INSERT INTO fdi.users VALUES (%s,true) ON CONFLICT DO NOTHING', (user,))
        for org, name in ((ORG_A, 'Fictional Organization A'), (ORG_B, 'Fictional Organization B')):
            conn.execute('INSERT INTO fdi.organizations VALUES (%s,%s) ON CONFLICT DO NOTHING', (org, name))
        for org, user, role in ((ORG_A, ADMIN_A, 'admin'), (ORG_A, member_a, access['role']),
                                (ORG_B, ADMIN_B, 'admin'), (ORG_B, MEMBER_B, 'member')):
            conn.execute('INSERT INTO fdi.memberships VALUES (%s,%s,%s,true) ON CONFLICT DO NOTHING', (org, user, role))
        for report in manifest:
            path = ROOT / report['local_path']
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != report['sha256']:
                raise SystemExit(f"Hash mismatch for {report['document_id']}; not registering")
            spec = fixed.get(report['document_id'], {})
            doc_id = uuid.UUID(spec['db_id']) if spec else uuid.uuid5(NAMESPACE, report['document_id'])
            if not conn.execute('SELECT 1 FROM fdi.documents WHERE id=%s', (doc_id,)).fetchone():
                key = storage.put(data)
                conn.execute('INSERT INTO fdi.documents VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                             (doc_id, ORG_A, f"{report['company']} {report['document_id']}", key,
                              report['sha256'], report['version'], spec.get('visibility', 'organization'), 'queued'))
                added += 1
            if spec.get('grant'):
                conn.execute('INSERT INTO fdi.document_grants VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', (ORG_A, doc_id, member_a))
            queued += enqueue(conn, ORG_A, doc_id, report['sha256'], chunker) is not None
    print(f'Registered {added} new documents; enqueued {queued} new jobs ({chunker})')


if __name__ == '__main__':
    main()
