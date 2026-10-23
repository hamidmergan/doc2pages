"""The one door every model call goes through: chat calls, picture calls and their errors."""

from __future__ import annotations

import base64
import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from . import limits
from .config import Settings
from .errors import ModelError

logger = logging.getLogger("doc2pages")

# Keys the pipeline passes along for its own bookkeeping, no server knows them.
_OWN_KEYS = ("name", "tags", "session_id")


def is_transient_error(e: BaseException) -> bool:
    """Transient upstream failures worth retrying: 5xx, 429, timeouts, connection errors."""
    status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
    if isinstance(status, int) and (500 <= status < 600 or status == 429):
        return True
    msg = str(e).lower()
    return any(kw in msg for kw in (
        "internal server error", "bad gateway", "service unavailable",
        "gateway timeout", "timeout", "connection", "temporarily",
        "rate limit", "429",
    ))


def overloaded(e: BaseException) -> bool:
    """A timeout, a refused connection, a 429 or a 5xx: the server, not the request."""
    from openai import APIConnectionError

    return isinstance(e, (APIConnectionError, TimeoutError)) or is_transient_error(e)


# Answers that stay the same however often the run asks again.
_REFUSAL_STATUSES = frozenset({400, 401, 403, 404})
_REFUSAL_TEXT = re.compile(r"(?:error code|client error)[: ']+(40[0134])\b")


def _status_of(e: BaseException) -> int | None:
    code = getattr(e, "status_code", None)
    if code is None:
        code = getattr(getattr(e, "response", None), "status_code", None)
    return code if isinstance(code, int) else None


def is_provider_refusal(e: BaseException | str) -> bool:
    """True when the server turned the call down for good: a wrong key, a missing model or a rejected request."""
    if isinstance(e, str):
        return bool(_REFUSAL_TEXT.search(e.lower()))
    seen: set[int] = set()
    cur: BaseException | None = e
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if _status_of(cur) in _REFUSAL_STATUSES or _REFUSAL_TEXT.search(str(cur).lower()):
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def _rejects_json_mode(exc: BaseException) -> bool:
    """True when the server explicitly rejected response_format."""
    if _status_of(exc) != 400:
        return False
    text = str(exc).lower()
    return "response_format" in text or "json" in text


@dataclass
class Caller:
    """Every chat call of one run, with the timeout in one place."""

    client: Any
    model: str
    # The window of this model, 0 when it is not known.
    window_tokens: int = 0
    timeout: float = limits.SUMMARY_CALL_TIMEOUT_SECONDS
    # How many calls of this run may be on their way at the same time.
    at_once: int = limits.SUMMARY_WRITE_CONCURRENCY
    # Probed once per run instead of again on every call.
    json_mode: bool = True
    calls: list = field(default_factory=list)

    async def create(self, **kwargs):
        name = kwargs.get("name") or ""
        for k in _OWN_KEYS:
            kwargs.pop(k, None)
        if not self.json_mode:
            kwargs.pop("response_format", None)
        self.calls.append(name)
        try:
            return await self.client.chat.completions.create(
                model=self.model, timeout=self.timeout, **kwargs)
        except Exception as exc:
            if "response_format" not in kwargs or not _rejects_json_mode(exc):
                raise
            logger.warning("The server rejected the JSON mode, this run asks without it: %s", exc)
            self.json_mode = False
            kwargs.pop("response_format", None)
            return await self.client.chat.completions.create(
                model=self.model, timeout=self.timeout, **kwargs)


def make_caller(settings: Settings) -> Caller:
    from openai import AsyncOpenAI

    # The pipeline retries on its own, so one attempt is the only way the limit holds.
    client = AsyncOpenAI(base_url=settings.base_url, api_key=settings.api_key,
                         timeout=settings.timeout, max_retries=0)
    return Caller(client=client, model=settings.model, window_tokens=settings.context_tokens,
                  timeout=settings.timeout, at_once=settings.concurrency)


# --- Pictures -------------------------------------------------------------------------------

# The size a server gets when it refuses ours.
_FALLBACK_SIZE = "1024x1024"


# Newer releases of the openai package bring the HTTP client as httpx2, older ones as httpx.
# httpx2 comes first, because that is the one an install of this package pulls in.
_HTTP_LIBRARIES = ("httpx2", "httpx")


def _http_library():
    """The HTTP library this installation has, or None for the standard library."""
    for name in _HTTP_LIBRARIES:
        try:
            return __import__(name)
        except ImportError:
            continue
    return None


def _fetch(url: str, timeout: float) -> bytes:
    """The bytes behind a URL, with whichever HTTP library is installed.

    All three ways behave the same: they follow a redirect, which image URLs of S3 and
    most content networks need, and they raise on a 4xx or 5xx answer instead of handing
    an error page on as if it were a picture.
    """
    library = _http_library()
    if library is None:
        from urllib.request import urlopen

        # urlopen follows redirects and raises HTTPError on an error status.
        with urlopen(url, timeout=timeout) as answer:  # noqa: S310 - the URL comes from the server
            return answer.read()
    answer = library.get(url, timeout=timeout, follow_redirects=True)
    answer.raise_for_status()
    return answer.content


def draw_image(settings: Settings, prompt: str, size: str) -> bytes:
    """One picture as image bytes, the square size as a fallback when the server refuses ours."""
    from openai import BadRequestError, OpenAI

    client = OpenAI(base_url=settings.image_base_url, api_key=settings.image_api_key,
                    timeout=max(settings.timeout, 300.0), max_retries=1)
    answer = None
    for wanted in (size, _FALLBACK_SIZE):
        try:
            answer = client.images.generate(model=settings.image_model, prompt=prompt, size=wanted,
                                            n=1, response_format="b64_json")
            break
        except BadRequestError:
            if wanted == _FALLBACK_SIZE:
                raise
    data = getattr(answer, "data", None) or []
    if not data:
        raise ModelError("The image server returned no picture.")
    entry = data[0]
    if getattr(entry, "b64_json", None):
        return base64.b64decode(entry.b64_json)
    if getattr(entry, "url", None):
        return _fetch(entry.url, settings.timeout)
    raise ModelError("The image server answered without picture data.")


def webp(data: bytes) -> bytes:
    """A picture shrunk to the page's width and stored as WebP, a fraction of the PNG."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as picture:
        picture = picture.convert("RGB")
        picture.thumbnail((limits.PAGES_IMAGE_MAX_PX, limits.PAGES_IMAGE_MAX_PX))
        out = io.BytesIO()
        picture.save(out, "WEBP", quality=limits.PAGES_IMAGE_QUALITY, method=4)
        return out.getvalue()
