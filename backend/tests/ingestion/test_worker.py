"""Worker against the real fdi_test database with generated PDFs and a hash embedder."""
import hashlib
import logging
import threading
from uuid import UUID
import pymupdf
import pytest
from fdi.db.config import dsn
from fdi.db.session import create_pool, request_connection
from fdi.ingestion.embedding import HashEmbedder
from fdi.ingestion.extract import PermanentIngestionError, extract_pdf_isolated
from fdi.storage import LocalStorage
from fdi.worker import jobs
from fdi.ingestion.chunking import fixed_word_chunks
from fdi.worker.jobs import Settings, claim, enqueue, process, run_once

SETTINGS = Settings(lease_seconds=60, extract_timeout_seconds=60)
CHUNKER = 'fixed_words_v1:20/5'


def u(n): return UUID(int=n)


def make_pdf(path, pages=3, marker='CANARY_TEXT'):
    doc = pymupdf.open()
    for p in range(pages):
        page = doc.new_page()
        for line in range(8):
            page.insert_text((72, 72 + 14 * line), f'{marker} page {p + 1} line {line} revenue {1000 + line}')
    doc.save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def small_chunker(monkeypatch):
    monkeypatch.setitem(jobs.CHUNKERS, CHUNKER, lambda pages, title: fixed_word_chunks(pages, 20, 5))


@pytest.fixture
def env(database, tmp_path):
    admin, app = database
    storage = LocalStorage(tmp_path / 'documents')
    worker = create_pool(dsn(role='worker'), max_size=2, expected_role='fdi_worker')

    def add_document(n, org=1, status='queued', pages=3, sha=None, visibility='organization'):
        src = tmp_path / f'{n}.pdf'
        digest = make_pdf(src, pages)
        key = storage.put(src.read_bytes())
        admin.execute('INSERT INTO fdi.documents VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                      (u(n), u(org), f'Doc {n}', key, sha or digest, 'test-v1', visibility, status))
        enqueue(admin, u(org), u(n), sha or digest, CHUNKER)
        return key

    try:
        yield admin, app, worker, storage, add_document
    finally:
        worker.close()


def job_of(admin, n):
    return admin.execute('SELECT status,attempts,last_error,lease_owner FROM fdi.ingestion_jobs WHERE document_id=%s', (u(n),)).fetchone()


def doc_status(admin, n):
    return admin.execute('SELECT status FROM fdi.documents WHERE id=%s', (u(n),)).fetchone()[0]


def counts(admin, n):
    return tuple(admin.execute(f'SELECT count(*) FROM fdi.{t} WHERE document_id=%s', (u(n),)).fetchone()[0]
                 for t in ('document_pages', 'chunks'))


def test_ingest_end_to_end_then_member_can_retrieve(env, caplog):
    admin, app, worker, storage, add = env
    add(201)
    caplog.set_level(logging.INFO, logger='fdi.worker')
    assert run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS) == 'succeeded'
    assert job_of(admin, 201)[:2] == ('succeeded', 1) and doc_status(admin, 201) == 'ready'
    pages, chunks = counts(admin, 201)
    assert pages == 3 and chunks > 1
    assert admin.execute('SELECT DISTINCT chunker, embedding_model FROM fdi.chunks').fetchall() == [(CHUNKER, 'test-hash-embedder')]
    with request_connection(app, u(12), u(1)) as conn:
        assert conn.execute('SELECT count(*) AS n FROM fdi.chunks WHERE document_id=%s', (u(201),)).fetchone()['n'] == chunks
    with request_connection(app, u(21), u(2)) as conn:
        assert conn.execute('SELECT count(*) AS n FROM fdi.chunks').fetchone()['n'] == 0
    assert 'CANARY_TEXT' not in caplog.text
    assert run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS) is None


def test_reprocessing_replaces_without_duplicates(env):
    admin, _, worker, storage, add = env
    add(201)
    run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS)
    before = counts(admin, 201)
    admin.execute("INSERT INTO fdi.ingestion_jobs (organization_id,document_id,dedup_key,chunker) VALUES (%s,%s,'manual-rerun',%s)", (u(1), u(201), CHUNKER))
    assert run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS) == 'succeeded'
    assert counts(admin, 201) == before


def test_enqueue_is_deduplicated(env):
    admin, *_ = env
    add = env[4]
    add(201)
    sha = admin.execute('SELECT sha256 FROM fdi.documents WHERE id=%s', (u(201),)).fetchone()[0]
    assert enqueue(admin, u(1), u(201), sha, CHUNKER) is None
    assert admin.execute('SELECT count(*) FROM fdi.ingestion_jobs').fetchone()[0] == 1


