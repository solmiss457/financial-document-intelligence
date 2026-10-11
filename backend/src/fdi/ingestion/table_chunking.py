"""R1 table-aware chunking from word coordinates.

Financial statements are rebuilt into visual rows ("Total revenues 371,433 364,482 302,020"),
grouped into table regions, and emitted in row groups that repeat the document, statement
title, units, and column headers. Text outside table regions is chunked exactly like B0, so
the only change from B0 is how tables are represented. Detected tables are retrieval units,
not verified financial facts.
"""
import re
from dataclasses import dataclass
from fdi.ingestion.chunking import Chunk, _spans, fixed_word_chunks
from fdi.ingestion.extract import Page

NUMERIC = re.compile(r'^\(?[-−]?\$?\d[\d,]*(\.\d+)?\)?%?$')
BLANK = {'—', '–', '-', '$', '—%'}
YEAR = re.compile(r'^(19|20)\d\d$')
DOT_LEADER = re.compile(r'^\.+$')
UNITS = re.compile(r'(in|dollars in|amounts in)\s+(millions|thousands|billions)[^).;\n]{0,60}', re.I)


def chunker_name(rows, size, overlap, max_chars=1200):
    return f'table_rows_v1:{rows}r{max_chars}c+{size}/{overlap}'


@dataclass
class Line:
    words: list
    label: str
    values: list
    page: int

    @property
    def text(self):
        return ' '.join(w.text for w in self.words)

    @property
    def is_row(self):
        return bool(self.values) and not self.is_header

    @property
    def is_header(self):
        return len(self.values) >= 2 and all(YEAR.match(v) for v in self.values)


def visual_lines(page):
    """Cluster words by vertical center, then order left to right."""
    lines = []
    for w in sorted(page.words, key=lambda w: ((w.y0 + w.y1) / 2, w.x0)):
        center, height = (w.y0 + w.y1) / 2, w.y1 - w.y0
        if lines and abs(lines[-1][0] - center) <= 0.45 * max(height, lines[-1][1]):
            lines[-1][2].append(w)
        else:
            lines.append([center, height, [w]])
    out = []
    for _, _, words in lines:
        words.sort(key=lambda w: w.x0)
        tokens = [w.text for w in words if not DOT_LEADER.match(w.text)]  # ". . . ." in row labels
        cut = len(tokens)
        while cut and (NUMERIC.match(tokens[cut - 1]) or tokens[cut - 1] in BLANK):
            cut -= 1
        values = [t for t in tokens[cut:] if t not in ('$',)]
        out.append(Line(words, ' '.join(t for t in tokens[:cut] if t != '$'), values, page.number))
    return out


def _regions(lines, min_rows=3, max_gap=2):
    """Runs of numeric rows, allowing short label-only lines (section headings) in between."""
    regions, current, gap = [], [], 0
    for i, line in enumerate(lines):
        if line.is_row or line.is_header:
            current.append(i)
            gap = 0
        elif current and gap < max_gap and len(line.text.split()) <= 12:
            current.append(i)
            gap += 1
        else:
            if sum(lines[j].is_row for j in current) >= min_rows:
                regions.append(current)
            current, gap = [], 0
    if sum(lines[j].is_row for j in current) >= min_rows:
        regions.append(current)
    # Trailing label-only lines belong to the following text, not the table.
    return [r[:max(k for k, j in enumerate(r) if lines[j].is_row) + 1] for r in regions]


def _context(lines, region, max_title=4):
    start = region[0]
    title = []
    for j in range(start - 1, -1, -1):
        if lines[j].is_row or len(title) == max_title or len(lines[j].text.split()) > 20:
            break
        title.insert(0, lines[j].text)
    header = next((lines[j] for j in region if lines[j].is_header), None)
    if header is None:
        header = next((lines[j] for j in range(start - 1, max(-1, start - 4), -1) if lines[j].is_header), None)
    nearby = ' '.join(title + ([header.text] if header else []))
    units = UNITS.search(nearby) or UNITS.search(' '.join(l.text for l in lines))
    return title, header, units.group(0).strip(' ,(') if units else None


def _row_text(line, header):
    if not line.values:
        return line.label
    label = line.label or '(unlabeled total)'
    if header and len(header.values) == len(line.values):
        return f'{label}: ' + '; '.join(f'{h} = {v}' for h, v in zip(header.values, line.values))
    return f'{label}: ' + ' | '.join(line.values)


def _groups(body, header, prefix_chars, rows, max_chars):
    """Row groups capped by row count and characters so chunks stay within the embedding limit."""
    group, used = [], prefix_chars
    for line in body:
        size = len(_row_text(line, header)) + 1
        if group and (len(group) == rows or used + size > max_chars):
            yield group
            group, used = [], prefix_chars
        group.append(line)
        used += size
    if group:
        yield group


def table_aware_chunks(pages, document_title, rows=12, size=150, overlap=30, max_chars=1200):
    chunks, outside = [], []
    for page in pages:
        lines = visual_lines(page)
        regions = _regions(lines)
        in_table = {j for r in regions for j in r}
        outside.append(Page(page.number, page.width, page.height, page.text,
                            tuple(w for j, l in enumerate(lines) if j not in in_table for w in l.words)))
        for region in regions:
            title, header, units = _context(lines, region)
            prefix = [f'{document_title} | PDF page {page.number}']
            if title:
                prefix.append(' / '.join(title))
            if units:
                prefix.append(f'Units: {units}')
            if header:
                prefix.append('Columns: ' + ' | '.join(header.values))
            body = [lines[j] for j in region if not lines[j].is_header]
            section = None
            for group in _groups(body, header, sum(len(x) + 1 for x in prefix) + 60, rows, max_chars):
                text = list(prefix)
                if section and group[0].values:
                    text.append(f'Section: {section}')
                text += [_row_text(l, header) for l in group]
                for l in group:
                    if not l.values:
                        section = l.label
                words = [w for l in group for w in l.words]
                chunks.append(Chunk(len(chunks), '\n'.join(text), page.number, page.number, _spans(words)))
    for c in fixed_word_chunks(outside, size, overlap):
        chunks.append(Chunk(len(chunks), c.text, c.page_start, c.page_end, c.spans))
    return chunks
