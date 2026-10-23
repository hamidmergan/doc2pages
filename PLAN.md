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
  original tests are carried with the same renames.
- The model's context window is unknown to the tool. Without `context_tokens` it assumes
  131072 tokens, the same assumption the original makes for an unmeasured model.

## Checklist

- [x] 0 Scaffold: repo, LICENSE, pyproject, package, tests, CI, PLAN.md, README skeleton
- [x] 1 Core: schema, writing, pipeline, text, translate, source reading, config, errors
- [x] 2 Output: Markdown, HTML with embedded CSS, images as files, overview index.html
- [ ] 3 API and CLI: `make_pages`, `doc2pages` with `-o`, `--translate`, `--images`, `--markdown-only`
- [ ] 4 Tests with a fake server: structure, translation, images, HTML, CLI, configuration
- [ ] 5 README, CHANGELOG 0.1.0, local smoke test with a real model
- [ ] 6 English sweep, acceptance greps, final commit
- [ ] 7 Web UI (`doc2pages serve`) and Docker (`Dockerfile`, `docker-compose.yml`)

## Open

- none
