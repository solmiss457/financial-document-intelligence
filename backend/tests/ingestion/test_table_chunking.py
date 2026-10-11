from fdi.ingestion.extract import Page, Word
from fdi.ingestion.table_chunking import table_aware_chunks, visual_lines

TITLE = 'Example Corp. example-2024'


def page(lines, number=1):
    """lines: list of token lists; each line on its own baseline, tokens laid out left to right.
    Labels and numbers deliberately come from different PyMuPDF blocks, as in real statements."""
    words = []
    for row, tokens in enumerate(lines):
        y = 50 + 14 * row
        x = 40
        for tok in tokens:
            numeric = tok[0].isdigit() or tok[0] in '($'
            block = 1 if numeric else 0
            words.append(Word(tok, x, y, x + 6 * len(tok), y + 9, number, (number, block, row)))
            x += 6 * len(tok) + 8 if not numeric else 70
    return Page(number, 612, 792, '', tuple(words))


STATEMENT = [
    ['EXAMPLE', 'CORP.'], ['CONSOLIDATED', 'STATEMENTS', 'OF', 'EARNINGS'], ['(dollars', 'in', 'millions)'],
    ['2024', '2023', '2022'],
    ['Revenues:'],
    ['Sales', '$', '100,000', '$', '90,000', '$', '80,000'],
    ['Other', 'income', '1,000', '900', '(800)'],
    ['Total', 'revenues', '101,000', '90,900', '79,200'],
    ['Net', 'earnings', '.', '.', '.', '.', '(21,998)', '5,000', '4,000'],
    ['This', 'paragraph', 'explains', 'the', 'results', 'in', 'words', 'and', 'continues', 'with', 'more', 'narrative', 'text', 'here', 'today'],
]


def test_visual_rows_join_labels_and_values_across_blocks():
    lines = visual_lines(page(STATEMENT))
    total = next(l for l in lines if l.label == 'Total revenues')
    assert total.values == ['101,000', '90,900', '79,200'] and total.is_row
    assert next(l for l in lines if l.values == ['2024', '2023', '2022']).is_header
    assert next(l for l in lines if l.label == 'Net earnings').values == ['(21,998)', '5,000', '4,000']  # dot leaders dropped


def test_table_chunk_repeats_context_and_keeps_label_with_value():
    chunks = table_aware_chunks([page(STATEMENT)], TITLE)
    table = [c for c in chunks if c.text.startswith(TITLE)]
    assert len(table) == 1
    text = table[0].text
    assert f'{TITLE} | PDF page 1' in text and 'CONSOLIDATED STATEMENTS OF EARNINGS' in text
    assert 'Units: dollars in millions' in text and 'Columns: 2024 | 2023 | 2022' in text
    assert 'Total revenues: 2024 = 101,000; 2023 = 90,900; 2022 = 79,200' in text
    assert 'Sales: 2024 = 100,000' in text and 'Net earnings: 2024 = (21,998)' in text
    assert 'paragraph' not in text and table[0].page_start == table[0].page_end == 1


def test_text_outside_tables_is_chunked_like_b0():
    chunks = table_aware_chunks([page(STATEMENT)], TITLE, size=10, overlap=0)
    text = [c for c in chunks if not c.text.startswith(TITLE)]
    joined = ' '.join(c.text for c in text)
    assert 'paragraph explains' in joined and '101,000' not in joined


def test_row_groups_repeat_header_and_section():
    rows = [['Revenues:']] + [[f'Item{i}', f'{i},000', f'{i},100'] for i in range(1, 8)]
    lines = [['STATEMENT'], ['(in', 'millions)'], ['2024', '2023']] + rows
    table = [c for c in table_aware_chunks([page(lines)], TITLE, rows=3) if c.text.startswith(TITLE)]
    assert len(table) == 3
    for c in table:
        assert 'Columns: 2024 | 2023' in c.text and 'Units: in millions' in c.text
    assert 'Section: Revenues:' in table[1].text and 'Item3: 2024 = 3,000' in table[1].text


def test_character_cap_splits_wide_tables():
    lines = [['T'], ['2024', '2023']] + [[f'Row{i}', f'{i},000', f'{i},100'] for i in range(1, 11)]
    capped = [c for c in table_aware_chunks([page(lines)], TITLE, rows=12, max_chars=200) if c.text.startswith(TITLE)]
    assert len(capped) > 1 and all(len(c.text) <= 260 for c in capped)


def test_mismatched_columns_fall_back_to_plain_values_and_short_runs_are_text():
    lines = [['2024', '2023'], ['A', '1', '2', '3'], ['B', '4', '5', '6'], ['C', '7', '8', '9']]
    [table] = [c for c in table_aware_chunks([page(lines)], TITLE) if c.text.startswith(TITLE)]
    assert 'A: 1 | 2 | 3' in table.text
    two_rows = [['A', '1'], ['B', '2']]
    assert not [c for c in table_aware_chunks([page(two_rows)], TITLE) if c.text.startswith(TITLE)]
