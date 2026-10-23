"""The page schema cuts every page to its limits and the draft is built from plan and blocks."""

from doc2pages import pipeline as pl
from doc2pages import schema
from doc2pages.limits import PAGES_MAX_SECTIONS, PAGES_MAX_SHORT_CHARS, PAGES_MAX_TABLE_ROWS
from doc2pages.models import Outline, Section
from doc2pages.source_reading import Source


def _page(*sections, **extra):
    return {"sections": list(sections), **extra}


def _source(name: str, text: str) -> Source:
    return Source(name=name, checksum="x", text=text, pieces=[], pages=1)


def test_unknown_kinds_and_html_never_survive():
    page = schema.clean_page(_page({"id": "a", "title": "<b>T</b>", "blocks": [
        {"kind": "script", "text": "x"}, {"kind": "bullets", "items": ["eins", "", None, {"x": 1}]}]}))
    blocks = page["sections"][0]["blocks"]
    assert blocks == [{"kind": "bullets", "items": ["eins"]}]
    # Text stays text, the renderer escapes it, nothing here turns it into markup.
    assert page["sections"][0]["title"] == "<b>T</b>"


def test_limits_cut_sections_tables_and_text():
    many = [{"title": f"S{i}", "blocks": [{"kind": "bullets", "items": ["x"]}]} for i in range(40)]
    page = schema.clean_page(_page(*many))
    assert len(page["sections"]) == PAGES_MAX_SECTIONS
    rows = [[str(i), "a", "b"] for i in range(30)]
    t = schema.clean_block({"kind": "table", "header": ["", "A", "B"], "rows": rows})
    assert len(t["rows"]) == PAGES_MAX_TABLE_ROWS
    long = schema.clean_page(_page({"title": "Wort " * 100, "blocks": []}))
    assert len(long["sections"][0]["title"]) <= PAGES_MAX_SHORT_CHARS


def test_chart_needs_matching_numbers():
    good = schema.clean_block({"kind": "chart", "chart_type": "line", "categories": ["1", "2", "3"],
                               "series": [{"name": "a", "values": [1, "2,5", 3]}]})
    assert good["series"][0]["values"] == [1.0, 2.5, 3.0]
    assert schema.clean_block({"kind": "chart", "categories": ["1", "2", "3"],
                               "series": [{"values": [1, 2]}]}) is None


def test_images_only_by_their_own_names():
    assert schema.clean_block({"kind": "image", "src": "../../etc/passwd"}) is None
    assert schema.clean_block({"kind": "image", "src": "img_0.webp"})["src"] == "img_0.webp"


def test_hidden_sections_stay_out_of_the_viewer_copy():
    page = schema.clean_page(_page(
        {"id": "a", "title": "Sichtbar", "blocks": [{"kind": "image", "src": "img_0.webp"}]},
        {"id": "b", "title": "Versteckt", "hidden": True, "blocks": [{"kind": "image", "src": "img_1.webp"}]}))
    seen = schema.for_viewers(page)
    assert [s["id"] for s in seen["sections"]] == ["a"]
    assert schema.images_of(page) == {"img_0.webp"}


def test_duplicate_section_ids_are_renamed():
    page = schema.clean_page(_page({"id": "a", "title": "x"}, {"id": "a", "title": "y"}))
    ids = [s["id"] for s in page["sections"]]
    assert len(set(ids)) == 2


def test_word_cloud_counts_the_material():
    words = pl.word_cloud(["Gerade", "gerade", "Residuum", "fehlt"],
                          "Die Gerade, die Gerade und ein Residuum.")
    assert words == [["Gerade", 2], ["Residuum", 1]]


