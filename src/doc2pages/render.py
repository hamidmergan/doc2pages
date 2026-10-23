"""A page as a standalone HTML file and as Markdown.

Every block kind of the schema is drawn here in one fixed look. Charts, mind maps and
word clouds become inline SVG, so a page needs no script and no network.
"""

from __future__ import annotations

import html
import math

from . import schema
from .style import CSS
from .texts import t

ICONS = {"check": "✓", "x": "✕", "warning": "!", "idea": "★", "info": "i", "none": ""}


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _num(v: float) -> str:
    return f"{v:g}"


def _cols(count: int) -> str:
    return "g1" if count <= 1 else "g2" if count == 2 else "g3" if count == 3 else "g4"


def _caption(block: dict) -> str:
    caption = block.get("caption")
    return f"<figcaption>{esc(caption)}</figcaption>" if caption else ""


# --- the single blocks ----------------------------------------------------------------

def _text(b: dict) -> str:
    return f'<p class="prose">{esc(b["text"])}</p>'


def _bullets(b: dict) -> str:
    items = "".join(f"<li>{esc(x)}</li>" for x in b["items"])
    return f'<ul class="bul">{items}</ul>'


def _highlight(b: dict) -> str:
    key = f'<div class="k">{esc(b.get("key"))}</div>' if b.get("key") else ""
    body = f'<div class="x">{esc(b.get("text"))}</div>' if b.get("text") else ""
    return f'<div class="hl">{key}{body}</div>'


def _cards(b: dict) -> str:
    cards = b["cards"]
    out = []
    for c in cards:
        icon = c.get("icon") or "none"
        mark = f'<div class="ic {esc(icon)}">{ICONS.get(icon, "")}</div>' if icon != "none" else ""
        out.append(f'<div class="cell">{mark}<h3>{esc(c["title"])}</h3>'
                   f'<p>{esc(c["text"])}</p></div>')
    grid = "g1" if b.get("cols") == 1 else _cols(len(cards))
    return f'<div class="grid {grid}">{"".join(out)}</div>'


def _steps(b: dict) -> str:
    items = "".join(f'<li><h3>{esc(s["title"])}</h3><p>{esc(s["text"])}</p></li>' for s in b["steps"])
    return f'<ol class="steps">{items}</ol>'


def _figures(b: dict) -> str:
    cells = "".join(f'<div class="cell fig-n"><div class="v">{esc(f["value"])}</div>'
                    f'<div class="l">{esc(f["label"])}</div></div>' for f in b["figures"])
    return f'<div class="grid {_cols(len(b["figures"]))}">{cells}</div>'


def _bars(b: dict) -> str:
    top = b.get("max") or max((x["value"] for x in b["bars"]), default=1) or 1
    rows = []
    for x in b["bars"]:
        share = max(0.0, min(1.0, x["value"] / top)) * 100
        note = f'<div class="bt">{esc(x["text"])}</div>' if x.get("text") else ""
        rows.append(f'<div class="barrow"><div><div class="bl">{esc(x["label"])}</div>{note}</div>'
                    f'<div class="track"><i style="width:{share:.1f}%"></i>'
                    f'<b>{esc(_num(x["value"]))}</b></div></div>')
    return f'<div class="panel">{"".join(rows)}</div>'


