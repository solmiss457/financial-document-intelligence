"""B0 fixed-size chunking: word windows over the whole document, ignoring layout."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    page_start: int
    page_end: int
    spans: tuple  # ({'page': n, 'bbox': [x0, y0, x1, y1]}, ...)


def chunker_name(size, overlap):
    return f'fixed_words_v1:{size}/{overlap}'


def _text(words):
    parts, previous = [], None
    for w in words:
        if previous is not None:
            parts.append(' ' if w.line == previous else '\n')
        parts.append(w.text)
        previous = w.line
    return ''.join(parts)


def _spans(words):
    boxes = {}
    for w in words:
        b = boxes.setdefault(w.page, [w.x0, w.y0, w.x1, w.y1])
        b[:] = [min(b[0], w.x0), min(b[1], w.y0), max(b[2], w.x1), max(b[3], w.y1)]
    return tuple({'page': p, 'bbox': [round(v, 2) for v in b]} for p, b in sorted(boxes.items()))


def fixed_word_chunks(pages, size, overlap):
    if not 0 <= overlap < size:
        raise ValueError('Require 0 <= overlap < size')
    words = [w for page in pages for w in page.words]
    chunks, step = [], size - overlap
    for start in range(0, len(words), step):
        window = words[start:start + size]
        chunks.append(Chunk(len(chunks), _text(window), window[0].page, window[-1].page, _spans(window)))
        if start + size >= len(words):
            break
    return chunks
