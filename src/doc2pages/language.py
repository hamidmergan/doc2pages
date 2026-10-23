"""The language of a text, read locally with langdetect instead of by a model call."""

from __future__ import annotations

from langdetect import DetectorFactory, LangDetectException, detect_langs

_SAMPLE_CHARS = 1500
# Below this the guess is noise, a file name or a page number is not a language.
_MIN_CHARS = 80
# A mixed or unclear sample is better described than named wrongly.
_MIN_PROB = 0.7
DetectorFactory.seed = 0

# English names of the languages the detector knows, the model reads the name.
_NAMES = {
    "af": "Afrikaans", "ar": "Arabic", "bg": "Bulgarian", "bn": "Bangla", "ca": "Catalan",
    "cs": "Czech", "cy": "Welsh", "da": "Danish", "de": "German", "el": "Greek", "en": "English",
    "es": "Spanish", "et": "Estonian", "fa": "Persian", "fi": "Finnish", "fr": "French",
    "gu": "Gujarati", "he": "Hebrew", "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian",
    "id": "Indonesian", "it": "Italian", "ja": "Japanese", "kn": "Kannada", "ko": "Korean",
    "lt": "Lithuanian", "lv": "Latvian", "mk": "Macedonian", "ml": "Malayalam", "mr": "Marathi",
    "ne": "Nepali", "nl": "Dutch", "no": "Norwegian", "pa": "Punjabi", "pl": "Polish",
    "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "sk": "Slovak", "sl": "Slovenian",
    "so": "Somali", "sq": "Albanian", "sv": "Swedish", "sw": "Swahili", "ta": "Tamil",
    "te": "Telugu", "th": "Thai", "tl": "Tagalog", "tr": "Turkish", "uk": "Ukrainian",
    "ur": "Urdu", "vi": "Vietnamese", "zh": "Chinese",
}


def language_sample(text: str, sample_chars: int = _SAMPLE_CHARS) -> str:
    """An excerpt from the middle as a language sample, the edges mislead."""
    if len(text) <= sample_chars:
        return " ".join(text.split())
    middle = len(text) // 2
    body = " ".join(text[max(0, middle - sample_chars): middle + sample_chars].split())
    if len(body) <= sample_chars:
        return body
    # Cut from the middle outwards, else exactly the middle drops out again.
    start = (len(body) - sample_chars) // 2
    return body[start:start + sample_chars]


def language_code(text: str) -> str | None:
    """The two-letter code of the text, None when it is too short or unclear."""
    sample = language_sample(text)
    if len(sample) < _MIN_CHARS:
        return None
    try:
        hit = detect_langs(sample)[0]
    except LangDetectException:
        return None
    return hit.lang.split("-")[0] if hit.prob >= _MIN_PROB else None


def language_name(text: str) -> str | None:
    """The English name of the text's language, None when it is too short or unclear."""
    code = language_code(text)
    return _NAMES.get(code) if code else None
