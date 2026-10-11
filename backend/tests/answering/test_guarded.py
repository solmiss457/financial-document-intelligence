"""G1 evidence assessment and G2 claim verification: unit checks and the pipeline with a fake LLM."""
import json
from datetime import date
from uuid import UUID
import pytest
from fdi.answering import verification as v
from fdi.answering.b0 import CONFIGS, answer_question
from fdi.answering.llm import LLMResult
from fdi.ingestion.embedding import HashEmbedder, vector_literal
from fdi.retrieval import Evidence


def u(n): return UUID(int=n)


CONSOLIDATED = ('Example Inc. ex-2024 | PDF page 90\nEXAMPLE INC. / CONSOLIDATED STATEMENTS OF EARNINGS / (dollars in millions)\n'
                'Units: dollars in millions\nColumns: 2024 | 2023\nTotal revenues: 2024 = 371,433; 2023 = 364,482\n'
                'Net earnings (loss): 2024 = 89,561; 2023 = (21,998)')
PARENT = ('Example Inc. ex-2023 | PDF page 145\nCondensed Financial Information / (Dollars in millions) / Schedule I / Statements of Cash Flows\n'
          'Units: Dollars in millions\nColumns: 2023 | 2022\nNet cash flows from operating activities: 2023 = 7,611; 2022 = 8,462')
FISCAL = ('Apple Inc. apple-fy2025 | PDF page 32\nApple Inc. / CONSOLIDATED STATEMENTS OF OPERATIONS / (In millions) / Years ended\n'
          'September 27, September 28, September 30,\nColumns: 2025 | 2024 | 2023\nTotal net sales: 2025 = 416,161; 2024 = 391,035; 2023 = 383,285')
TEXT = 'Revenues in 2024 were $371,433 million, up from 2023.'


def ev(text, n=1):
    apple = text.startswith('Apple')
    title = 'Apple Inc. apple-fy2025' if apple else 'Example Inc. ex-2024'
    return Evidence(u(n), u(100 + n), title, 1, 1, [], text, 0.0, date(2025, 9, 27) if apple else date(2024, 12, 31))


def fact(value, label='Total revenues', period='2024', citation='E1', unit='USD millions'):
    return {'label': label, 'value': value, 'unit': unit, 'period': period, 'citation': citation}


SEGMENT = ('Example Inc. ex-2024 | PDF page 70\nManufacturing, Service and Retailing results\nUnits: dollars in millions\n'
           'Columns: 2024 | 2023\nTotal revenues: 2024 = 215,903; 2023 = 219,747')


def test_scope_classification():
    assert [v.scope_of(ev(t)) for t in (CONSOLIDATED, PARENT, FISCAL, TEXT, SEGMENT)] == \
        ['consolidated', 'parent_only', 'consolidated', 'text', 'other_table']
    assert v.scope_of(ev('Pro forma revenues in 2022 were $383,115 million.')) == 'pro_forma'


def test_consolidated_conflict_catches_same_label_from_another_table():
    pool = [ev(CONSOLIDATED), ev(SEGMENT, 2)]
    assert v.consolidated_conflict(fact('215,903'), pool)                 # segment "Total revenues" 2024
    assert not v.consolidated_conflict(fact('371,433'), pool)             # agrees with the consolidated row
    assert not v.consolidated_conflict(fact('9,999', label='Membership income'), pool)  # no consolidated row to compare


@pytest.mark.parametrize('question,evidence,flagged', [
    ('What were Example total revenues?', [CONSOLIDATED], True),                  # no period
    ('What were Example total revenues in 2024?', [CONSOLIDATED], False),         # December year end
    ('What were Example total revenues in 2024?', [CONSOLIDATED, FISCAL], False), # another company's fiscal year is ignored
    ("What were Apple's total net sales in 2024?", [FISCAL], True),               # bare year, September year end
    ("What were Apple's total net sales in fiscal 2024?", [FISCAL], False),
    ("What were Apple's latest total net sales?", [FISCAL], False),
])
def test_period_flags(question, evidence, flagged):
    assert bool(v.period_flags(question, [ev(t) for t in evidence])) is flagged


