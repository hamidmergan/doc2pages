# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-23

### Added

- Reading of PDF, DOCX, PPTX, TXT, MD, SRT and VTT files into one canonical text per source.
- Pipeline that plans the sections over the numbered material, writes each section as prose
  plus one visual block, and fills the frame of the page in the same call.
- 27 block kinds and four page designs, every answer cut to the limits of the schema.
- Optional title picture through an image model, optional translation into the other language.
- Output per page: a standalone `index.html` with its CSS inside it, `page.md`, `page.json`
  and the pictures, plus an overview `index.html` that lists every page.
- Library API `make_pages` and the command line `doc2pages`.
- Settings through arguments, flags or `DOC2PAGES_*` environment variables, for any
  OpenAI-compatible server.