def test_concurrent_claims_never_share_a_job(env):
    admin, _, worker, _, add = env
    for n in range(201, 206):
        add(n)
    results, barrier = [], threading.Barrier(5)

    def grab(i):
        barrier.wait()
        results.append(claim(worker, f'w{i}', 60))
    threads = [threading.Thread(target=grab, args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    ids = [r['id'] for r in results if r]
    assert len(ids) == len(set(ids)) == 5
    assert claim(worker, 'late', 60) is None


def test_crashed_worker_lease_expires_and_stale_worker_cannot_write(env):
    admin, _, worker, storage, add = env
    add(201)
    stale = claim(worker, 'crashed', 60)  # worker dies before processing
    assert claim(worker, 'other', 60) is None
    admin.execute("UPDATE fdi.ingestion_jobs SET lease_expires_at=now()-interval '1 second'")
    assert run_once(worker, 'recovered', storage, HashEmbedder(), SETTINGS) == 'succeeded'
    assert job_of(admin, 201)[:2] == ('succeeded', 2)
    before = counts(admin, 201)
    assert process(worker, stale, 'crashed', storage, HashEmbedder(), SETTINGS) == 'lease_lost'
    assert counts(admin, 201) == before and job_of(admin, 201)[0] == 'succeeded'


def test_stale_worker_cannot_write_while_new_owner_is_running(env):
    admin, _, worker, storage, add = env
    add(201)
    stale = claim(worker, 'slow', 60)
    admin.execute("UPDATE fdi.ingestion_jobs SET lease_expires_at=now()-interval '1 second'")
    current = claim(worker, 'new-owner', 60)
    assert current['id'] == stale['id'] and current['attempts'] == 2
    assert process(worker, stale, 'slow', storage, HashEmbedder(), SETTINGS) == 'lease_lost'
    assert counts(admin, 201) == (0, 0) and job_of(admin, 201)[3] == 'new-owner'
    assert process(worker, current, 'new-owner', storage, HashEmbedder(), SETTINGS) == 'succeeded'


def test_lease_lost_mid_processing_discards_results(env):
    admin, _, worker, storage, add = env
    add(201)
    job = claim(worker, 'slow', 60)

    class StealingEmbedder(HashEmbedder):
        def embed_documents(self, texts):
            admin.execute("UPDATE fdi.ingestion_jobs SET lease_owner='thief', lease_expires_at=now()+interval '1 minute'")
            return super().embed_documents(texts)
    assert process(worker, job, 'slow', storage, StealingEmbedder(), SETTINGS) == 'lease_lost'
    assert counts(admin, 201) == (0, 0)


def test_final_write_rechecks_lease_even_without_renewal(env, monkeypatch):
    admin, _, worker, storage, add = env
    add(201)
    job = claim(worker, 'slow', 60)
    monkeypatch.setattr(jobs, 'renew', lambda *a, **k: None)  # isolate the last guard

    class StealingEmbedder(HashEmbedder):
        def embed_documents(self, texts):
            admin.execute("UPDATE fdi.ingestion_jobs SET lease_owner='thief'")
            return super().embed_documents(texts)
    assert process(worker, job, 'slow', storage, StealingEmbedder(), SETTINGS) == 'lease_lost'
    assert counts(admin, 201) == (0, 0)


def test_final_attempt_lease_expiry_is_reaped(env):
    admin, _, worker, storage, add = env
    add(201)
    admin.execute('UPDATE fdi.ingestion_jobs SET max_attempts=1')
    claim(worker, 'crashed', 60)
    admin.execute("UPDATE fdi.ingestion_jobs SET lease_expires_at=now()-interval '1 second'")
    assert run_once(worker, 'w2', storage, HashEmbedder(), SETTINGS) is None
    assert job_of(admin, 201)[:2] == ('failed', 1) and doc_status(admin, 201) == 'failed'


class FlakyEmbedder(HashEmbedder):
    def __init__(self, failures): self.failures = failures

    def embed_documents(self, texts):
        if self.failures:
            self.failures -= 1
            raise ConnectionError('CANARY_TEXT secret detail')
        return super().embed_documents(texts)


def test_transient_failure_retries_then_succeeds(env):
    admin, _, worker, storage, add = env
    add(201)
    embedder = FlakyEmbedder(failures=1)
    assert run_once(worker, 'w1', storage, embedder, SETTINGS) == 'failed'
    assert job_of(admin, 201)[:3] == ('queued', 1, 'ConnectionError') and doc_status(admin, 201) == 'queued'
    assert counts(admin, 201) == (0, 0)
    assert run_once(worker, 'w1', storage, embedder, SETTINGS) == 'succeeded'
    assert job_of(admin, 201)[:2] == ('succeeded', 2)


def test_retries_exhausted_marks_failed(env):
    admin, _, worker, storage, add = env
    add(201)
    embedder = FlakyEmbedder(failures=99)
    for _ in range(3):
        assert run_once(worker, 'w1', storage, embedder, SETTINGS) == 'failed'
    assert job_of(admin, 201)[:2] == ('failed', 3) and doc_status(admin, 201) == 'failed'
    assert run_once(worker, 'w1', storage, embedder, SETTINGS) is None


@pytest.mark.parametrize('corrupt', ['hash', 'missing', 'not_pdf'])
def test_permanent_input_errors_fail_without_retry(env, corrupt):
    admin, _, worker, storage, add = env
    key = add(201, sha='f' * 64 if corrupt == 'hash' else None)
    path = storage.path(key)
    if corrupt == 'missing':
        path.unlink()
    elif corrupt == 'not_pdf':
        path.write_bytes(b'not a pdf')
        admin.execute('UPDATE fdi.documents SET sha256=%s', (hashlib.sha256(b'not a pdf').hexdigest(),))
    assert run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS) == 'failed'
    status, attempts, error, _ = job_of(admin, 201)
    assert (status, attempts) == ('failed', 1) and doc_status(admin, 201) == 'failed'
    assert counts(admin, 201) == (0, 0)


def test_deleting_before_claim_cancels(env):
    admin, _, worker, storage, add = env
    add(201, status='deleting')
    assert run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS) == 'cancelled'
    assert job_of(admin, 201)[0] == 'cancelled' and doc_status(admin, 201) == 'deleting'


