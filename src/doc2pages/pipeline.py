"""One run of a page: the plan, blocks per section, the frame, then the page itself.

The plan is made over the numbered text of every source, each section is written from
the original passages it names. Pictures are drawn afterwards, this module only names them.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Callable

from . import concurrency, instruction, planning, schema
from . import text_map as tm
from .client import Caller, is_provider_refusal
from .errors import Doc2PagesError
from .language import language_name
from .limits import (
    MAP_PASSAGE_NEIGHBOURS,
    PAGES_SECTION_CHARS,
    PAGES_SECTION_GROUP_CHARS,
    PAGES_SECTIONS,
    SUMMARY_SECTION_GROUP_CHARS,
    SUMMARY_SOURCE_OPENING_CHARS,
)
from .log import logger
from .models import LANGUAGE_FALLBACK, Outline
from .source_reading import Source
from .texts import t
from .translate import LANGUAGES
from .writing import FRAME_FIELDS, FRAME_RULES, frame_from_plan, write_blocks, write_frame


class PipelineInterrupted(Doc2PagesError):
    """The run was asked to stop, what is done is kept."""


class NoPlan(Doc2PagesError):
    """No planning call came back usable."""


# The build plan the planner reads for a page.
TEMPLATE_BODY = (
    "Plan a learning web page for students. The sections follow the subject's own "
    "structure: core ideas and terms, how something works or is done, examples with their "
    "figures, comparisons, limits and common mistakes. Each section covers one theme a "
    "student takes in at a glance. A heading names its subject only, never the kind of "
    "section such as example, comparison or overview. No section for exercises, questions "
    "or a quiz."
)

# How the pictures look, a calm style, overridable by the person's own style.
IMAGE_STYLE = (
    "Editorial illustration, flat shapes with subtle paper grain, calm deep blue (#004261) and "
    "soft mist grey palette with a single warm amber accent. Clean, modern, generous negative "
    "space."
)
NO_TEXT = ("Absolutely no text, letters, numbers, words, labels, signs, logos, charts, diagrams, "
           "calendars or screens.")
HERO_IMAGE = "img_0.webp"
# The title picture runs across the whole width above the title.
HERO_SIZE = "1536x656"
SECTION_SIZE = "1152x864"
# The id of the section that holds the title picture above the title.
COVER_ID = "cover"
MIN_MAP_SECTIONS = 4
# Words a reader gets through per minute, for the reading time under the title.
WORDS_PER_MINUTE = 200
MIN_CLOUD_WORDS = 6
# A section's opening text has at least this many sentences, a shorter one is written anew.
MIN_SENTENCES = 2
# About six sentences, the most a section's text keeps when it is written anew.
PROSE_CHARS = 900
CLOUD_WORDS = 20

# Where the answers of the topic pieces wait until every piece is in.
_PARTS_DONE = "parts_done"


def default_image_style() -> str:
    """The look every picture gets unless the person wrote their own."""
    return IMAGE_STYLE.strip()


def image_prompt(subject: str, style: str = "") -> str:
    """The prompt the image model gets, the style first, the subject after."""
    look = " ".join(style.split()) or default_image_style()
    return f"{look} Subject: {' '.join(subject.split())} {NO_TEXT}".strip()


class RunStore:
    """Everything of one run that the stages hand on to each other, kept in memory."""

    def __init__(self, on_progress: Callable[[str, int | None, int | None], None] | None = None):
        self._progress = on_progress
        self.basis: tm.Basis | None = None
        self.topic_parts: dict[str, str] = {}
        self.language: str | None = None
        self.outline: Outline | None = None
        self.blocks: dict[int, dict] = {}
        self.frame: dict | None = None

    def progress(self, step: str, part: int | None = None, total: int | None = None) -> None:
        if self._progress is not None:
            self._progress(step, part, total)

    def load_basis(self) -> tm.Basis | None:
        return self.basis

    def save_basis(self, basis: tm.Basis) -> None:
        self.basis = basis

    def load_language(self) -> str | None:
        return self.language

    def save_language(self, language: str) -> None:
        self.language = language

    def load_outline(self) -> Outline | None:
        return self.outline

    def save_outline(self, outline: Outline) -> None:
        self.outline = outline

    def load_blocks(self) -> dict[int, dict]:
        return self.blocks

    def save_blocks(self, index: int, data: dict) -> None:
        self.blocks[index] = data

    def load_frame(self) -> dict | None:
        return self.frame

    def save_frame(self, data: dict) -> None:
        self.frame = data


def detect_language(sources: list[Source]) -> str:
    """The language of the material, read locally. A text without one falls back."""
    return language_name("\n".join(q.text for q in sources[:1])) or LANGUAGE_FALLBACK


async def _topics(caller: Caller, messages: list[dict], part: int) -> str | None:
    """One part of the material boiled down to topics, None when the call failed."""
    try:
        answer = await caller.create(messages=messages, temperature=0.2, name=f"topics:{part}",
                                     response_format={"type": "json_object"})
        return answer.choices[0].message.content
    except Exception as e:  # noqa: BLE001 - a lost part costs its topics, not the run
        if concurrency.overloaded(e) or is_provider_refusal(e):
            raise
        logger.warning("Topics of part {} not read ({})", part, e)
        return None


async def _basis(caller: Caller, text_map: tm.TextMap, language: str,
                 store: RunStore, should_stop: Callable[[], bool] | None = None) -> tm.Basis:
    """What the planning call reads: the numbered text, or its topics when it is too long."""
    kept = store.load_basis()
    if kept:
        return kept
    if len(text_map.parts(caller.window_tokens)) <= 1:
        basis = tm.Basis(material=text_map.block(), mode=tm.PASSAGES, topics=[])
    else:
        stretches = text_map.stretches(caller.window_tokens)
        done: dict[str, str] = store.topic_parts

        async def one(i: int, stretch: range, count: int) -> None:
            answer = await _topics(caller, tm.topic_messages(
                text_map, stretch, len(stretches), i + 1, language, "a learning web page",
                at_most=count), i + 1)
            if answer is not None:
                done[str(i)] = answer
            store.progress("outline", len(done), len(stretches))

        may = (lambda: not should_stop()) if should_stop else None
        results = await concurrency.run_limited(
            [lambda i=i, stretch=stretch, count=count: one(i, stretch, count)
             for i, (stretch, count) in enumerate(stretches) if str(i) not in done],
            caller.at_once, may_start=may)
        if any(e is concurrency.SKIPPED for e in results):
            raise PipelineInterrupted
        answers = [done.get(str(i)) for i in range(len(stretches))]
        topics: list[tm.Topic] = []
        for answer, (stretch, count) in zip(answers, stretches):
            topics.extend(tm.parse_topics(answer, text_map, len(topics) + 1, at_most=count,
                                          within=stretch))
        if not topics:
            raise NoPlan("No part of the material yielded any topics.")
        basis = tm.Basis(material=tm.topics_block(topics), mode=tm.TOPICS, topics=topics)
    store.save_basis(basis)
    logger.info("{} passages, planned over {}", len(text_map),
                "the whole text" if basis.mode == tm.PASSAGES else f"{len(basis.topics)} topics")
    return basis


async def _way(caller: Caller, instructions: str, material: str) -> str:
    """What the instruction is, read once next to the material the plan reads."""
    if not instruction.clean(instructions):
        return instruction.NONE
    try:
        answer = await caller.create(
            messages=instruction.classify_messages(instructions, material,
                                                   "a learning web page"),
            temperature=0.0, name="instruction", response_format={"type": "json_object"})
        way = instruction.read_way(answer.choices[0].message.content)
    except Exception as e:  # noqa: BLE001 - a lost call keeps the instruction under guard
        if concurrency.overloaded(e) or is_provider_refusal(e):
            raise
        logger.warning("Instruction not classified ({}), it counts as a manner", e)
        way = instruction.MANNER
    logger.info("Instruction counts as {}", way)
    return way


async def _outline(caller: Caller, *, language: str, sources: list[Source],
                   text_map: tm.TextMap, store: RunStore, instructions: str = "",
                   should_stop: Callable[[], bool] | None = None) -> Outline:
    """The plan, taken from the store when a stage already paid for it."""
    kept = store.load_outline()
    if kept:
        return kept
    store.progress("outline")
    basis = await _basis(caller, text_map, language, store, should_stop)
    way = await _way(caller, instructions, basis.material)
    # A page on one subject leaves files out on purpose, nothing drags them back in.
    focus = instruction.focus(instructions, way)

    async def plan_it(missing: list[str] | None) -> Outline:
        return await planning.plan_outline(
            caller, language=language, template_body=TEMPLATE_BODY,
            sources=[q.name for q in sources], material=basis.material,
            target=planning.target_sections(sum(len(q.text) for q in sources) // 10,
                                            len(sources), PAGES_SECTIONS),
            mode=basis.mode, spots=lambda refs: basis.passages_of(refs, text_map),
            span=PAGES_SECTIONS, missing=missing,
            openings=[q.text[:SUMMARY_SOURCE_OPENING_CHARS] for q in sources],
            instructions=instructions, way=way,
            # Over the full text the copied first words find the passage, topics carry their own.
            anchor=(lambda numbers, quote: text_map.anchor(numbers, quote))
            if basis.mode == tm.PASSAGES else None,
            extra_fields=FRAME_FIELDS, extra_rules=FRAME_RULES, enforce_schema=False)

    plan = await plan_it(None)
    plan.instruction_way = way
    # A plan that starves a file loses it for good, so it is asked for once more.
    gaps = (tm.too_thin([a.spots for a in plan.sections], text_map)
            if len(sources) > 1 and not focus else [])
    if plan.sections and gaps:
        note = [f"{n} ({a} % of the material)" for n, a in gaps]
        logger.warning("The plan gives too little weight to: {}", ", ".join(note))
        second = await plan_it(note)
        if second.sections and len(tm.too_thin([a.spots for a in second.sections],
                                               text_map)) < len(gaps):
            plan = second
            plan.instruction_way = way
    if plan.sections:
        before = tm.coverage([a.spots for a in plan.sections], len(text_map))
        own = tm.exclusive([a.spots for a in plan.sections])
        # Off the subject the rest of the text stays out, else it goes to the nearest section.
        spread = own if focus else tm.cover_all(own, len(text_map),
                                                file=lambda n: text_map.spot(n).source)
        for section, named, spots in zip(plan.sections, own, spread):
            section.named, section.spots = named, spots
        logger.info("The plan names {:.0%} of the passages, the rest goes to the "
                    "nearest section", before)
        store.save_outline(plan)
    return plan


def _text_from_prose(text: str) -> list[dict]:
    """A section the block call could not shape: a list stays a list, prose stays text."""
    lines = [z.strip() for z in text.split("\n") if z.strip() and not z.strip().startswith(("#", "|"))]
    points = [re.sub(r"^(?:[-*]|\d+[.)])\s+", "", z) for z in lines if re.match(r"^(?:[-*]|\d+[.)])\s+", z)]
    if len(points) >= len(lines) / 2:
        return [{"kind": "bullets", "items": points}] if points else []
    return [{"kind": "text", "text": " ".join(lines)}]


def _sentences(text: str, most: int) -> str:
    """Whole sentences of a prose up to about ``most`` characters, never cut in the middle."""
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    out = ""
    for sentence in sentences:
        if out and len(out) + len(sentence) + 1 > most:
            break
        out = f"{out} {sentence}".strip()
    return out


def _prose_first(blocks: list) -> tuple[str, list[dict]]:
    """The section's running text joined into one and the one block that shows it, extras drop."""
    texts = [str(b.get("text") or "").strip() for b in blocks
             if isinstance(b, dict) and b.get("kind") == "text" and str(b.get("text") or "").strip()]
    others = [b for b in blocks if isinstance(b, dict) and b.get("kind") != "text" and schema.clean_block(b)]
    if len(others) > 1:
        logger.info("Section with {} visuals, only the first one stays", len(others))
    return " ".join(texts), others[:1]


