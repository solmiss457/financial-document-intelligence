"""Retrieval over chunks the caller may read. Always run inside request_connection so
RLS (organization, ACL, ready status) filters candidates before ranking."""
from dataclasses import dataclass, replace
from uuid import UUID


@dataclass(frozen=True)
class Evidence:
    chunk_id: UUID
    document_id: UUID
    title: str
    page_start: int
    page_end: int
    spans: list
    text: str
    score: float


def retrieve_vector(conn, query_literal, chunker, k):
    """Exact cosine search (no ANN index) over authorized chunks of one chunker."""
    rows = conn.execute('''SELECT c.id, c.document_id, d.title, c.page_start, c.page_end, c.spans, c.text,
            1 - (c.embedding <=> %s::vector) AS score
        FROM fdi.chunks c JOIN fdi.documents d ON d.organization_id=c.organization_id AND d.id=c.document_id
        WHERE c.chunker=%s ORDER BY c.embedding <=> %s::vector, c.id LIMIT %s''',
        (query_literal, chunker, query_literal, k)).fetchall()
    return [Evidence(r['id'], r['document_id'], r['title'], r['page_start'], r['page_end'], r['spans'],
                     r['text'], float(r['score'])) for r in rows]


def retrieve_keyword(conn, question, chunker, k):
    """PostgreSQL full-text search (not BM25). Question terms are OR-ed so long questions still
    match; ts_rank_cd normalization 1 divides by the log of chunk length."""
    rows = conn.execute('''SELECT c.id, c.document_id, d.title, c.page_start, c.page_end, c.spans, c.text,
            ts_rank_cd(c.search_text, query.q, 1) AS score
        FROM fdi.chunks c JOIN fdi.documents d ON d.organization_id=c.organization_id AND d.id=c.document_id,
            LATERAL (SELECT NULLIF(replace(plainto_tsquery('english', %s)::text, ' & ', ' | '), '')::tsquery AS q) query
        WHERE c.chunker=%s AND query.q IS NOT NULL AND c.search_text @@ query.q
        ORDER BY score DESC, c.id LIMIT %s''', (question, chunker, k)).fetchall()
    return [Evidence(r['id'], r['document_id'], r['title'], r['page_start'], r['page_end'], r['spans'],
                     r['text'], float(r['score'])) for r in rows]


def reciprocal_rank_fusion(rankings, k, rrf_k=60):
    """score = sum(1 / (rrf_k + rank)) over rankings; ties broken by chunk id for determinism."""
    scores, items = {}, {}
    for ranking in rankings:
        for rank, e in enumerate(ranking, start=1):
            scores[e.chunk_id] = scores.get(e.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            items.setdefault(e.chunk_id, e)
    ordered = sorted(scores, key=lambda cid: (-scores[cid], str(cid)))[:k]
    return [replace(items[c], score=scores[c]) for c in ordered]


def retrieve(conn, config, question, query_literal):
    if config.retrieval == 'vector':
        return retrieve_vector(conn, query_literal, config.chunker, config.k)
    if config.retrieval == 'hybrid':
        return reciprocal_rank_fusion([retrieve_vector(conn, query_literal, config.chunker, config.candidates),
                                       retrieve_keyword(conn, question, config.chunker, config.candidates)],
                                      config.k, config.rrf_k)
    raise ValueError(f'Unknown retrieval {config.retrieval}')


def visible_chunk_ids(conn, chunk_ids):
    rows = conn.execute('SELECT id FROM fdi.chunks WHERE id = ANY(%s)', (list(chunk_ids),)).fetchall()
    return {r['id'] for r in rows}
