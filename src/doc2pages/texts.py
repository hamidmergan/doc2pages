"""The fixed texts on a page, in the page's own language."""

from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    "pages.gistTitle": {"de": "Das Wichtigste in Kürze", "en": "The key points"},
    "pages.mapTitle": {"de": "Das Thema auf einer Karte", "en": "The topic at a glance"},
    "pages.mapCaption": {"de": "Aufbau der Seite", "en": "Structure of the page"},
    "pages.wordsTitle": {"de": "Wörter, die immer wieder fallen", "en": "Words that keep coming up"},
    "pages.wordsCaption": {"de": "Die häufigsten Fachwörter", "en": "The most frequent terms"},
    "pages.meta": {
        "de": "Erstellt mit KI am {date}, etwa {minutes} Min. Lesezeit.",
        "en": "Made with AI on {date}, about {minutes} min to read.",
    },
    "pages.contents": {"de": "Inhalt", "en": "Contents"},
    "pages.overview": {"de": "Seiten", "en": "Pages"},
}

DEFAULT_LOCALE = "en"


def t(key: str, locale: str = DEFAULT_LOCALE, **values) -> str:
    """One fixed text in the page's language, the key itself when it is unknown."""
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(locale) or entry.get(DEFAULT_LOCALE) or ""
    return text.format(**values) if values else text
