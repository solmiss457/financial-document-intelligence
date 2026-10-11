"""B0 answering with a fake LLM against the real fdi_test database. No network calls."""
import json
import logging
from types import SimpleNamespace
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from fdi.answering import b0, llm as llm_module
from fdi.answering.b0 import B0Config, INSTRUCTIONS, NotMember, answer_question
from fdi.answering.llm import LLMError, LLMResult, OpenAIResponsesLLM
from fdi.api.main import Principal, authenticated_principal, create_app
from fdi.ingestion.embedding import HashEmbedder, vector_literal

CHUNKER = B0Config().chunker
QUESTION = 'SECRET_QUESTION What was total revenue in 2024?'


def u(n): return UUID(int=n)


class FakeLLM:
    def __init__(self, data=None, error=None, side_effect=None):
        self.data, self.error, self.side_effect, self.calls = data, error, side_effect, []

    def generate(self, instructions, input_text, schema_name, schema):
        self.calls.append((instructions, input_text, schema))
        if self.side_effect: self.side_effect()
        if self.error: raise self.error
        return LLMResult(self.data, 'fake-model', 100, 20)


def answer(state='answered', citations=('E1',), calculation=None):
    return {'state': state, 'answer': 'Revenue was 100 USD million.', 'citations': list(citations), 'calculation': calculation}


@pytest.fixture
def corpus(database):
    admin, pool = database
    embedder = HashEmbedder()
    for doc, org in {101: 1, 102: 1, 103: 2, 104: 2, 105: 1, 106: 1}.items():
        text = f'CANARY_EVIDENCE_{doc} total revenue 2024'
        admin.execute('''INSERT INTO fdi.chunks (organization_id,document_id,chunker,chunk_index,page_start,page_end,
            spans,text,embedding_model,embedding) VALUES (%s,%s,%s,0,3,3,%s,%s,%s,%s::vector)''',
            (u(org), u(doc), CHUNKER, json.dumps([{'page': 3, 'bbox': [1, 2, 3, 4]}]), text, embedder.name,
             vector_literal(embedder.embed_documents([text])[0])))
    return admin, pool, embedder


def ask(corpus, user, org, llm, config=B0Config(), question=QUESTION):
    _, pool, embedder = corpus
    return answer_question(pool, u(user), u(org), question, embedder, llm, config)


@pytest.mark.parametrize('user,org,docs', [(12, 1, {101}), (11, 1, {101, 102}), (13, 1, {101, 102}),
                                           (17, 2, {103}), (21, 2, {103, 104})])
def test_llm_receives_only_authorized_ready_evidence(corpus, user, org, docs):
    fake = FakeLLM(answer())
    result = ask(corpus, user, org, fake)
    instructions, input_text, _ = fake.calls[0]
    seen = {n for n in range(101, 107) if f'CANARY_EVIDENCE_{n}' in input_text}
    assert seen == docs
    assert instructions == INSTRUCTIONS and 'CANARY_EVIDENCE' not in instructions
    assert {UUID(r['document_id']).int for r in result['meta']['retrieved']} == docs
    assert result['state'] == 'answered'


def test_answer_maps_citations_to_documents_and_pages(corpus):
    result = ask(corpus, 12, 1, FakeLLM(answer()))
    [c] = result['citations']
    assert (c['ref'], UUID(c['document_id']).int, c['page_start'], c['page_end']) == ('E1', 101, 3, 3)
    assert c['spans'] == [{'page': 3, 'bbox': [1, 2, 3, 4]}] and 'CANARY_EVIDENCE_101' in c['excerpt']
    meta = result['meta']
    assert (meta['configuration'], meta['chunker'], meta['k'], meta['llm_model']) == ('B0', CHUNKER, 5, 'fake-model')
    assert (meta['input_tokens'], meta['output_tokens']) == (100, 20) and meta['prompt_version'].startswith('b0-v2-')


def test_invalid_citations_are_reported_not_resolved(corpus):
    calc = {'formula': 'a-b', 'result': '1', 'inputs': [
        {'label': 'a', 'value': '2', 'unit': 'USD', 'period': '2024', 'citation': 'E7'}]}
    result = ask(corpus, 12, 1, FakeLLM(answer(citations=['E1', 'E9', 'E1'], calculation=calc)))
    assert [c['ref'] for c in result['citations']] == ['E1']
    assert result['invalid_citations'] == ['E7', 'E9'] and result['calculation'] == calc


@pytest.mark.parametrize('user,org', [(21, 1), (14, 1), (15, 1), (16, 1)])
def test_non_members_inactive_users_rejected_before_llm(corpus, user, org):
    fake = FakeLLM(answer())
    with pytest.raises(NotMember):
        ask(corpus, user, org, fake)
    assert fake.calls == []


def test_no_authorized_evidence_abstains_without_llm(corpus):
    fake = FakeLLM(answer())
    result = ask(corpus, 12, 1, fake, B0Config(chunker='unused-chunker'))
    assert result['state'] == 'insufficient_evidence' and result['citations'] == [] and fake.calls == []


@pytest.mark.parametrize('fake', [FakeLLM(error=LLMError('APIConnectionError')),
                                  FakeLLM({'state': 'maybe', 'answer': 'x', 'citations': [], 'calculation': None}),
                                  FakeLLM(['not', 'an', 'object'])])
