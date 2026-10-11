"""Database-backed ingestion jobs: claim with SKIP LOCKED, leases, retries, idempotent writes.

Logs carry IDs, counts, and outcomes only, never document text.
"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from fdi.db.session import organization_connection
from fdi.ingestion.chunkers import CHUNKERS
from fdi.ingestion.embedding import vector_literal
from fdi.ingestion.extract import PermanentIngestionError, extract_pdf_isolated

log = logging.getLogger('fdi.worker')


@dataclass(frozen=True)
class Settings:
    lease_seconds: int = 600
    max_bytes: int = 50 * 1024 * 1024
    max_pages: int = 1000
    extract_timeout_seconds: int = 300
    embed_batch: int = 64


class LeaseLost(Exception):
    """Another worker reclaimed the job; this worker must not write results."""


def dedup_key(document_id, sha256, chunker):
    return f'ingest:{document_id}:{sha256}:{chunker}'


def enqueue(conn, organization_id, document_id, sha256, chunker):
    """Idempotent: the same document version and chunker produce one job."""
    return conn.execute('''INSERT INTO fdi.ingestion_jobs (organization_id,document_id,dedup_key,chunker)
        VALUES (%s,%s,%s,%s) ON CONFLICT (dedup_key) DO NOTHING RETURNING id''',
        (organization_id, document_id, dedup_key(document_id, sha256, chunker), chunker)).fetchone()


def reap_exhausted(pool):
    """Fail jobs whose final attempt's lease expired (crashed worker), and their documents."""
    with pool.connection() as conn, conn.transaction():
        rows = conn.execute('''UPDATE fdi.ingestion_jobs SET status='failed', lease_owner=NULL,
            lease_expires_at=NULL, last_error='Lease expired on final attempt', updated_at=now()
            WHERE status='running' AND lease_expires_at < now() AND attempts >= max_attempts
            RETURNING id, organization_id, document_id''').fetchall()
    for row in rows:
        _set_document_status(pool, row, 'failed')
        log.warning('job %s failed: lease expired on final attempt', row['id'])
    return len(rows)


def claim(pool, worker_id, lease_seconds):
    with pool.connection() as conn, conn.transaction():
        return conn.execute('''UPDATE fdi.ingestion_jobs SET status='running', attempts=attempts+1,
            lease_owner=%s, lease_expires_at=now() + make_interval(secs => %s), updated_at=now()
            WHERE id = (SELECT id FROM fdi.ingestion_jobs
                WHERE attempts < max_attempts
                AND (status='queued' OR (status='running' AND lease_expires_at < now()))
                ORDER BY created_at, id FOR UPDATE SKIP LOCKED LIMIT 1)
            RETURNING id, organization_id, document_id, attempts, max_attempts, chunker, kind''',
            (worker_id, lease_seconds)).fetchone()


def renew(pool, job, worker_id, lease_seconds):
    with pool.connection() as conn, conn.transaction():
        if not conn.execute('''UPDATE fdi.ingestion_jobs SET lease_expires_at=now() + make_interval(secs => %s),
                updated_at=now() WHERE id=%s AND status='running' AND lease_owner=%s''',
                (lease_seconds, job['id'], worker_id)).rowcount:
            raise LeaseLost(str(job['id']))


def _lock_own_job(conn, job, worker_id):
    if not conn.execute('''SELECT 1 FROM fdi.ingestion_jobs WHERE id=%s AND status='running'
            AND lease_owner=%s FOR UPDATE''', (job['id'], worker_id)).fetchone():
        raise LeaseLost(str(job['id']))


def _finish_job(conn, job, status, error=None):
    conn.execute('''UPDATE fdi.ingestion_jobs SET status=%s, lease_owner=NULL, lease_expires_at=NULL,
        last_error=%s, updated_at=now() WHERE id=%s''', (status, error, job['id']))


def _set_document_status(pool, job, status, unless=('deleting',)):
    with organization_connection(pool, job['organization_id']) as conn:
        conn.execute('UPDATE fdi.documents SET status=%s WHERE id=%s AND status <> ALL(%s)',
                     (status, job['document_id'], list(unless)))


def _start(pool, job, worker_id):
    """Returns the document row, or None when the job should be cancelled."""
    with organization_connection(pool, job['organization_id']) as conn:
        _lock_own_job(conn, job, worker_id)
        doc = conn.execute('''SELECT id, title, storage_key, sha256, status FROM fdi.documents
            WHERE id=%s FOR UPDATE''', (job['document_id'],)).fetchone()
        if not doc or doc['status'] == 'deleting':
            _finish_job(conn, job, 'cancelled', 'Document missing or being deleted')
            return None
        conn.execute("UPDATE fdi.documents SET status='processing' WHERE id=%s", (doc['id'],))
        return doc


def _read_verified(storage, doc, settings):
    path = storage.path(doc['storage_key'])
    if not path.is_file():
        raise PermanentIngestionError('Stored file missing')
    if path.stat().st_size > settings.max_bytes:
        raise PermanentIngestionError(f'File exceeds {settings.max_bytes} bytes')
    if hashlib.sha256(path.read_bytes()).hexdigest() != doc['sha256']:
        raise PermanentIngestionError('Stored file hash does not match document version')
    return path


def _embed(pool, job, worker_id, embedder, chunks, settings):
    vectors = []
    for start in range(0, len(chunks), settings.embed_batch):
        batch = chunks[start:start + settings.embed_batch]
        vectors.extend(embedder.embed_documents([c.text for c in batch]))
        renew(pool, job, worker_id, settings.lease_seconds)
    return vectors


