"""The command line: help, a whole run, the switches and the error messages."""

from pathlib import Path

import pytest

from doc2pages.cli import build_parser, main


def test_the_help_is_english_and_names_the_settings(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    for word in ("--base-url", "--model", "--translate", "--images", "--markdown-only",
                 "--combine", "DOC2PAGES_BASE_URL", "serve"):
        assert word in out


def test_the_version_is_printed(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert "0.1.0" in capsys.readouterr().out


def test_without_a_file_the_help_is_shown(capsys):
    assert main([]) == 2
    assert "usage:" in capsys.readouterr().out


def test_a_run_writes_the_pages_and_prints_their_folders(server, material, tmp_path, capsys):
    out = tmp_path / "out"
    code = main([str(material), "-o", str(out), "--base-url", server.base_url,
                 "--model", "your-model", "--quiet"])
    assert code == 0
    printed = capsys.readouterr().out.strip()
    assert str(out / "lineare-regression") == printed
    assert (out / "lineare-regression" / "index.html").exists()


def test_markdown_only_and_translate_reach_the_run(server, material, tmp_path, capsys):
    out = tmp_path / "out"
    assert main([str(material), "-o", str(out), "--base-url", server.base_url,
                 "--model", "your-model", "--translate", "en", "--markdown-only", "--quiet"]) == 0
    folders = sorted(p.name for p in out.iterdir() if p.is_dir())
    assert len(folders) == 2
    assert not (out / folders[0] / "index.html").exists()


def test_a_missing_setting_ends_with_code_one(material, capsys):
    assert main([str(material), "--quiet"]) == 1
    assert "--base-url" in capsys.readouterr().err


def test_an_unreadable_file_ends_with_code_one(server, tmp_path: Path, capsys):
    bad = tmp_path / "picture.jpg"
    bad.write_bytes(b"x")
    assert main([str(bad), "--base-url", server.base_url, "--model", "m", "--quiet"]) == 1
    assert "not supported" in capsys.readouterr().err


def test_the_parser_knows_the_two_page_languages():
    parser = build_parser()
    args = parser.parse_args(["a.pdf", "--language", "de", "--translate", "en"])
    assert args.language == "de" and args.translate_to == "en"
    with pytest.raises(SystemExit):
        parser.parse_args(["a.pdf", "--language", "fr"])
