"""G1 evidence assessment and G2 claim verification, all in code.

G1, before generation: flag questions whose period is ambiguous (no year, or a bare year for a
company whose fiscal year does not end in December). After generation: figures for a question
that does not ask for a segment, parent-only, or pro forma view must come from consolidated
statement tables.
G2, after generation: every stated figure must appear in its cited excerpt on a row matching
its label and in the column for its period, and every number in the answer text must be one of
those verified figures or the computed result.
"""
import re
from fdi.calculation import CalculationError, parse_amount

YEAR = re.compile(r'\b(19|20)\d\d\b')
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December')
PERIOD_END = re.compile(r'\b(' + '|'.join(MONTHS) + r')\s+\d{1,2},?\s*(?:(19|20)\d\d)?')
EXPLICIT_PERIOD = re.compile(r'\b(fiscal|calendar|year ended|years ended|year ending|quarter|ended)\b', re.I)
OTHER_SCOPE = re.compile(r'\b(segment|parent[- ]company|parent only|schedule i|condensed financial|pro forma|subsidiar\w*|business unit)\b', re.I)
PARENT_ONLY = re.compile(r'condensed financial information|schedule i\b|parent company', re.I)
STOP = {'the', 'of', 'and', 'in', 'for', 'to', 'a', 'from', 'by', 'net', 'total', 'usd', 'million', 'millions'}


def is_table_chunk(evidence):
    return ' | PDF page ' in evidence.text.split('\n', 1)[0]


def table_title(evidence):
    lines = evidence.text.split('\n')
    return lines[1] if is_table_chunk(evidence) and len(lines) > 1 else ''


def scope_of(evidence):
    if not is_table_chunk(evidence):
        return 'pro_forma' if re.search(r'pro forma', evidence.text, re.I) else 'text'
    title = table_title(evidence)
    if PARENT_ONLY.search(title):
        return 'parent_only'
    if re.search(r'pro forma', title, re.I):
        return 'pro_forma'
    return 'consolidated' if re.search(r'\bconsolidated\b', title, re.I) else 'other_table'


def fiscal_year_end_month(evidence):
    """Fiscal year-end month recorded on the evidence documents (None when not recorded)."""
    months = {e.fiscal_year_end.month for e in evidence if getattr(e, 'fiscal_year_end', None)}
    non_december = sorted(m for m in months if m != 12)
    if non_december:
        return MONTHS[non_december[0] - 1]
    return 'December' if months else None


NAME_STOP = {'the', 'inc', 'co', 'corp', 'company', 'and', 'group', 'holdings', 'plc', 'ltd'}


def company_words(title):
    """Distinctive words of the company name: the title without its trailing document id."""
    name = title.rsplit(' ', 1)[0] if ' ' in title else title
    return {w for w in re.findall(r'[a-z]+', name.lower()) if w not in NAME_STOP and len(w) > 1}


def same_company(question, evidence):
    """Evidence from documents whose company name appears in the question; all evidence when none
    matches (hybrid retrieval may return other companies' tables)."""
    words = set(re.findall(r'[a-z]+', question.lower()))
    own = [e for e in evidence if company_words(e.title) & words]
    return own or list(evidence)


def period_flags(question, evidence):
    """G1 pre-generation checks. Returns human-readable reasons passed to the model."""
    flags = []
    if re.search(r'\b(latest|most recent)\b', question, re.I):
        return flags
    if not YEAR.search(question):
        flags.append('The question does not state a fiscal period.')
    elif not EXPLICIT_PERIOD.search(question):
        month = fiscal_year_end_month(same_company(question, evidence))
        if month and month != 'December':
            flags.append(f'The company\'s fiscal year ends in {month}, and the question gives a year without saying '
                         'fiscal or calendar year.')
    return flags


def requested_scope(question):
    return None if OTHER_SCOPE.search(question) else 'consolidated'


def _words(text):
    return {w for w in re.findall(r'[a-z]+', text.lower()) if w not in STOP}


def _same_amount(printed, value):
    try:
        return parse_amount(printed) == value
    except CalculationError:
        return False


