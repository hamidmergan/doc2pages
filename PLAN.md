# doc2pages: plan

## What the tool does

doc2pages turns source files (PDF, DOCX, PPTX, TXT, MD, SRT, VTT) into a structured learning web page.
A model plans the sections over the numbered text of the material, writes each section as a short
prose text plus at most one visual block, and adds a frame: title, lead, key points, an optional
formula, a mind map of the sections and a word cloud. An image model can draw the title picture.
The page can be translated into its other language (German or English).

A page is plain data (`page.json`): a list of sections, each with a title, a lead and blocks.
There are 27 block kinds: text, bullets, highlight, cards, steps, figures, bars, table, chart,
image, mindmap, wordcloud, quote, checklist, definitions, accordion, cycle, timeline, tree,
levels, scale, versus, matrix, venn, formula, mistakes, example. A page has one of four
designs: chapters, timeline, magazine, guide.

Output per page: a folder with `index.html` (standalone, CSS embedded, no script needed),
`page.md`, `page.json` and the pictures as files. An `index.html` at the top lists all pages.

## Scope of v0.1

- Reading: PDF (text layer, headers and footers counted out), DOCX, PPTX, TXT, MD, SRT, VTT.
- Pipeline: language detection, text map, topic stage for long material, outline with frame,
  blocks per section in groups, prose fallback, short text rewrite, frame call, citation removal,
  word cloud, mind map, cleaning to the schema limits, reading time line.
- Optional instruction for the content and optional style for pictures.
- Optional title picture through an image model (`--images`).
- Optional translation into the other language (`--translate de|en`).
- Output: HTML per page, Markdown per page, JSON per page, overview page.
- Library API `make_pages`, CLI `doc2pages`, web UI `doc2pages serve`, Docker image.

Not in v0.1: the page editor, sharing, collections, workspaces, user accounts, quotas.

## Decisions

- Prompts, limits and defaults are taken over unchanged from the original service.
- One OpenAI-compatible interface for chat and images. No fixed provider, no default model.
- Storage between stages is kept in memory for one run. There is no job queue.
- By default every input file becomes its own page. `--combine` makes one page from all files
  together (at most 10 files), as the original service does.
- Page languages are German and English, as in the original. Material in any other language
  gives an English page.
- The HTML output draws every block kind in one fixed look. The original rotates between
  several looks per kind, a static template keeps the first one.
- Language detection uses `langdetect` with the same sample and thresholds as the original.
- The Markdown input is cleaned with the same regular expressions as the original, so the
  `markdown` package is not needed.
- Source code is copied from the original service with mechanical English renames of
  identifiers only. Logic, prompts, limits and output formats stay byte for byte, the
  original tests are carried with the same renames. Where this tool knowingly steps away
  from that, the reason is written down under "Deliberate deviations from the source".
- The model's context window is unknown to the tool. Without `context_tokens` it assumes
  131072 tokens, the same assumption the original makes for an unmeasured model.

## Checklist

- [x] 0 Scaffold: repo, LICENSE, pyproject, package, tests, CI, PLAN.md, README skeleton
- [x] 1 Core: schema, writing, pipeline, text, translate, source reading, config, errors
- [x] 2 Output: Markdown, HTML with embedded CSS, images as files, overview index.html
- [x] 3 API and CLI: `make_pages`, `doc2pages` with `-o`, `--translate`, `--images`, `--markdown-only`
- [x] 4 Tests with a fake server: structure, translation, images, HTML, CLI, configuration
- [x] 5 README, CHANGELOG 0.1.0, local smoke test with a real model
- [x] 6 English sweep, acceptance greps, final commit
- [x] 7 Web UI (`doc2pages serve`) and Docker (`Dockerfile`, `docker-compose.yml`)
- [x] 8 Review fixes: the findings of the code review, with tests that can see them

## Deliberate deviations from the source

Everything else follows the original service line by line. These points do not, each for a
reason that a user of this tool would notice.

- Two prompt strings name what is being made. The original says "a written summary" in the
  topic call and in the instruction classification, because its pages tool reuses the summary
  pipeline. This tool writes a learning web page and says so in both places
  (`pipeline.py:171,205`), which is what every other prompt in the package already says.
