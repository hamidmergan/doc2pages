"""Brackets that only name sources leave a page, brackets with content stay."""

from doc2pages.pipeline import drop_citations

NAMES = {"vl1", "einführung_ws", "einführung_ws.pdf"}


def test_labels_and_names_go():
    assert drop_citations("Neuere Literatur wird bevorzugt (VL1, Einführung_WS).", NAMES) == \
        "Neuere Literatur wird bevorzugt."
    assert drop_citations("Tools wie Zotero helfen (SZ48, SZ66, SZ67, SZ68).", NAMES) == "Tools wie Zotero helfen."
    assert drop_citations("Siehe dort (SZ12-SZ15) und weiter.", NAMES) == "Siehe dort und weiter."
    assert drop_citations("Am Anfang steht ein Lehrbuch (VL1, S. 4).", NAMES) == "Am Anfang steht ein Lehrbuch."


def test_content_brackets_stay():
    for s in ("Die Frist beträgt zwei Wochen (§ 15 Abs. 4).", "Der Mittelwert liegt bei 3 (n = 30).",
              "Dienste wie Google Scholar (kostenlos) helfen.", "Mischung (VL1, Beispiel 3)."):
        assert drop_citations(s, NAMES) == s


def test_walks_blocks_but_not_prompts():
    page = [{"id": "s1", "blocks": [{"kind": "bullets", "items": ["Eins (SZ3).", "Zwei (VL1)."]},
                                    {"kind": "image", "prompt": "a scene (SZ1)", "src": "img_1"}]}]
    out = drop_citations(page, NAMES)
    assert out[0]["blocks"][0]["items"] == ["Eins.", "Zwei."]
    assert out[0]["blocks"][1]["prompt"] == "a scene (SZ1)"