def test_deletion_during_processing_writes_nothing(env):
    admin, _, worker, storage, add = env
    add(201)

    class DeletingEmbedder(HashEmbedder):
        def embed_documents(self, texts):
            admin.execute("UPDATE fdi.documents SET status='deleting' WHERE id=%s", (u(201),))
            return super().embed_documents(texts)
    assert run_once(worker, 'w1', storage, DeletingEmbedder(), SETTINGS) == 'cancelled'
    assert counts(admin, 201) == (0, 0) and doc_status(admin, 201) == 'deleting'
    assert job_of(admin, 201)[0] == 'cancelled'


def test_page_limit_and_extraction_timeout(tmp_path):
    path = tmp_path / 'a.pdf'
    make_pdf(path, pages=3)
    with pytest.raises(PermanentIngestionError, match='Page count'):
        extract_pdf_isolated(path, max_pages=2, timeout_seconds=60)
    with pytest.raises(PermanentIngestionError, match='exceeded'):
        extract_pdf_isolated(path, max_pages=5, timeout_seconds=0.001)
    assert len(extract_pdf_isolated(path, max_pages=5, timeout_seconds=60)) == 3


def test_worker_rejects_cross_org_job_document(env):
    """A job row pointing at another org's document cannot exist (composite FK)."""
    admin, *_ = env
    env[4](201, org=1)
    import psycopg
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        admin.execute("INSERT INTO fdi.ingestion_jobs (organization_id,document_id,dedup_key) VALUES (%s,%s,'x')", (u(2), u(201)))


def test_unknown_chunker_fails_permanently(env):
    admin, _, worker, storage, add = env
    add(201)
    admin.execute("UPDATE fdi.ingestion_jobs SET chunker='no-such-chunker'")
    assert run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS) == 'failed'
    assert job_of(admin, 201)[:3] == ('failed', 1, 'Unknown chunker no-such-chunker')


def test_chunkers_coexist_per_document(env, monkeypatch):
    admin, _, worker, storage, add = env
    add(201)
    monkeypatch.setitem(jobs.CHUNKERS, 'other', lambda pages, title: fixed_word_chunks(pages, 40, 0))
    run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS)
    sha = admin.execute('SELECT sha256 FROM fdi.documents').fetchone()[0]
    enqueue(admin, u(1), u(201), sha, 'other')
    assert run_once(worker, 'w1', storage, HashEmbedder(), SETTINGS) == 'succeeded'
    rows = dict(admin.execute('SELECT chunker, count(*) FROM fdi.chunks GROUP BY chunker').fetchall())
    assert set(rows) == {CHUNKER, 'other'} and counts(admin, 201)[0] == 3
