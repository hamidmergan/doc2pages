# doc2pages

A Python tool that turns source files into a structured learning web page. A model plans the
sections over the material, writes each one as short prose plus one visual block, and adds a
frame: title, lead, key points, an optional formula, a mind map of the sections and a word
cloud. The result is a standalone `index.html` with its CSS inside it, a `page.md` and a
`page.json`, so a page opens anywhere and needs no build step and no server.

doc2pages currently reads:

- PDF (text layer, headers and footers counted out)
- Word (DOCX) and PowerPoint (PPTX)
- Text and Markdown (TXT, MD)
- Subtitles (SRT, VTT)

## Prerequisites

- Python 3.10 or newer
- A server with an OpenAI-compatible API and a **chat model** (for example Ollama, vLLM,
  LM Studio, a university server or a cloud provider). A model with a context window of at
  least 32k tokens is recommended, longer material is split automatically.
- An **image model** only for `--images`. Without it the page is written without a picture.
- An API key is optional. Many self-hosted servers do not need one.

If you run your own model, your material stays on your own network. Nothing leaves your
machine or data center.

## Installation

doc2pages is installed from GitHub:

```bash
pip install git+https://github.com/hamidmergan/doc2pages.git
```

With the web UI:

```bash
pip install "doc2pages[ui] @ git+https://github.com/hamidmergan/doc2pages.git"
```

Alternatively, you can install it from a local copy (`pip install ".[ui]"` for the web UI):

```bash
git clone https://github.com/hamidmergan/doc2pages.git
cd doc2pages
pip install .
```

## Usage

### Command-Line

One page per file, written into a folder:

```bash
doc2pages chapter.pdf -o pages/ --base-url http://localhost:11434/v1 --model your-model
```

This writes `pages/<title>/index.html`, `page.md`, `page.json` and the pictures, plus a
`pages/index.html` that lists every page.

One page out of several files together:

```bash
doc2pages lecture1.pdf lecture2.pptx -o pages/ --combine --base-url http://localhost:11434/v1 --model your-model
```

The page in a second language, and with its title picture drawn:

```bash
doc2pages chapter.pdf -o pages/ --translate en --images --base-url http://localhost:11434/v1 --model your-model
```

Only the data, no HTML and no pictures:

```bash
doc2pages chapter.pdf -o pages/ --markdown-only --base-url http://localhost:11434/v1 --model your-model
```

Errors appear on stderr. The exit code is 1 when the run failed.

### Web UI

```bash
pip install "doc2pages[ui] @ git+https://github.com/hamidmergan/doc2pages.git"
doc2pages serve
```

Then open http://127.0.0.1:8000. Drop your material on the page, add an instruction if you
want one, pick the language and whether a title picture is drawn, and press Create page. The
finished page is shown right there, opens in a new tab and downloads as a ZIP with the HTML,
the Markdown, the JSON and the pictures.

The settings come from the `DOC2PAGES_*` environment variables. When no model is set, the page
asks for `base_url`, `model` and an optional `api_key` itself:

```bash
DOC2PAGES_BASE_URL=http://localhost:11434/v1 DOC2PAGES_MODEL=your-model doc2pages serve
```

The page is in English and German and switches with the two buttons in the header. It listens
on this computer only. With `--host 0.0.0.0` it is reachable from your network, but it has no
login, so do not expose it to the internet. The server only answers requests whose `Host`
header is `localhost`, `127.0.0.1`, `::1` or the address it was started with. Behind a proxy
that rewrites the header, name the hosts yourself with `--allowed-hosts example.org`, or pass
`--allowed-hosts '*'` to accept any. Uploads and results live in a temporary folder and go
away when the server stops.

### Docker

The image runs the web UI on port 8000:

```bash
docker compose up
```

The port is published on `127.0.0.1` only, so the container is reachable from this computer
and not from your network. Set `DOC2PAGES_PORT` to use another port on the host.

Or without compose:

