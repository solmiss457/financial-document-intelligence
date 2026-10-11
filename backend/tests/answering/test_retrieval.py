import json
from uuid import UUID
import pytest
from fdi.answering.b0 import CONFIGS
from fdi.db.session import request_connection
from fdi.ingestion.embedding import HashEmbedder, vector_literal
from fdi.retrieval import Evidence, reciprocal_rank_fusion, retrieve, retrieve_keyword

CHUNKER = CONFIGS['R2'].chunker


def u(n): return UUID(int=n)


def ev(n): return Evidence(u(n), u(1), 't', 1, 1, [], f'text {n}', 0.0)


def test_rrf_rewards_agreement_and_is_deterministic():
    fused = reciprocal_rank_fusion([[ev(1), ev(2), ev(3)], [ev(3), ev(4), ev(1)]], k=3)
    assert [e.chunk_id.int for e in fused] == [1, 3, 2]
    assert fused[0].score == pytest.approx(1 / 61 + 1 / 63)
    assert [e.chunk_id.int for e in reciprocal_rank_fusion([[ev(2)], [ev(1)]], k=2)] == [1, 2]  # tie -> id order


@pytest.fixture
def corpus(database):
    admin, pool = database
    emb = HashEmbedder()
    texts = {101: 'Total revenues 371,433 Berkshire', 102: 'restricted Total revenues 5', 103: 'Total revenues other org',
             104: 'restricted other org revenues', 105: 'deleting revenues', 106: 'queued revenues'}
    org = {101: 1, 102: 1, 103: 2, 104: 2, 105: 1, 106: 1}
    for doc, text in texts.items():
        admin.execute('''INSERT INTO fdi.chunks (organization_id,document_id,chunker,chunk_index,page_start,page_end,
            spans,text,embedding_model,embedding) VALUES (%s,%s,%s,0,1,1,%s,%s,'h',%s::vector)''',
            (u(org[doc]), u(doc), CHUNKER, json.dumps([]), text, vector_literal(emb.embed_documents([text])[0])))
    return pool, emb


@pytest.mark.parametrize('user,org,docs', [(12, 1, {101}), (11, 1, {101, 102}), (13, 1, {101, 102}),
                                           (17, 2, {103}), (21, 2, {103, 104}), (21, 1, set())])
def test_keyword_and_hybrid_retrieval_respect_rls(corpus, user, org, docs):
    pool, emb = corpus
    question = 'What were total revenues?'
    with request_connection(pool, u(user), u(org)) as conn:
        keyword = retrieve_keyword(conn, question, CHUNKER, 50)
        hybrid = retrieve(conn, CONFIGS['R2'], question, vector_literal(emb.embed_query(question)))
    assert {e.document_id.int for e in keyword} == docs
    assert {e.document_id.int for e in hybrid} == docs


def test_keyword_ranks_matching_terms_and_handles_stopword_only_questions(corpus):
    pool, _ = corpus
    with request_connection(pool, u(11), u(1)) as conn:
        ranked = retrieve_keyword(conn, 'Berkshire total revenues', CHUNKER, 5)
        assert ranked[0].document_id.int == 101
        assert retrieve_keyword(conn, 'what is the', CHUNKER, 5) == []


def test_unknown_retrieval_rejected(corpus):
    pool, _ = corpus
    from dataclasses import replace
    with request_connection(pool, u(11), u(1)) as conn, pytest.raises(ValueError):
        retrieve(conn, replace(CONFIGS['B0'], retrieval='bm25'), 'q', '[0]')