def test_llm_failures_become_processing_error(corpus, fake):
    result = ask(corpus, 12, 1, fake)
    assert result['state'] == 'processing_error' and result['citations'] == []
    assert 'CANARY' not in json.dumps(result['answer'])


@pytest.mark.parametrize('revoke', ['grant', 'deleting', 'membership'])
def test_access_revoked_during_generation_withholds_answer(corpus, revoke):
    admin = corpus[0]
    sql = {'grant': ('DELETE FROM fdi.document_grants WHERE document_id=%s', (u(102),)),
           'deleting': ("UPDATE fdi.documents SET status='deleting' WHERE id=%s", (u(102),)),
           'membership': ('UPDATE fdi.memberships SET active=false WHERE user_id=%s', (u(11),))}[revoke]
    result = ask(corpus, 11, 1, FakeLLM(answer(citations=['E1', 'E2']), side_effect=lambda: admin.execute(*sql)))
    assert result['state'] == 'insufficient_evidence' and result['meta'].get('withheld')
    assert result['citations'] == [] and 'Revenue' not in result['answer']


@pytest.mark.parametrize('question', ['', '   ', 'x' * 1001])
def test_question_length_validated(corpus, question):
    with pytest.raises(ValueError):
        ask(corpus, 12, 1, FakeLLM(answer()), question=question)


def test_logs_exclude_question_and_document_text(corpus, caplog):
    caplog.set_level(logging.DEBUG)
    ask(corpus, 11, 1, FakeLLM(answer()))
    ask(corpus, 11, 1, FakeLLM(error=LLMError('RateLimitError')))
    assert 'SECRET_QUESTION' not in caplog.text and 'CANARY_EVIDENCE' not in caplog.text
    assert 'answered' in caplog.text


def api(corpus, llm, user=None):
    _, pool, embedder = corpus
    app = create_app(pool, embedder=embedder, llm=llm)
    if user is not None:
        app.dependency_overrides[authenticated_principal] = lambda: Principal(u(user))
    return TestClient(app)


def test_question_endpoint(corpus):
    with api(corpus, FakeLLM(answer())) as client:
        assert client.post(f'/organizations/{u(1)}/questions', json={'question': QUESTION},
                           headers={'X-User-ID': str(u(12))}).status_code == 401
    with api(corpus, FakeLLM(answer()), user=12) as client:
        ok = client.post(f'/organizations/{u(1)}/questions', json={'question': QUESTION})
        assert ok.status_code == 200 and ok.json()['state'] == 'answered'
        assert 'CANARY_EVIDENCE_10' + '3' not in ok.text and 'CANARY_EVIDENCE_102' not in ok.text
        assert client.post(f'/organizations/{u(2)}/questions', json={'question': QUESTION}).status_code == 404
        assert client.post(f'/organizations/{u(1)}/questions', json={'question': ''}).status_code == 422
        assert client.post(f'/organizations/{u(1)}/questions', json={'question': '   '}).status_code == 422


def test_question_endpoint_without_llm_key_is_503(corpus, monkeypatch):
    monkeypatch.setattr(llm_module, 'settings', lambda: {})
    monkeypatch.setitem(__import__('sys').modules, 'openai', SimpleNamespace(OpenAI=None, OpenAIError=Exception))
    with api(corpus, None, user=12) as client:
        assert client.post(f'/organizations/{u(1)}/questions', json={'question': QUESTION}).status_code == 503


class FakeResponses:
    def __init__(self, response=None, error=None): self.response, self.error, self.kwargs = response, error, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error: raise self.error
        return self.response


def openai_llm(monkeypatch, responses):
    monkeypatch.setattr(llm_module, 'settings', lambda: {'OPENAI_API_KEY': 'test-not-a-key'})
    client = OpenAIResponsesLLM('model-x')
    client.client = SimpleNamespace(responses=responses)
    return client


def test_openai_client_requests_strict_schema_and_no_storage(monkeypatch):
    response = SimpleNamespace(status='completed', output_text=json.dumps(answer()), model='model-x-2026',
                               usage=SimpleNamespace(input_tokens=7, output_tokens=3))
    responses = FakeResponses(response)
    result = openai_llm(monkeypatch, responses).generate('inst', 'input', 'financial_answer', b0.SCHEMA)
    assert result == LLMResult(answer(), 'model-x-2026', 7, 3)
    fmt = responses.kwargs['text']['format']
    assert fmt['strict'] is True and fmt['type'] == 'json_schema' and responses.kwargs['store'] is False
    assert responses.kwargs['instructions'] == 'inst' and responses.kwargs['input'] == 'input'


@pytest.mark.parametrize('case', ['api_error', 'incomplete', 'bad_json'])
def test_openai_client_errors_are_sanitized(monkeypatch, case):
    import openai
    import httpx2 as httpx
    request = httpx.Request('POST', 'https://example.invalid')
    responses = {
        'api_error': FakeResponses(error=openai.APIConnectionError(message='CANARY detail', request=request)),
        'incomplete': FakeResponses(SimpleNamespace(status='incomplete', output_text='', model='m', usage=None)),
        'bad_json': FakeResponses(SimpleNamespace(status='completed', output_text='CANARY{', model='m', usage=None)),
    }[case]
    with pytest.raises(LLMError) as exc:
        openai_llm(monkeypatch, responses).generate('i', 'x', 'n', {})
    assert 'CANARY' not in str(exc.value)