def test_requested_scope():
    assert v.requested_scope('What were total revenues in 2024?') == 'consolidated'
    assert v.requested_scope('What were segment revenues in 2024?') is None
    assert v.requested_scope('What was pro forma revenue?') is None


@pytest.mark.parametrize('figure,text,ok', [
    (fact('371,433'), CONSOLIDATED, True),
    (fact('364,482', period='2023'), CONSOLIDATED, True),
    (fact('371,433', period='2023'), CONSOLIDATED, False),                          # right row, wrong column
    (fact('371,433', label='Investment gains'), CONSOLIDATED, False),               # value under another label
    (fact('-21,998', label='Net earnings (loss)', period='2023'), CONSOLIDATED, True),  # printed as (21,998)
    (fact('372,000'), CONSOLIDATED, False),
    (fact('371,433'), TEXT, True),
    (fact('371,433', period='2022'), TEXT, False),
])
def test_verify_figure_checks_row_and_column(figure, text, ok):
    assert v.verify_figure(figure, ev(text))[0] is ok


def test_unverified_numbers():
    verified = v.as_decimals([fact('371,433'), fact('364,482')])
    assert v.unverified_numbers('Revenues were $371,433 million in 2024 vs 364,482 in 2023.', verified, None) == []
    assert v.unverified_numbers('Revenues were $89.0 billion.', verified, None) == ['$89.0 billion']
    assert v.unverified_numbers('Growth was 1.91% (371,433 vs 364,482).', verified, '1.91%') == []
    assert v.unverified_numbers('Revenue was 400,000.', verified, None) == ['400,000']
    assert v.unverified_numbers('From 2023 to 2024, revenue rose; in 2024. it was 371,433.', verified, None) == []
    assert v.unverified_numbers('Revenue was 2,024 million.', verified, None) == ['2,024']
    assert v.unverified_numbers('Revenue (fiscal 2025) was 371,433; the loss was (364,482).', verified, None) == []


# Pipeline: member 11 of organization 1 reads 101 (Example, organization-wide) and 102 (Apple, granted).
@pytest.fixture
def corpus(database):
    admin, pool = database
    emb = HashEmbedder()
    chunker = CONFIGS['G2'].chunker
    admin.execute("UPDATE fdi.documents SET title='Example Inc. ex-2024', fiscal_year_end='2024-12-31' WHERE id=%s", (u(101),))
    admin.execute("UPDATE fdi.documents SET title='Apple Inc. apple-fy2025', fiscal_year_end='2025-09-27' WHERE id=%s", (u(102),))
    for i, text in enumerate((CONSOLIDATED, PARENT, FISCAL, SEGMENT)):
        doc = u(102) if text is FISCAL else u(101)
        admin.execute('''INSERT INTO fdi.chunks (organization_id,document_id,chunker,chunk_index,page_start,page_end,
            spans,text,embedding_model,embedding) VALUES (%s,%s,%s,%s,1,1,%s,%s,'h',%s::vector)''',
            (u(1), doc, chunker, i, json.dumps([]), text, vector_literal(emb.embed_documents([text])[0])))
    return pool, emb


class FakeLLM:
    def __init__(self, make):
        self.make, self.inputs = make, []

    def generate(self, instructions, input_text, name, schema):
        self.inputs.append(input_text)
        refs = {}
        first = input_text.split('Evidence excerpts:\n\n', 1)[1]
        for block in ('\n' + first).split('\n[E')[1:]:
            ref = 'E' + block.split(']')[0]
            refs[ref] = block
        return LLMResult(self.make(refs), 'fake', 1, 1)


def ref_of(refs, needle):
    return next(r for r, block in refs.items() if needle in block)


