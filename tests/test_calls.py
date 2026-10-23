"""A page costs few model calls: the frame rides on the plan, repairs and translations go in bulk."""

import asyncio
import json
from types import SimpleNamespace

from doc2pages import pipeline as pl
from doc2pages import planning as sw
from doc2pages import translate as tr
from doc2pages import writing as pw
from doc2pages import text_map as tm
from doc2pages.models import Outline, Section
from doc2pages.source_reading import from_text

_TEXT = " ".join(f"Satz {i} erklärt den Gegenstand der Vorlesung ausführlich und genau."
                 for i in range(60))


class _Store:
    def __init__(self):
        self.blocks: dict[int, dict] = {}

    def progress(self, *a, **k):
        pass

    def load_blocks(self):
        return dict(self.blocks)

    def save_blocks(self, i, data):
        self.blocks[i] = data


def _plan(n: int) -> Outline:
    return Outline(title="T", intro="I", sections=[
        Section(title=f"Abschnitt {i}", scope="s", spots=[1]) for i in range(n)])


def _block(i: int, sentences: int = 3) -> dict:
    text = " ".join(f"Satz {k} zu Abschnitt {i}." for k in range(sentences))
    return {"lead": "l", "map_label": "m", "keywords": [],
            "blocks": [{"kind": "text", "text": text}]}


def _run(plan, monkeypatch, answers, prose=None):
    """Runs the block stage with scripted answers, returns the calls it made."""
    calls = []

    async def write_blocks(caller, *, indices, **kw):
        calls.append(("blocks", list(indices)))
        return answers(list(indices))

    async def write_sections(caller, *, group, **kw):
        calls.append(("prose", [s.title for s in group]))
        return prose(group) if prose else ["Ein Satz. Noch ein Satz. Und ein dritter."] * len(group)

    monkeypatch.setattr(pl, "write_blocks", write_blocks)
    monkeypatch.setattr(pl.planning, "write_sections", write_sections)
    text_map = tm.TextMap([from_text("a.txt", _TEXT)])
    store = _Store()
    caller = SimpleNamespace(window_tokens=0)
    done = asyncio.run(pl._blocks(caller, language="German", plan=plan, text_map=text_map,
                                  store=store, should_stop=None, instructions=""))
    return done, calls


def test_several_sections_share_one_call(monkeypatch):
    done, calls = _run(_plan(8), monkeypatch, lambda idx: [_block(i) for i in idx])
    assert len(done) == 8
    assert [c for c in calls if c[0] == "blocks"] == [("blocks", [0, 1, 2, 3, 4]), ("blocks", [5, 6, 7])]


def test_missing_sections_come_back_in_one_call(monkeypatch):
    first = {"n": 0}

    def answers(idx):
        first["n"] += 1
        # The first calls drop every odd section, the repair call delivers them all.
        return [_block(i) if (i % 2 == 0 or first["n"] > 2) else None for i in idx]

    done, calls = _run(_plan(8), monkeypatch, answers)
    assert len(done) == 8
    assert calls[-1] == ("blocks", [1, 3, 5, 7])
    assert len(calls) == 3


def test_what_is_still_missing_becomes_text_in_one_call(monkeypatch):
    done, calls = _run(_plan(4), monkeypatch, lambda idx: [None for _ in idx])
    assert len(done) == 4
    assert [c[0] for c in calls] == ["blocks", "blocks", "prose"]
    assert all(done[i]["blocks"] for i in range(4))


def test_too_short_a_text_is_rewritten_for_all_in_one_call(monkeypatch):
    done, calls = _run(_plan(4), monkeypatch,
                       lambda idx: [_block(i, sentences=1 if i in (1, 2) else 3) for i in idx])
    assert calls[-1] == ("prose", ["Abschnitt 1", "Abschnitt 2"])
    assert len(calls) == 2
    assert done[1]["blocks"][0]["text"].startswith("Ein Satz.")


def test_the_frame_comes_out_of_the_outline():
    schema = sw.outline_schema(pw.FRAME_FIELDS)["json_schema"]["schema"]
    assert {"lead", "gist", "hero_prompt"} <= set(schema["required"])
    assert "lead" not in sw.OUTLINE_SCHEMA["json_schema"]["schema"]["properties"]

    answer = json.dumps({
        "title": "Titel", "intro": "Intro.", "documents": [],
        "sections": [{"section_index": i, "title": f"A{i}", "description": "d", "refs": [], "start": ""}
                     for i in range(4)],
        "lead": "Worum es geht.", "gist": ["Eins.", "Zwei.", "Drei."],
        "formula": {"key": "", "text": ""}, "design": "chapters",
        "hero_prompt": "a calm scene", "hero_alt": "Ein Bild.",
    })
    plan = sw.parse_outline(answer, extra=list(pw.FRAME_FIELDS))
    frame = pw.frame_from_plan(plan.extra)
    assert frame["lead"] == "Worum es geht."
    assert frame["formula"] is None
    assert pw.frame_from_plan({}) == {}


def test_a_translation_packs_sections_together():
    items = [(("sections", s, "blocks", 0, "text"), "x" * 500) for s in range(10) for _ in range(2)]
    batches = tr._batches(items)
    assert len(batches) == 2
    # A section never splits between two calls.
    for b in batches:
        assert len({p[1] for p, _ in b}) * 2 == len(b)


def test_forgotten_texts_go_again_together(monkeypatch):
    asked = []

    async def ask(caller, system, page, batch):
        asked.append(len(batch))
        if len(asked) == 1:
            return {str(i): "übersetzt" for i in range(1, len(batch) + 1) if i % 3}
        return {str(i): "übersetzt" for i in range(1, len(batch) + 1)}

    monkeypatch.setattr(tr, "_ask", ask)
    page = {"lang": "de", "sections": [{"id": f"s{i}", "title": f"Titel {i}", "lead": "", "blocks": [
        {"kind": "text", "text": f"Text {i}"}]} for i in range(6)]}
    monkeypatch.setattr(tr.schema, "clean_page", lambda p: p)
    fresh = asyncio.run(tr.translate(None, page, "en"))
    assert len(asked) == 2
    assert all(s["title"] == "übersetzt" for s in fresh["sections"])


def test_an_answer_in_the_shape_of_the_request_counts():
    async def create(**kw):
        content = '```json\n{"1": {"text": "Hello", "max_chars": 40}, "2": "World"}\n```'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    page = {"sections": [{"title": "Hallo", "lead": "Welt", "blocks": []}]}
    caller = SimpleNamespace(create=create)
    answer = asyncio.run(tr._ask(caller, "s", page, [(("sections", 0, "title"), "Hallo"),
                                                     (("sections", 0, "lead"), "Welt")]))
    assert answer == {"1": "Hello", "2": "World"}