def test_draft_builds_title_gist_map_sections_and_cloud():
    plan = Outline(title="Lineare Regression", intro="Es geht um Geraden. Sie sagen voraus.",
                   sections=[Section(title=f"Teil {i}") for i in range(4)])
    stuff = " ".join(["Steigung Achsenabschnitt Residuum Korrelation Varianz Modell"] * 3)
    blocks = {i: {"lead": "Lead", "map_label": f"T{i}",
                  "blocks": [{"kind": "bullets", "items": ["a", "b"]}],
                  "keywords": ["Steigung", "Achsenabschnitt", "Residuum", "Korrelation", "Varianz",
                               "Modell"][i:i + 3]}
              for i in range(4)}
    frame = {"lead": "Kurz", "gist": ["Eins.", "Zwei."], "formula": {"key": "y = a + bx", "text": "t"},
             "design": "magazine",
             "hero_prompt": "a desk", "section_image": {"section_index": 1, "prompt": "a lamp"}}
    page = pl.draft(plan, blocks, frame, sources=[_source("Skript.pdf", stuff)], language="German")
    ids = [s["id"] for s in page["sections"]]
    assert ids == [pl.COVER_ID, "top", "gist", "map", "s1", "s2", "s3", "s4", "words"]
    assert page["sections"][0]["blocks"][0]["src"] == pl.HERO_IMAGE
    # One picture per page, at the top, an older frame's section picture is left out.
    assert [b["src"] for x in page["sections"] for b in x["blocks"] if b["kind"] == "image"] == [pl.HERO_IMAGE]
    assert page["footer"] == ""
    done = pl.finish(schema.clean_page(page), today=__import__("datetime").date(2026, 10, 8))
    # The page names no source.
    assert done["sections"][1]["meta"].startswith("Erstellt mit KI am 08.10.2026, etwa ")
    assert "Skript" not in done["sections"][1]["meta"]


def test_long_highlight_key_becomes_text_and_dashes_go():
    b = schema.clean_block({"kind": "highlight", "key": "Tägliche Höchstarbeitszeit 8 Stunden, Verlängerung bis 10 Stunden", "text": "Gilt immer"})
    assert b["key"] == "" and b["text"].startswith("Tägliche Höchstarbeitszeit")
    assert schema.text("Arbeitszeitgesetz – Überblick", 120) == "Arbeitszeitgesetz: Überblick"
    assert schema.text("lang – aber gut", 120) == "lang, aber gut"
    assert pl._short_title("Arbeitszeitgesetz: Überblick für Studierende") == "Arbeitszeitgesetz"


def test_cards_once_no_highlight_box_and_the_design_is_kept():
    plan = Outline(title="T", intro="I.", sections=[Section(title=f"S{i}") for i in range(4)])
    cards = {"kind": "cards", "cards": [{"title": "A", "text": "a"}, {"title": "B", "text": "b"}]}
    hl = {"kind": "highlight", "key": "y = a + bx", "text": "Gerade"}
    blocks = {i: {"lead": "", "blocks": [dict(cards), dict(hl)], "keywords": []} for i in range(4)}
    page = pl.draft(plan, blocks, {"formula": {"key": "Risikowert", "text": "W mal A"}, "design": "guide",
                                   "hero_prompt": "a desk"},
                    sources=[_source("a.pdf", "t")], language="German")
    kinds = [b["kind"] for s in page["sections"] for b in s["blocks"]]
    assert "highlight" not in kinds
    assert kinds.count("cards") == 1 and kinds.count("formula") == 1
    # A frame formula without a sign is a term, it becomes a definition.
    assert page["sections"][2]["blocks"][1] == {"kind": "definitions", "items": [{"term": "Risikowert", "text": "W mal A"}]}
    assert page["design"] == "guide"
    # Every page opens with its picture as a section of its own above the title.
    assert page["sections"][0]["id"] == pl.COVER_ID
    assert [b["src"] for b in page["sections"][0]["blocks"]] == [pl.HERO_IMAGE]
    assert page["sections"][1]["hero"] is True and page["sections"][1]["blocks"] == []
    assert schema.clean_block({"kind": "text", "text": "Ein Satz."}) == {"kind": "text", "text": "Ein Satz."}


def test_own_picture_style_replaces_the_default():
    assert pl.image_prompt("a desk", "Watercolour, soft greens.").startswith("Watercolour, soft greens. Subject: a desk")
    assert pl.image_prompt("a desk").startswith(pl.default_image_style())


def test_page_as_text_keeps_sections_and_spells_out_charts():
    from doc2pages import text as pt
    page = schema.clean_page(_page(
        {"id": "top", "hero": True, "title": "T", "lead": "L", "meta": "Erstellt mit KI"},
        {"id": "s1", "title": "Messwerte", "blocks": [{"kind": "chart", "chart_type": "line", "caption": "Punkte",
            "categories": ["2", "4", "6"], "series": [{"name": "Gemessen", "values": [18, 30, 32.5]}]}]},
        {"id": "s2", "title": "Versteckt", "hidden": True, "blocks": [{"kind": "text", "text": "geheim"}]},
        {"id": "map", "title": "Karte", "blocks": []}))
    parts = pt.parts(page)
    assert [p.anchor for p in parts] == ["top", "s1"]
    assert "Gemessen: 2: 18, 4: 30, 6: 32,5" in parts[1].text
    assert "geheim" not in pt.as_text(page)