def answered(answer, facts=(), state='answered', calculation=None):
    return {'state': state, 'answer': answer, 'citations': [f['citation'] for f in facts], 'facts': list(facts),
            'calculation': calculation}


def ask(corpus, config, make, question='What were Example total revenues in 2024?'):
    pool, emb = corpus
    llm = FakeLLM(make)
    return answer_question(pool, u(11), u(1), question, emb, llm, CONFIGS[config]), llm


def test_g1_adds_period_check_to_model_input(corpus):
    result, llm = ask(corpus, 'G1', lambda refs: answered('Which year?', state='needs_clarification'),
                      question='What were Example total revenues?')
    assert 'System checks:' in llm.inputs[0] and result['meta']['g1_flags']
    _, llm = ask(corpus, 'G1', lambda refs: answered('ok'))
    assert 'System checks:' not in llm.inputs[0]


def test_g1_rejects_parent_only_figures_for_company_question(corpus):
    make = lambda refs: answered('Operating cash flow was 7,611.', [fact('7,611', 'Net cash flows from operating activities', '2023', ref_of(refs, 'Schedule I'))])
    result, _ = ask(corpus, 'G1', make, 'What were Example net cash flows from operating activities in 2023?')
    assert result['state'] == 'insufficient_evidence' and result['meta']['g1_scope_failure'] == 'parent only'
    result, _ = ask(corpus, 'N2', make, 'What were Example net cash flows from operating activities in 2023?')
    assert result['state'] == 'answered'  # N2 has no scope check


def test_g1_allows_other_scope_when_question_asks_for_it(corpus):
    make = lambda refs: answered('Parent-only operating cash flow was 7,611.', [fact('7,611', 'Net cash flows from operating activities', '2023', ref_of(refs, 'Schedule I'))])
    result, _ = ask(corpus, 'G1', make, 'What were Example parent company only operating cash flows in 2023 (Schedule I)?')
    assert result['state'] == 'answered'


def test_g2_accepts_verified_figures_and_rejects_unverified_ones(corpus):
    good = lambda refs: answered('Total revenues were $371,433 million in 2024.', [fact('371,433', citation=ref_of(refs, 'Total revenues'))])
    assert ask(corpus, 'G2', good)[0]['state'] == 'answered'
    wrong_column = lambda refs: answered('Total revenues were $371,433 million in 2023.', [fact('371,433', period='2023', citation=ref_of(refs, 'Total revenues'))])
    result = ask(corpus, 'G2', wrong_column)[0]
    assert result['state'] == 'insufficient_evidence' and result['meta']['g2_failures'][0] == 'not_in_cited_row'
    rounded = lambda refs: answered('Total revenues were about $371.4 billion.', [fact('371,433', citation=ref_of(refs, 'Total revenues'))])
    assert ask(corpus, 'G2', rounded)[0]['meta']['g2_failures'] == ['unlisted_number:$371.4 billion']
    assert ask(corpus, 'G1', rounded)[0]['state'] == 'answered'  # G1 alone does not verify numbers


def test_g2_verifies_calculation_inputs_and_allows_computed_result(corpus):
    def make(refs):
        r = ref_of(refs, 'Total revenues')
        inputs = [fact('371,433', citation=r), fact('364,482', period='2023', citation=r)]
        return answered('Revenue grew {{result}} from 364,482 to 371,433.', calculation={'operation': 'growth_percent', 'inputs': inputs, 'decimal_places': 2})
    result = ask(corpus, 'G2', make, 'What was Example total revenue growth from 2023 to 2024?')[0]
    assert result['state'] == 'answered' and '1.91%' in result['answer']
    def bad(refs):
        r = ref_of(refs, 'Total revenues')
        inputs = [fact('371,433', citation=r), fact('300,000', period='2023', citation=r)]
        return answered('Revenue grew {{result}}.', calculation={'operation': 'growth_percent', 'inputs': inputs, 'decimal_places': 2})
    assert ask(corpus, 'G2', bad, 'What was Example total revenue growth from 2023 to 2024?')[0]['meta']['g2_failures'] == ['not_in_cited_row']


