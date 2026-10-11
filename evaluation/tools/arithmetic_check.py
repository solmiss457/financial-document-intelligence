"""Arithmetic on identical ground-truth inputs: LLM vs fdi.calculation, without retrieval.

Separates calculation errors from retrieval and extraction errors (plan section 7). Each
calculation question's reviewed inputs are given to the same model used for answers.

    .venv/bin/python -m evaluation.tools.arithmetic_check --repeats 5
"""
import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from evaluation.tools.scoring import value_matches
from fdi.answering.b0 import CONFIGS
from fdi.calculation import calculate
from fdi.db.config import ROOT

INSTRUCTIONS = ('Compute the answer to the question using only the inputs given. '
                'Return the numeric result in the unit and rounding the question asks for.')
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['result'],
          'properties': {'result': {'type': 'string'}}}


def prompt(q):
    lines = [f"- {i['row_label']} ({i['period_end']}): {Decimal(i['value']):,} {i['currency']} millions" for i in q['inputs']]
    return f"Question: {q['question']}\nInputs:\n" + '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    from fdi.answering.llm import OpenAIResponsesLLM
    config = CONFIGS['R3']
    llm = OpenAIResponsesLLM(config.llm_model, config.reasoning_effort)
    questions = [q for q in json.loads((ROOT / 'evaluation/questions/s1_development.json').read_text()) if q['formula']]
    rows = []
    for q in questions:
        exp = q['expected_answer']
        inputs = [{'value': i['value'], 'unit': f"{i['currency']} millions", 'period': i['period_end']} for i in q['inputs']]
        decimal = calculate(q['formula'], inputs, None if q['formula'] == 'difference' else 2)
        decimal_ok = value_matches(decimal.display + ('' if exp['unit'] == 'percent' else ' million'),
                                   exp['value'], exp['unit'], q['tolerance']) == 'exact'
        for repeat in range(1, args.repeats + 1):
            out = llm.generate(INSTRUCTIONS, prompt(q), 'arithmetic', SCHEMA)
            text = out.data['result']
            llm_ok = value_matches(text if exp['unit'] == 'percent' else f'{text} million', exp['value'], exp['unit'], q['tolerance']) == 'exact'
            rows.append({'question_id': q['question_id'], 'repeat': repeat, 'formula': q['formula'], 'expected': exp['value'],
                         'llm_result': text, 'llm_correct': llm_ok, 'decimal_result': decimal.display, 'decimal_correct': decimal_ok})
            print(f"{q['question_id']} r{repeat} {q['formula']}: expected {exp['value']} llm {text!r} {'OK' if llm_ok else 'WRONG'} | decimal {decimal.display}")
    out_dir = ROOT / 'evaluation/runs' / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-arithmetic"
    out_dir.mkdir(parents=True)
    summary = {'model': config.llm_model, 'reasoning_effort': config.reasoning_effort, 'repeats': args.repeats,
               'questions': [q['question_id'] for q in questions],
               'llm_correct': sum(r['llm_correct'] for r in rows), 'decimal_correct': sum(r['decimal_correct'] for r in rows),
               'total': len(rows), 'rows': rows}
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f"LLM {summary['llm_correct']}/{len(rows)} correct; Decimal {summary['decimal_correct']}/{len(rows)}; wrote {out_dir.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