def _usable(part: dict | None) -> bool:
    return part is not None and any(schema.clean_block(b) for b in part.get("blocks") or [])


def _short(part: dict) -> bool:
    text, _ = _prose_first(part["blocks"])
    return len(re.findall(r"[.!?](?:\s|$)", text)) < MIN_SENTENCES


def _prose_lines(prose: str) -> str:
    """Running text out of a written section, list lines and headings left out."""
    return " ".join(z for z in prose.split("\n") if z.strip()
                    and not re.match(r"^\s*(?:[-*#|]|\d+[.)]\s)", z))


def _costs(sections: list) -> list[int]:
    """What each section of a page is expected to write, its running text and one further block."""
    return [PAGES_SECTION_CHARS for _ in sections]


async def _blocks(caller: Caller, *, language: str, plan: Outline, text_map: tm.TextMap,
                  store: RunStore, should_stop, instructions: str,
                  already: list[str] | None = None) -> dict[int, dict]:
    """Every section as blocks, several sections per call, what is missing after that in one more.

    A section the first calls left out is asked for again together with every other one left
    out, a section whose running text came out too short gets it in one prose call for all of
    them. So a failure costs one call for the whole page, not one per section.

    ``already`` is what the frame already put on the page, the writers leave it out.
    """
    done = dict(store.load_blocks())
    groups = planning.group_sections(plan.sections, _costs(plan.sections), PAGES_SECTION_GROUP_CHARS)
    open_groups = [g for g in ([i for i in all_of if i not in done] for all_of in groups) if g]
    all_others = lambda group: [a for j, a in enumerate(plan.sections) if j not in group]

    def material(group: list[int]) -> list[str]:
        each = tm.write_budget(caller.window_tokens) // max(1, len(group))
        return [text_map.passages(plan.sections[i].spots, first=plan.sections[i].named,
                                  neighbours=MAP_PASSAGE_NEIGHBOURS, budget=each) for i in group]

    async def blocks_of(group: list[int]) -> None:
        result = await write_blocks(caller, language=language, group=[plan.sections[i] for i in group],
                                    indices=group, others=all_others(group), material=material(group),
                                    names=plan.names, instructions=instructions, on_page=already)
        for i, part in zip(group, result):
            if _usable(part):
                text, shows = _prose_first(part["blocks"])
                done[i] = {**part, "blocks": ([{"kind": "text", "text": text}] if text else []) + shows}
                store.save_blocks(i, done[i])
        store.progress("section", len(done), len(plan.sections))

    async def prose(group: list[int]) -> list[str]:
        """Running text for these sections in one call, one call each only when it cannot be cut apart."""
        others, stuff = all_others(group), material(group)
        texts = await planning.write_sections(
            caller, language=language, template_body=TEMPLATE_BODY,
            group=[plan.sections[i] for i in group], others=others, written=None,
            material=stuff, budget=SUMMARY_SECTION_GROUP_CHARS, names=plan.names,
            instructions=instructions)
        return texts if texts and len(texts) == len(group) else [""] * len(group)

    may = (lambda: not should_stop()) if should_stop else None
    store.progress("section", len(done), len(plan.sections))
    results = await concurrency.run_limited([lambda g=g: blocks_of(g) for g in open_groups],
                                            caller.at_once, may_start=may)
    if any(e is concurrency.SKIPPED for e in results):
        raise PipelineInterrupted

    missing = [i for i in range(len(plan.sections)) if i not in done]
    if missing:
        logger.info("{} sections are missing, one call fetches them", len(missing))
        await blocks_of(missing)
    missing = [i for i in range(len(plan.sections)) if i not in done]
    if missing:
        # Prose is the fallback, a section never goes missing for its shape.
        logger.warning("Sections {} without blocks, they are written as text", missing)
        texts = await prose(missing)
        for i, text in zip(missing, texts):
            if not text.strip():
                text = (await prose([i]))[0]
            done[i] = {"lead": "", "map_label": "", "blocks": _text_from_prose(text), "keywords": [],
                       "prose": True}
            store.save_blocks(i, done[i])

    short = [i for i, part in done.items()
             if part.get("blocks") and not part.get("prose") and _short(part)]
    if short:
        logger.info("{} sections with too short a text, one call writes it", len(short))
        for i, text in zip(short, await prose(short)):
            fresh = _sentences(_prose_lines(text), PROSE_CHARS)
            if not fresh:
                continue
            _, shows = _prose_first(done[i]["blocks"])
            done[i] = {**done[i], "blocks": [{"kind": "text", "text": fresh}] + shows}
            store.save_blocks(i, done[i])
    return done


