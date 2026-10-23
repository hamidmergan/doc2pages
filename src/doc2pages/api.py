"""The library: source files in, finished learning pages out."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import pipeline, schema
from .client import draw_image, make_caller, webp
from .config import Settings, resolve
from .errors import LimitError
from .log import logger
from .output import Page, write_pages
from .pipeline import NoPlan, PipelineInterrupted, RunStore
from .source_reading import Source, read_file
from .translate import LANGUAGES, other_language, translate

__all__ = ["NoPlan", "Page", "PipelineInterrupted", "make_pages", "pages_from_sources",
           "read_sources"]

# Two pictures at a time, the same as the service draws with.
_IMAGE_WORKERS = 2


def read_sources(paths: Sequence[str | Path], settings: Settings) -> list[Source]:
    """Every input file as a source record, checked against the limits of the run."""
    if not paths:
        raise LimitError("No input file was given.")
    if len(paths) > settings.max_files:
        raise LimitError(f"{len(paths)} files were given, at most {settings.max_files} are allowed "
                         "(max_files, --max-files or DOC2PAGES_MAX_FILES).")
    sources = [read_file(p, max_pages=settings.max_pages, max_file_mb=settings.max_file_mb)
               for p in paths]
    total = sum(len(q.text) for q in sources)
    if total > settings.max_chars:
        raise LimitError(f"The material has {total} characters, at most {settings.max_chars} are "
                         "allowed (max_chars, --max-chars or DOC2PAGES_MAX_CHARS).")
    return sources


def _wishes(page: dict) -> list[dict]:
    return [b for s in page["sections"] for b in s["blocks"] if b["kind"] == "image"]


def _draw(settings: Settings, draft: dict) -> dict[str, bytes]:
    """Every picture the draft names, a failed one is left out instead of standing empty."""
    wishes = _wishes(draft)
    if not wishes:
        return {}
    sizes = {pipeline.HERO_IMAGE: pipeline.HERO_SIZE}

    def one(wish: dict) -> tuple[str, bytes] | None:
        try:
            raw = draw_image(settings, wish["prompt"], sizes.get(wish["src"], pipeline.SECTION_SIZE))
        except Exception as e:  # noqa: BLE001 - a page without a picture is still a page
            logger.warning("Picture {} failed: {}", wish["src"], e)
            return None
        return wish["src"], webp(raw)

    with ThreadPoolExecutor(max_workers=_IMAGE_WORKERS) as pool:
        done = list(pool.map(one, wishes))
    return {name: data for name, data in (d for d in done if d)}


def _without_missing_pictures(draft: dict, drawn: set[str]) -> dict:
    for s in draft["sections"]:
        s["blocks"] = [b for b in s["blocks"] if b["kind"] != "image" or b["src"] in drawn]
    return draft


def _title(page: dict) -> str:
    return schema.text(schema.title_of(page), 80) or "page"


async def _one_page(settings: Settings, sources: list[Source], *,
                    should_stop: Callable[[], bool] | None,
                    on_progress: Callable[[str, int | None, int | None], None] | None,
                    today: date) -> list[Page]:
    """One group of sources to one page, plus its translation when one was asked for."""
    caller = make_caller(settings)
    store = RunStore(on_progress)
    if settings.language:
        store.save_language(LANGUAGES[settings.language]["name"])
    draft = await pipeline.run(caller, sources=sources, store=store, should_stop=should_stop,
                               instructions=settings.instructions,
                               image_style=settings.image_style)
    images = _draw(settings, draft) if settings.images else {}
    draft = _without_missing_pictures(draft, set(images))
    page = pipeline.finish(schema.clean_page(draft), today=today)
    out = [Page(data=page, title=_title(page), images=dict(images))]
    target = settings.translate_to
    if target:
        if target == page.get("lang"):
            target = other_language(page)
        second = await translate(caller, page, target)
        second = pipeline.finish(second, today=today)
        out.append(Page(data=second, title=_title(second), images=dict(images)))
    return out


async def pages_from_sources(sources: list[Source], settings: Settings, *,
                             combine: bool = False,
                             should_stop: Callable[[], bool] | None = None,
                             on_progress: Callable[[str, int | None, int | None], None] | None = None,
                             today: date | None = None) -> list[Page]:
    """The finished pages of already read sources, nothing is written to disk."""
    today = today or date.today()
    groups = [sources] if combine else [[q] for q in sources]
    pages: list[Page] = []
    for group in groups:
        pages.extend(await _one_page(settings, group, should_stop=should_stop,
                                     on_progress=on_progress, today=today))
    return pages


def make_pages(
    paths: Sequence[str | Path],
    output_dir: Optional[str | Path] = None,
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    image_base_url: Optional[str] = None,
    image_model: Optional[str] = None,
    image_api_key: Optional[str] = None,
    language: Optional[str] = None,
    translate_to: Optional[str] = None,
    images: Optional[bool] = None,
    image_style: Optional[str] = None,
    instructions: Optional[str] = None,
    combine: bool = False,
    markdown_only: bool = False,
    max_files: Optional[int] = None,
    max_file_mb: Optional[float] = None,
    max_pages: Optional[int] = None,
    max_chars: Optional[int] = None,
    concurrency: Optional[int] = None,
    timeout: Optional[float] = None,
    context_tokens: Optional[int] = None,
    on_progress: Optional[Callable[[str, int | None, int | None], None]] = None,
    today: Optional[date] = None,
) -> list[Page]:
    """Turn source files into learning pages and write them into ``output_dir``.

    Every file becomes its own page, ``combine`` makes one page out of all of them.
    Without ``output_dir`` nothing is written and the pages come back in memory only.
    """
    settings = resolve(
        base_url=base_url, model=model, api_key=api_key, image_base_url=image_base_url,
        image_model=image_model, image_api_key=image_api_key, language=language,
        translate_to=translate_to, images=images, image_style=image_style,
        instructions=instructions, max_files=max_files, max_file_mb=max_file_mb,
        max_pages=max_pages, max_chars=max_chars, concurrency=concurrency, timeout=timeout,
        context_tokens=context_tokens,
    )
    sources = read_sources(paths, settings)
    pages = asyncio.run(pages_from_sources(sources, settings, combine=combine,
                                           on_progress=on_progress, today=today))
    if output_dir is not None:
        write_pages(pages, output_dir, markdown_only=markdown_only)
    return pages