def _table(b: dict) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in b["header"])
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in b["rows"])
    return (f'<figure><div class="tbl"><table><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>{_caption(b)}</figure>")


# --- charts ---------------------------------------------------------------------------

_W, _H = 720, 360
_PAD_L, _PAD_R, _PAD_T, _PAD_B = 56, 16, 16, 48


def _axes(categories: list[str], low: float, high: float, y_label: str, x_label: str) -> list[str]:
    out = []
    span = high - low or 1
    for i in range(5):
        y = _PAD_T + (_H - _PAD_T - _PAD_B) * i / 4
        value = high - span * i / 4
        out.append(f'<line class="grid-line" x1="{_PAD_L}" y1="{y:.1f}" x2="{_W - _PAD_R}" y2="{y:.1f}"/>')
        out.append(f'<text class="axis" x="{_PAD_L - 8}" y="{y + 4:.1f}" text-anchor="end">{esc(_num(value))}</text>')
    step = (_W - _PAD_L - _PAD_R) / max(1, len(categories) - 1 if len(categories) > 1 else 1)
    for i, c in enumerate(categories):
        x = _PAD_L + step * i if len(categories) > 1 else (_W - _PAD_R + _PAD_L) / 2
        out.append(f'<text class="axis" x="{x:.1f}" y="{_H - _PAD_B + 20}" text-anchor="middle">{esc(c)}</text>')
    if y_label:
        out.append(f'<text class="axis-title" x="4" y="{_PAD_T + 4}">{esc(y_label)}</text>')
    if x_label:
        out.append(f'<text class="axis-title" x="{_W - _PAD_R}" y="{_H - 6}" text-anchor="end">{esc(x_label)}</text>')
    return out


def _line_chart(b: dict) -> str:
    cats, series = b["categories"], b["series"]
    values = [v for s in series for v in s["values"]]
    low, high = min(0.0, min(values)), max(values) or 1
    parts = _axes(cats, low, high, b.get("y_label"), b.get("x_label"))
    span = high - low or 1
    step = (_W - _PAD_L - _PAD_R) / max(1, len(cats) - 1)
    for n, s in enumerate(series):
        points = []
        for i, v in enumerate(s["values"]):
            x = _PAD_L + step * i
            y = _PAD_T + (_H - _PAD_T - _PAD_B) * (1 - (v - low) / span)
            points.append((x, y))
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
        parts.append(f'<path class="s{n % 2}" d="{path}" fill="none" stroke-width="3"/>')
        for x, y in points:
            parts.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="4" stroke-width="2"/>')
    return "".join(parts)


def _bar_chart(b: dict) -> str:
    cats = b["categories"]
    values = b["series"][0]["values"]
    high = max(values) or 1
    parts = _axes(cats, 0, high, b.get("y_label"), b.get("x_label"))
    width = (_W - _PAD_L - _PAD_R) / len(cats)
    for i, v in enumerate(values):
        height = (_H - _PAD_T - _PAD_B) * (v / high)
        x = _PAD_L + width * i + width * 0.2
        y = _H - _PAD_B - height
        parts.append(f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{width * 0.6:.1f}" '
                     f'height="{height:.1f}" rx="4"/>')
    return "".join(parts)


def _pie_chart(b: dict) -> str:
    cats = b["categories"]
    values = b["series"][0]["values"]
    total = sum(values) or 1
    cx, cy, r = _W / 2, _H / 2, min(_W, _H) / 2 - 20
    parts, angle = [], -math.pi / 2
    for i, v in enumerate(values):
        sweep = 2 * math.pi * (v / total)
        x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
        angle += sweep
        x2, y2 = cx + r * math.cos(angle), cy + r * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        shade = 0.35 + 0.6 * (i / max(1, len(values) - 1)) if len(values) > 1 else 0.7
        parts.append(f'<path d="M{cx:.1f},{cy:.1f} L{x1:.1f},{y1:.1f} '
                     f'A{r:.1f},{r:.1f} 0 {large} 1 {x2:.1f},{y2:.1f} Z" '
                     f'fill="var(--pg-fill)" fill-opacity="{shade:.2f}" stroke="var(--pg-cell)" stroke-width="2"/>')
    legend = "".join(f'<span><i class="s0" style="opacity:{0.35 + 0.6 * (i / max(1, len(values) - 1)) if len(values) > 1 else 0.7:.2f}"></i>'
                     f"{esc(c)} {esc(_num(v))}</span>" for i, (c, v) in enumerate(zip(cats, values)))
    body = "".join(parts)
    return (f'<svg viewBox="0 0 {_W} {_H}" role="img">{body}</svg>'
            f'<div class="legend">{legend}</div>')


def _chart(b: dict) -> str:
    kind = b.get("chart_type") or "bar"
    if kind == "pie":
        inner = _pie_chart(b)
        svg = inner
    else:
        body = _line_chart(b) if kind == "line" else _bar_chart(b)
        svg = f'<svg viewBox="0 0 {_W} {_H}" role="img">{body}</svg>'
        if kind == "line" and len(b["series"]) > 1:
            svg += '<div class="legend">' + "".join(
                f'<span><i class="s{n % 2}"></i>{esc(s["name"])}</span>'
                for n, s in enumerate(b["series"])) + "</div>"
    return f'<figure><div class="panel">{svg}</div>{_caption(b)}</figure>'


def _image(b: dict) -> str:
    caption = f'<figcaption>{esc(b["caption"])}</figcaption>' if b.get("caption") else ""
    return (f'<figure class="img"><div class="pic">'
            f'<img src="{esc(b["src"])}" alt="{esc(b.get("alt"))}" loading="lazy"></div>'
            f"{caption}</figure>")


# One character of a mind map label, at the font sizes the stylesheet sets for it.
_MM_NODE_CHAR = 7.4   # 13px, bold
_MM_CENTER_CHAR = 8.4  # 15px, bolder


def _mm_label(text: str, limit: int) -> str:
    """A label short enough for a pill, cut between words and marked when it was cut."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return (text[:limit - 1].rsplit(" ", 1)[0] or text[:limit - 1]) + "…"


def _mindmap(b: dict) -> str:
    branches = b["branches"]
    labels = [_mm_label(br["title"], 28) for br in branches]
    # Every pill is as wide as its own label, so no title is cut off by its box.
    halves = [min(124.0, max(70.0, len(s) * _MM_NODE_CHAR / 2 + 14)) for s in labels]
    width = 760
    wide = max(halves)
    rx = width / 2 - wide - 8
    ry = max(120.0, 34.0 * len(branches))
    height = 2 * (ry + 30)
    cx, cy = width / 2, height / 2
    parts = []
    for i, (label, half) in enumerate(zip(labels, halves)):
        angle = 2 * math.pi * i / len(branches) - math.pi / 2
        x, y = cx + rx * math.cos(angle), cy + ry * math.sin(angle)
        parts.append(f'<path class="mm-edge" d="M{cx:.1f},{cy:.1f} Q{(cx + x) / 2:.1f},{y:.1f} '
                     f'{x:.1f},{y:.1f}" stroke-width="2"/>')
        parts.append(f'<rect class="mm-node" x="{x - half:.1f}" y="{y - 16:.1f}" '
                     f'width="{2 * half:.1f}" height="32" rx="10" stroke-width="2"/>')
        parts.append(f'<text class="mm-node-text" x="{x:.1f}" y="{y + 5:.1f}" '
                     f'text-anchor="middle">{esc(label)}</text>')
    center = _mm_label(b["center"], 18)
    # The circle keeps its size, the label shrinks until it fits inside it.
    size = min(15.0, 86.0 / max(len(center) * _MM_CENTER_CHAR, 1) * 15.0)
    parts.append(f'<circle class="mm-center" cx="{cx:.1f}" cy="{cy:.1f}" r="54"/>')
    parts.append(f'<text class="mm-center-text" x="{cx:.1f}" y="{cy + size / 3:.1f}" '
                 f'font-size="{size:.1f}px" text-anchor="middle">{esc(center)}</text>')
    listed = "".join(f'<li><b>{esc(br["title"])}</b>'
                     + (f'<span>{esc(", ".join(br["leaves"]))}</span>' if br.get("leaves") else "")
                     + "</li>" for br in branches)
    svg = f'<svg viewBox="0 0 {width} {height:.0f}" role="img">{"".join(parts)}</svg>'
    return (f'<figure><div class="panel">{svg}</div>'
            f'<ul class="mm-list">{listed}</ul>{_caption(b)}</figure>')


def _wordcloud(b: dict) -> str:
    words = b["words"]
    high = max(n for _, n in words) or 1
    width, line_height = 760, 46
    rows: list[list[tuple[str, int]]] = [[]]
    used = 0.0
    for word, n in words:
        size = 16 + 26 * (n / high)
        room = len(word) * size * 0.58 + 24
        if used + room > width and rows[-1]:
            rows.append([])
            used = 0.0
        rows[-1].append((word, n))
        used += room
    parts = []
    for r, row in enumerate(rows):
        total = sum(len(w) * (16 + 26 * (n / high)) * 0.58 + 24 for w, n in row)
        x = (width - total) / 2
        y = (r + 1) * line_height
        for word, n in row:
            size = 16 + 26 * (n / high)
            rank = 0 if n >= high * 0.7 else 1 if n >= high * 0.4 else 2
            room = len(word) * size * 0.58 + 24
            parts.append(f'<text class="cw cw{rank}" x="{x + room / 2:.1f}" y="{y:.1f}" '
                         f'font-size="{size:.1f}" text-anchor="middle">{esc(word)}</text>')
            x += room
    height = len(rows) * line_height + 16
    svg = f'<svg viewBox="0 0 {width} {height}" role="img">{"".join(parts)}</svg>'
    return f'<figure><div class="panel">{svg}</div>{_caption(b)}</figure>'


def _quote(b: dict) -> str:
    body = esc(b["text"])
    key = b.get("keyword")
    if key:
        marked = esc(key)
        body = body.replace(marked, f"<b>{marked}</b>", 1)
    return f'<blockquote class="quote">{body}</blockquote>'


def _checklist(b: dict) -> str:
    return '<ul class="check">' + "".join(f"<li>{esc(x)}</li>" for x in b["items"]) + "</ul>"


def _definitions(b: dict) -> str:
    body = "".join(f'<dt>{esc(d["term"])}</dt><dd>{esc(d["text"])}</dd>' for d in b["items"])
    return f'<dl class="defs">{body}</dl>'


def _accordion(b: dict) -> str:
    body = "".join(f'<details><summary>{esc(e["title"])}</summary><p>{esc(e["text"])}</p></details>'
                   for e in b["items"])
    return f'<div class="acc panel">{body}</div>'


def _cycle(b: dict) -> str:
    center = f'<p class="cycle-center">{esc(b["center"])}</p>' if b.get("center") else ""
    items = "".join(f'<li><h3>{esc(s["title"])}</h3><p>{esc(s["text"])}</p></li>' for s in b["steps"])
    return f'<div class="panel">{center}<ol class="cycle">{items}</ol></div>'


def _timeline(b: dict) -> str:
    items = "".join(f'<li><span class="date">{esc(e["date"])}</span>'
                    f'<h3>{esc(e["title"])}</h3><p>{esc(e["text"])}</p></li>' for e in b["events"])
    return f'<ul class="tl">{items}</ul>'


def _tree(b: dict) -> str:
    items = "".join(f'<li><b>{esc(br["title"])}</b>'
                    + (f'<span>{esc(", ".join(br["leaves"]))}</span>' if br.get("leaves") else "")
                    + "</li>" for br in b["branches"])
    return f'<div class="panel"><p class="tree-root">{esc(b["root"])}</p><ul class="tree">{items}</ul></div>'


def _levels(b: dict) -> str:
    items = "".join(f'<li><h3>{esc(e["title"])}</h3><p>{esc(e["text"])}</p></li>' for e in b["items"])
    return f'<figure><ol class="levels">{items}</ol>{_caption(b)}</figure>'


def _scale(b: dict) -> str:
    pins = "".join(f'<span class="pin" style="left:{x["pos"] * 100:.1f}%">'
                   f'<span>{esc(x["label"])}</span></span>' for x in b["items"])
    return (f'<figure><div class="panel scale"><div class="rail">{pins}</div>'
            f'<div class="poles"><span>{esc(b["left"])}</span><span>{esc(b["right"])}</span></div>'
            f"</div>{_caption(b)}</figure>")


def _side(side: dict, extra: str = "") -> str:
    items = "".join(f"<li>{esc(x)}</li>" for x in side["items"])
    return f'<div class="side {extra}"><h3>{esc(side["title"])}</h3><ul>{items}</ul></div>'


def _versus(b: dict) -> str:
    good_bad = b.get("tone") == "good_bad"
    return ('<div class="sides">'
            + _side(b["a"], "good" if good_bad else "")
            + _side(b["b"], "bad" if good_bad else "")
            + "</div>")


def _venn(b: dict) -> str:
    sides = [b["a"], b["b"]] + ([b["c"]] if b.get("c") else [])
    grid = "sides three" if len(sides) == 3 else "sides"
    both = "".join(f"<li>{esc(x)}</li>" for x in b["both"])
    return (f'<div class="{grid}">' + "".join(_side(s) for s in sides) + "</div>"
            f'<div class="both"><h3>&amp;</h3><ul>{both}</ul></div>')


def _matrix(b: dict) -> str:
    cells = "".join(f'<div class="cell"><h3>{esc(c["title"])}</h3><p>{esc(c["text"])}</p></div>'
                    for c in b["cells"])
    points = ""
    if b.get("points"):
        points = '<ul class="bul">' + "".join(
            f'<li>{esc(p["label"])}</li>' for p in b["points"]) + "</ul>"
    return (f'<div class="panel"><div class="axes"><span>{esc(b["y"])}</span>'
            f'<span>{esc(b["x"])}</span></div><div class="matrix">{cells}</div>{points}</div>')


def _formula(b: dict) -> str:
    parts = ""
    if b.get("parts"):
        parts = "<ul>" + "".join(f'<li><b>{esc(p["sym"])}</b> {esc(p["text"])}</li>'
                                 for p in b["parts"]) + "</ul>"
    example = ""
    if b.get("example"):
        example = '<div class="ex">' + "".join(f"<div>{esc(x)}</div>" for x in b["example"]) + "</div>"
    body = f"<p>{esc(b['text'])}</p>" if b.get("text") else ""
    return f'<div class="panel formula"><p class="key">{esc(b["key"])}</p>{body}{parts}{example}</div>'


def _mistakes(b: dict) -> str:
    items = "".join(f'<li><div class="wrong">{esc(p["wrong"])}</div>'
                    f'<div class="right">{esc(p["right"])}</div></li>' for p in b["pairs"])
    return f'<ul class="mistakes">{items}</ul>'


def _example(b: dict) -> str:
    title = f"<h3>{esc(b['title'])}</h3>" if b.get("title") else ""
    situation = f"<p>{esc(b['situation'])}</p>" if b.get("situation") else ""
    steps = "<ol>" + "".join(f"<li>{esc(x)}</li>" for x in b["steps"]) + "</ol>" if b.get("steps") else ""
    return (f'<div class="panel example">{title}{situation}{steps}'
            f'<p class="result">{esc(b["result"])}</p></div>')


_HTML = {
    "text": _text, "bullets": _bullets, "highlight": _highlight, "cards": _cards, "steps": _steps,
    "figures": _figures, "bars": _bars, "table": _table, "chart": _chart, "image": _image,
    "mindmap": _mindmap, "wordcloud": _wordcloud, "quote": _quote, "checklist": _checklist,
    "definitions": _definitions, "accordion": _accordion, "cycle": _cycle, "timeline": _timeline,
    "tree": _tree, "levels": _levels, "scale": _scale, "versus": _versus, "matrix": _matrix,
    "venn": _venn, "formula": _formula, "mistakes": _mistakes, "example": _example,
}


def block_html(block: dict) -> str:
    """One block as HTML, an empty string for a kind that draws nothing."""
    draw = _HTML.get(block.get("kind"))
    if draw is None:
        return ""
    return f'<div class="blk k-{esc(block["kind"])}">{draw(block)}</div>'


def _section_html(section: dict) -> str:
    blocks = "".join(block_html(b) for b in section.get("blocks") or [])
    if section.get("hero"):
        lead = f'<p class="lead">{esc(section["lead"])}</p>' if section.get("lead") else ""
        meta = f'<p class="meta">{esc(section["meta"])}</p>' if section.get("meta") else ""
        return (f'<section id="{esc(section["id"])}" class="hero"><div class="hero-text">'
                f'<h1>{esc(section["title"])}</h1>{lead}{meta}</div>{blocks}</section>')
    cover = " cover" if section.get("id") == "cover" else ""
    head = ""
    if section.get("title") or section.get("lead"):
        title = f'<h2>{esc(section["title"])}</h2>' if section.get("title") else ""
        lead = f'<p class="lead">{esc(section["lead"])}</p>' if section.get("lead") else ""
        head = f'<div class="txt">{title}{lead}</div>'
    return (f'<section id="{esc(section["id"])}" class="sec{cover}">'
            f'{head}<div class="body">{blocks}</div></section>')


def page_html(page: dict, *, title: str = "") -> str:
    """The whole page as one standalone HTML document, the stylesheet inside it."""
    view = schema.for_viewers(page)
    lang = view.get("lang") or "en"
    head_title = title or schema.title_of(view) or t("pages.overview", lang)
    sections = "".join(_section_html(s) for s in view["sections"])
    footer = f'<div class="pfoot"><p>{esc(view["footer"])}</p></div>' if view.get("footer") else ""
    return (
        "<!doctype html>\n"
        f'<html lang="{esc(lang)}">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(head_title)}</title>\n<style>{CSS}</style>\n</head>\n"
        f'<body class="d-{esc(view.get("design") or "chapters")}">\n'
        f'<main class="wrap">{sections}{footer}</main>\n</body>\n</html>\n'
    )


# --- Markdown -------------------------------------------------------------------------

def _md_rows(rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in rows]


def block_markdown(b: dict) -> list[str]:
    """One block as Markdown lines."""
    k = b.get("kind")
    if k == "text":
        return [b["text"]]
    if k == "bullets":
        return [f"- {x}" for x in b["items"]]
    if k == "highlight":
        return ["> " + ": ".join(x for x in (b.get("key"), b.get("text")) if x)]
    if k == "cards":
        return [f'**{c["title"]}** {c["text"]}'.strip() for c in b["cards"]]
    if k == "steps":
        return [f'{i + 1}. **{s["title"]}** {s["text"]}'.strip() for i, s in enumerate(b["steps"])]
    if k == "figures":
        return [f'- **{f["value"]}** {f["label"]}'.strip() for f in b["figures"]]
    if k == "bars":
        return [f'- {x["label"]}: {_num(x["value"])}'
                + (f', {x["text"]}' if x.get("text") else "") for x in b["bars"]]
    if k == "table":
        lines = [f'*{b["caption"]}*', ""] if b.get("caption") else []
        lines += _md_rows([b["header"]])
        lines.append("| " + " | ".join("---" for _ in b["header"]) + " |")
        lines += _md_rows(b["rows"])
        return lines
    if k == "chart":
        lines = [f'*{b["caption"]}*', ""] if b.get("caption") else []
        lines += _md_rows([[""] + list(b["categories"])])
        lines.append("| " + " | ".join("---" for _ in range(len(b["categories"]) + 1)) + " |")
        lines += _md_rows([[s["name"]] + [_num(v) for v in s["values"]] for s in b["series"]])
        return lines
    if k == "image":
        line = f'![{b.get("alt") or ""}]({b["src"]})'
        return [line] + ([f'*{b["caption"]}*'] if b.get("caption") else [])
    if k == "mindmap":
        lines = [f'**{b["center"]}**']
        lines += [f'- {br["title"]}' + (f': {", ".join(br["leaves"])}' if br["leaves"] else "")
                  for br in b["branches"]]
        return lines
    if k == "wordcloud":
        return [", ".join(f"{w} ({n})" for w, n in b["words"])]
    if k == "quote":
        return ["> " + b["text"]]
    if k == "checklist":
        return [f"- [ ] {x}" for x in b["items"]]
    if k == "definitions":
        return [f'- **{d["term"]}**: {d["text"]}'.rstrip(": ") for d in b["items"]]
    if k in ("accordion", "levels"):
        lines = [f'*{b["caption"]}*', ""] if b.get("caption") else []
        return lines + [f'- **{e["title"]}** {e["text"]}'.strip() for e in b["items"]]
    if k == "cycle":
        lines = [f'**{b["center"]}**'] if b.get("center") else []
        return lines + [f'{i + 1}. **{s["title"]}** {s["text"]}'.strip()
                        for i, s in enumerate(b["steps"])]
    if k == "timeline":
        return [f'- **{e["date"]}** {e["title"]}: {e["text"]}'.rstrip(": ") for e in b["events"]]
    if k == "tree":
        return [f'**{b["root"]}**'] + [
            f'- {br["title"]}' + (f': {", ".join(br["leaves"])}' if br["leaves"] else "")
            for br in b["branches"]]
    if k == "scale":
        lines = [f'*{b["caption"]}*', ""] if b.get("caption") else []
        return lines + [f'{b["left"]} … {b["right"]}'] + [
            f'- {x["label"]} ({x["pos"]:.2f})' for x in b["items"]]
    if k in ("versus", "venn"):
        sides = [b["a"], b["b"]] + ([b["c"]] if b.get("c") else [])
        lines = []
        for side in sides:
            lines.append(f'**{side["title"]}**')
            lines += [f"- {x}" for x in side["items"]]
        if b.get("both"):
            lines.append("**&**")
            lines += [f"- {x}" for x in b["both"]]
        return lines
    if k == "matrix":
        lines = [f'{b["y"]} / {b["x"]}']
        lines += [f'- **{c["title"]}** {c["text"]}'.strip() for c in b["cells"]]
        lines += [f'- {p["label"]}' for p in b.get("points") or []]
        return lines
    if k == "formula":
        lines = [f'**{b["key"]}**'] + ([b["text"]] if b.get("text") else [])
        lines += [f'- **{p["sym"]}**: {p["text"]}' for p in b["parts"]]
        if b["example"]:
            lines += ["", "```", *b["example"], "```"]
        return lines
    if k == "mistakes":
        return [f'- {p["wrong"]} → {p["right"]}' for p in b["pairs"]]
    if k == "example":
        lines = [f'**{b["title"]}**'] if b.get("title") else []
        if b.get("situation"):
            lines.append(b["situation"])
        lines += [f"{i + 1}. {x}" for i, x in enumerate(b["steps"])]
        lines.append(f'**{b["result"]}**')
        return lines
    return []


def page_markdown(page: dict) -> str:
    """The whole page as Markdown, one heading per section."""
    view = schema.for_viewers(page)
    out: list[str] = []
    for s in view["sections"]:
        if s.get("hero"):
            if s.get("title"):
                out += [f'# {s["title"]}', ""]
            if s.get("lead"):
                out += [s["lead"], ""]
            if s.get("meta"):
                out += [f'*{s["meta"]}*', ""]
        elif s.get("title"):
            out += [f'## {s["title"]}', ""]
        if s.get("lead") and not s.get("hero"):
            out += [s["lead"], ""]
        for b in s.get("blocks") or []:
            lines = block_markdown(b)
            if lines:
                out += lines + [""]
    if view.get("footer"):
        out += ["---", "", view["footer"], ""]
    return "\n".join(out).strip() + "\n"


def overview_html(entries: list[dict], *, locale: str = "en") -> str:
    """The page that lists every page of a run, each card linking into its folder."""
    cards = []
    for e in entries:
        picture = (f'<img src="{esc(e["folder"])}/{esc(e["image"])}" alt="">'
                   if e.get("image") else "")
        lead = f'<p>{esc(e["lead"])}</p>' if e.get("lead") else ""
        cards.append(f'<a href="{esc(e["folder"])}/index.html">{picture}'
                     f'<div class="cap"><h2>{esc(e["title"])}</h2>{lead}</div></a>')
    title = t("pages.overview", locale)
    return (
        "<!doctype html>\n"
        f'<html lang="{esc(locale)}">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f'<main class="wrap"><section class="hero"><div class="hero-text">'
        f"<h1>{esc(title)}</h1></div></section>"
        f'<div class="overview">{"".join(cards)}</div></main>\n</body>\n</html>\n'
    )
