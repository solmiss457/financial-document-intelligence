"""PDF text/word extraction in a separate, time-limited process."""
import multiprocessing
import resource
from dataclasses import dataclass


class PermanentIngestionError(Exception):
    """Input problems that retrying cannot fix. Messages never include document text."""


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    line: tuple  # (page, block, line) for reconstructing line breaks


@dataclass(frozen=True)
class Page:
    number: int
    width: float
    height: float
    text: str
    words: tuple


def extract_pdf(path, max_pages):
    import pymupdf
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise PermanentIngestionError('File is not a readable PDF') from exc
    with doc:
        if not doc.is_pdf:
            raise PermanentIngestionError('File is not a PDF')
        if doc.needs_pass:
            raise PermanentIngestionError('PDF is encrypted')
        if doc.page_count == 0 or doc.page_count > max_pages:
            raise PermanentIngestionError(f'Page count {doc.page_count} outside 1..{max_pages}')
        pages = []
        for i, page in enumerate(doc, start=1):
            words = tuple(Word(w[4], *w[:4], i, (i, w[5], w[6])) for w in page.get_text('words', sort=False))
            pages.append(Page(i, page.rect.width, page.rect.height, page.get_text(), words))
        return pages


def _limit_child(cpu_seconds):
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))


def extract_pdf_isolated(path, max_pages, timeout_seconds):
    """Parser crashes, hangs, or CPU exhaustion stay in the child process."""
    ctx = multiprocessing.get_context('spawn')
    with ctx.Pool(1, initializer=_limit_child, initargs=(int(timeout_seconds) + 1,)) as pool:
        result = pool.apply_async(extract_pdf, (str(path), max_pages))
        try:
            return result.get(timeout_seconds)
        except multiprocessing.TimeoutError as exc:
            pool.terminate()
            raise PermanentIngestionError(f'Extraction exceeded {timeout_seconds}s') from exc
