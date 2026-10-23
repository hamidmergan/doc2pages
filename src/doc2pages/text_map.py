"""The whole material of a run as numbered passages, and the way back from a number.

Planning happens over this map, writing happens from the original text behind the
numbers. Nothing is extracted in between: a number points into the canonical text of
the sources and never into something a model wrote.

The reason is time. A model reads fast and writes slowly. A call that plans over the whole
text writes little, a call that writes one part of the result writes little too, so every
call stays short.
"""

from __future__ import annotations

import bisect
import json
import math
import re
from dataclasses import dataclass
from typing import Callable

from .limits import (
    CHARS_PER_TOKEN,
    MAP_ANCHOR_MIN_CHARS,
    MAP_ANCHOR_MIN_SHARE,
    MAP_FILE_WEIGHT_FLOOR,
    MAP_MATERIAL_MAX_CHARS,
    MAP_MAX_REFS,
    MAP_MAX_TOPICS_PER_PART,
    MAP_MAX_TOPICS_TOTAL,
    MAP_MIN_FILE_SHARE,
    MAP_MIN_TOPICS_PER_FILE,
    MAP_MIN_WINDOW_TOKENS,
    MAP_OUTPUT_TOKENS,
    MAP_PROMPT_TOKENS,
    MAP_RANGE_MAX,
    MAP_UNMEASURED_WINDOW_TOKENS,
)
from .source_reading import Source

# What the answer of a planning call calls its passage or topic numbers.
REFS = "refs"
# The first words of an entry's text, copied, so the passage itself can be found.
START = "start"

PASSAGES = "passages"
TOPICS = "topics"

# Labels in front of passage and topic numbers, a bare [45] reads like § 45 in a law.
PASSAGE_LABEL = "SZ"
TOPIC_LABEL = "TZ"

# A number or a range with or without its label, any dash a model writes, some models use the non-breaking hyphen.
_RANGE = re.compile(r"^\s*[A-Za-z]{0,3}\s*(\d+)\s*[-‐‑‒–—−]\s*[A-Za-z]{0,3}\s*(\d+)\s*$")
_SINGLE = re.compile(r"^\s*[A-Za-z]{0,3}\s*(\d+)\s*$")


class WindowTooSmall(ValueError):
    """The chosen model cannot carry a useful part of the material, refused up front."""


@dataclass(frozen=True)
class Spot:
    """Where a numbered passage sits: which source, which of its pieces."""

    source: int
    piece: int


@dataclass(frozen=True)
class Topic:
    """One topic a part of the material was boiled down to, with the passages behind it."""

    number: int
    title: str
    gist: str
    passages: tuple[int, ...]


def window_chars(window_tokens: int) -> int:
    """How much numbered text one planning call may carry on this model."""
    if window_tokens and window_tokens < MAP_MIN_WINDOW_TOKENS:
        raise WindowTooSmall(window_tokens)
    window = window_tokens or MAP_UNMEASURED_WINDOW_TOKENS
    return max(1, int((window - MAP_PROMPT_TOKENS - MAP_OUTPUT_TOKENS) * CHARS_PER_TOKEN))


_SPACE = re.compile(r"\s+")
# Soft hyphen and the like vanish, every dash becomes one, so a copied quote still matches.
_CHARS = str.maketrans({"­": None, "‐": "-", "‑": "-", "‒": "-",
                        "–": "-", "—": "-", "−": "-", "„": '"',
                        "“": '"', "”": '"', "’": "'"})


def _normal(text: str) -> str:
    return _SPACE.sub(" ", text.translate(_CHARS)).strip().casefold()


def _normal_with_places(text: str) -> tuple[str, list[int]]:
    """The text as ``_normal`` makes it, with the original position of every character kept."""
    chars: list[str] = []
    places: list[int] = []
    blank = True
    for i, c in enumerate(text):
        c = c.translate(_CHARS)
        if not c:
            continue
        if c.isspace():
            if not blank:
                chars.append(" ")
                places.append(i)
            blank = True
            continue
        for part in c.casefold():
            chars.append(part)
            places.append(i)
        blank = False
    return "".join(chars), places