async def run(caller: Caller, *, sources: list[Source], store: RunStore,
              should_stop: Callable[[], bool] | None = None, instructions: str = "",
              image_style: str = "") -> dict:
    """Plan, blocks and frame, laid down as a draft that is finished with pictures."""
    language = store.load_language()
    if not language:
        # A page is German or English, material in any other language makes it English.
        language = LANGUAGES[page_locale(detect_language(sources))]["name"]
        store.save_language(language)
    text_map = tm.TextMap(sources)
    if not len(text_map):
        raise NoPlan("No source carries text.")

    plan = await _outline(caller, language=language, should_stop=should_stop,
                          sources=sources, text_map=text_map, store=store,
                          instructions=instructions)
    if not plan.sections:
        raise NoPlan("no outline")
    effective = "" if instruction.drops_out(plan.instruction_way) else instructions

    frame = store.load_frame()
    if frame is None:
        # The planning call wrote the frame along, a call of its own only when it left it out.
        frame = frame_from_plan(plan.extra) or await write_frame(
            caller, language=language, plan=plan, instructions=effective)
        store.save_frame(frame)
    already = [g for g in (frame.get("gist") or []) if isinstance(g, str)]
    blocks = await _blocks(caller, language=language, plan=plan, text_map=text_map, store=store,
                           should_stop=should_stop, instructions=effective, already=already)
    return draft(plan, blocks, frame, sources=sources, language=language, image_style=image_style)


