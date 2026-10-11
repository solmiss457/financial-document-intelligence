import json
from pathlib import Path
import pytest
from evaluation.tools.scoring import (evidence_covered, evidence_recall, numbers_in, percentile, rate,
                                      score_answer, summarize, value_matches)

ROOT = Path(__file__).resolve().parents[3]
QUESTIONS = {q['question_id']: q for q in json.loads((ROOT / 'evaluation/questions/s1_development.json').read_text())}
ITEM = {'document_id': 'doc-a', 'pdf_page': 90, 'row_label': 'Total revenues', 'value': '371433'}


def chunk(text, doc='doc-a', start=89, end=90):
    return {'document_key': doc, 'page_start': start, 'page_end': end, 'text': text}


@pytest.mark.parametrize('c,covered', [
    (chunk('Total\nrevenues 371,433 364,482'), True),
    (chunk('Total revenues 371,433', doc='doc-b'), False),     # wrong document
    (chunk('Total revenues 371,433', start=91, end=92), False),  # wrong page
    (chunk('Investment gains 371,433'), False),                 # number without its row label
    (chunk('Total revenues 364,482'), False),                   # label without the value
])
def test_evidence_coverage_requires_document_page_label_and_value(c, covered):
    assert evidence_covered(ITEM, c) is covered


def test_negative_values_match_parenthesized_source():
    item = dict(ITEM, row_label='Net earnings (loss)', value='-21998')
    assert evidence_covered(item, chunk('Net earnings (loss) 97,147 (21,998)'))
    assert not evidence_covered(item, chunk('Net earnings (loss) 97,147 21,998'))


def test_recall_uses_best_alternative_set_and_top_k_only():
    q = {'inputs': [ITEM], 'alternative_evidence_sets': [[ITEM, dict(ITEM, value='364482')], [dict(ITEM, pdf_page=12)]]}
    chunks = [chunk('nothing')] * 5 + [chunk('Total revenues 364,482')]
    assert evidence_recall(q, [chunk('Total revenues 371,433')] + chunks) == (0.5, False)
    assert evidence_recall(q, chunks) == (0.0, False)  # the 6th chunk is outside top 5
    assert evidence_recall({'inputs': [], 'alternative_evidence_sets': []}, chunks) == (None, None)


@pytest.mark.parametrize('text,expected,unit,tol,match', [
    ('Total revenues were $371,433 million.', '371433', 'USD million', '0', 'exact'),
    ('Total revenues were $371.433 billion.', '371433', 'USD million', '0', 'exact'),
    ('About $371.4 billion.', '371433', 'USD million', '0', None),  # rounded below requested precision
    ('Growth was 1.91%.', '1.91', '%', '0.005', 'exact'),
    ('Growth was 1.92 percent.', '1.91', '%', '0.005', None),
    ('Growth was 1.91 million.', '1.91', '%', '0.005', None),
    ('Net earnings were -$21,998 million.', '-21998', 'USD million', '0', 'exact'),
    ('Net earnings were $(21,998) million.', '-21998', 'USD million', '0', 'exact'),
    ('It reported a net loss of $21,998 million.', '-21998', 'USD million', '0', 'sign_inferred'),
    ('It reported net earnings of $21,998 million.', '-21998', 'USD million', '0', None),
    ('Revenue was 371,433 in 2024 and 364,482 in 2023.', '6951', 'USD million', '0', None),
])
def test_value_matching(text, expected, unit, tol, match):
    assert value_matches(text, expected, unit, tol) == match


def test_numbers_parse_scale_percent_and_sign():
    assert numbers_in('(1,234) and 5% and 2.5 billion') == [(-1234, None, True), (5, 'percent', False), (2.5, 'billion', False)]


def test_score_answer_by_expected_state():
    lookup, abstain, clarify = QUESTIONS['dev-01'], QUESTIONS['dev-09'], QUESTIONS['dev-11']
    assert score_answer(lookup, {'state': 'answered', 'answer': '$371,433 million'})['correct']
    assert not score_answer(lookup, {'state': 'needs_clarification', 'answer': '$371,433 million'})['correct']
    assert score_answer(abstain, {'state': 'insufficient_evidence', 'answer': ''})['correct']
    assert not score_answer(abstain, {'state': 'answered', 'answer': '$400,000 million'})['correct']
    assert score_answer(clarify, {'state': 'needs_clarification', 'answer': 'Which year? For 2024 it was $371,433 million.'})['correct']
    assert not score_answer(clarify, {'state': 'needs_clarification', 'answer': 'Which year do you mean?'})['correct']
    both = QUESTIONS['dev-28']
    assert score_answer(both, {'state': 'needs_clarification', 'answer': 'Fiscal 2025: $680,985 million; fiscal 2026: $713,163 million.'})['correct']
    assert not score_answer(both, {'state': 'needs_clarification', 'answer': 'Fiscal 2025 was $680,985 million.'})['correct']
    signed = score_answer(QUESTIONS['dev-02'], {'state': 'answered', 'answer': 'a net loss of $21,998 million'})
    assert signed['value_match'] == 'sign_inferred' and not signed['correct']


def test_rates_are_none_for_zero_denominators_and_percentile():
    assert rate(0, 0) is None and rate(1, 4) == 0.25
    assert percentile([], 95) is None and percentile([5, 1, 3], 50) == 3 and percentile(list(range(1, 13)), 95) == 12


def test_summarize_denominators():
    def row(qid, state, answer='', recall=None, complete=None):
        q = QUESTIONS[qid]
        return {'question': q, 'score': score_answer(q, {'state': state, 'answer': answer}), 'recall': recall,
                'complete': complete, 'latency_ms': 10, 'input_tokens': 1, 'output_tokens': 1, 'invalid_citations': []}
    s = summarize([row('dev-01', 'answered', '$371,433 million', 1.0, True),
                   row('dev-03', 'insufficient_evidence', '', 0.0, False),
                   row('dev-09', 'insufficient_evidence'), row('dev-11', 'answered', '$364,482 million')])
    assert (s['evidence_recall_at_5'], s['complete_evidence_at_5'], s['answerable_accuracy']) == (0.5, 0.5, 0.5)
    assert (s['false_deferral_rate'], s['out_of_scope_deferral_rate'], s['clarification_accuracy']) == (0.5, 1.0, 0.0)
    assert s['answer_coverage'] == 0.5 and s['denominators']['answerable'] == 2
