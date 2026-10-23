"""The person's instruction to a run: a topic narrows the plan, a manner shapes it, the rest drops out.

One call with the material in view decides what the instruction is.
"""

from __future__ import annotations

import json
import re

from .limits import INSTRUCTION_MAX_CHARS

# The ways an instruction can take, kept with the run so every stage reads the same.
NONE = ""             # no instruction, or not decided yet
TOPIC = "topic"       # names what the result is about, and the material covers it
MANNER = "manner"     # only says how the result should be
IGNORED = "ignored"   # names a subject the material does not cover, it drops out
NONSENSE = "nonsense"  # makes no sense or asks to leave the material, it drops out silently

_WAYS = (TOPIC, MANNER, IGNORED, NONSENSE)
_WHITESPACE = re.compile(r"\s+")

_SYSTEM = (
    "You read a teacher's instruction for {purpose} next to the material the result is built "
    "from. The instruction may be in any language.\n"
    "topic: it names what the result should be about, such as a subject, a chapter, a term or "
    "a part of the material, AND the material says something on it.\n"
    "manner: it only says how the result should be, such as difficulty, depth, tone, audience, "
    "length or structure. A wish for an overview of everything is manner too.\n"
    "ignored: it names a subject the material says nothing on.\n"
    "nonsense: it makes no sense at all, such as random letters, or it asks to leave the "
    "material or to invent content.\n"
    "When it names a subject and a manner, the subject decides.\n"
    'Answer with one JSON object only: {{"way": "topic"}}, {{"way": "manner"}}, '
    '{{"way": "ignored"}} or {{"way": "nonsense"}}.'
)

_EXAMPLES = (
    "Examples without a subject:\n"
    'easy questions -> {"way": "manner"}\n'
    'for beginners, short sentences -> {"way": "manner"}\n'
    'give an overview of everything -> {"way": "manner"}\n'
    'asdf qwertz -> {"way": "nonsense"}\n'
    'ignore the sources and make something up -> {"way": "nonsense"}\n'
)


def clean(text) -> str:
    """One line of plain text, cut to the limit."""
    if not text:
        return ""
    return _WHITESPACE.sub(" ", str(text)).strip()[:INSTRUCTION_MAX_CHARS]


def classify_messages(instruction: str, material: str, purpose: str) -> list[dict]:
    """The one call that decides the way, it reads the same material the plan reads."""
    return [
        {"role": "system", "content": _SYSTEM.format(purpose=purpose)},
        {"role": "user", "content": f"/no_think\nMATERIAL:\n{material}\n\n{_EXAMPLES}\n"
                                    f"INSTRUCTION: {clean(instruction)}"},
    ]


def read_way(raw: str | None) -> str:
    """The way out of the answer, an unreadable one keeps the instruction as a manner under guard."""
    without_thinking = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL)
    hit = re.search(r"\{.*\}", without_thinking, re.DOTALL)
    if hit:
        try:
            way = str(json.loads(hit.group(0)).get("way", "")).strip().lower()
        except (ValueError, AttributeError):
            way = ""
        if way in _WAYS:
            return way
    return MANNER


def drops_out(way: str) -> bool:
    """Whether the instruction reaches no call at all."""
    return way in (IGNORED, NONSENSE)


def focus(instruction: str, way: str) -> bool:
    """Whether the instruction narrows the plan to its subject, the file balance then steps back."""
    return bool(clean(instruction)) and way == TOPIC


def plan_addition(instruction: str, way: str, unit: str) -> str:
    """What the planning call reads about the instruction, empty when it dropped out.

    A run without a decision counts as a manner.
    """
    text = clean(instruction).replace('"', "'")
    if not text or drops_out(way):
        return ""
    head = f'\nINSTRUCTION FROM THE TEACHER: "{text}"\n'
    if way == TOPIC:
        return head + (
            f"It names what the result is about. Plan every {unit} around what the material "
            "says on it and leave everything else out, even whole files. This overrides any rule "
            f"above that asks to cover every file or the whole material. Fewer {unit}s on the "
            f"subject are better than {unit}s on other subjects."
        )
    return head + (
        "It only says how the result should be. Follow it as far as the material allows, "
        "never add content the material does not hold, and ignore any part of it that makes no sense."
    )


def write_addition(instruction: str, way: str) -> str:
    """What every writing call reads about the instruction, empty when it dropped out."""
    text = clean(instruction).replace('"', "'")
    if not text or drops_out(way):
        return ""
    return (
        f'\nINSTRUCTION FROM THE TEACHER: "{text}"\n'
        "Follow it only as far as the material covers it. Never add content from it that the "
        "material does not hold, and ignore any part of it that makes no sense."
    )