def page_locale(language: str) -> str:
    """German pages get German fixed texts, every other language the English ones."""
    return "de" if (language or "").casefold().startswith(("german", "deutsch")) else "en"


def _count(term: str, text: str) -> int:
    return len(re.findall(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I))


def word_cloud(keywords: list[str], material: str) -> list[list]:
    """The terms of the sections, weighted by how often the material itself uses them."""
    counted: dict[str, list] = {}
    for w in keywords:
        key = w.casefold()
        if key not in counted:
            n = _count(w, material)
            if n:
                counted[key] = [w, n]
    return sorted(counted.values(), key=lambda e: -e[1])[:CLOUD_WORDS]


def _short_title(title: str) -> str:
    """The title's first part for the middle of the mind map, a subtitle after a colon or dash drops."""
    return re.split(r"\s*[:–—]\s*|\s+-\s+", title, maxsplit=1)[0].strip() or title


def draft(plan: Outline, blocks: dict[int, dict], frame: dict, *, sources: list[Source],
          language: str, image_style: str = "") -> dict:
    """The page with its pictures only named, cleaned to the limits of the schema."""
    loc = page_locale(language)
    title = plan.title or Path(sources[0].name).stem
    gist = [g for g in (frame.get("gist") or []) if isinstance(g, str) and g.strip()]
    if not gist and plan.intro:
        gist = [s.strip() for s in re.split(r"(?<=[.!?])\s+", plan.intro) if s.strip()][:4]
    lead = str(frame.get("lead") or "").strip()
    if not lead and plan.intro:
        lead = re.split(r"(?<=[.!?])\s+", plan.intro.strip())[0]

    design = frame.get("design") if frame.get("design") in schema.DESIGNS else schema.DESIGNS[0]
    hero = {"id": "top", "hero": True, "title": title, "lead": lead, "meta": "", "blocks": []}
    # Every page opens with a picture of its subject, the title stands in when the frame named none.
    subject = str(frame.get("hero_prompt") or "").strip() or f"a calm symbolic scene that stands for the topic {title}"
    picture = {"kind": "image", "src": HERO_IMAGE, "alt": frame.get("hero_alt") or "",
               "prompt": image_prompt(subject, image_style), "caption": ""}
    # The picture is a section of its own above the title, so it can be moved or hidden alone.
    pages = [{"id": COVER_ID, "title": "", "lead": "", "blocks": [picture]}, hero]

    gist_blocks: list[dict] = []
    if gist:
        gist_blocks.append({"kind": "bullets", "items": gist[:4]})
    formula = frame.get("formula")
    if isinstance(formula, dict) and (formula.get("key") or "").strip():
        gist_blocks.append({"kind": "formula", "key": formula.get("key"), "text": formula.get("text")})
    if gist_blocks:
        pages.append({"id": "gist", "title": t("pages.gistTitle", loc), "lead": "",
                      "blocks": gist_blocks})

    content = []
    for i, section in enumerate(plan.sections):
        part = blocks.get(i)
        if not part:
            continue
        content.append((i, {"id": f"s{i + 1}", "title": section.title, "lead": part.get("lead", ""),
                            "blocks": list(part.get("blocks") or [])}, part))

    _once([gist_blocks] + [s["blocks"] for _, s, _ in content])

    # A timeline is its own overview, the map would only repeat it.
    if len(content) >= MIN_MAP_SECTIONS and design != "timeline":
        pages.append({"id": "map", "title": t("pages.mapTitle", loc), "lead": "",
                      "blocks": [{"kind": "mindmap", "center": _short_title(title),
                                  "caption": t("pages.mapCaption", loc),
                                  "branches": [{"title": part.get("map_label") or s["title"],
                                                "to": s["id"], "leaves": part.get("keywords", [])[:3]}
                                               for _, s, part in content[:schema.MAX_BRANCHES]]}]})
    pages.extend(s for _, s, _ in content)

    stuff = "\n".join(q.text for q in sources)
    words = word_cloud([w for _, _, part in content for w in part.get("keywords", [])], stuff)
    if len(words) >= MIN_CLOUD_WORDS:
        pages.append({"id": "words", "title": t("pages.wordsTitle", loc), "lead": "",
                      "blocks": [{"kind": "wordcloud", "caption": t("pages.wordsCaption", loc),
                                  "words": words}]})

    # The model copies the labels and names of its material even when told not to, so they go here.
    names = {n.casefold() for n in [*plan.names, *plan.names.values(),
                                    *(Path(q.name).stem for q in sources), *(q.name for q in sources)] if n}
    pages = drop_citations(pages, names)
    # The line under the title is the page's one AI notice, so there is no footer repeating it.
    return schema.clean_page({"lang": loc, "design": design, "sections": pages, "footer": ""})


