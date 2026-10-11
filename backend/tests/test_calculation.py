"""Deterministic calculation, including the plan's required edge cases and ground-truth inputs."""
import json
from decimal import Decimal
from pathlib import Path
import pytest
from fdi.calculation import CalculationError, calculate, parse_amount, unit_key

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = json.loads((ROOT / 'evaluation/questions/s1_development.json').read_text())
M = 'USD millions'


def i(value, period, unit=M):
    return {'value': value, 'unit': unit, 'period': period}


@pytest.mark.parametrize('text,expected', [('416,161', '416161'), ('$ 416,161', '416161'), ('(21,998)', '-21998'),
                                           ('$(9,237)', '-9237'), ('−368', '-368'), ('-368', '-368'), ('6.43', '6.43')])
def test_parse_amount(text, expected):
    assert parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize('text,code', [('6.43%', 'percent_input'), ('n/a', 'unparseable_value'), ('', 'unparseable_value'),
                                       ('1.2.3', 'unparseable_value')])
def test_parse_amount_rejects(text, code):
    with pytest.raises(CalculationError) as exc:
        parse_amount(text)
    assert exc.value.code == code


def test_operations_and_half_up_rounding_at_the_end():
    growth = calculate('growth_percent', [i('416,161', 'fiscal 2025'), i('391,035', 'fiscal 2024')], 2)
    assert growth.value == Decimal('6.43') and growth.display == '6.43%'  # exact 6.4255..., the LLM said 6.42
    assert calculate('growth_percent', [i('713,163', '2026'), i('680,985', '2025')], 2).value == Decimal('4.73')
    assert calculate('difference', [i('30,592', '2024'), i('49,196', '2023')]).display == '-18,604'
    assert calculate('ratio_percent', [i('29,825', 'fiscal 2026'), i('713,163', 'fiscal 2026')], 2).value == Decimal('4.18')
    assert calculate('growth_percent', [i('105', '2024'), i('100', '2023')], 0).value == Decimal('5')
    assert calculate('growth_percent', [i('1', '2024'), i('8', '2023')], 2).value == Decimal('-87.50')


@pytest.mark.parametrize('operation,inputs,code', [
    ('growth_percent', [i('10', '2024'), i('0', '2023')], 'zero_denominator'),
    ('ratio_percent', [i('10', '2024'), i('0', '2024')], 'zero_denominator'),
    ('growth_percent', [i('10', '2024'), i('(5)', '2023')], 'negative_baseline'),
    ('difference', [i('10', '2024', 'USD millions'), i('5', '2023', 'USD thousands')], 'unit_mismatch'),
    ('difference', [i('10', '2024', 'USD millions'), i('5', '2023', 'EUR millions')], 'unit_mismatch'),
    ('ratio_percent', [i('10', '2024'), i('50', '2023')], 'period_mismatch'),
    ('growth_percent', [i('10', '2024'), i('5', '2024')], 'same_period'),
    ('multiply', [i('1', '2024'), i('2', '2023')], 'unsupported_operation'),
    ('difference', [i('1', '2024')], 'wrong_input_count'),
    ('growth_percent', [i('10', '2024'), i('5', '2023')], 'invalid_precision'),
])
def test_refuses_incomparable_or_undefined_calculations(operation, inputs, code):
    with pytest.raises(CalculationError) as exc:
        calculate(operation, inputs, 9 if code == 'invalid_precision' else None)
    assert exc.value.code == code


def test_unit_parsing():
    assert unit_key('USD millions') == ('USD', 'million')
    assert unit_key('$ in millions') == ('USD', 'million')
    assert unit_key('millions') == (None, 'million')


def test_ground_truth_inputs_reproduce_every_expected_calculation():
    """Calculation evaluation with ground-truth inputs, separate from end-to-end scoring."""
    calc = [q for q in QUESTIONS if q['formula']]
    assert len(calc) >= 8
    for q in calc:
        inputs = [{'value': x['value'], 'unit': f"{x['currency']} millions", 'period': x['period_end']} for x in q['inputs']]
        places = 2 if q['formula'] != 'difference' else None
        assert calculate(q['formula'], inputs, places).value == Decimal(q['expected_answer']['value']), q['question_id']
