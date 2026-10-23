"""Every block kind reaches the HTML and the Markdown, and a page writes its own folder."""

import json
from pathlib import Path

from doc2pages import schema
from doc2pages.output import Page, write_pages
from doc2pages.render import block_html, block_markdown, page_html, page_markdown

ALL_BLOCKS = [
    {"kind": "text", "text": "Ein Satz. Noch einer."},
    {"kind": "bullets", "items": ["eins", "zwei"]},
    {"kind": "highlight", "key": "A = b", "text": "x"},
    {"kind": "cards", "cards": [{"icon": "check", "title": "A", "text": "a"},
                                {"icon": "none", "title": "B", "text": "b"}]},
    {"kind": "steps", "steps": [{"title": "Eins", "text": "a"}, {"title": "Zwei", "text": "b"}]},
    {"kind": "figures", "figures": [{"value": "30 min", "label": "Dauer"},
                                    {"value": "4", "label": "Teile"}]},
    {"kind": "bars", "max": 1, "bars": [{"label": "A", "value": 0.6, "text": "x"},
                                        {"label": "B", "value": 0.2, "text": ""}]},
    {"kind": "table", "caption": "Vergleich", "header": ["", "A", "B"],
     "rows": [["x", "1", "2"], ["y", "3", "4"]]},
    {"kind": "chart", "chart_type": "line", "caption": "Verlauf", "x_label": "t", "y_label": "m",
     "categories": ["1", "2", "3"], "series": [{"name": "a", "values": [1, 2, 3]}]},
    {"kind": "chart", "chart_type": "bar", "categories": ["a", "b"],
     "series": [{"name": "", "values": [2, 5]}]},
    {"kind": "chart", "chart_type": "pie", "categories": ["a", "b"],
     "series": [{"name": "", "values": [2, 5]}]},
    {"kind": "image", "src": "img_0.webp", "alt": "Ein Tisch", "prompt": "a desk", "caption": "Bild"},
    {"kind": "mindmap", "center": "Thema", "caption": "Karte",
     "branches": [{"title": "A", "to": "s1", "leaves": ["x"]}, {"title": "B", "to": "", "leaves": []}]},
    {"kind": "wordcloud", "caption": "Wolke", "words": [["Alpha", 5], ["Beta", 3], ["Gamma", 1]]},
    {"kind": "quote", "text": "Die Gerade zählt.", "keyword": "Gerade"},
    {"kind": "checklist", "items": ["Budget", "Termine"]},
    {"kind": "definitions", "items": [{"term": "Median", "text": "Mitte"}]},
    {"kind": "accordion", "items": [{"title": "A", "text": "a"}, {"title": "B", "text": "b"},
                                    {"title": "C", "text": "c"}]},
    {"kind": "cycle", "center": "PDCA", "steps": [{"title": "Plan", "text": "a"},
                                                  {"title": "Do", "text": "b"},
                                                  {"title": "Check", "text": "c"}]},
    {"kind": "timeline", "events": [{"date": "1957", "title": "A", "text": "a"},
                                    {"date": "1960", "title": "B", "text": "b"}]},
    {"kind": "tree", "root": "Ganzes", "branches": [{"title": "A", "leaves": ["x"]},
                                                    {"title": "B", "leaves": []}]},
    {"kind": "levels", "caption": "Rang", "items": [{"title": "Oben", "text": "a"},
                                                    {"title": "Unten", "text": "b"}]},
    {"kind": "scale", "caption": "Lage", "left": "kalt", "right": "warm",
     "items": [{"label": "A", "pos": 0.2}, {"label": "B", "pos": 0.8}]},
    {"kind": "versus", "tone": "good_bad", "a": {"title": "Gut", "items": ["x"]},
     "b": {"title": "Schlecht", "items": ["y"]}},
    {"kind": "venn", "a": {"title": "A", "items": ["x"]}, "b": {"title": "B", "items": ["y"]},
     "both": ["z"]},
    {"kind": "matrix", "x": "Interesse", "y": "Einfluss",
     "cells": [{"pos": q, "title": q.upper(), "text": "t"} for q in ("tl", "tr", "bl", "br")],
     "points": [{"label": "P", "x": 0.5, "y": 0.5}]},
    {"kind": "formula", "key": "E = m c²", "text": "Energie",
     "parts": [{"sym": "m", "text": "Masse"}], "example": ["m = 2", "E = 2 c²"]},
    {"kind": "mistakes", "pairs": [{"wrong": "falsch", "right": "richtig"}]},
    {"kind": "example", "title": "Fall", "situation": "s", "steps": ["a", "b"], "result": "r"},
]


