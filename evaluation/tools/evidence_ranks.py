"""Retrieval diagnostic without LLM calls: best rank of an evidence-covering chunk per question.

Vector and keyword ranks are over all authorized chunks of the configuration's chunker; the hybrid
rank is within the fused candidate pool the configuration actually uses (None = not in the pool).

    .venv/bin/python -m evaluation.tools.evidence_ranks
"""
import json
from uuid import UUID
from backend.scripts.register_reports import document_ids
from evaluation.tools.scoring import evidence_covered
from fdi.answering.b0 import CONFIGS
from fdi.db.config import ROOT, dsn
from fdi.db.session import create_pool, request_connection
from fdi.ingestion.embedding import vector_literal
from fdi.retrieval import reciprocal_rank_fusion, retrieve_keyword, retrieve_vector


def best_rank(items, ranking, by_db):
    """Per evidence item, the best 1-based rank of a covering chunk; None if absent."""
    out = []
    for item in items:
        ranks = [i for i, e in enumerate(ranking, start=1)
                 if evidence_covered(item, {'document_key': by_db.get(e.document_id), 'page_start': e.page_start,
                                            'page_end': e.page_end, 'text': e.text})]
        out.append(min(ranks) if ranks else None)
    return out


def main():
    from fdi.ingestion.embedding import SentenceTransformerEmbedder
    embedder = SentenceTransformerEmbedder()
    by_db = {v: k for k, v in document_ids().items()}
    questions = [q for q in json.loads((ROOT / 'evaluation/questions/s1_development.json').read_text()) if q['inputs']]
    pool = create_pool(dsn(), max_size=1)
    results = {}
    for name in ('B0', 'R1', 'R2', 'R3'):
        config = CONFIGS[name]
        for q in questions:
            query = vector_literal(embedder.embed_query(q['question']))
            with request_connection(pool, UUID(q['user_id']), UUID(q['organization_id'])) as conn:
                vector = retrieve_vector(conn, query, config.chunker, 100000)
                keyword = retrieve_keyword(conn, q['question'], config.chunker, 100000)
            row = results.setdefault(q['question_id'], {})
            if config.retrieval == 'vector':
                row[name] = best_rank(q['inputs'], vector, by_db)
            else:
                fused = reciprocal_rank_fusion([vector[:config.candidates], keyword[:config.candidates]],
                                               2 * config.candidates, config.rrf_k)
                row[name] = best_rank(q['inputs'], fused, by_db)
                row[f'{name} keyword-only'] = best_rank(q['inputs'], keyword, by_db)
    # Equal context budget: per question, B0's top-5 token total; other configurations take chunks
    # in their own rank order until that budget is spent, so larger table chunks earn no extra room.
    budget_hits = {name: 0 for name in ('B0', 'R1', 'R2', 'R3')}
    total_items = 0
    for q in questions:
        query = vector_literal(embedder.embed_query(q['question']))
        with request_connection(pool, UUID(q['user_id']), UUID(q['organization_id'])) as conn:
            rankings = {}
            for name in ('B0', 'R1', 'R2', 'R3'):
                c = CONFIGS[name]
                vector = retrieve_vector(conn, query, c.chunker, c.candidates)
                rankings[name] = vector if c.retrieval == 'vector' else reciprocal_rank_fusion(
                    [vector, retrieve_keyword(conn, q['question'], c.chunker, c.candidates)], 2 * c.candidates, c.rrf_k)
        budget = sum(embedder.token_counts([e.text for e in rankings['B0'][:5]]))
        total_items += len(q['inputs'])
        for name, ranking in rankings.items():
            chosen, used = [], 0
            for e, tokens in zip(ranking, embedder.token_counts([e.text for e in ranking])):
                if used + tokens > budget:
                    break
                chosen.append(e)
                used += tokens
            budget_hits[name] += sum(r is not None for r in best_rank(q['inputs'], chosen, by_db))
    pool.close()
    print(json.dumps(results, indent=1))
    for name, hits in budget_hits.items():
        print(f'{name} under B0 top-5 token budget: evidence items covered {hits}/{total_items}')
    for name in ('B0', 'R1', 'R2', 'R3'):
        ranks = [r for q in results.values() for r in q[name]]
        print(f"{name}: evidence items in top 5: {sum(r is not None and r <= 5 for r in ranks)}/{len(ranks)}; "
              f"in top 50: {sum(r is not None and r <= 50 for r in ranks)}/{len(ranks)}")


if __name__ == '__main__':
    main()
