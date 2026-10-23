"""The drawings keep inside their boxes: sizes, coordinates and overlaps are measured here.

A label that is wider than its pill, an element outside the viewBox or a font size the
stylesheet overrides is a defect a reader sees at once and no string assertion catches.
"""

import re

from doc2pages import schema
from doc2pages.output import Page, write_pages
from doc2pages.render import CSS, _mm_center_lines, _mm_label, block_html

# The widths the stylesheet draws with, the same numbers the renderer plans with.
NODE_CHAR = 7.4
CENTER_CHAR = 8.4
CENTER_FIT = 86.0

_VIEWBOX = re.compile(r'viewBox="0 0 ([\d.]+) ([\d.]+)"')
_RECT = re.compile(r'<rect class="mm-node" x="(-?[\d.]+)" y="(-?[\d.]+)" '
                   r'width="([\d.]+)" height="(\d+)"')
_TEXT = re.compile(r'<text class="([\w -]+)" x="(-?[\d.]+)" y="(-?[\d.]+)"([^>]*)>([^<]*)</text>')
_FONT_SIZE = re.compile(r'font-size:\s*([\d.]+)px')


def _svg(block: dict) -> str:
    cleaned = schema.clean_block(block)
    assert cleaned is not None
    return block_html(cleaned)


def _box(svg: str) -> tuple[float, float]:
    width, height = _VIEWBOX.search(svg).groups()
    return float(width), float(height)


def _mindmap(center: str, titles: list[str]) -> str:
    return _svg({"kind": "mindmap", "center": center, "caption": "Karte",
                 "branches": [{"title": title, "to": f"s{i + 1}", "leaves": []}
                              for i, title in enumerate(titles)]})


def test_every_mind_map_pill_stays_inside_the_picture_and_keeps_its_own_room():
    """Eight long branch titles: no pill leaves the box and no two pills overlap."""
    titles = [f"Grundlagen der Messreihen {i:02d}" for i in range(8)]
    assert all(len(t) == 28 for t in titles)
    svg = _mindmap("Lineare Regression", titles)
    width, height = _box(svg)

    pills = [tuple(float(v) for v in m.groups()) for m in _RECT.finditer(svg)]
    assert len(pills) == 8
    for x, y, w, h in pills:
        assert 0 <= x and x + w <= width, (x, w, width)
        assert 0 <= y and y + h <= height, (y, h, height)
    for i, (ax, ay, aw, ah) in enumerate(pills):
        for bx, by, bw, bh in pills[i + 1:]:
            apart = ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay
            assert apart, ((ax, ay, aw, ah), (bx, by, bw, bh))

    # Every label fits into the pill that was drawn for it.
    for match in _TEXT.finditer(svg):
        if match.group(1) != "mm-node-text":
            continue
        middle, label = float(match.group(2)), match.group(5)
        pill = next(p for p in pills if p[0] <= middle <= p[0] + p[2])
        assert len(label) * NODE_CHAR <= pill[2], (label, pill)


def test_a_mind_map_label_is_cut_between_words_and_says_so():
    assert _mm_label("Kurz", 28) == "Kurz"
    long_one = _mm_label("Die lineare Regression und ihre Grenzen", 28)
    assert len(long_one) <= 28
    assert long_one.endswith("…")
    assert not long_one[:-1].endswith(" ")
    assert long_one[:-1] in "Die lineare Regression und ihre Grenzen"
    # A single word without a space is cut inside the word, still within the limit.
    single = _mm_label("Konfigurationsmanagementsystem", 18)
    assert len(single) == 18 and single.endswith("…")
    # A cut between words that would keep less than half the room cuts the word instead.
    pair = _mm_label("Grundlagen Versionsverwaltung", 28)
    assert pair == "Grundlagen Versionsverwaltu…"
    assert len(pair) <= 28


def test_the_centre_label_really_is_drawn_at_the_size_that_fits():
    """The size the renderer computes has to beat the stylesheet, not lose to it."""
    # Nothing in the stylesheet may set a size for the class the renderer sizes itself.
    rule = next(line for line in CSS.splitlines() if line.startswith("svg .mm-center-text"))
    assert "font-size" not in rule

    svg = _mindmap("Konfigurationsmanagement", ["A", "B", "C"])
    labels = [m for m in _TEXT.finditer(svg) if m.group(1) == "mm-center-text"]
    assert labels
    for match in labels:
        size = float(_FONT_SIZE.search(match.group(4)).group(1))
        assert size <= 15.0
        width = len(match.group(5)) * CENTER_CHAR * size / 15.0
        assert width <= CENTER_FIT, (match.group(5), width)


def test_a_long_compound_centre_word_is_broken_before_it_is_shrunk():
    lines, size = _mm_center_lines("Lineare Regression")
    assert lines == ["Lineare", "Regression"] and size == 15.0
    lines, size = _mm_center_lines("Konfigurationsmanagement")
    assert len(lines) == 1 and lines[0].endswith("…")
    assert size >= 9.0
    assert len(lines[0]) * CENTER_CHAR * size / 15.0 <= CENTER_FIT


def test_no_word_of_a_cloud_starts_left_of_the_picture():
    words = [[f"Datenverarbeitungsanlagenbetrieb{i:02d}", 10 - (i % 10)] for i in range(24)]
    assert all(len(w[0]) == 34 for w in words)
    svg = _svg({"kind": "wordcloud", "caption": "Wolke", "words": words})
    width, _ = _box(svg)
    drawn = re.findall(r'<text class="cw cw\d" x="([\d.-]+)" y="[\d.]+" font-size="([\d.]+)"'
                       r'[^>]*>([^<]*)</text>', svg)
    assert len(drawn) == 24
    for x, size, word in drawn:
        half = len(word) * float(size) * 0.58 / 2
        assert float(x) - half >= 0, (word, x)
        assert float(x) + half <= width, (word, x)


def test_a_keyword_that_reads_like_an_entity_marks_the_word_and_not_the_entity():
    html = _svg({"kind": "quote", "text": "R&D treibt das amp hoch.", "keyword": "amp"})
    assert "R&amp;D treibt das <b>amp</b> hoch." in html
    assert "R&<b>amp</b>;D" not in html


def test_a_pin_at_the_edge_of_a_scale_keeps_its_label_in_the_panel():
    html = _svg({"kind": "scale", "caption": "Lage", "left": "kalt", "right": "warm",
                 "items": [{"label": "ganz links", "pos": 0.0},
                           {"label": "mitte", "pos": 0.5},
                           {"label": "ganz rechts", "pos": 1.0}]})
    shifts = re.findall(r"transform:translateX\(-(\d+)%\)", html)
    assert shifts == ["0", "50", "100"]


def test_two_pages_with_the_same_title_and_a_title_without_latin_letters(tmp_path):
    def page(title: str) -> Page:
        data = schema.clean_page({"lang": "de", "sections": [
            {"id": "top", "hero": True, "title": title, "lead": "Kurz", "blocks": []},
            {"id": "s1", "title": "Teil", "blocks": [{"kind": "text", "text": "Ein Satz."}]}]})
        return Page(data=data, title=title)

    folders = write_pages([page("Lineare Regression"), page("Lineare Regression"),
                           page("机器学习导论")], tmp_path)
    names = [f.name for f in folders]
    assert len(set(names)) == 3, names
    assert names[0] == "lineare-regression"
    # A title with no Latin letters keeps no name of its own, it still gets its own folder.
    assert names[2].startswith("page-")
    overview = (tmp_path / "index.html").read_text(encoding="utf-8")
    for name in names:
        assert f"{name}/index.html" in overview
    assert "机器学习导论" in overview