def _write(pool, job, worker_id, pages, chunks, vectors, chunker, embedder):
    """All-or-nothing replacement; skipped if the lease was lost or deletion began."""
    with organization_connection(pool, job['organization_id']) as conn:
        _lock_own_job(conn, job, worker_id)
        status = conn.execute('SELECT status FROM fdi.documents WHERE id=%s FOR UPDATE',
                              (job['document_id'],)).fetchone()
        if not status or status['status'] == 'deleting':
            _finish_job(conn, job, 'cancelled', 'Document deleted during processing')
            return False
        org, doc = job['organization_id'], job['document_id']
        conn.execute('DELETE FROM fdi.document_pages WHERE organization_id=%s AND document_id=%s', (org, doc))
        conn.execute('DELETE FROM fdi.chunks WHERE organization_id=%s AND document_id=%s AND chunker=%s',
                     (org, doc, chunker))
        with conn.cursor() as cur:
            cur.executemany('INSERT INTO fdi.document_pages VALUES (%s,%s,%s,%s,%s,%s)',
                            [(org, doc, p.number, p.width, p.height, p.text) for p in pages])
            cur.executemany('''INSERT INTO fdi.chunks (organization_id,document_id,chunker,chunk_index,
                page_start,page_end,spans,text,embedding_model,embedding) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)''',
                [(org, doc, chunker, c.index, c.page_start, c.page_end, json.dumps(c.spans), c.text,
                  embedder.name, vector_literal(v)) for c, v in zip(chunks, vectors, strict=True)])
        conn.execute("UPDATE fdi.documents SET status='ready' WHERE id=%s", (doc,))
        _finish_job(conn, job, 'succeeded')
        return True


def _record_failure(pool, job, worker_id, exc):
    permanent = isinstance(exc, PermanentIngestionError)
    # Only our own messages are stored; library exceptions are reduced to their type.
    error = str(exc) if permanent else type(exc).__name__
    final = permanent or job['attempts'] >= job['max_attempts']
    with pool.connection() as conn, conn.transaction():
        if not conn.execute('''UPDATE fdi.ingestion_jobs SET status=%s, lease_owner=NULL, lease_expires_at=NULL,
                last_error=%s, updated_at=now() WHERE id=%s AND status='running' AND lease_owner=%s''',
                ('failed' if final else 'queued', error, job['id'], worker_id)).rowcount:
            return
    _set_document_status(pool, job, 'failed' if final else 'queued')
    log.warning('job %s attempt %s/%s %s: %s', job['id'], job['attempts'], job['max_attempts'],
                'failed' if final else 'will retry', error)


def delete_document(pool, job, worker_id, storage):
    """Deletion job: remove the original, then the row; FK cascades remove pages, chunks, grants, and
    jobs (this one included). Only documents already marked deleting can be removed."""
    with organization_connection(pool, job['organization_id']) as conn:
        _lock_own_job(conn, job, worker_id)
        doc = conn.execute('SELECT storage_key, status FROM fdi.documents WHERE id=%s FOR UPDATE',
                           (job['document_id'],)).fetchone()
        if not doc or doc['status'] != 'deleting':
            _finish_job(conn, job, 'cancelled', 'Document is not marked for deletion')
            return 'cancelled'
        storage.path(doc['storage_key']).unlink(missing_ok=True)
        conn.execute('DELETE FROM fdi.documents WHERE id=%s', (job['document_id'],))
    log.info('job %s deleted document %s', job['id'], job['document_id'])
    return 'deleted'


def process(pool, job, worker_id, storage, embedder, settings=Settings(), chunkers=None):
    started = time.monotonic()
    if job.get('kind') == 'delete':
        try:
            return delete_document(pool, job, worker_id, storage)
        except LeaseLost:
            log.warning('job %s lease lost; deletion will be retried', job['id'])
            return 'lease_lost'
        except Exception as exc:
            _record_failure(pool, job, worker_id, exc)
            return 'failed'

    chunker = job['chunker']
    chunk = (chunkers or CHUNKERS).get(chunker)
    try:
        doc = _start(pool, job, worker_id)
        if doc is None:
            log.info('job %s cancelled before processing', job['id'])
            return 'cancelled'
        if chunk is None:
            raise PermanentIngestionError(f'Unknown chunker {chunker}')
        path = _read_verified(storage, doc, settings)
        pages = extract_pdf_isolated(path, settings.max_pages, settings.extract_timeout_seconds)
        renew(pool, job, worker_id, settings.lease_seconds)
        chunks = chunk(pages, doc['title'])
        if not chunks:
            raise PermanentIngestionError('No extractable text')
        vectors = _embed(pool, job, worker_id, embedder, chunks, settings)
        if not _write(pool, job, worker_id, pages, chunks, vectors, chunker, embedder):
            log.info('job %s cancelled: document deleted during processing', job['id'])
            return 'cancelled'
    except LeaseLost:
        log.warning('job %s lease lost; results discarded', job['id'])
        return 'lease_lost'
    except Exception as exc:
        _record_failure(pool, job, worker_id, exc)
        return 'failed'
    log.info('job %s document %s ready: %d pages, %d chunks, %.1fs', job['id'], job['document_id'],
             len(pages), len(chunks), time.monotonic() - started)
    return 'succeeded'


def run_once(pool, worker_id, storage, embedder, settings=Settings(), chunkers=None):
    reap_exhausted(pool)
    job = claim(pool, worker_id, settings.lease_seconds)
    return None if job is None else process(pool, job, worker_id, storage, embedder, settings, chunkers)