# A passage or topic label of the material, alone or as a range, such as SZ12 or SZ12-SZ15.
_LABEL = re.compile(r"^(?:SZ|TZ)\s*\d+(?:\s*[-‐-—−]\s*(?:SZ|TZ)?\s*\d+)?$", re.I)
# A page, slide or folio after a document name, such as "S. 3" or "Folie 4".
_PLACE = re.compile(r"[,\s]*(?:S\.|Seite|Seiten|p\.|pp\.|page|Folie|slide)\s*\d+(?:\s*[-–]\s*\d+)?$", re.I)
_BRACKET = re.compile(r"\s*[(\[]([^()\[\]]{1,200})[)\]]")
# A bare chapter or section number of the material, such as 2.1 or 3; a year stays.
_NUMBERING = re.compile(r"^(?:\d{1,3}(?:\.\d{1,3})*)$")


def _is_source(part: str, names: set[str]) -> bool:
    rest = _PLACE.sub("", part.strip()).strip()
    # A bare page or slide is a source part too, as in "(VL1, S. 4)".
    if not rest:
        return bool(part.strip())
    return bool(_LABEL.match(rest) or _NUMBERING.match(rest)) or rest.casefold() in names


def drop_citations(value, names: set[str]):
    """Strips brackets that only name sources, a page condenses and cites nothing.

    A bracket stays as soon as one of its parts is not a source, so "(§ 15 Abs. 4)" or "(n = 30)" remain.
    """
    if isinstance(value, str):
        def away(m: re.Match) -> str:
            parts = re.split(r"\s*[,;]\s*|\s+(?:und|and|&)\s+", m.group(1))
            return "" if all(_is_source(x, names) for x in parts if x.strip()) else m.group(0)
        return re.sub(r"\s+([.,:!?])", r"\1", _BRACKET.sub(away, value)).strip()
    if isinstance(value, list):
        return [drop_citations(x, names) for x in value]
    if isinstance(value, dict):
        return {k: (x if k in ("src", "prompt", "kind", "id", "to", "icon", "chart_type") else drop_citations(x, names))
                for k, x in value.items()}
    return value


