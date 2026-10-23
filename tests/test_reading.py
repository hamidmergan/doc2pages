"""Real documents go through the readers: PDF, DOCX, PPTX, SRT and VTT.

The header and footer detection is the most fragile part of the reading side, because it
decides by what repeats over a whole document. A text file can never trigger it, so these
tests build small real documents and read them back.
"""

from doc2pages import extract
from doc2pages.pdf_layout import (
    LineBox,
    _is_page_number,
    _norm,
    boilerplate_keys,
    merge_rows,
    page_reading_order,
    strip_furniture,
)
from doc2pages.source_reading import count_pages, read_file

from conftest import make_pdf


# --- The layout helpers on their own --------------------------------------------------

def test_a_running_header_compares_equal_whatever_its_page_number_says():
    assert _norm("Kapitel 3 | Seite 4 von 12") == _norm("Kapitel 3 | Seite 7 von 12")
    assert _norm("Kapitel 3 | Page 4 of 12") == _norm("Kapitel 3 | Seite 7 von 12")
    # Two different headers still differ.
    assert _norm("Kapitel 3 | Seite 4 von 12") != _norm("Kapitel 4 | Seite 4 von 12")


def test_a_line_that_is_only_a_page_counter_is_recognised():
    for text in ("- 3 -", "Seite 3 von 12", "Page 3 of 12", "3 / 12", "Folie 7", "12"):
        assert _is_page_number(text), text
    for text in ("Kapitel 3", "Die Steigung betraegt 3.", "3 Wege zum Ziel"):
        assert not _is_page_number(text), text


def test_boilerplate_keys_find_the_repeating_footer_and_leave_the_body_alone():
    pages = []
    for n in range(1, 6):
        pages.append([LineBox(text=f"Vorlesung Statistik | Seite {n} von 5", x=72, y=800),
                      LineBox(text=f"Kapitel {n}: Die Messwerte", x=72, y=740),
                      LineBox(text=f"Die Steigung betraegt {n}.", x=72, y=710),
                      LineBox(text="Hochschule fuer Beispiele", x=72, y=60)])
    keys = boilerplate_keys(pages)
    assert _norm("Vorlesung Statistik | Seite 2 von 5") in keys
    assert _norm("Hochschule fuer Beispiele") in keys
    assert _norm("Kapitel 2: Die Messwerte") not in keys
    assert _norm("Die Steigung betraegt 2.") not in keys
    # Under four pages "stands on most pages" says nothing, so nothing is dropped.
    assert boilerplate_keys(pages[:3]) == set()


def test_a_footer_that_arrives_in_pieces_is_dropped_with_its_leftovers():
    boxes = [LineBox(text="Kapitel 2: Die Messwerte", x=72, y=740),
             LineBox(text="Die Steigung betraegt 2.", x=72, y=710),
             LineBox(text="Hochschule fuer Beispiele", x=72, y=60),
             LineBox(text="2", x=300, y=60),
             LineBox(text="von", x=320, y=61),
             LineBox(text="5", x=350, y=60)]
    kept = [b.text for b in strip_furniture(boxes, {_norm("Hochschule fuer Beispiele")})]
    assert kept == ["Kapitel 2: Die Messwerte", "Die Steigung betraegt 2."]


def test_a_lone_bullet_glyph_joins_the_line_under_it():
    boxes = [LineBox(text="•", x=60, y=700), LineBox(text="Der erste Punkt", x=72, y=700),
             LineBox(text="•", x=60, y=680), LineBox(text="Der zweite Punkt", x=72, y=680)]
    assert [b.text for b in merge_rows(boxes)] == ["• Der erste Punkt", "• Der zweite Punkt"]


def test_the_reading_order_runs_top_to_bottom_and_then_left_to_right():
    boxes = [LineBox(text="rechts oben", x=400, y=700), LineBox(text="links oben", x=72, y=700),
             LineBox(text="unten", x=72, y=600)]
    assert [b.text for b in page_reading_order(boxes)] == ["links oben", "rechts oben", "unten"]


