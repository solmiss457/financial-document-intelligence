import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = json.loads((ROOT / 'evaluation/questions/s1_development.json').read_text())


def test_question_contract_and_ground_truth():
    assert len(QUESTIONS) == len({q['question_id'] for q in QUESTIONS}) == 12
    manifest = {d['document_id']: d for d in json.loads((ROOT / 'evaluation/manifests/s1_reports.json').read_text())}
    for q in QUESTIONS:
        assert q['split'] == 'development'
        assert q['human_review_status'] == 'pending'
        assert q['expected_state'] in ('answered','insufficient_evidence','needs_clarification')
        assert q['reviewed_by'] and q['reviewed_at']
        if q['expected_state'] == 'answered':
            assert q['inputs'] and q['expected_answer'] and q['alternative_evidence_sets']
        for item in q['inputs']:
            doc = manifest[item['document_id']]
            assert item['document_id'] in q['authorized_document_ids']
            assert item['document_version'] == doc['version']
            assert item['sha256'] == doc['sha256']
            assert 1 <= item['pdf_page'] <= doc['page_count']
            assert item['column_label'] == item['period_end'][:4]
        if q['expected_state'] == 'answered':
            vals = [Decimal(e['value']) for e in q['inputs']]
            op = q['formula']
            if op == 'difference': value = vals[0] - vals[1]
            elif op == 'growth_percent': value = (vals[0] - vals[1]) / vals[1] * 100
            elif op == 'ratio_percent': value = vals[0] / vals[1] * 100
            else: value = vals[0]
            if op in ('growth_percent','ratio_percent'):
                value = value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            assert value == Decimal(q['expected_answer']['value'])


def test_source_values_present_on_hash_pinned_pages():
    """Presence check supplements visual review; does not prove row/column semantics."""
    import pymupdf
    manifest = json.loads((ROOT / 'evaluation/manifests/s1_reports.json').read_text())
    for d in manifest:
        path = ROOT / d['local_path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == d['sha256']
        with pymupdf.open(path) as pdf:
            for q in QUESTIONS:
                for item in q['inputs']:
                    if item['document_id'] != d['document_id']: continue
                    text = ''.join(pdf[item['pdf_page']-1].get_text().split())
                    value = Decimal(item['value'])
                    original = f'{abs(value):,}'
                    if value < 0: original = '(' + original + ')'
                    assert original in text
                    assert ''.join(item['row_label'].split()) in text
                    assert item['column_label'] in text
