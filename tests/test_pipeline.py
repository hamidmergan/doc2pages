"""One whole run against the fake server: structure, pictures, translation and output."""

import json
from datetime import date
from pathlib import Path

import pytest

from doc2pages import make_pages
from doc2pages.errors import ConfigError, LimitError


def _run(server, material, **kw):
    return make_pages([material], base_url=server.base_url, model="your-model",
                      today=date(2026, 10, 8), **kw)


def test_a_page_has_cover_title_gist_and_its_sections(server, material):
    pages = _run(server, material)
    assert len(pages) == 1
    page = pages[0].data
    ids = [s["id"] for s in page["sections"]]
    # Without a picture the cover section has nothing left and goes.
    assert ids[:3] == ["top", "gist", "map"]
    assert page["lang"] == "de"
    assert page["design"] == "chapters"
    titles = [s["title"] for s in page["sections"] if s["id"].startswith("s")]
    assert titles == ["Grundbegriffe", "Vorgehen", "Beispiel mit Zahlen", "Grenzen"]
    # Without --images the named picture leaves the page instead of standing empty.
    assert not [b for s in page["sections"] for b in s["blocks"] if b["kind"] == "image"]
    assert pages[0].title == "Lineare Regression"


def test_the_reading_time_line_stands_under_the_title(server, material):
    page = _run(server, material)[0].data
    hero = next(s for s in page["sections"] if s.get("hero"))
    assert hero["meta"].startswith("Erstellt mit KI am 08.10.2026, etwa ")


def test_the_frame_rides_on_the_plan(server, material):
    _run(server, material)
    systems = [r["body"]["messages"][0]["content"] for r in server.requests]
    assert not any("You write the frame" in s for s in systems)


def test_pictures_are_drawn_and_written_next_to_the_page(server, material, tmp_path):
    out = tmp_path / "out"
    pages = _run(server, material, output_dir=out, images=True)
    page = pages[0].data
    cover = page["sections"][0]
    assert cover["blocks"][0]["kind"] == "image"
    assert server.images and server.images[0]["size"] == "1536x656"
    folder = out / "lineare-regression"
    assert (folder / "img_0.webp").read_bytes().startswith(b"RIFF")
    assert "img_0.webp" in (folder / "index.html").read_text(encoding="utf-8")


def test_a_picture_that_fails_leaves_the_page(server, material):
    server.fail_images = True
    page = _run(server, material, images=True)[0].data
    assert not [b for s in page["sections"] for b in s["blocks"] if b["kind"] == "image"]


def test_a_translation_is_a_page_of_its_own(server, material, tmp_path):
    out = tmp_path / "out"
    pages = _run(server, material, output_dir=out, translate_to="en")
    assert len(pages) == 2
    second = pages[1].data
    assert second["lang"] == "en"
    assert second["sections"][0]["title"].startswith("EN ")
    assert [s["id"] for s in second["sections"]] == [s["id"] for s in pages[0].data["sections"]]
    assert (out / "index.html").exists()
    assert len(list(p for p in out.iterdir() if p.is_dir())) == 2


def test_the_output_folder_carries_html_markdown_and_json(server, material, tmp_path):
    out = tmp_path / "out"
    _run(server, material, output_dir=out)
    folder = out / "lineare-regression"
    html = (folder / "index.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "Lineare Regression" in html
    assert (folder / "page.md").read_text(encoding="utf-8").startswith("# Lineare Regression")
    data = json.loads((folder / "page.json").read_text(encoding="utf-8"))
    assert data["version"] == 1
    overview = (out / "index.html").read_text(encoding="utf-8")
    assert "lineare-regression/index.html" in overview


def test_markdown_only_writes_no_html(server, material, tmp_path):
    out = tmp_path / "out"
    _run(server, material, output_dir=out, markdown_only=True)
    folder = out / "lineare-regression"
    assert (folder / "page.md").exists() and not (folder / "index.html").exists()


def test_combine_makes_one_page_out_of_several_files(server, material, tmp_path):
    second = tmp_path / "second.txt"
    second.write_text(material.read_text(encoding="utf-8"), encoding="utf-8")
    apart = make_pages([material, second], base_url=server.base_url, model="your-model")
    together = make_pages([material, second], base_url=server.base_url, model="your-model",
                          combine=True)
    assert len(apart) == 2 and len(together) == 1


def test_an_own_language_wins_over_the_material(server, material):
    page = _run(server, material, language="en")[0].data
    assert page["lang"] == "en"
    hero = next(s for s in page["sections"] if s.get("hero"))
    assert hero["meta"].startswith("Made with AI on ")


def test_the_key_is_optional_and_a_placeholder_is_sent(server, material):
    _run(server, material)
    assert server.requests[0]["headers"]["authorization"] == "Bearer none"


def test_a_key_is_sent_when_it_is_given(server, material):
    _run(server, material, api_key="secret-key")
    assert server.requests[0]["headers"]["authorization"] == "Bearer secret-key"


def test_a_missing_base_url_and_model_name_what_to_set(material):
    with pytest.raises(ConfigError) as e:
        make_pages([material])
    assert "--base-url" in str(e.value) and "--model" in str(e.value)


def test_too_much_material_is_refused(server, material):
    with pytest.raises(LimitError) as e:
        _run(server, material, max_chars=10)
    assert "max_chars" in str(e.value)


def test_an_unsupported_file_names_what_works(server, tmp_path):
    bad = tmp_path / "picture.jpg"
    bad.write_bytes(b"x")
    with pytest.raises(Exception) as e:
        make_pages([bad], base_url=server.base_url, model="your-model")
    assert ".pdf" in str(e.value)


def test_an_empty_file_is_refused(server, tmp_path: Path):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(Exception) as e:
        make_pages([empty], base_url=server.base_url, model="your-model")
    assert "empty" in str(e.value)


def test_the_concurrency_setting_limits_the_calls_of_a_run(monkeypatch, server, material,
                                                           tmp_path):
    """Every stage that runs calls side by side asks for the number the user set."""
    from doc2pages import concurrency, pipeline
    from doc2pages.cli import main

    asked: list[int] = []
    real = concurrency.run_limited

    async def watched(jobs, at_once, **rest):
        asked.append(at_once)
        return await real(jobs, at_once, **rest)

    monkeypatch.setattr(pipeline.concurrency, "run_limited", watched)
    assert main([str(material), "-o", str(tmp_path / "out"), "--base-url", server.base_url,
                 "--model", "your-model", "--concurrency", "1", "--quiet"]) == 0
    assert asked and set(asked) == {1}


def test_the_picture_stage_reports_its_own_progress(server, material):
    """Without this the browser stands on the last written section for the whole stage."""
    steps: list[tuple] = []
    _run(server, material, images=True, on_progress=lambda *a: steps.append(a))
    images = [s for s in steps if s[0] == "images"]
    assert images, steps
    assert images[0] == ("images", 0, images[-1][2])
    assert images[-1][1] == images[-1][2] >= 1


def test_an_endpoint_that_never_answers_says_so(material, tmp_path, capsys):
    """A model server that is not running must not end in an internal marker."""
    from doc2pages.cli import main

    code = main([str(material), "-o", str(tmp_path / "out"), "--base-url",
                 "http://127.0.0.1:9/v1", "--model", "your-model", "--quiet"])
    assert code == 1
    err = capsys.readouterr().err
    assert "endpoint" in err and "model" in err
    assert "no outline" not in err