def write_budget(window_tokens: int) -> int:
    """How much original text one writing call may carry, the fixed cap or what the window leaves."""
    return min(MAP_MATERIAL_MAX_CHARS, window_chars(window_tokens))


class TextMap:
    """Every piece of every source under one running number, counted from 1."""

    def __init__(self, sources: list[Source]) -> None:
        self.sources = sources
        self.spots: list[Spot] = [
            Spot(source=q, piece=p)
            for q, source in enumerate(sources) for p in range(len(source.pieces))
        ]

    def __len__(self) -> int:
        return len(self.spots)

    def spot(self, number: int) -> Spot:
        return self.spots[number - 1]

    def _page(self, number: int) -> tuple[int, int]:
        sp = self.spot(number)
        return sp.source, self.sources[sp.source].pieces[sp.piece].page

    def segment(self, number: int) -> str:
        """The text of one number, up to where the next piece begins.

        Pieces overlap so that no sentence is cut apart. On the map the overlap would
        only double the text, so each number shows its piece up to its successor.
        """
        sp = self.spot(number)
        source = self.sources[sp.source]
        pieces = source.pieces
        start = pieces[sp.piece].start
        end = pieces[sp.piece + 1].start if sp.piece + 1 < len(pieces) else pieces[sp.piece].end
        return source.text[start:end].strip()

    def block(self, numbers: range | None = None) -> str:
        """The numbered text as a planning call reads it, each file under its name."""
        parts: list[str] = []
        previous = -1
        for n in numbers if numbers is not None else range(1, len(self) + 1):
            sp = self.spot(n)
            if sp.source != previous:
                parts.append(f"=== {self.sources[sp.source].name} ===")
                previous = sp.source
            parts.append(f"[{PASSAGE_LABEL}{n}] {self.segment(n)}")
        return "\n\n".join(parts)

    def parts(self, window_tokens: int) -> list[range]:
        """The numbers cut into as few planning calls as the window allows.

        Cut at a change of file or page near the even share, so no call starts in the
        middle of a page when it does not have to.
        """
        if not self.spots:
            return []
        usable = window_chars(window_tokens)
        # What each number costs on the map, its header included where a file begins.
        costs = []
        for n in range(1, len(self) + 1):
            head = len(self.sources[self.spot(n).source].name) + 10 \
                if n == 1 or self.spot(n).source != self.spot(n - 1).source else 0
            costs.append(len(self.segment(n)) + len(str(n)) + 4 + head)
        total = sum(costs)
        if total <= usable:
            return [range(1, len(self) + 1)]
        count = math.ceil(total / usable)
        target = total / count
        bounds = [1]
        running = 0
        for n in range(1, len(self) + 1):
            running += costs[n - 1]
            full = len(bounds) < count and running >= target * len(bounds)
            if full and n < len(self):
                bounds.append(self._next_boundary(n, bounds[-1]))
        bounds.append(len(self) + 1)
        return [range(a, b) for a, b in zip(bounds, bounds[1:]) if b > a]

    def stretches(self, window_tokens: int) -> list[tuple[range, int]]:
        """The pieces of the topic stage: the parts, cut again where a file ends.

        Each piece gets topics by its share of the whole, never fewer than a floor. One call
        over several files lists the first ones and runs out before the last.
        """
        parts = self.parts(window_tokens)
        total = min(MAP_MAX_TOPICS_PER_PART * len(parts), MAP_MAX_TOPICS_TOTAL)
        out: list[tuple[range, int]] = []
        for part in parts:
            start = part.start
            for n in range(part.start + 1, part.stop + 1):
                if n == part.stop or self.spot(n).source != self.spot(n - 1).source:
                    stretch = range(start, n)
                    count = max(MAP_MIN_TOPICS_PER_FILE, round(total * len(stretch) / len(self)))
                    out.append((stretch, count))
                    start = n
        return out

    def _next_boundary(self, n: int, start: int) -> int:
        """The first number of the next part: a new file or page close before n, else n + 1."""
        for candidate in range(n + 1, max(start + 1, n - 30), -1):
            if candidate > len(self):
                continue
            if self._page(candidate) != self._page(candidate - 1):
                return candidate
        return n + 1

    def valid(self, raw) -> list[int]:
        """The passage numbers of an answer, invented and doubled ones dropped.

        Accepts numbers and ranges written as "12-15", a range is capped so one wild
        answer cannot pull in a whole document.
        """
        return _numbers(raw, len(self))

    def find(self, quote, *, within: range | None = None,
             near: list[int] | None = None) -> int | None:
        place = self.find_with_share(quote, within=within, near=near)
        return place[0] if place else None

    def find_with_share(self, quote, *, within: range | None = None,
                        near: list[int] | None = None) -> tuple[int, float] | None:
        """The passage where these copied words stand, None when they stand nowhere.

        A model copies text far more reliably than it keeps numbers apart from the
        paragraph numbers of a law, so its first words find the place it meant. Words
        cut off at the end still count, the shorter the rest the likelier it repeats,
        so it never gets shorter than MAP_ANCHOR_MIN_CHARS. Of several places the one
        where most of the copied words go on matching wins, a table of contents repeats
        a heading but not the sentence after it. A tie goes to the one closest to ``near``.
        """
        whole = _normal(str(quote or ""))
        words = whole.split(" ")
        if not hasattr(self, "_index"):
            self._index = [_normal_with_places(q.text) for q in self.sources]
        for length in range(len(words), 0, -1):
            needle = " ".join(words[:length])
            if len(needle) < MAP_ANCHOR_MIN_CHARS:
                return None
            places = [(n, same) for n, same in self._places(needle, whole) if within is None or n in within]
            if places:
                distance = (lambda n: min(abs(n - m) for m in near)) if near else (lambda n: 0)
                place, same = min(places, key=lambda o: (-o[1], distance(o[0])))
                return place, same / max(1, len(whole))
        return None

    def _places(self, needle: str, whole: str) -> list[tuple[int, int]]:
        """Every passage in which the words begin, with how many characters of ``whole`` match there."""
        places: list[tuple[int, int]] = []
        before = 0
        for q, (text, positions) in enumerate(self._index):
            starts = [s.start for s in self.sources[q].pieces]
            start = text.find(needle)
            while start != -1:
                same = len(needle)
                while same < len(whole) and start + same < len(text) and text[start + same] == whole[same]:
                    same += 1
                places.append((before + bisect.bisect_right(starts, positions[start]), same))
                start = text.find(needle, start + 1)
            before += len(starts)
        return places

    def anchor(self, numbers: list[int], quote, *, within: range | None = None) -> list[int]:
        """The passages moved to where the copied first words really stand.

        Unchanged when the words stand nowhere or already at or next to the passages
        named. Otherwise as many passages as were named, from the found place on, kept
        inside its file and ``within``.
        """
        hit = self.find_with_share(quote, within=within, near=numbers or None)
        if hit is None or hit[1] < MAP_ANCHOR_MIN_SHARE:
            return numbers
        place = hit[0]
        if any(abs(place - n) <= 1 for n in numbers):
            return numbers
        file = self.spot(place).source
        end = max(n for n in range(place, len(self) + 1) if self.spot(n).source == file
                  and (within is None or n in within))
        return list(range(place, min(place + max(1, len(set(numbers))), end + 1, place + MAP_MAX_REFS)))

    def passages(self, numbers: list[int], *, first: list[int] | None = None,
                 neighbours: int = 1, budget: int | None = None) -> str:
        """The original text behind these numbers, each with its neighbours.

        Neighbouring numbers are joined into one passage, each passage names its file
        and page. The passages come in the order of the text. When they do not fit the
        budget, the numbers in ``first`` go first and the rest fills what is left, in
        both every file keeps its share, spread over the whole file.
        """
        priority = set(first or []) & set(numbers)
        named = self._by_file(n for n in numbers if n in priority)
        rest = self._by_file(n for n in numbers if n not in priority)
        wanted = self._with_neighbours(self._merged(named, rest), neighbours)
        if budget is not None and self._cost(wanted) > budget:
            wanted = self._shortened(named, rest, neighbours, budget)
        parts: list[str] = []
        for q in sorted(wanted):
            source = self.sources[q]
            runs: list[list[int]] = []
            for p in sorted(wanted[q]):
                if runs and p == runs[-1][-1] + 1:
                    runs[-1].append(p)
                else:
                    runs.append([p])
            for run in runs:
                head = source.pieces[run[0]]
                text = source.text[head.start:source.pieces[run[-1]].end].strip()
                parts.append(f"[{source.name}, S. {head.page}]\n{text}")
        return "\n\n".join(parts)

    def _by_file(self, numbers) -> dict[int, set[int]]:
        out: dict[int, set[int]] = {}
        for n in numbers:
            if 1 <= n <= len(self):
                sp = self.spot(n)
                out.setdefault(sp.source, set()).add(sp.piece)
        return out

    @staticmethod
    def _merged(*parts: dict[int, set[int]]) -> dict[int, set[int]]:
        out: dict[int, set[int]] = {}
        for part in parts:
            for q, pieces in part.items():
                out.setdefault(q, set()).update(pieces)
        return out

    def _shortened(self, first: dict[int, set[int]], rest: dict[int, set[int]],
                   neighbours: int, budget: int) -> dict[int, set[int]]:
        """The first numbers within the budget, the rest only in the room they leave."""
        if not first:
            return self._in_budget(rest, neighbours, budget)
        wanted = self._with_neighbours(first, neighbours)
        if self._cost(wanted) > budget:
            return self._in_budget(first, neighbours, budget)
        free = budget - self._cost(wanted)
        left = {q: {p for p in pieces if p not in wanted.get(q, set())}
                for q, pieces in rest.items()}
        left = {q: pieces for q, pieces in left.items() if pieces}
        mean = self._cost(left) / max(1, sum(len(v) for v in left.values()))
        if not left or free < mean * len(left):
            return wanted
        return self._merged(wanted, self._in_budget(left, neighbours, free))

    def _with_neighbours(self, named: dict[int, set[int]], neighbours: int) -> dict[int, set[int]]:
        out: dict[int, set[int]] = {}
        for q, pieces in named.items():
            count = len(self.sources[q].pieces)
            out[q] = {p + d for p in pieces for d in range(-neighbours, neighbours + 1)
                      if 0 <= p + d < count}
        return out

    def _piece_cost(self, q: int, p: int) -> int:
        """What one piece costs in a passage, its own header counted as if it stood alone."""
        source = self.sources[q]
        piece = source.pieces[p]
        return piece.end - piece.start + len(source.name) + 12

    def _cost(self, wanted: dict[int, set[int]]) -> int:
        return sum(self._piece_cost(q, p) for q, pieces in wanted.items() for p in pieces)

    def _in_budget(self, named: dict[int, set[int]], neighbours: int,
                   budget: int) -> dict[int, set[int]]:
        """Every file gets the budget by its share of the named pieces, spread over the file.

        Cut in the order of the text, the first file would fill the budget and a later one
        would reach no writer at all. Neighbours come only where a file's share has room.
        """
        total = self._cost(named) or 1
        out: dict[int, set[int]] = {}
        for q, pieces in named.items():
            row = sorted(pieces)
            share = budget * self._cost({q: pieces}) / total
            mean = self._cost({q: pieces}) / len(row)
            k = max(1, min(len(row), int(share // mean)))
            chosen = {row[round(i * (len(row) - 1) / (k - 1))] for i in range(k)} \
                if k > 1 else {row[0]}
            left = share - self._cost({q: chosen})
            count = len(self.sources[q].pieces)
            for p in sorted(chosen):
                for d in range(1, neighbours + 1):
                    for neighbour in (p - d, p + d):
                        if 0 <= neighbour < count and neighbour not in chosen:
                            price = self._piece_cost(q, neighbour)
                            if price <= left:
                                chosen.add(neighbour)
                                left -= price
            out[q] = chosen
        return out


def coverage(lists: list[list[int]], total: int) -> float:
    """Which share of all passages the entries of a plan name, from 0 to 1."""
    if not total:
        return 1.0
    return len({n for lst in lists for n in lst if 1 <= n <= total}) / total


def too_thin(lists: list[list[int]], text_map: "TextMap") -> list[tuple[str, int]]:
    """The files a plan hardly draws on, with the share of the material they hold.

    Naming one passage of a file is not covering it: an entry follows its title, and a
    file that only turns up in a stray number is talked over. A file gets at least a
    quarter of the weight it has in the material, files below a twentieth are spared.
    """
    named = [n for lst in lists for n in set(lst) if 1 <= n <= len(text_map)]
    if not named or not len(text_map):
        return []
    out: list[tuple[str, int]] = []
    for i, q in enumerate(text_map.sources):
        text_share = len(q.pieces) / len(text_map)
        if text_share < MAP_MIN_FILE_SHARE:
            continue
        plan_share = sum(1 for n in named if text_map.spot(n).source == i) / len(named)
        if plan_share < text_share * MAP_FILE_WEIGHT_FLOOR:
            out.append((q.name, round(text_share * 100)))
    return out


def exclusive(lists: list[list[int]]) -> list[list[int]]:
    """A passage several entries name stays with the first, two writers would repeat it.

    An entry that would be left with nothing keeps its own numbers, an empty entry
    would rest on the whole text instead.
    """
    given: set[int] = set()
    out: list[list[int]] = []
    for lst in lists:
        own = [n for n in lst if n not in given]
        out.append(own if own else list(lst))
        given.update(lst)
    return out


def cover_all(lists: list[list[int]], total: int,
              file: Callable[[int], int] | None = None) -> list[list[int]]:
    """Every passage no entry names goes to the entry whose numbers lie closest.

    A plan that leaves a stretch of the text out would lose it for good, the writer only
    ever sees what its entry names. Entries without numbers stay as they are, they rest
    on the whole anyway. With ``file`` a passage only goes to an entry that already draws
    on its file, a file no entry names falls back to the closest entry.
    """
    named = {n for lst in lists for n in lst}
    with_numbers = [i for i, lst in enumerate(lists) if lst]
    if not with_numbers:
        return [list(lst) for lst in lists]
    out = [list(lst) for lst in lists]
    for n in range(1, total + 1):
        if n in named:
            continue
        own = [] if file is None else [i for i in with_numbers if any(file(m) == file(n) for m in lists[i])]
        if own:
            nearest = min(own, key=lambda i: min(abs(n - m) for m in lists[i] if file(m) == file(n)))
        else:
            nearest = min(with_numbers, key=lambda i: min(abs(n - m) for m in lists[i]))
        out[nearest].append(n)
    return [sorted(lst) for lst in out]


def _numbers(raw, highest: int) -> list[int]:
    if not isinstance(raw, list):
        return []
    # A model sometimes packs several numbers into one entry, "10, 16, 30".
    values = [part for value in raw if not isinstance(value, bool)
              for part in (re.split(r"[,;]", value) if isinstance(value, str) else [value])]
    out: list[int] = []
    for value in values:
        hit = _RANGE.match(str(value))
        if hit:
            a, b = int(hit.group(1)), int(hit.group(2))
            if b < a:
                a, b = b, a
            candidates = range(a, min(b, a + MAP_RANGE_MAX - 1) + 1)
        else:
            single = _SINGLE.match(str(value))
            if not single:
                continue
            candidates = [int(single.group(1))]
        for n in candidates:
            if 1 <= n <= highest and n not in out:
                out.append(n)
            if len(out) >= MAP_MAX_REFS:
                return out
    return out


# --- The basis of the plan ---------------------------------------------------------------

def labels_note(mode: str) -> str:
    """What the labels in the material mean."""
    if mode == TOPICS:
        return (
            f'The material is a list of topics, each written as "[{TOPIC_LABEL}n] title: gist". '
            "Together they cover the whole text. Under \"refs\" name the labels of the "
            f'topics an entry draws on, copied exactly, such as "{TOPIC_LABEL}3". Labels stand '
            "only under refs, never in a title, intro or any other text you write."
        )
    return (
        f'The material is the full text, cut into passages, each written as "[{PASSAGE_LABEL}n] text". '
        "Under \"refs\" name the passages an entry draws on by their labels, copied exactly. "
        f'Write neighbouring passages as one range such as "{PASSAGE_LABEL}12-{PASSAGE_LABEL}18" '
        "instead of listing them, and keep refs short: at most 10 entries. Name only labels "
        f"that appear in the material. A label is never a paragraph, article or page: § 45 or "
        f"S. 45 in the text is not {PASSAGE_LABEL}45, look up the label in front of the passage "
        "that holds it. Labels stand only under refs, never in a title, intro or any other "
        "text you write."
    )


@dataclass
class Basis:
    """What a planning call reads, and how its answer finds its way back to the text."""

    material: str
    mode: str
    topics: list[Topic]

    def passages_of(self, refs, text_map: TextMap, start=None) -> list[int]:
        """The passage numbers behind the refs of one entry, moved to its copied first words."""
        if self.mode != TOPICS:
            numbers = text_map.valid(refs)
            # Empty refs stay empty, an agenda slide or a slide without material asks for nothing.
            return text_map.anchor(numbers, start) if numbers and start else numbers
        by_number = {t.number: t for t in self.topics}
        out: list[int] = []
        for n in _numbers(refs, len(self.topics)):
            for s in by_number[n].passages:
                if s not in out:
                    out.append(s)
        return out


def topic_messages(text_map: TextMap, part: range, parts: int, number: int,
                   language: str, purpose: str,
                   at_most: int = MAP_MAX_TOPICS_PER_PART) -> list[dict]:
    """One part of the material boiled down to its topics, when the whole does not fit."""
    system = (
        "You map a text. The text is cut into labelled passages. List the topics this "
        f"text covers, in the order they appear, at most {at_most}, spread over the "
        "whole text to its last passage. "
        f"This is part {number} of {parts} of the material, other parts are mapped "
        "separately. For every topic give a short title, one sentence saying what the "
        "text states about it that names the concrete duties, deadlines and figures it gives, "
        f'and the passages it draws on by the labels in front of them, such as "{PASSAGE_LABEL}4" or '
        f'a range "{PASSAGE_LABEL}4-{PASSAGE_LABEL}7". A label is never a paragraph or page: § 4 in '
        f"the text is not {PASSAGE_LABEL}4, name the label of the passage that holds it. Under "
        '"start" copy the first six to ten words of the text the topic begins with, exactly as '
        "they stand, never the label. Every passage that carries content belongs to a topic. "
        f"Write titles and sentences in {language}. The material will be used for: {purpose}.\n"
        'Answer with one JSON object only: {"topics": [{"title": "...", "gist": "...", '
        f'"start": "...", "refs": ["{PASSAGE_LABEL}1", "{PASSAGE_LABEL}4-{PASSAGE_LABEL}7"]}}]}}'
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"/no_think\n{text_map.block(part)}"}]


def parse_topics(raw: str | None, text_map: TextMap, first_number: int,
                 at_most: int = MAP_MAX_TOPICS_PER_PART,
                 within: range | None = None) -> list[Topic]:
    """The topics out of one answer, numbered on from where the previous part stopped.

    The copied first words of a topic move its passages to where they really stand,
    looked up only inside ``within``, the part this answer read.
    """
    data = _json_object(raw)
    raw_topics = data.get("topics") if isinstance(data, dict) else None
    out: list[Topic] = []
    for entry in raw_topics if isinstance(raw_topics, list) else []:
        if not isinstance(entry, dict):
            continue
        title = " ".join(str(entry.get("title") or "").split())[:120]
        passages = text_map.anchor(text_map.valid(entry.get(REFS)), entry.get(START),
                                   within=within)
        if not title or not passages:
            continue
        out.append(Topic(number=first_number + len(out), title=title,
                         gist=" ".join(str(entry.get("gist") or "").split())[:300],
                         passages=tuple(passages)))
        if len(out) >= at_most:
            break
    return out


def topics_block(topics: list[Topic]) -> str:
    return "\n".join(f"[{TOPIC_LABEL}{t.number}] {t.title}: {t.gist}" for t in topics)


def _json_object(raw: str | None):
    text = (raw or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
