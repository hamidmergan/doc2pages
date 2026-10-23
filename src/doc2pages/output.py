"""A finished page on disk: one folder per page, plus an overview that lists them all."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import schema
from .render import overview_html, page_html, page_markdown

INDEX_FILE = "index.html"
MARKDOWN_FILE = "page.md"
DATA_FILE = "page.json"

_SLUG_KEEP = re.compile(r"[^a-z0-9]+")
_UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"}


def slug(text: str, fallback: str = "page") -> str:
    """A short folder name out of a title, letters, digits and dashes only."""
    for sign, plain in _UMLAUTS.items():
        text = text.replace(sign, plain)
    name = _SLUG_KEEP.sub("-", text.casefold()).strip("-")[:60].strip("-")
    return name or fallback


@dataclass
class Page:
    """One finished page: its data, its pictures and where it was written."""

    data: dict
    title: str = ""
    images: dict[str, bytes] = field(default_factory=dict)
    folder: Path | None = None

    @property
    def markdown(self) -> str:
        return page_markdown(self.data)

    @property
    def html(self) -> str:
        return page_html(self.data, title=self.title)


def write_page(page: Page, folder: Path, *, markdown_only: bool = False) -> Path:
    """One page into its own folder, the pictures as files next to the page."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / MARKDOWN_FILE).write_text(page.markdown, encoding="utf-8")
    (folder / DATA_FILE).write_text(json.dumps(page.data, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    if not markdown_only:
        for name, data in page.images.items():
            (folder / name).write_bytes(data)
        (folder / INDEX_FILE).write_text(page.html, encoding="utf-8")
    page.folder = folder
    return folder


def _entry(page: Page, folder_name: str) -> dict:
    view = schema.for_viewers(page.data)
    lead = ""
    for s in view["sections"]:
        if s.get("hero") and s.get("lead"):
            lead = s["lead"]
            break
    return {"folder": folder_name, "title": page.title or schema.title_of(view) or folder_name,
            "lead": lead, "image": schema.first_image(view)}


def write_pages(pages: list[Page], out_dir: str | Path, *,
                markdown_only: bool = False) -> list[Path]:
    """Every page into ``out_dir``, with an ``index.html`` that lists them."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    taken: set[str] = set()
    entries: list[dict] = []
    folders: list[Path] = []
    for i, page in enumerate(pages, 1):
        name = slug(page.title or schema.title_of(page.data), f"page-{i}")
        while name in taken:
            name = f"{name}-{i}"
        taken.add(name)
        folders.append(write_page(page, out / name, markdown_only=markdown_only))
        entries.append(_entry(page, name))
    if not markdown_only:
        locale = (pages[0].data.get("lang") if pages else None) or "en"
        (out / INDEX_FILE).write_text(overview_html(entries, locale=locale), encoding="utf-8")
    return folders