def _page_with_all_blocks() -> dict:
    """One page that carries every block kind, three per section so none is cut."""
    sections = [{"id": "top", "hero": True, "title": "Titel", "lead": "Kurz", "meta": "Meta",
                 "blocks": []}]
    for i in range(0, len(ALL_BLOCKS), 3):
        sections.append({"id": f"s{i + 1}", "title": f"Abschnitt {i + 1}", "lead": "L",
                         "blocks": ALL_BLOCKS[i:i + 3]})
    return schema.clean_page({"lang": "de", "design": "chapters", "sections": sections,
                              "footer": ""})


def test_every_block_kind_draws_html_and_markdown():
    for b in ALL_BLOCKS:
        cleaned = schema.clean_block(b)
        assert cleaned is not None, b["kind"]
        assert block_html(cleaned).strip(), b["kind"]
        assert block_markdown(cleaned), b["kind"]


def test_the_page_is_one_standalone_document():
    html = page_html(_page_with_all_blocks())
    assert html.startswith("<!doctype html>")
    assert "<style>" in html and "</html>" in html
    # Nothing is pulled in from the network and no script runs.
    assert "<script" not in html and "http://" not in html and "https://" not in html
    for b in ALL_BLOCKS:
        assert f'k-{b["kind"]}' in html, b["kind"]


def test_html_escapes_markup_in_the_data():
    html = page_html(schema.clean_page({"sections": [
        {"id": "a", "title": "<b>T</b>", "blocks": [{"kind": "text", "text": "a <script>x</script>"}]}]}))
    assert "<b>T</b>" not in html and "&lt;b&gt;T&lt;/b&gt;" in html
    assert "<script>" not in html


def test_markdown_keeps_headings_tables_and_pictures():
    md = page_markdown(_page_with_all_blocks())
    assert md.startswith("# Titel")
    assert "## Abschnitt 1" in md
    assert "| --- |" in md
    assert "![Ein Tisch](img_0.webp)" in md


def test_hidden_sections_never_reach_the_output():
    page = schema.clean_page({"sections": [
        {"id": "a", "title": "Sichtbar", "blocks": [{"kind": "text", "text": "offen"}]},
        {"id": "b", "title": "Versteckt", "hidden": True,
         "blocks": [{"kind": "text", "text": "geheim"}]}]})
    assert "geheim" not in page_html(page)
    assert "geheim" not in page_markdown(page)


def test_write_pages_builds_folders_and_an_overview(tmp_path: Path):
    page = Page(data=_page_with_all_blocks(), title="Lineare Regression",
                images={"img_0.webp": b"not-a-real-picture"})
    folders = write_pages([page], tmp_path)
    folder = folders[0]
    assert folder.name == "lineare-regression"
    assert (folder / "index.html").exists()
    assert (folder / "page.md").exists()
    assert (folder / "img_0.webp").read_bytes() == b"not-a-real-picture"
    data = json.loads((folder / "page.json").read_text(encoding="utf-8"))
    assert data["sections"][0]["title"] == "Titel"
    overview = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "lineare-regression/index.html" in overview


def test_markdown_only_writes_no_html(tmp_path: Path):
    page = Page(data=_page_with_all_blocks(), title="Nur Text",
                images={"img_0.webp": b"x"})
    folder = write_pages([page], tmp_path, markdown_only=True)[0]
    assert (folder / "page.md").exists()
    assert not (folder / "index.html").exists()
    assert not (folder / "img_0.webp").exists()
    assert not (tmp_path / "index.html").exists()


def test_the_html_is_well_formed():
    """Every tag that opens also closes, read back with the standard parser."""
    from html.parser import HTMLParser

    void = {"meta", "img", "br", "hr", "input", "link", "source", "path", "circle", "rect",
            "line", "text", "use"}

    class Reader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.open: list[str] = []
            self.bad: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag not in void:
                self.open.append(tag)

        def handle_endtag(self, tag):
            if tag in void:
                return
            if not self.open or self.open[-1] != tag:
                self.bad.append(f"{tag} closes {self.open[-1] if self.open else 'nothing'}")
                return
            self.open.pop()

        def handle_startendtag(self, tag, attrs):
            pass

    reader = Reader()
    reader.feed(page_html(_page_with_all_blocks()))
    assert reader.bad == []
    assert reader.open == []
