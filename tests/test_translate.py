"""A page carried into its other language, and the grid sections the schema keeps."""

import asyncio
import json
from types import SimpleNamespace

from doc2pages import schema
from doc2pages import translate as tr
from doc2pages.limits import PAGES_MAX_ITEM_CHARS, PAGES_MAX_LONG_CHARS


def _page(*sections, **extra):
    return {"sections": list(sections), **extra}


def test_layout_keeps_every_field_in_its_place():
    page = schema.clean_page(_page({"id": "n1", "title": "Neu", "layout": "3", "blocks": [
        {"kind": "empty"}, {"kind": "bullets", "items": ["a"]}, {"kind": "script"},
        {"kind": "text", "text": "x"}]}))
    s = page["sections"][0]
    assert s["layout"] == "3"
    assert [b["kind"] for b in s["blocks"]] == ["empty", "bullets", "empty"]


def test_layout_pads_missing_fields_and_unknown_layout_is_dropped():
    page = schema.clean_page(_page(
        {"id": "n1", "title": "Neu", "layout": "4", "blocks": [{"kind": "text", "text": "x"}]},
        {"id": "n2", "title": "Alt", "layout": "9",
         "blocks": [{"kind": "empty"}, {"kind": "text", "text": "y"}]}))
    assert [b["kind"] for b in page["sections"][0]["blocks"]] == ["text", "empty", "empty", "empty"]
    assert "layout" not in page["sections"][1]
    assert page["sections"][1]["blocks"] == [{"kind": "text", "text": "y"}]


def test_an_untouched_new_section_without_text_goes():
    page = schema.clean_page(_page({"id": "n1", "title": "", "layout": "2", "blocks": []},
                                   {"id": "s1", "title": "Bleibt", "blocks": []}))
    assert [s["id"] for s in page["sections"]] == ["s1"]


def test_a_page_is_german_or_english():
    assert schema.clean_page(_page({"title": "T"}, lang="en"))["lang"] == "en"
    assert schema.clean_page(_page({"title": "T"}, lang="uk"))["lang"] == "de"
    assert "easy" not in schema.clean_page(_page({"title": "T"}, lang="de", easy=True))


def test_the_other_language_is_english_for_german_and_german_for_english():
    assert tr.other_language({"lang": "de"}) == "en"
    assert tr.other_language({"lang": "en"}) == "de"
    assert set(tr.LANGUAGES) == {"de", "en"}


SAMPLE = schema.clean_page(_page(
    {"id": "top", "hero": True, "title": "Regression", "lead": "Ein Überblick.",
     "meta": "Erstellt mit KI",
     "blocks": [{"kind": "image", "src": "img_0.webp", "alt": "Bild", "prompt": "flat", "caption": ""}]},
    {"id": "s1", "title": "Gerade", "lead": "", "blocks": [
        {"kind": "text", "text": "Die Gerade passt."},
        {"kind": "chart", "chart_type": "bar", "caption": "Werte", "x_label": "Jahr", "y_label": "",
         "categories": ["2020", "2021"], "series": [{"name": "", "values": [1, 2]}]},
        {"kind": "highlight", "key": "y = a + bx", "text": "Die Formel."}]},
    {"id": "words", "title": "Wörter", "lead": "", "blocks": [
        {"kind": "wordcloud", "caption": "", "words": [["Gerade", 3], ["Wert", 2], ["Fehler", 1]]}]},
    lang="de"))


def test_texts_leave_pictures_numbers_and_ids_alone():
    found = dict(tr.texts(SAMPLE))
    values = set(found.values())
    assert "Regression" in values and "Die Gerade passt." in values and "Gerade" in values
    assert "img_0.webp" not in values and "flat" not in values
    assert "s1" not in values and "bar" not in values
    assert not any(isinstance(v, (int, float)) for v in values)


def test_limits_follow_the_place_of_a_text():
    texts = dict(tr.texts(SAMPLE))
    by_text = {v: k for k, v in texts.items()}
    assert tr._limit(SAMPLE, by_text["Die Gerade passt."]) == PAGES_MAX_LONG_CHARS
    assert tr._limit(SAMPLE, by_text["Die Formel."]) == PAGES_MAX_ITEM_CHARS
    assert tr._limit(SAMPLE, by_text["2020"]) == schema.CHART_LABEL_CHARS
    assert tr._limit(SAMPLE, by_text["Fehler"]) == schema.MAP_LABEL_CHARS


class _FakeCaller:
    """Answers like a model that drops one key in a batch and gets it right alone."""

    def __init__(self):
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        data = json.loads(kwargs["messages"][1]["content"].split("\n\n", 1)[1])
        answer = {k: "EN " + v["text"] for k, v in data.items()}
        if len(data) > 1:
            answer.pop("1")
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(answer)))])


def test_translate_puts_every_text_back_and_asks_again_for_a_dropped_one():
    caller = _FakeCaller()
    fresh = asyncio.run(tr.translate(caller, SAMPLE, "en"))
    assert fresh["lang"] == "en" and "easy" not in fresh
    assert fresh["sections"][0]["title"] == "EN Regression"
    assert fresh["sections"][1]["blocks"][0]["text"] == "EN Die Gerade passt."
    assert fresh["sections"][1]["blocks"][1]["series"][0]["values"] == [1.0, 2.0]
    assert fresh["sections"][0]["blocks"][0]["src"] == "img_0.webp"
    assert [s["id"] for s in fresh["sections"]] == [s["id"] for s in SAMPLE["sections"]]
    # The same texts at the same places, nothing left in the source language.
    assert all(v.startswith("EN ") for _, v in tr.texts(fresh))
