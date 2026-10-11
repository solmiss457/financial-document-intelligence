"""Deterministic allowlisted calculations with Decimal (plan N2).

The LLM only chooses an operation and copies input values as printed; arithmetic, rounding,
and compatibility checks happen here. No formula text from the model is ever evaluated.
"""
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

OPERATIONS = ('difference', 'growth_percent', 'ratio_percent')
SCALES = ('thousand', 'million', 'billion', 'trillion')
CURRENCIES = {'usd': 'USD', 'us$': 'USD', '$': 'USD', 'dollar': 'USD', 'eur': 'EUR', '€': 'EUR'}


class CalculationError(Exception):
    """code is a short machine-readable reason; messages never include document text."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CalculationResult:
    operation: str
    value: Decimal
    display: str
    formula: str


def parse_amount(text):
    """'416,161', '$ (21,998)', '−368', '6.43' -> Decimal. Percent signs are rejected."""
    raw = (text or '').strip().replace('−', '-').replace('–', '-')
    if '%' in raw:
        raise CalculationError('percent_input')
    negative = '(' in raw and raw.endswith(')')
    cleaned = re.sub(r'[\s$,()]|USD|US\$', '', raw, flags=re.I)
    if negative:
        cleaned = '-' + cleaned.lstrip('-')
    if not re.fullmatch(r'-?\d+(\.\d+)?', cleaned):
        raise CalculationError('unparseable_value')
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise CalculationError('unparseable_value') from exc


def unit_key(unit):
    """(currency, scale) from free text such as 'USD millions' or '$ in millions'; None when absent."""
    text = (unit or '').lower()
    currency = next((v for k, v in CURRENCIES.items() if k in text), None)
    scale = next((s for s in SCALES if s in text), None)
    return currency, scale


def _compatible(units):
    keys = [unit_key(u) for u in units]
    currencies = {c for c, _ in keys if c}
    scales = {s for _, s in keys}
    return len(currencies) <= 1 and len(scales) == 1


def _years(period):
    return set(re.findall(r'(?:19|20)\d\d', period or ''))


def _rounded(value, places):
    if places is None:
        return value
    if not 0 <= places <= 6:
        raise CalculationError('invalid_precision')
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def calculate(operation, inputs, decimal_places=None):
    """inputs: dicts with value, unit, period. Order: first = current/numerator, second = previous/denominator."""
    if operation not in OPERATIONS:
        raise CalculationError('unsupported_operation')
    if len(inputs) != 2:
        raise CalculationError('wrong_input_count')
    a, b = (parse_amount(i['value']) for i in inputs)
    if not _compatible([i.get('unit') for i in inputs]):
        raise CalculationError('unit_mismatch')
    ya, yb = (_years(i.get('period')) for i in inputs)
    if operation == 'ratio_percent':
        if ya and yb and ya != yb:
            raise CalculationError('period_mismatch')
        if b == 0:
            raise CalculationError('zero_denominator')
        value = _rounded(a / b * 100, 2 if decimal_places is None else decimal_places)
        return CalculationResult(operation, value, f'{value}%', f'{a} / {b} × 100')
    if ya and yb and ya == yb:
        raise CalculationError('same_period')
    if operation == 'difference':
        value = _rounded(a - b, decimal_places)
        return CalculationResult(operation, value, f'{value:,}', f'{a} − {b}')
    if b == 0:
        raise CalculationError('zero_denominator')
    if b < 0:
        raise CalculationError('negative_baseline')
    value = _rounded((a - b) / b * 100, 2 if decimal_places is None else decimal_places)
    return CalculationResult(operation, value, f'{value}%', f'({a} − {b}) / {b} × 100')
