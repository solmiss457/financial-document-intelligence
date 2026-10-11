"""Scoring for development/final evaluation runs. Pure functions; no database or network.

Ground truth is located by document, PDF page, row label, and value, never by chunk ID,
so the same questions score any chunker.
"""
import re
from decimal import Decimal, InvalidOperation
from statistics import median

SCALES = {'thousand': Decimal('0.001'), 'million': Decimal(1), 'billion': Decimal(1000), 'trillion': Decimal(1000000)}
NUMBER = re.compile(r'(?P<neg>[-−–])?\s*\$?\s*(?P<paren>\()?\s*\$?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<close>\))?\s*'
                    r'(?P<pct>%|percent\b)?\s*(?P<scale>thousand|million|billion|trillion)?', re.I)
NEGATIVE_WORDS = re.compile(r'\b(loss|losses|decrease[sd]?|declin\w*|fell|lower|negative|outflow|used in|purchases?|down)\b', re.I)


def compact(text):
    return ''.join((text or '').split()).lower()


def source_forms(value):
    """How a statement value appears on the page: 1,234 or (1,234) for negatives."""
    v = Decimal(value)
    body = f'{abs(v):,}' if v == v.to_integral() else f'{abs(v):,.2f}'
    return [f'({body})'] if v < 0 else [body]


def evidence_covered(item, chunk):
    """A chunk covers an evidence item when it is from the same document, spans the PDF page,
    and contains both the row label and the value as printed, so the number keeps its label."""
    if chunk['document_key'] != item['document_id']:
        return False
    if not chunk['page_start'] <= item['pdf_page'] <= chunk['page_end']:
        return False
    text = compact(chunk['text'])
    return compact(item['row_label']) in text and any(compact(f) in text for f in source_forms(item['value']))


def evidence_recall(question, chunks, k=5):
    """Best fraction of one alternative evidence set covered by the top-k chunks (None if no evidence)."""
    sets = question['alternative_evidence_sets'] or ([question['inputs']] if question['inputs'] else [])
    if not sets:
        return None, None
    top = chunks[:k]
    best = max(sum(any(evidence_covered(i, c) for c in top) for i in items) / len(items) for items in sets)
    return best, best == 1


def numbers_in(text):
    """(value, unit, negative_marked) for each number; unit is 'percent', a scale word, or None."""
    found = []
    for m in NUMBER.finditer(text or ''):
        try:
            value = Decimal(m.group('num').replace(',', ''))
        except InvalidOperation:
            continue
        negative = bool(m.group('neg') or (m.group('paren') and m.group('close')))
        unit = 'percent' if m.group('pct') else (m.group('scale') or '').lower() or None
        found.append((-value if negative else value, unit, negative))
    return found


def value_matches(text, expected, unit, tolerance):
    """Returns 'exact', 'sign_inferred' (magnitude matches and the wording signals a negative), or None.

    Values are compared in the expected unit after scale conversion; a rounded answer such as
    "$371.4 billion" does not meet a USD-million question. Tolerance never excuses unit or period."""
    expected, tol = Decimal(expected), Decimal(tolerance or '0')
    percent = unit.strip() in ('%', 'percent', 'percentage points')
    for value, found_unit, negative in numbers_in(text):
        if percent:
            if found_unit not in ('percent', None):
                continue
            candidates = [value]
        else:
            if found_unit == 'percent':
                continue
            candidates = [value * SCALES[found_unit]] if found_unit in SCALES else [value]
        for c in candidates:
            if abs(c - expected) <= tol:
                return 'exact'
            if expected < 0 and not negative and abs(c + expected) <= tol and NEGATIVE_WORDS.search(text):
                return 'sign_inferred'
    return None


def score_answer(question, response):
    state, expected_state = response['state'], question['expected_state']
    text = response.get('answer', '')
    result = {'state': state, 'state_correct': state == expected_state, 'value_match': None, 'correct': False}
    if expected_state == 'answered':
        exp = question['expected_answer']
        result['value_match'] = value_matches(text, exp['value'], exp['unit'], question['tolerance']) if state == 'answered' else None
        # Strict: only an explicit signed or exact value counts; sign_inferred is adjudicated by a person.
        result['correct'] = state == 'answered' and result['value_match'] == 'exact'
    elif expected_state == 'needs_clarification':
        pa = question['expected_clarification']['provisional_answer']
        result['value_match'] = value_matches(text, pa['value'], pa['unit'], '0')
        result['correct'] = state == 'needs_clarification' and result['value_match'] == 'exact'
    else:
        result['correct'] = state == expected_state
    return result


def rate(numerator, denominator):
    return None if denominator == 0 else numerator / denominator


def percentile(values, q):
    """Nearest-rank percentile; with few samples p95 is effectively the maximum."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * q // 100))
    return ordered[int(rank) - 1]


def summarize(rows):
    """rows: dicts with question, score, recall, complete, latency_ms, tokens."""
    answerable = [r for r in rows if r['question']['expected_state'] == 'answered']
    abstain = [r for r in rows if r['question']['expected_state'] == 'insufficient_evidence']
    clarify = [r for r in rows if r['question']['expected_state'] == 'needs_clarification']
    recalls = [r['recall'] for r in answerable if r['recall'] is not None]
    latencies = [r['latency_ms'] for r in rows]
    return {
        'questions': len(rows),
        'evidence_recall_at_5': rate(sum(recalls), len(recalls)),
        'complete_evidence_at_5': rate(sum(r['complete'] for r in answerable if r['complete'] is not None), len(recalls)),
        'answerable_accuracy': rate(sum(r['score']['correct'] for r in answerable), len(answerable)),
        'answerable_sign_inferred': sum(r['score']['value_match'] == 'sign_inferred' for r in answerable),
        'false_deferral_rate': rate(sum(r['score']['state'] != 'answered' for r in answerable), len(answerable)),
        'out_of_scope_deferral_rate': rate(sum(r['score']['correct'] for r in abstain), len(abstain)),
        'clarification_accuracy': rate(sum(r['score']['correct'] for r in clarify), len(clarify)),
        'clarification_state_rate': rate(sum(r['score']['state'] == 'needs_clarification' for r in clarify), len(clarify)),
        'answer_coverage': rate(sum(r['score']['state'] == 'answered' for r in rows), len(rows)),
        'invalid_citation_responses': sum(bool(r['invalid_citations']) for r in rows),
        'processing_errors': sum(r['score']['state'] == 'processing_error' for r in rows),
        'latency_ms_p50': median(latencies) if latencies else None,
        'latency_ms_p95_nearest_rank': percentile(latencies, 95),
        'input_tokens': sum(r['input_tokens'] for r in rows),
        'output_tokens': sum(r['output_tokens'] for r in rows),
        'denominators': {'answerable': len(answerable), 'answerable_with_evidence': len(recalls),
                         'insufficient_evidence': len(abstain), 'needs_clarification': len(clarify)},
    }
