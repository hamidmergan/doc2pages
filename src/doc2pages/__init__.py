"""Turn source files into structured learning web pages with any OpenAI-compatible model."""

from .api import Page, make_pages, pages_from_sources, read_sources
from .config import Settings, resolve
from .errors import (
    ConfigError,
    Doc2PagesError,
    LimitError,
    ModelError,
    NoReadableText,
    UnsupportedFileError,
)
from .pipeline import NoPlan, PipelineInterrupted
from .render import page_html, page_markdown
from .source_reading import EXTENSIONS

__version__ = "0.1.0"

__all__ = [
    "ConfigError",
    "Doc2PagesError",
    "EXTENSIONS",
    "LimitError",
    "ModelError",
    "NoPlan",
    "NoReadableText",
    "Page",
    "PipelineInterrupted",
    "Settings",
    "UnsupportedFileError",
    "__version__",
    "make_pages",
    "page_html",
    "page_markdown",
    "pages_from_sources",
    "read_sources",
    "resolve",
]