def test_a_page_gets_its_picture_from_the_title_when_the_frame_names_none():
    plan = Outline(title="Arbeitszeitgesetz", intro="Regeln.", sections=[Section(title="Pausen")])
    blocks = {0: {"lead": "", "blocks": [{"kind": "text", "text": "Nach sechs Stunden Pause."}], "keywords": []}}
    page = pl.draft(plan, blocks, {"design": "chapters", "hero_prompt": ""},
                    sources=[_source("AZG.pdf", "Pause")], language="German")
    picture = page["sections"][0]["blocks"][0]
    assert page["sections"][0]["id"] == pl.COVER_ID
    assert picture["src"] == pl.HERO_IMAGE and "Arbeitszeitgesetz" in picture["prompt"]
    assert page["sections"][1]["hero"] is True and page["sections"][1]["blocks"] == []


def test_new_kinds_are_cleaned_to_their_shape():
    c = schema.clean_block
    assert c({"kind": "cycle", "center": "PDCA", "steps": [{"title": "Plan"}, {"title": "Do"}]})["kind"] == "steps"
    assert c({"kind": "timeline", "events": [{"date": "1957", "title": "CPM"}, {"title": "ohne Datum"}]}) is None
    v = c({"kind": "versus", "tone": "schlimm", "a": {"title": "A", "items": ["x"]}, "b": {"title": "B", "items": ["y"]}})
    assert v["tone"] == "neutral"
    m = c({"kind": "matrix", "x": "Interesse", "y": "Einfluss", "points": [{"label": "P", "x": 3, "y": "0,5"}],
           "cells": [{"pos": q, "title": q} for q in ("br", "tl", "tr", "bl")]})
    assert [x["pos"] for x in m["cells"]] == ["tl", "tr", "bl", "br"] and m["points"] == [{"label": "P", "x": 1.0, "y": 0.5}]
    s = c({"kind": "scale", "left": "a", "right": "b", "items": [{"label": "y", "pos": 0.9}, {"label": "x", "pos": 0.1}]})
    assert [x["label"] for x in s["items"]] == ["x", "y"]
    assert c({"kind": "formula", "key": "E = m c²", "text": "Energie"})["kind"] == "formula"
    assert c({"kind": "example", "title": "T", "result": "R"}) is None
    assert c({"kind": "chart", "chart_type": "pie", "categories": ["a", "b"],
              "series": [{"values": [1, 2]}, {"values": [3, 4]}]})["series"] == [{"name": "", "values": [1.0, 2.0]}]


def test_bare_chapter_numbers_are_cut_years_and_formulas_stay():
    away = pl.drop_citations
    assert away("Es gibt 620 Sitzplätze (2.1).", set()) == "Es gibt 620 Sitzplätze."
    assert away("Zwei Drittel aus Landesmitteln (1)", set()) == "Zwei Drittel aus Landesmitteln"
    assert away("Das Manifest (2001) gilt.", set()) == "Das Manifest (2001) gilt."
    assert away("Der Wert (n = 30) reicht.", set()) == "Der Wert (n = 30) reicht."


def test_prose_comes_first_and_one_block_shows_it():
    text, shows = pl._prose_first([
        {"kind": "steps", "steps": [{"title": "A", "text": "a"}]},
        {"kind": "text", "text": "Erster Satz. Zweiter Satz."},
        {"kind": "table", "header": ["", "x"], "rows": [["a", "b"]]},
        {"kind": "text", "text": "Dritter Satz."},
    ])
    assert text == "Erster Satz. Zweiter Satz. Dritter Satz."
    assert [b["kind"] for b in shows] == ["steps"]
    assert pl._sentences("Eins ist kurz. Zwei ist auch kurz. Drei passt nicht mehr.", 40) == "Eins ist kurz. Zwei ist auch kurz."


def test_a_formula_stands_once():
    gist = [{"kind": "formula", "key": "E = (O + 4M + P) / 6", "text": "a"}]
    section = [{"kind": "text", "text": "T."}, {"kind": "formula", "key": "E=(O+4M+P)/6", "text": "b"}]
    pl._once([gist, section])
    assert [b["kind"] for b in section] == ["text"]