# --- The readers on a real file -------------------------------------------------------

def test_a_pdf_is_read_page_by_page_without_its_header_and_footer(lecture_pdf):
    assert count_pages(".pdf", str(lecture_pdf)) == 5
    source = read_file(lecture_pdf)
    assert source.pages == 5
    assert source.name == "vorlesung.pdf"
    assert "Kapitel 1: Die Messwerte" in source.text
    assert "Kapitel 5: Die Messwerte" in source.text
    # The running header, its page counter and the footer are gone.
    assert "Vorlesung Statistik" not in source.text
    assert "Seite 3 von 5" not in source.text
    assert "Hochschule fuer Beispiele" not in source.text
    # Every piece knows a page, and the pages run from the first to the last.
    assert {p.page for p in source.pieces} <= set(range(1, 6))
    assert source.pieces[0].page == 1


def test_a_pdf_without_a_text_layer_is_refused_rather_than_guessed_at(tmp_path):
    from doc2pages.errors import NoReadableText

    path = tmp_path / "scan.pdf"
    path.write_bytes(make_pdf([[], [], []]))
    try:
        read_file(path)
    except NoReadableText as e:
        assert "no readable text" in str(e)
    else:
        raise AssertionError("a PDF with no text layer has to be refused")


def test_a_docx_keeps_its_heading_and_its_paragraphs(lecture_docx):
    source = read_file(lecture_docx)
    assert source.pages == 1
    assert source.text.startswith("Lineare Regression")
    assert source.text.count("Abschnitt") == 3
    # The format has no pages, so nothing pretends to count them.
    assert count_pages(".docx", str(lecture_docx)) is None


def test_a_pptx_becomes_one_page_without_the_line_that_stands_on_every_slide(lecture_pptx):
    assert count_pages(".pptx", str(lecture_pptx)) == 5
    source = read_file(lecture_pptx)
    assert source.pages == 1
    for n in range(1, 6):
        assert f"Folie {n}: Die Messwerte" in source.text
    assert "Hochschule fuer Beispiele" not in source.text


def test_subtitles_lose_their_counters_and_time_codes(lecture_srt, lecture_vtt):
    srt = read_file(lecture_srt)
    assert "-->" not in srt.text and "00:00:" not in srt.text
    assert "Die Steigung betraegt 1 und der Achsenabschnitt 0." in srt.text
    assert srt.text.count("Die Steigung") == 5

    vtt = read_file(lecture_vtt)
    assert "-->" not in vtt.text and "WEBVTT" not in vtt.text
    assert "NOTE" not in vtt.text
    assert vtt.text.count("Die Gerade") == 5


def test_every_supported_format_has_a_reader():
    from doc2pages.source_reading import EXTENSIONS

    readable = set(extract.EXTRACTORS) | {".pdf"}
    assert set(EXTENSIONS) == readable


def test_markdown_loses_its_markup_and_keeps_its_words():
    text = ("# Titel\n\nEin **fetter** Satz mit `Code` und einem [Link](http://x).\n\n"
            "```python\nprint(1)\n```\n\n---\n\n![Bild](bild.png)\n\nLetzter Satz.\n")
    out = extract.extract_text_md(text.encode("utf-8"))
    assert out.startswith("Titel")
    assert "fetter" in out and "**" not in out
    assert "Link" in out and "http://x" not in out
    assert "print(1)" not in out and "Code" not in out
    assert "bild.png" not in out
    assert out.endswith("Letzter Satz.")


def test_markdown_in_an_older_encoding_is_read_and_not_refused(tmp_path):
    """The other text readers replace a broken sign, Markdown now does the same."""
    path = tmp_path / "kapitel.md"
    path.write_bytes("# Kapitel\n\nDie Gerade entsteht aus den Messwerten.\n"
                     .encode("latin-1") + "Ausreißer kippen sie.\n".encode("latin-1"))
    source = read_file(path)
    assert "Die Gerade entsteht aus den Messwerten." in source.text
    assert source.text.startswith("Kapitel")
