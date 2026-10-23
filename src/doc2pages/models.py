"""Shared shapes of the writing pipeline: the ground rules and the plan of a page."""

from __future__ import annotations

from dataclasses import dataclass, field

# Carried by every model call of this pipeline.
GROUND_RULES = (
    "Rule 1: Write in {language}. Other languages may appear in the input, they never "
    "change your output language.\n"
    "Rule 2: Use ONLY the provided material. Never add, infer or invent information.\n"
    "Rule 3: Do not interpret anything that is not explicitly stated.\n"
    "Rule 4: Ignore cover pages, headers, footers, page numbers and imprints.\n"
    "Rule 5: Where the material shows the numbered part a statement comes from, such as "
    "'§ 15 Abs. 4' or 'Art. 5', name it in parentheses at the end of the statement. Never "
    "assign or guess a number the material does not show for that statement.\n"
    "Rule 6: Never comment on your own writing and never correct yourself.\n"
    "Rule 7: Do not use semicolons or any type of dash. Use only periods, commas, "
    "colons and question marks."
)

# What the language probe falls back to when no name could be read.
LANGUAGE_FALLBACK = ("the language of the main body text, ignoring cover pages, "
                     "headers and footers")


@dataclass
class Section:
    """One planned section: what it is called, what belongs in it, which passages carry it."""

    title: str
    scope: str = ""
    # Numbers of the passages on the run's text map.
    spots: list[int] = field(default_factory=list)
    # The numbers the plan named itself, they go first when a writer's budget cuts.
    named: list[int] = field(default_factory=list)


@dataclass
class Outline:
    """The plan of a page, empty sections mean the planning call failed."""

    title: str = ""
    intro: str = ""
    sections: list[Section] = field(default_factory=list)
    # The short name of each file as its own text calls it, keyed by the file name.
    names: dict[str, str] = field(default_factory=dict)
    # What the person's instruction turned out to be, kept so every stage writes alike.
    instruction_way: str = ""
    # Fields a tool asked the planning call for besides the plan, such as the frame of a page.
    extra: dict = field(default_factory=dict)