```bash
docker build -t doc2pages .
docker run -p 127.0.0.1:8000:8000 \
  -e DOC2PAGES_BASE_URL=http://host.docker.internal:11434/v1 \
  -e DOC2PAGES_MODEL=your-model \
  doc2pages
```

Then open http://127.0.0.1:8000. `host.docker.internal` reaches a model server such as Ollama
on the same computer (on Linux, add `--add-host=host.docker.internal:host-gateway`).
`docker-compose.yml` lists every setting the container understands, so you can put them in a
`.env` file next to it. The page has no login, so do not expose the port to the internet.

### Python API

```python
from doc2pages import make_pages

pages = make_pages(
    ["chapter.pdf"],
    "pages/",
    base_url="http://localhost:11434/v1",
    model="your-model",
)
for page in pages:
    print(page.title, page.folder)
```

Without an output folder nothing is written and the pages come back in memory:

```python
pages = make_pages(["chapter.pdf"], base_url=..., model=...)
print(pages[0].html)       # the standalone page
print(pages[0].markdown)   # the same page as Markdown
print(pages[0].data)       # the page as plain data
```

A page is plain data: a list of sections, each with a title, a lead and blocks. There are 27
block kinds, among them text, bullets, cards, steps, table, chart, timeline, mind map and
word cloud. A page has one of four designs: chapters, timeline, magazine, guide.

With `translate_to` the run returns two pages, the written one first and its translation
after it. With `combine=True` all files become one page.

### Settings

Order: argument, then environment variable, then default.

| Argument / flag | Environment variable | Default |
| --- | --- | --- |
| `base_url` / `--base-url` | `DOC2PAGES_BASE_URL` | none, required |
| `model` / `--model` | `DOC2PAGES_MODEL` | none, required |
| `api_key` / `--api-key` | `DOC2PAGES_API_KEY` (then `OPENAI_API_KEY`) | optional |
| `image_base_url` / `--image-base-url` | `DOC2PAGES_IMAGE_BASE_URL` | `base_url` |
| `image_model` / `--image-model` | `DOC2PAGES_IMAGE_MODEL` | `model` |
| `image_api_key` / `--image-api-key` | `DOC2PAGES_IMAGE_API_KEY` | `api_key` |
| `language` / `--language` | `DOC2PAGES_LANGUAGE` | the language of the material |
| `translate_to` / `--translate` | `DOC2PAGES_TRANSLATE_TO` | off |
| `images` / `--images`, `--no-images` | `DOC2PAGES_IMAGES` | off |
| `image_style` / `--image-style` | `DOC2PAGES_IMAGE_STYLE` | a calm editorial style |
| `instructions` / `--instructions` | `DOC2PAGES_INSTRUCTIONS` | none |
| `context_tokens` / `--context-tokens` | `DOC2PAGES_CONTEXT_TOKENS` | 131072 assumed |
| `max_files` / `--max-files` | `DOC2PAGES_MAX_FILES` | 10 |
| `max_file_mb` / `--max-file-mb` | `DOC2PAGES_MAX_FILE_MB` | 500 |
| `max_pages` / `--max-pages` | `DOC2PAGES_MAX_PAGES` | 200 |
| `max_chars` / `--max-chars` | `DOC2PAGES_MAX_CHARS` | 500000 |
| `concurrency` / `--concurrency` | `DOC2PAGES_CONCURRENCY` | 3 |
| `timeout` / `--timeout` | `DOC2PAGES_TIMEOUT` | 270 seconds |

If a limit is exceeded, the file is rejected with a message naming the limit and the setting.
Nothing is silently truncated.

A page is written in German or English. Material in any other language gives an English page.

## Limitations

Quality depends on the chosen model. A small model plans fewer sections, picks plainer block
kinds and sometimes writes a section as plain prose. Check important results.

A scanned PDF without a text layer is rejected, doc2pages does no text recognition.

An image model is needed for `--images`. Many servers that answer chat calls do not draw.

## Running Tests

```bash
pip install -e ".[test]"
pytest
```

The tests run against a local fake server and need no real model.

## License

MIT