def _once(lists: list[list[dict]]) -> None:
    """Cards, the core sentence and each formula stand once on a page, later ones take a plainer kind or go."""
    seen: set[str] = set()
    formulas: set[str] = set()
    for blocks in lists:
        # The same formula stands once, a repeat of the opening one goes.
        for b in list(blocks):
            if b.get("kind") in ("formula", "highlight"):
                key = "".join(str(b.get("key") or "").split()).casefold()
                if key and key in formulas:
                    blocks.remove(b)
                formulas.add(key)
        for k, b in enumerate(blocks):
            kind = b.get("kind")
            if kind == "highlight":
                # There is no highlight box, a formula the model still sends that way becomes one.
                blocks[k] = b = {"kind": "formula", "key": b.get("key"), "text": b.get("text")}
                kind = "formula"
            if kind in seen and kind == "cards":
                blocks[k] = {"kind": "definitions", "items": [
                    {"term": c.get("title"), "text": c.get("text")} for c in b.get("cards") or []
                    if isinstance(c, dict)]}
            elif kind in seen and kind == "quote":
                blocks[k] = {"kind": "text", "text": b.get("text")}
            seen.add(kind)


def _words_on(page: dict) -> int:
    n = 0

    def count(v) -> None:
        nonlocal n
        if isinstance(v, str):
            n += len(v.split())
        elif isinstance(v, list):
            for x in v:
                count(x)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k not in ("src", "prompt", "kind", "id", "icon", "to", "chart_type"):
                    count(x)

    count(page.get("sections"))
    return n


def finish(page: dict, *, today: date) -> dict:
    """The line under the title, the page's one AI notice."""
    loc = page.get("lang") or "de"
    minutes = max(1, round(_words_on(page) / WORDS_PER_MINUTE))
    stamp = today.strftime("%d.%m.%Y") if loc == "de" else today.strftime("%d %B %Y").lstrip("0")
    meta = t("pages.meta", loc, date=stamp, minutes=minutes)
    for s in page["sections"]:
        if s.get("hero"):
            s["meta"] = meta
    return page
