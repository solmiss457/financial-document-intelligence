import pytest
from fdi.ingestion.chunking import chunker_name, fixed_word_chunks
from fdi.ingestion.extract import Page, Word


def pages(per_page, count=2, per_line=5):
    out = []
    for p in range(1, count + 1):
        words = tuple(Word(f'p{p}w{i}', i, 10 * (i // per_line), i + 1, 10 * (i // per_line) + 8, p, (p, 0, i // per_line))
                      for i in range(per_page))
        out.append(Page(p, 612, 792, '', words))
    return out


def test_windows_overlap_and_cover_every_word():
    chunks = fixed_word_chunks(pages(10), size=8, overlap=3)
    words = [c.text.split() for c in chunks]
    assert [len(w) for w in words] == [8, 8, 8, 5]
    assert words[0][-3:] == words[1][:3]
    assert {w for ws in words for w in ws} == {f'p{p}w{i}' for p in (1, 2) for i in range(10)}
    assert [c.index for c in chunks] == [0, 1, 2, 3]


def test_page_range_spans_and_line_breaks():
    chunk = fixed_word_chunks(pages(10), size=12, overlap=0)[0]
    assert (chunk.page_start, chunk.page_end) == (1, 2)
    assert [s['page'] for s in chunk.spans] == [1, 2]
    assert chunk.spans[0]['bbox'] == [0, 0, 10, 18]
    assert chunk.text.split('\n')[0] == 'p1w0 p1w1 p1w2 p1w3 p1w4'


def test_exact_fit_has_no_trailing_duplicate_and_empty_input():
    assert len(fixed_word_chunks(pages(4, count=1), size=4, overlap=1)) == 1
    assert fixed_word_chunks([Page(1, 1, 1, '', ())], size=4, overlap=1) == []


@pytest.mark.parametrize('size,overlap', [(5, 5), (5, -1), (0, 0)])
def test_invalid_parameters(size, overlap):
    with pytest.raises(ValueError):
        fixed_word_chunks(pages(3), size, overlap)


def test_chunker_name_records_parameters():
    assert chunker_name(150, 30) == 'fixed_words_v1:150/30'
