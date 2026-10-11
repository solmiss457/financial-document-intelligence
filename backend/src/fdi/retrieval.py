"""Retrieval over chunks the caller may read. Always run inside request_connection so
RLS (organization, ACL, ready status) filters candidates before ranking."""
from dataclasses import dataclass
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


def visible_chunk_ids(conn, chunk_ids):
    rows = conn.execute('SELECT id FROM fdi.chunks WHERE id = ANY(%s)', (list(chunk_ids),)).fetchall()
    return {r['id'] for r in rows}
