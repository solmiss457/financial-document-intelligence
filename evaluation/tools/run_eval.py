"""Run a configuration over the evaluation questions as each question's own user.

Writes evaluation/runs/<timestamp>-<config>/ (Git-ignored): run.json (settings, versions, hashes),
results.jsonl (per question and repeat), summary.json. Calls the real LLM, so it costs money.

    .venv/bin/python -m evaluation.tools.run_eval --config R1 --repeats 3
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from importlib import metadata
from statistics import mean
from uuid import UUID
from backend.scripts.register_reports import document_ids
from evaluation.tools.scoring import evidence_recall, score_answer, summarize
from fdi.answering.b0 import CONFIGS, answer_question, prompt_for
from fdi.db.config import ROOT, dsn
from fdi.db.session import create_pool, request_connection

PACKAGES = ('openai', 'sentence-transformers', 'torch', 'transformers', 'PyMuPDF', 'psycopg')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_state():
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout
    diff = subprocess.run(['git', 'diff', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout
    untracked = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT,
                               capture_output=True, text=True).stdout.split()
    # Identifies uncommitted code used by a run without storing it.
    digest = hashlib.sha256(diff.encode() + b''.join(sha256(ROOT / f).encode() for f in sorted(untracked))).hexdigest()
    return commit, {'dirty': bool(status.strip()), 'worktree_sha256': digest if status.strip() else None}


def verify_corpus(pool, questions, manifest, ids, chunker):
    """Refuse to run unless every authorized document is ready at the manifest's version."""
    by_db = {v: k for k, v in ids.items()}
    for user, org in {(q['user_id'], q['organization_id']) for q in questions}:
        wanted = {d for q in questions if (q['user_id'], q['organization_id']) == (user, org) for d in q['authorized_document_ids']}
        with request_connection(pool, UUID(user), UUID(org)) as conn:
            rows = conn.execute('''SELECT d.id, d.sha256, d.status, count(c.id) AS chunks FROM fdi.documents d
                LEFT JOIN fdi.chunks c ON c.organization_id=d.organization_id AND c.document_id=d.id AND c.chunker=%s
                GROUP BY d.id, d.sha256, d.status''', (chunker,)).fetchall()
        found = {by_db.get(r['id']): r for r in rows}
        for doc in wanted:
            r = found.get(doc)
            if not r or r['status'] != 'ready' or r['sha256'] != manifest[doc]['sha256'] or r['chunks'] == 0:
                raise SystemExit(f'Corpus not ready for {doc}; ingest it before evaluating')
        extra = set(found) - wanted
        if extra:
            raise SystemExit(f'User can read documents outside authorized_document_ids: {sorted(map(str, extra))}')


def retrieved_chunks(pool, user, org, retrieved, by_db):
    ids = [UUID(r['chunk_id']) for r in retrieved]
    with request_connection(pool, UUID(user), UUID(org)) as conn:
        rows = {r['id']: r for r in conn.execute('SELECT id, document_id, page_start, page_end, text FROM fdi.chunks WHERE id = ANY(%s)', (ids,))}
    return [{'chunk_id': str(i), 'document_key': by_db[rows[i]['document_id']], 'page_start': rows[i]['page_start'],
             'page_end': rows[i]['page_end'], 'text': rows[i]['text']} for i in ids if i in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--questions', default='evaluation/questions/s1_development.json')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--config', choices=sorted(CONFIGS), default='B0')
    args = parser.parse_args()
    questions_path, manifest_path = ROOT / args.questions, ROOT / 'evaluation/manifests/s1_reports.json'
    questions = json.loads(questions_path.read_text())
    manifest = {d['document_id']: d for d in json.loads(manifest_path.read_text())}
    ids = document_ids()
    by_db = {v: k for k, v in ids.items()}
    config = CONFIGS[args.config]

    from fdi.answering.llm import OpenAIResponsesLLM
    from fdi.ingestion.embedding import SentenceTransformerEmbedder
    embedder = SentenceTransformerEmbedder()
    llm = OpenAIResponsesLLM(config.llm_model, config.reasoning_effort)
    pool = create_pool(dsn(), max_size=2)
    verify_corpus(pool, questions, manifest, ids, config.chunker)

    started = datetime.now(timezone.utc)
    out = ROOT / 'evaluation/runs' / f"{started.strftime('%Y%m%dT%H%M%SZ')}-{config.name}"
    out.mkdir(parents=True)
    commit, dirty = git_state()
    run = {'label': config.name, 'started_at': started.isoformat(), 'git_commit': commit, 'git_worktree': dirty,
           'repeats': args.repeats, 'config': asdict(config), 'prompt_version': prompt_for(config)[2],
           'embedding_model': embedder.name, 'questions_file': args.questions, 'questions_sha256': sha256(questions_path),
           'manifest_sha256': sha256(manifest_path), 'document_sha256': {k: v['sha256'] for k, v in manifest.items()},
           'python': sys.version.split()[0], 'platform': platform.platform(),
           'packages': {p: metadata.version(p) for p in PACKAGES}}
    (out / 'run.json').write_text(json.dumps(run, indent=2) + '\n')

    per_repeat = []
    with (out / 'results.jsonl').open('w') as stream:
        for repeat in range(1, args.repeats + 1):
            rows = []
            for q in questions:
                response = answer_question(pool, UUID(q['user_id']), UUID(q['organization_id']), q['question'],
                                           embedder, llm, config)
                chunks = retrieved_chunks(pool, q['user_id'], q['organization_id'], response['meta']['retrieved'], by_db)
                recall, complete = evidence_recall(q, chunks) if q['expected_state'] == 'answered' else (None, None)
                meta = response['meta']
                row = {'repeat': repeat, 'question_id': q['question_id'], 'question': q, 'response': response,
                       'retrieved': [{k: c[k] for k in ('chunk_id', 'document_key', 'page_start', 'page_end')} for c in chunks],
                       'score': score_answer(q, response), 'recall': recall, 'complete': complete,
                       'invalid_citations': response['invalid_citations'], 'latency_ms': meta['latency_ms'],
                       'input_tokens': meta['input_tokens'], 'output_tokens': meta['output_tokens']}
                stream.write(json.dumps(row, default=str) + '\n')
                rows.append(row)
                print(f"repeat {repeat} {q['question_id']}: expected {q['expected_state']}, got {response['state']}, "
                      f"correct={row['score']['correct']} match={row['score']['value_match']} recall={recall}")
            per_repeat.append(summarize(rows))
    pool.close()

    numeric = [k for k, v in per_repeat[0].items() if isinstance(v, (int, float)) and v is not None]
    aggregate = {}
    for key in numeric:
        values = [s[key] for s in per_repeat if s[key] is not None]
        aggregate[key] = None if not values else {'mean': mean(values), 'min': min(values), 'max': max(values)}
    summary = {'run': run, 'per_repeat': per_repeat, 'aggregate': aggregate,
               'finished_at': datetime.now(timezone.utc).isoformat()}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'Wrote {out.relative_to(ROOT)}')
    for key in numeric:
        a = aggregate[key]
        print(f'  {key}: ' + ('N/A' if a is None else f"mean {a['mean']:.3f} (min {a['min']:.3f}, max {a['max']:.3f})"))


if __name__ == '__main__':
    main()