def test_g1_flags_fiscal_calendar_ambiguity_only_for_that_company(corpus):
    _, llm = ask(corpus, 'G1', lambda refs: answered('ok'), "What were Apple's total net sales in 2024?")
    assert 'fiscal year ends in September' in llm.inputs[0]
    _, llm = ask(corpus, 'G1', lambda refs: answered('ok'), 'What were Example total revenues in 2024?')
    assert 'System checks:' not in llm.inputs[0]


def test_g1_rejects_segment_figure_that_conflicts_with_consolidated_row(corpus):
    seg = lambda refs: answered('Total revenues were 215,903 in 2024.', [fact('215,903', citation=ref_of(refs, 'Manufacturing'))])
    result, _ = ask(corpus, 'G1', seg)
    assert result['state'] == 'insufficient_evidence' and result['meta']['g1_scope_failure'] == 'non-consolidated'


@pytest.mark.parametrize('title,question,match', [
    ('The Coca-Cola Company cocacola-fy2025', "What were Coca-Cola's net operating revenues in 2025?", True),
    ('JPMorgan Chase & Co. jpmorgan-2025', 'What was JPMorgan total net revenue in 2025?', True),
    ('NIKE, Inc. nike-fy2026', "What were Nike's revenues in fiscal 2026?", True),
    ('Apple Inc. apple-fy2025', "What were Walmart's total revenues?", False),
])
def test_company_matching(title, question, match):
    e = Evidence(u(1), u(2), title, 1, 1, [], 'x', 0.0)
    other = Evidence(u(3), u(4), 'Zzz Corp. zzz-2025', 1, 1, [], 'x', 0.0)
    assert (v.same_company(question, [e, other]) == [e]) is match


def test_g2_repairs_citation_when_value_is_in_another_retrieved_excerpt(corpus):
    def make(refs):
        wrong = ref_of(refs, 'Schedule I')
        return answered('Total revenues were $371,433 million in 2024.', [fact('371,433', citation=wrong)])
    result = ask(corpus, 'G2', make)[0]
    assert result['state'] == 'answered' and result['meta']['g2_repaired_citations'] == 1
    assert any('Total revenues' in c['excerpt'] for c in result['citations'])


def test_g2_accepts_answer_text_restating_computed_result_and_long_labels(corpus):
    def make(refs):
        r = ref_of(refs, 'Total revenues')
        inputs = [fact('371,433', citation=r), fact('364,482', period='2023', citation=r)]
        return answered('Total revenues increased by $6,951 million.', calculation={'operation': 'difference', 'inputs': inputs, 'decimal_places': None})
    assert ask(corpus, 'G2', make, 'How much did Example total revenues change from 2023 to 2024?')[0]['state'] == 'answered'
    long_label = lambda refs: answered('Net loss before noncontrolling interests was (21,998).',
        [fact('(21,998)', label='Net earnings (loss) before attribution to noncontrolling interests', period='2023', citation=ref_of(refs, 'Net earnings'))])
    assert ask(corpus, 'G2', long_label, 'What were Example net earnings (loss) in 2023?')[0]['state'] == 'answered'


def test_g2_ignores_non_numeric_placeholders_but_still_checks_answer_numbers(corpus):
    def make(refs):
        r = ref_of(refs, 'Total revenues')
        return answered('Which year? For 2024, total revenues were $371,433 million.',
                        [fact('371,433', citation=r), fact('not provided', period='calendar 2024', citation=r)], state='needs_clarification')
    assert ask(corpus, 'G2', make)[0]['state'] == 'needs_clarification'
    def unverified(refs):
        r = ref_of(refs, 'Total revenues')
        return answered('Which year? Calendar 2024 was $380,000 million.', [fact('not provided', citation=r)], state='needs_clarification')
    assert ask(corpus, 'G2', unverified)[0]['state'] == 'insufficient_evidence'
