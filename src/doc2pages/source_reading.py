"""One input file into the canonical text of a run, with its pieces and their places.

What comes out of here is the single truth about a source for the rest of the run. The
text is produced once and never derived again, because every position a passage later
carries is a position in exactly this text.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from . import limits
from .errors import LimitError, NoReadableText, UnsupportedFileError
from .pdf_layout import (
    boilerplate_keys,
    line_boxes,
    merge_rows,
    page_reading_order,
    strip_boilerplate_text,
    strip_furniture,
)
from .text_pieces import clean, split_spans

logger = logging.getLogger("doc2pages")

# One pdfium call at a time per process, the library is not thread safe.
PDFIUM_LOCK = threading.RLock()

# What a page break looks like in the assembled text.
_PAGE_BREAK = "\n\n"

# Subtitles are in here because a transcript is a document like any other.
EXTENSIONS: tuple[str, ...] = (".pdf", ".txt", ".md", ".docx", ".pptx", ".srt", ".vtt")


@dataclass(frozen=True)
class Piece:
    """One piece of the text and where it sits, counted in the text of this source."""

    page: int
    start: int
    end: int


@dataclass(frozen=True)
class Source:
    """A read file as the rest of the run sees it."""

    name: str
    # Checksum of the original file.
    checksum: str
    text: str
    pieces: list[Piece]
    pages: int


def _checksum(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _pdf_pages(path: str) -> list[str]:
    """Every page of a PDF as cleaned text, headers and footers counted out.

    No text recognition: a page without a text layer stays empty and the caller
    refuses the file rather than guessing at a picture.
    """
    import pypdfium2 as pdfium

    page_texts: list[str] = []
    page_boxes: list[list] = []
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(path)
        try:
            for number in range(len(doc)):
                page = doc[number]
                textpage = page.get_textpage()
                page_texts.append(clean(textpage.get_text_range() or "").strip())
                page_boxes.append(line_boxes(textpage))
                textpage.close()
                page.close()
        finally:
            doc.close()

    # Counted over the whole document, a header only shows itself in the whole.
    boiler = boilerplate_keys(page_boxes, page_texts)
    out: list[str] = []
    for boxes, raw in zip(page_boxes, page_texts):
        ordered = page_reading_order(strip_furniture(boxes, boiler))
        rows = merge_rows(ordered)
        out.append("\n".join(b.text for b in rows) if rows
                   else strip_boilerplate_text(raw, boiler))
    logger.info("Source %s: %d page(s), %d header or footer line(s) removed",
                Path(path).name, len(out), len(boiler))
    return out


def _pptx_page(path: str) -> str:
    """All slides as one page, the lines that stand on most slides counted out."""
    from .extract import pptx_slide_texts

    slides = [clean(f).strip() for f in pptx_slide_texts(path)]
    boiler = boilerplate_keys([], slides)
    logger.info("Source %s: %d slide(s), %d header or footer line(s) removed",
                Path(path).name, len(slides), len(boiler))
    return "\n".join(strip_boilerplate_text(f, boiler) for f in slides if f)


def _other_pages(path: str, ext: str) -> list[str]:
    """Every other format as one single page, they carry no page numbers worth keeping."""
    from .extract import EXTRACTORS

    if ext == ".pptx":
        return [_pptx_page(path)]
    reader = EXTRACTORS.get(ext)
    if reader is None:
        raise UnsupportedFileError(f"Format {ext} is not supported")
    return [clean(reader(path) or "").strip()]


def _assemble(pages: list[str]) -> tuple[str, list[tuple[int, int, int]]]:
    """The pages as one text, plus where each page starts and ends in it.

    An empty page keeps its number but takes no room, so the page of a piece stays
    right even in a document with blank pages in the middle.
    """
    parts: list[str] = []
    bounds: list[tuple[int, int, int]] = []
    pos = 0
    for number, raw in enumerate(pages, start=1):
        # Stripped, else leading white space counts as page content.
        page = raw.strip()
        if not page:
            continue
        if parts:
            pos += len(_PAGE_BREAK)
        bounds.append((number, pos, pos + len(page)))
        parts.append(page)
        pos += len(page)
    return _PAGE_BREAK.join(parts), bounds


def _page_of(pos: int, bounds: list[tuple[int, int, int]]) -> int:
    """The page a position sits on, the page it starts on when a piece spans two."""
    for number, start, end in bounds:
        if start <= pos < end:
            return number
    return bounds[-1][0] if bounds else 1


def _pieces(text: str, bounds: list[tuple[int, int, int]]) -> list[Piece]:
    """The text cut into pieces, each one knowing its page and its place."""
    return [Piece(page=_page_of(start, bounds), start=start, end=end)
            for start, end in split_spans(text, limits.PIECE_CHARS, limits.PIECE_OVERLAP)]


def count_pages(ext: str, path: str) -> int | None:
    """Page or slide count of a file on disk, None where the format has no pages."""
    try:
        if ext == ".pdf":
            import pypdfium2 as pdfium
            with PDFIUM_LOCK:
                doc = pdfium.PdfDocument(path)
                try:
                    return len(doc)
                finally:
                    doc.close()
        if ext == ".pptx":
            from pptx import Presentation
            return len(Presentation(path).slides)
    except Exception as e:  # noqa: BLE001 - an unreadable count must not fail the file
        logger.warning("Page count of %s not readable: %s", ext, e)
    return None


def read_file(path: str | Path, name: str | None = None, *, max_pages: int = limits.MAX_SOURCE_PAGES,
              max_file_mb: float = limits.MAX_FILE_MB) -> Source:
    """One file to the canonical source record. Raises when it carries no text."""
    path = str(path)
    name = name or Path(path).name
    ext = Path(name).suffix.lower()
    if ext not in EXTENSIONS:
        raise UnsupportedFileError(
            f"{name}: format {ext or '(none)'} is not supported. Supported: {', '.join(EXTENSIONS)}")
    p = Path(path)
    if not p.is_file():
        raise UnsupportedFileError(f"{name}: file not found")
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > max_file_mb:
        raise LimitError(f"{name}: the file has {size_mb:.1f} MB, at most {max_file_mb:g} MB are allowed "
                         "(max_file_mb, --max-file-mb or DOC2PAGES_MAX_FILE_MB).")
    if p.stat().st_size == 0:
        raise UnsupportedFileError(f"{name}: the file is empty")
    pages = count_pages(ext, path)
    if pages is not None and pages > max_pages:
        raise LimitError(f"{name}: the document has {pages} pages, at most {max_pages} are allowed "
                         "(max_pages, --max-pages or DOC2PAGES_MAX_PAGES).")
    try:
        page_texts = _pdf_pages(path) if ext == ".pdf" else _other_pages(path, ext)
    except UnsupportedFileError:
        raise
    except Exception as e:  # noqa: BLE001 - a broken file is no fault of the run
        raise UnsupportedFileError(f"{name}: the file cannot be read ({e})") from e
    text, bounds = _assemble(page_texts)
    if not text.strip():
        raise NoReadableText(f"{name}: the file carries no readable text, a scan without a text layer "
                             "for instance.")
    pieces = _pieces(text, bounds)
    logger.info("Source %s: %d characters, %d piece(s)", name, len(text), len(pieces))
    return Source(name=name, checksum=_checksum(path), text=text, pieces=pieces, pages=len(page_texts))


def from_text(name: str, text: str) -> Source:
    """A text with no document behind it, it becomes the same record a file becomes."""
    whole, bounds = _assemble([clean(text or "")])
    if not whole.strip():
        raise NoReadableText(f"{name}: the text is empty")
    pieces = _pieces(whole, bounds)
    return Source(name=name, checksum=hashlib.sha256(whole.encode("utf-8")).hexdigest(),
                  text=whole, pieces=pieces, pages=1)
