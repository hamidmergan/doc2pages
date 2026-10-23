"""The web UI of doc2pages: drop material in the browser, get a learning page back.

One run at a time. The finished pages are written into a temporary folder and served
from there, so the page can be looked at and downloaded as a ZIP.
"""

from __future__ import annotations

import io
import shutil
import tempfile
import threading
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Sequence
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__
from ..api import pages_from_sources, read_sources
from ..config import LANGUAGES, Settings, resolve
from ..errors import ConfigError, Doc2PagesError
from ..limits import IMAGE_STYLE_MAX_CHARS, INSTRUCTION_MAX_CHARS
from ..log import logger
from ..output import INDEX_FILE, write_pages
from ..source_reading import EXTENSIONS

STATIC = Path(__file__).parent / "static"
MB = 1024 * 1024

# What the browser is told while a run goes through its stages.
STEPS = ("outline", "section", "images")


class CreateRequest(BaseModel):
    instructions: str = ""
    image_style: str = ""
    language: str = ""
    translate_to: str = ""
    images: bool = False
    combine: bool = False
    base_url: str = ""
    model: str = ""
    api_key: str = ""


class Job:
    """The one run the server holds, with what the browser needs to show it."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.state = "idle"  # idle, running, done or error
        self.step = ""
        self.part = 0
        self.total = 0
        self.error = ""
        self.pages: list[dict] = []

    def as_dict(self) -> dict:
        return {"state": self.state, "step": self.step, "part": self.part, "total": self.total,
                "error": self.error, "pages": self.pages}


def _hostname(host: str) -> str:
    if host.startswith("["):
        return host[1:host.find("]")].lower()
    return host.rsplit(":", 1)[0].lower() if host.count(":") == 1 else host.lower()


def _settings(request: CreateRequest) -> Settings:
    return resolve(
        base_url=request.base_url.strip() or None,
        model=request.model.strip() or None,
        api_key=request.api_key.strip() or None,
        language=request.language.strip() or None,
        translate_to=request.translate_to.strip() or None,
        images=request.images,
        image_style=request.image_style.strip()[:IMAGE_STYLE_MAX_CHARS] or None,
        instructions=request.instructions.strip()[:INSTRUCTION_MAX_CHARS] or None,
    )


def create_app(settings: Optional[Settings] = None,
               allowed_hosts: Optional[Sequence[str]] = None) -> FastAPI:
    """The page and its JSON API. ``allowed_hosts`` limits the Host header."""
    room = tempfile.TemporaryDirectory(prefix="doc2pages-")
    root = Path(room.name)
    uploads = root / "uploads"
    results = root / "pages"
    uploads.mkdir()
    job = Job()
    lock = threading.Lock()
    files: list[Path] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        room.cleanup()

    app = FastAPI(title="doc2pages", version=__version__, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    hosts = {h.lower() for h in allowed_hosts} if allowed_hosts is not None else None

    def limits() -> Settings | None:
        try:
            return settings or resolve()
        except ConfigError:
            return None

    def max_upload_bytes() -> int:
        s = limits()
        files_at_once = s.max_files if s else 10
        size = s.max_file_mb if s else 500
        return int(files_at_once * size * MB) + MB

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = request.headers.get("host", "")
        if hosts is not None and _hostname(host) not in hosts:
            return PlainTextResponse("Unknown host", status_code=400)
        origin = request.headers.get("origin")
        own = {host.lower(), request.headers.get("x-forwarded-host", "").lower()}
        if origin is not None and urlsplit(origin).netloc.lower() not in own:
            return PlainTextResponse("Cross-origin requests are not allowed", status_code=403)
        if request.url.path == "/api/upload":
            length = request.headers.get("content-length", "")
            if not length.isdigit():
                return PlainTextResponse("The upload needs a Content-Length header.",
                                         status_code=411)
            if int(length) > max_upload_bytes():
                return PlainTextResponse("The upload is too large.", status_code=413)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/info")
    def info():
        s = limits()
        return {
            "version": __version__,
            "extensions": list(EXTENSIONS),
            "languages": list(LANGUAGES),
            "max_files": s.max_files if s else 10,
            "max_file_mb": s.max_file_mb if s else 500,
            "instruction_max_chars": INSTRUCTION_MAX_CHARS,
            "image_style_max_chars": IMAGE_STYLE_MAX_CHARS,
            "model": s.model if s else "",
            "image_model": s.image_model if s else "",
            # What the environment already decided, so the fields start where it points.
            "language": (s.language if s else "") or "",
            "translate_to": (s.translate_to if s else "") or "",
            "images": bool(s.images) if s else False,
            "image_style": s.image_style if s else "",
            "instructions": s.instructions if s else "",
            # What is already uploaded, so a reloaded page finds its files again.
            "files": [p.name for p in files],
            # Without a model in the environment the page asks for one.
            "configured": s is not None,
        }

    @app.post("/api/upload")
    async def upload(uploaded: list[UploadFile] = File(..., alias="files")):
        s = limits()
        at_most = s.max_files if s else 10
        with lock:
            if job.state == "running":
                raise HTTPException(409, "A page is being created right now.")
            for f in uploaded:
                name = Path(f.filename or "").name
                if not name:
                    continue
                if Path(name).suffix.lower() not in EXTENSIONS:
                    raise HTTPException(400, f"{name}: this file type is not supported.")
                if len(files) >= at_most:
                    raise HTTPException(400, f"At most {at_most} files per page.")
                target = uploads / name
                target.write_bytes(await f.read())
                if target not in files:
                    files.append(target)
            return {"files": [p.name for p in files]}

    @app.post("/api/clear")
    def clear():
        with lock:
            if job.state == "running":
                raise HTTPException(409, "A page is being created right now.")
            for p in files:
                p.unlink(missing_ok=True)
            files.clear()
            return {"files": []}

    def run(request: CreateRequest, chosen: Settings, sources) -> None:
        def progress(step: str, part: Optional[int], total: Optional[int]) -> None:
            with lock:
                job.step, job.part, job.total = step, part or 0, total or 0

        import asyncio

        try:
            if results.exists():
                shutil.rmtree(results)
            pages = asyncio.run(pages_from_sources(sources, chosen, combine=request.combine,
                                                   on_progress=progress))
            folders = write_pages(pages, results)
        except Doc2PagesError as e:
            with lock:
                job.state, job.error = "error", str(e)
            return
        except Exception as e:  # noqa: BLE001 - the browser must see why the run stopped
            logger.warning("The run failed: {}", e)
            with lock:
                job.state, job.error = "error", str(e)
            return
        with lock:
            job.pages = [{"index": i, "title": p.title, "folder": f.name,
                          "language": p.data.get("lang", "")}
                         for i, (p, f) in enumerate(zip(pages, folders))]
            job.state, job.step, job.part, job.total = "done", "", 0, 0

    @app.post("/api/create")
    def create(request: CreateRequest):
        with lock:
            if job.state == "running":
                raise HTTPException(409, "A page is being created right now.")
            if not files:
                raise HTTPException(400, "Upload material first.")
            try:
                chosen = _settings(request)
                sources = read_sources(list(files), chosen)
            except Doc2PagesError as e:
                # A missing setting or a file over the limit: the page shows the sentence.
                raise HTTPException(400, str(e)) from None
            job.reset()
            job.state = "running"
            job.step = STEPS[0]
        threading.Thread(target=run, args=(request, chosen, sources), daemon=True).start()
        return job.as_dict()

    @app.get("/api/status")
    def status():
        with lock:
            return job.as_dict()

    def page_folder(index: int) -> Path:
        with lock:
            if index < 0 or index >= len(job.pages):
                raise HTTPException(404, "This page does not exist.")
            return results / job.pages[index]["folder"]

    @app.get("/api/page/{index}", response_class=HTMLResponse)
    def page(index: int):
        return FileResponse(page_folder(index) / INDEX_FILE)

    @app.get("/api/page/{index}/{name}")
    def asset(index: int, name: str):
        safe = Path(name).name
        path = page_folder(index) / safe
        if not path.is_file():
            raise HTTPException(404, "This file does not exist.")
        return FileResponse(path)

    @app.get("/api/download")
    def download():
        with lock:
            if not job.pages:
                raise HTTPException(404, "There is no page to download yet.")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(results.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(results).as_posix())
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="pages.zip"'})

    return app


def serve(host: str = "127.0.0.1", port: int = 8000,
          settings: Optional[Settings] = None) -> None:
    """Starts the web UI. Settings missing here are read from the environment per run."""
    import uvicorn

    # The Host header is checked without its port, so only names belong in here.
    hosts = None if host == "0.0.0.0" else {_hostname(host), "localhost", "127.0.0.1"}
    app = create_app(settings, allowed_hosts=hosts)
    print(f"doc2pages is listening on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