- A model refusal (401, 403, 404) reaches the user as one sentence naming `--api-key`,
  `--model` and `--base-url`. In the original a web route turned the exception into a message,
  there is no route here, so `cli.main` does it (`cli.py`).
- "no outline" was an internal marker in the original, replaced by a message in its frontend.
  Here the sentence says what to check (`pipeline.py:418`).
- `concurrency` limits the calls of a run. The original pins its stages to a module constant
  and takes the number from a server setting the tool does not have.
- The picture stage reports its progress, so the web UI shows the step it has for it. The
  original reports it from its task queue, which this tool has no counterpart for.
- The mind map branches link to their sections, which the original does in its frontend.
- The drawings carry their own geometry: a pill is as wide as its label, a label too long is
  cut between words, the centre word is broken and shrunk until it fits the circle, and a
  single long word in the word cloud is shrunk instead of running out of the picture. The
  original draws in the browser, where the layout engine does this.
- `_fetch` tries `httpx2` before `httpx`, follows redirects and raises on a 4xx or 5xx answer.
  All three ways through it behave the same, so the way the tests take is the way an install
  of this package takes.
- The keyword of a quote is marked in the raw text and escaped afterwards. Marking it in the
  escaped text hits inside an entity, so "amp" marked the middle of an "&".
- `--no-images` switches the title picture off for one run, even when the environment turned
  it on. The original decides per job and never had a flag to contradict.
- The Host header check stays on when the server listens on every interface, and
  `docker-compose.yml` publishes the port on `127.0.0.1` only. `--allowed-hosts` names the
  hosts for a run behind a proxy.
- Markdown is decoded with `errors="replace"`, like the other text readers. The original lets
  a file in an older encoding fail.
- A page folder is cleared of the files of an earlier page before it is written, so a run with
  fewer pictures does not leave the old ones behind. Only `index.html`, `page.md`, `page.json`
  and `img_<n>.webp` are touched.
- A translation into the language the page already has says in the log that the other language
  is written instead.

## Known properties

Carried from the original and kept, because nothing a user does goes wrong with them.

- `--translate de` on German material writes the English page, because a page knows only its
  own language and the other one. The log says so.
- A title with no Latin letters gives a folder name with no information, `page-1` and so on.
  The overview still shows the real title, and two equal names never collide.
- A second run into an output folder leaves whole page folders of a run whose titles slugged
  differently. The new overview does not list them.
- The schema carries `layout` and `heading` on a section, and `LAYOUTS` with them. The HTML
  writer ignores both, because v0.1 has no editor that could set them.
- `Basis` is the record a planning call reads. The word is read as the English noun here.
- `schema.py:51` keeps German examples in a comment, because they are the date forms the
  regular expression below it matches.
- The reading time line says "Made with AI on <date>". It is carried from the original and
  belongs to the page the tool writes.
- The web UI holds one run at a time and keeps it in memory. A second browser sees the same
  run, which is what one person on one machine needs.

## Open

- The smoke test with a real model is done: a Markdown chapter and the same chapter as a
  three page PDF each went through the command line and through the web page, once with
  `--translate de`, once with `--combine` and once with an instruction. The pages carry the
  expected frame, the blocks keep to the schema and the HTML parses with no unclosed tag.
- The title picture was drawn by a real image model: `--images` wrote `img_0.webp`
  (1536 x 656, WEBP) next to the page, and the run reported "images 0/1" and "images 1/1"
  on its way there.
- The image was built and started, and a whole run was made inside the container against a
  real model: upload, create, status, the finished page and the ZIP with four files. An
  unknown Host is refused with 400 there too, although the server listens on every interface.
- The mind map was checked again after the review: a page with four centre words, among them
  three long German compounds, was rendered and looked at in a browser at 1200 px. Every
  centre label now stays inside its circle, and a test asserts the size that is drawn rather
  than the attribute that is written.
- The readers now run in the suite against real PDF, DOCX, PPTX, SRT and VTT files, so the
  header and footer detection is exercised. The drawings are measured, not just checked for
  being a non-empty string.
