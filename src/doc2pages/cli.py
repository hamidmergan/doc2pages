"""The command line around the library."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .api import make_pages
from .client import is_provider_refusal
from .config import ENV_PREFIX, LANGUAGES
from .errors import Doc2PagesError
from .source_reading import EXTENSIONS

PROGRAM = "doc2pages"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Turn PDF, Word, PowerPoint and text files into structured learning web pages "
                    "with any OpenAI-compatible model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            f"  {PROGRAM} chapter.pdf -o pages/ --base-url http://localhost:11434/v1 --model your-model\n"
            f"  {PROGRAM} *.pptx -o pages/ --combine --translate en\n"
            f"  {PROGRAM} serve --host 127.0.0.1 --port 8000\n\n"
            f"Every setting can also come from the environment, for example {ENV_PREFIX}BASE_URL.\n"
            f"Supported input files: {', '.join(EXTENSIONS)}"
        ),
    )
    parser.add_argument("paths", nargs="*", type=Path,
                        help="input files, or 'serve' to start the web UI")
    parser.add_argument("-o", "--output", type=Path,
                        help="folder the pages are written into (default: pages)")
    parser.add_argument("--version", action="version", version=f"{PROGRAM} {__version__}")

    model = parser.add_argument_group("model")
    model.add_argument("--base-url", help="OpenAI-compatible endpoint, for example http://localhost:11434/v1")
    model.add_argument("--model", help="chat model that writes the page")
    model.add_argument("--api-key", help="API key, optional for a local server")
    model.add_argument("--image-base-url", help="endpoint of the image model (default: --base-url)")
    model.add_argument("--image-model", help="image model that draws the picture (default: --model)")
    model.add_argument("--image-api-key", help="API key of the image model (default: --api-key)")
    model.add_argument("--context-tokens", type=int,
                       help="context window of the chat model, so long material is split well")

    page = parser.add_argument_group("page")
    page.add_argument("--language", choices=LANGUAGES,
                      help="language of the page (default: the language of the material)")
    page.add_argument("--translate", dest="translate_to", choices=LANGUAGES,
                      help="also write the page in this language")
    page.add_argument("--images", action="store_true",
                      help="draw the title picture with the image model")
    page.add_argument("--no-images", action="store_true",
                      help=f"no title picture, even when {ENV_PREFIX}IMAGES is set")
    page.add_argument("--image-style", help="how the pictures should look")
    page.add_argument("--instructions", help="your own instruction for the content")
    page.add_argument("--combine", action="store_true",
                      help="one page out of all files instead of one page per file")
    page.add_argument("--markdown-only", action="store_true",
                      help="write only page.md and page.json, no HTML and no pictures")

    guard = parser.add_argument_group("limits")
    guard.add_argument("--max-files", type=int, help="files that go into one run")
    guard.add_argument("--max-file-mb", type=float, help="size of one input file in MB")
    guard.add_argument("--max-pages", type=int, help="pages or slides of one document")
    guard.add_argument("--max-chars", type=int, help="characters of all material together")
    guard.add_argument("--concurrency", type=int, help="model calls at the same time")
    guard.add_argument("--timeout", type=float, help="seconds one model call may take")

    serve = parser.add_argument_group("web UI")
    serve.add_argument("--host", default="127.0.0.1", help="address the web UI listens on")
    serve.add_argument("--port", type=int, default=8000, help="port the web UI listens on")
    serve.add_argument("--allowed-hosts", default="",
                       help="Host header names the web UI accepts, comma separated "
                            "(default: localhost, 127.0.0.1, ::1 and --host, '*' accepts any)")

    parser.add_argument("-q", "--quiet", action="store_true", help="only report errors")
    return parser


def _report(step: str, part: int | None, total: int | None) -> None:
    if part is None:
        print(f"{step} ...", file=sys.stderr)
    else:
        print(f"{step} {part}/{total}", file=sys.stderr)


def _message(e: BaseException) -> str:
    """What the user reads instead of a traceback when a call went wrong."""
    if is_provider_refusal(e):
        return (f"the model server turned the request down ({e}). "
                "Check --api-key, --model and --base-url.")
    return str(e) or e.__class__.__name__


def _images(args) -> bool | None:
    """Whether the title picture is drawn. None lets the environment decide."""
    if args.no_images:
        return False
    return args.images or None


def _serve(args) -> int:
    try:
        import uvicorn  # noqa: F401 - serve() needs it, the hint below beats a traceback

        from .web.app import serve
    except ImportError:
        print("The web UI needs the extra dependencies: pip install 'doc2pages[ui]'",
              file=sys.stderr)
        return 2
    serve(host=args.host, port=args.port,
          allowed_hosts=[h for h in args.allowed_hosts.split(",") if h.strip()] or None)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO,
                        format="%(message)s")

    paths = list(args.paths)
    if paths and str(paths[0]) == "serve":
        return _serve(args)
    if not paths:
        parser.print_help()
        return 2

    try:
        pages = make_pages(
            paths, args.output or Path("pages"),
            base_url=args.base_url, model=args.model, api_key=args.api_key,
            image_base_url=args.image_base_url, image_model=args.image_model,
            image_api_key=args.image_api_key, language=args.language,
            translate_to=args.translate_to, images=_images(args),
            image_style=args.image_style, instructions=args.instructions,
            combine=args.combine, markdown_only=args.markdown_only,
            max_files=args.max_files, max_file_mb=args.max_file_mb, max_pages=args.max_pages,
            max_chars=args.max_chars, concurrency=args.concurrency, timeout=args.timeout,
            context_tokens=args.context_tokens,
            on_progress=None if args.quiet else _report,
        )
    except Doc2PagesError as e:
        print(f"{PROGRAM}: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"{PROGRAM}: stopped", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001 - a rejected key gets a sentence, not a traceback
        print(f"{PROGRAM}: {_message(e)}", file=sys.stderr)
        return 1
    for page in pages:
        print(page.folder if page.folder else page.title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