def table_rows(evidence):
    """(row label, year or None, printed value) for each cell of an R1 table excerpt."""
    rows = []
    if not is_table_chunk(evidence):
        return rows
    for line in evidence.text.split('\n'):
        if ':' not in line:
            continue
        label, cells = line.split(':', 1)
        pairs = re.findall(r'((?:19|20)\d\d)\s*=\s*([^;]+)', cells)
        rows += [(label, y, p.strip()) for y, p in pairs] or [(label, None, p.strip()) for p in cells.split('|')]
    return rows


def consolidated_conflict(figure, evidence_pool):
    """True when a consolidated statement in the pool shows the same row label and year with another value."""
    try:
        value = parse_amount(figure['value'])
    except CalculationError:
        return False
    years = set(re.findall(r'(?:19|20)\d\d', figure.get('period') or ''))
    label = ' '.join(sorted(_words(figure.get('label') or '')))
    for e in evidence_pool:
        if scope_of(e) != 'consolidated':
            continue
        for row_label, year, printed in table_rows(e):
            if year in years and ' '.join(sorted(_words(row_label))) == label and not _same_amount(printed, value):
                try:
                    parse_amount(printed)
                except CalculationError:
                    continue
                return True
    return False


def verify_figure(figure, evidence):
    """G2: (ok, reason). Table excerpts: a row whose label shares words with the figure's label has
    the value in the column for the figure's year. Text excerpts: value and year both present."""
    try:
        value = parse_amount(figure['value'])
    except CalculationError:
        return False, 'unparseable_value'
    years = set(re.findall(r'(?:19|20)\d\d', figure.get('period') or ''))
    if is_table_chunk(evidence):
        label_words = _words(figure.get('label') or '')
        for line in evidence.text.split('\n'):
            if ':' not in line:
                continue
            row_label, cells = line.split(':', 1)
            pairs = re.findall(r'((?:19|20)\d\d)\s*=\s*([^;]+)', cells)
            values = [(y, v.strip()) for y, v in pairs] or [(None, v.strip()) for v in cells.split('|')]
            for year, printed in values:
                if not _same_amount(printed, value):
                    continue
                if years and year and year not in years:
                    continue
                row_words = _words(row_label)
                # Overlap relative to the shorter label: "Net earnings (loss)" matches a longer paraphrase.
                if not label_words or not row_words or len(label_words & row_words) / min(len(label_words), len(row_words)) >= 0.5:
                    return True, None
        return False, 'not_in_cited_row'
    text = evidence.text.replace(',', '')
    if not any(_same_amount(m, value) for m in re.findall(r'\(?-?\$?\s*\d[\d,]*(?:\.\d+)?\)?', evidence.text)):
        return False, 'value_not_in_excerpt'
    if years and not any(y in text for y in years):
        return False, 'period_not_in_excerpt'
    return True, None


def answer_numbers(answer):
    """Numbers stated in the answer, excluding bare years and small counts."""
    out = []
    for m in re.finditer(r'\(?-?\$?\s*\d[\d,]*(?:\.\d+)?\)?\s*%?(?:\s*(?:billion|thousand|trillion))?', answer):
        token = m.group(0).strip().rstrip(',.;:')  # sentence punctuation, e.g. "from 2023 to 2024,"
        if token.endswith(')') and '(' not in token:
            token = token[:-1]  # "(fiscal 2025)" closes a parenthetical, not a negative number
        digits = re.sub(r'[^\d.]', '', token)
        if not digits or YEAR.fullmatch(token.lstrip('$(')) or (re.fullmatch(r'\d{1,2}', digits) and '%' not in token):
            continue
        out.append(token)
    return out


def unverified_numbers(answer, verified_values, computed):
    """Answer numbers that are neither a verified figure nor the computed result."""
    allowed = set(verified_values)
    if computed:
        first = re.search(r'-?[\d,]+(?:\.\d+)?', computed)
        if first:
            allowed.add(parse_amount(first.group(0)))
    missing = []
    for token in answer_numbers(answer):
        if re.search(r'billion|thousand|trillion', token, re.I):
            missing.append(token)  # converted or rounded forms cannot be checked against printed values
            continue
        try:
            number = parse_amount(token.replace('%', ''))
        except CalculationError:
            continue
        if not any(number == v or number == -v for v in allowed):
            missing.append(token)
    return missing


def as_decimals(figures):
    out = []
    for f in figures:
        try:
            out.append(parse_amount(f['value']))
        except CalculationError:
            pass
    return out

