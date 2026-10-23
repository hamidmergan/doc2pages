"""Default values and resolution of settings.

Order: argument, then environment variable, then default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from . import limits
from .errors import ConfigError

# Placeholder, because the OpenAI library requires a value. Local servers ignore it.
PLACEHOLDER_API_KEY = "none"

ENV_PREFIX = "DOC2PAGES_"

# The languages a page is written or translated in.
LANGUAGES = ("de", "en")

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Settings:
    base_url: str
    model: str
    api_key: str
    image_base_url: str
    image_model: str
    image_api_key: str
    language: Optional[str]
    translate_to: Optional[str]
    images: bool
    image_style: str
    instructions: str
    max_files: int
    max_file_mb: float
    max_pages: int
    max_chars: int
    concurrency: int
    timeout: float
    context_tokens: int


def _env(name: str) -> Optional[str]:
    value = os.environ.get(ENV_PREFIX + name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _bool(raw: str) -> bool:
    low = raw.lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    raise ValueError(raw)


def _pick(arg, env_name: str, default, cast):
    if arg is not None:
        return arg
    raw = _env(env_name)
    if raw is None:
        return default
    try:
        return cast(raw)
    except ValueError:
        raise ConfigError(
            f"Environment variable {ENV_PREFIX}{env_name} has an invalid value: {raw!r}"
        )


def _language(value: Optional[str], name: str, flag: str) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    key = str(value).strip().lower()
    if key not in LANGUAGES:
        raise ConfigError(
            f"{name} must be one of {', '.join(LANGUAGES)}, but is {value!r} "
            f"({flag} or {ENV_PREFIX}{name.upper()})."
        )
    return key


def resolve(
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
    max_files: Optional[int] = None,
    max_file_mb: Optional[float] = None,
    max_pages: Optional[int] = None,
    max_chars: Optional[int] = None,
    concurrency: Optional[int] = None,
    timeout: Optional[float] = None,
    context_tokens: Optional[int] = None,
) -> Settings:
    base_url = _pick(base_url, "BASE_URL", None, str)
    model = _pick(model, "MODEL", None, str)
    missing = []
    if not base_url:
        missing.append("base_url (--base-url or DOC2PAGES_BASE_URL)")
    if not model:
        missing.append("model (--model or DOC2PAGES_MODEL)")
    if missing:
        raise ConfigError(
            "Missing: " + " and ".join(missing) + ". "
            "Example for Ollama: base_url http://localhost:11434/v1 and a chat model."
        )

    key = _pick(api_key, "API_KEY", None, str)
    if not key:
        key = os.environ.get("OPENAI_API_KEY") or PLACEHOLDER_API_KEY

    # The image model has its own settings, each falls back to the chat value.
    img_url = _pick(image_base_url, "IMAGE_BASE_URL", None, str) or base_url
    img_model = _pick(image_model, "IMAGE_MODEL", None, str) or model
    img_key = _pick(image_api_key, "IMAGE_API_KEY", None, str) or key

    settings = Settings(
        base_url=base_url,
        model=model,
        api_key=key,
        image_base_url=img_url,
        image_model=img_model,
        image_api_key=img_key,
        language=_language(_pick(language, "LANGUAGE", None, str), "language", "--language"),
        translate_to=_language(_pick(translate_to, "TRANSLATE_TO", None, str),
                               "translate_to", "--translate"),
        images=_pick(images, "IMAGES", False, _bool),
        image_style=" ".join(_pick(image_style, "IMAGE_STYLE", "", str).split()),
        instructions=_pick(instructions, "INSTRUCTIONS", "", str).strip(),
        max_files=_pick(max_files, "MAX_FILES", limits.MAX_FILES, int),
        max_file_mb=_pick(max_file_mb, "MAX_FILE_MB", limits.MAX_FILE_MB, float),
        max_pages=_pick(max_pages, "MAX_PAGES", limits.MAX_SOURCE_PAGES, int),
        max_chars=_pick(max_chars, "MAX_CHARS", limits.MAX_TOTAL_CHARS, int),
        concurrency=_pick(concurrency, "CONCURRENCY", limits.SUMMARY_WRITE_CONCURRENCY, int),
        timeout=_pick(timeout, "TIMEOUT", limits.SUMMARY_CALL_TIMEOUT_SECONDS, float),
        context_tokens=_pick(context_tokens, "CONTEXT_TOKENS", 0, int),
    )
    _validate(settings)
    return settings


def _validate(s: Settings) -> None:
    positive = {
        "max_files": s.max_files,
        "max_file_mb": s.max_file_mb,
        "max_pages": s.max_pages,
        "max_chars": s.max_chars,
        "concurrency": s.concurrency,
        "timeout": s.timeout,
    }
    for name, value in positive.items():
        if value <= 0:
            raise ConfigError(f"{name} must be greater than 0, but is {value}.")
    if s.context_tokens < 0:
        raise ConfigError("context_tokens must not be negative.")
    if s.context_tokens and s.context_tokens < limits.MAP_MIN_WINDOW_TOKENS:
        raise ConfigError(
            f"context_tokens is {s.context_tokens}, the pipeline needs a model with at least "
            f"{limits.MAP_MIN_WINDOW_TOKENS} tokens of context."
        )
    if len(s.image_style) > limits.IMAGE_STYLE_MAX_CHARS:
        raise ConfigError(
            f"image_style has {len(s.image_style)} characters, at most "
            f"{limits.IMAGE_STYLE_MAX_CHARS} are allowed."
        )
