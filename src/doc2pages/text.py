"""A page as plain text, one part per section, so it can be read and quoted."""

from __future__ import annotations

from dataclasses import dataclass

from . import schema


@dataclass
class Part:
    """One section of the page as text, ``anchor`` is the section's id on the page."""

    anchor: str
    title: str
    text: str


def _num(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _block(b: dict) -> list[str]:
    """The lines a reader would take from one block, charts and tables spelled out."""
    k = b.get("kind")
    if k == "text":
        return [b["text"]]
    if k == "bullets":
        return [f"- {x}" for x in b["items"]]
    if k == "highlight":
        return [": ".join(x for x in (b.get("key"), b.get("text")) if x)]
    if k == "cards":
        return [": ".join(x for x in (c["title"], c["text"]) if x) for c in b["cards"]]
    if k == "steps":
        return [f"{i + 1}. " + ": ".join(x for x in (s["title"], s["text"]) if x)
                for i, s in enumerate(b["steps"])]
    if k == "figures":
        return [f"{f['value']} {f['label']}".strip() for f in b["figures"]]
    if k == "bars":
        return [f"{x['label']}: {_num(x['value'])}" + (f", {x['text']}" if x.get("text") else "")
                for x in b["bars"]]
    if k == "table":
        lines = [b["caption"]] if b.get("caption") else []
        lines.append(" | ".join(b["header"]))
        lines += [" | ".join(r) for r in b["rows"]]
        return lines
    if k == "chart":
        lines = [b["caption"]] if b.get("caption") else []
        for s in b["series"]:
            values = ", ".join(f"{c}: {_num(v)}" for c, v in zip(b["categories"], s["values"]))
            lines.append(f"{s['name']}: {values}" if s.get("name") else values)
        return lines
    if k == "image":
        return [b["caption"]] if b.get("caption") else []
    if k == "mindmap":
        return [f"{br['title']}: {', '.join(br['leaves'])}" for br in b["branches"]]
    if k == "wordcloud":
        return [", ".join(w for w, _ in b["words"])]
    if k in ("quote", "checklist"):
        return [b["text"]] if k == "quote" else [f"- {x}" for x in b["items"]]
    if k == "definitions":
        return [": ".join(x for x in (d["term"], d["text"]) if x) for d in b["items"]]
    if k in ("accordion", "levels"):
        return ([b["caption"]] if b.get("caption") else []) + [
            ": ".join(x for x in (e["title"], e["text"]) if x) for e in b["items"]]
    if k == "cycle":
        return ([b["center"]] if b.get("center") else []) + [
            f"{i + 1}. " + ": ".join(x for x in (s["title"], s["text"]) if x) for i, s in enumerate(b["steps"])]
    if k == "timeline":
        return [f"{e['date']}: " + ": ".join(x for x in (e["title"], e["text"]) if x) for e in b["events"]]
    if k == "tree":
        return [b["root"]] + [f"{br['title']}: {', '.join(br['leaves'])}".rstrip(": ") for br in b["branches"]]
    if k == "scale":
        return [f"{b['left']} … {b['right']}: " + ", ".join(x["label"] for x in b["items"])]
    if k in ("versus", "venn"):
        sides = [b["a"], b["b"]] + ([b["c"]] if b.get("c") else [])
        lines = [f"{x['title']}: {', '.join(x['items'])}" for x in sides]
        return lines + ([", ".join(b["both"])] if b.get("both") else [])
    if k == "matrix":
        return [f"{b['y']} / {b['x']}"] + [": ".join(x for x in (c["title"], c["text"]) if x) for c in b["cells"]]
    if k == "formula":
        return [": ".join(x for x in (b["key"], b["text"]) if x)] + [
            f"{x['sym']}: {x['text']}" for x in b["parts"]] + b["example"]
    if k == "mistakes":
        return [f"{x['wrong']} → {x['right']}" for x in b["pairs"]]
    if k == "example":
        return [x for x in (b["title"], b["situation"], *b["steps"], b["result"]) if x]
    return []


def parts(page: dict) -> list[Part]:
    """Every section others may see, in page order, without the frame's map and cloud."""
    out: list[Part] = []
    for s in schema.for_viewers(page)["sections"]:
        if s.get("id") in ("map", "words"):
            continue
        lines = [x for x in (s.get("lead"), s.get("meta") if not s.get("hero") else "") if x]
        for b in s.get("blocks") or []:
            lines += [z for z in _block(b) if z]
        text = "\n".join(lines).strip()
        if s.get("title") or text:
            out.append(Part(anchor=s["id"], title=s.get("title") or "", text=text))
    return out


def as_text(page: dict) -> str:
    """The whole page as one text, each section under its heading."""
    return "\n\n".join(f"{p.title}\n{p.text}".strip() for p in parts(page))
