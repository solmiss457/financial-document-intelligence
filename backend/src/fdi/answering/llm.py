"""LLM clients returning schema-constrained JSON. Prompts and outputs are never logged."""
import json
from dataclasses import dataclass
from fdi.db.config import settings


class LLMError(Exception):
    """Messages contain only error types or statuses, never prompt or document text."""


@dataclass(frozen=True)
class LLMResult:
    data: dict
    model: str
    input_tokens: int
    output_tokens: int


class OpenAIResponsesLLM:
    def __init__(self, model, reasoning_effort='low', max_output_tokens=4000, timeout=60, max_retries=2):
        import openai
        key = settings().get('OPENAI_API_KEY')
        if not key:
            raise LLMError('OPENAI_API_KEY is not configured')
        self._openai = openai
        self.client = openai.OpenAI(api_key=key, timeout=timeout, max_retries=max_retries)
        self.model, self.reasoning_effort, self.max_output_tokens = model, reasoning_effort, max_output_tokens

    def generate(self, instructions, input_text, schema_name, schema):
        try:
            response = self.client.responses.create(
                model=self.model, instructions=instructions, input=input_text,
                text={'format': {'type': 'json_schema', 'name': schema_name, 'schema': schema, 'strict': True}},
                reasoning={'effort': self.reasoning_effort}, max_output_tokens=self.max_output_tokens,
                store=False)
        except self._openai.OpenAIError as exc:
            raise LLMError(type(exc).__name__) from exc
        if response.status != 'completed':
            raise LLMError(f'Response status {response.status}')
        try:
            data = json.loads(response.output_text)
        except ValueError as exc:
            raise LLMError('Output is not valid JSON') from exc
        usage = response.usage
        return LLMResult(data, response.model, usage.input_tokens if usage else 0, usage.output_tokens if usage else 0)
