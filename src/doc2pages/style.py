"""The stylesheet of a page, embedded in every ``index.html`` so a page needs no server."""

CSS = """
:root {
  --pg-ink: #15202b;
  --pg-ink-soft: #3d4b59;
  --pg-muted: #67737f;
  --pg-accent: #004261;
  --pg-fill: #0a6a93;
  --pg-mist: #eef2f5;
  --pg-line: #d7dee4;
  --pg-cell: #ffffff;
  --pg-soft: #8fb6c8;
  --pg-amber: #e0a100;
  --pg-good: #1d7a4c;
  --pg-good-bg: #e4f4ea;
  --pg-bad: #b3261e;
  --pg-bad-bg: #fbe9e7;
  --pg-warn: #8a5a00;
  --pg-warn-bg: #fdf1dc;
  --pg-bg: #ffffff;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--pg-bg); color: var(--pg-ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 18px; line-height: 1.6;
}
.wrap { max-width: 1080px; margin: 0 auto; padding: 0 24px; }
.txt { max-width: 680px; }
section { position: relative; padding-top: 84px; scroll-margin-top: 16px; }
h1, h2 { hyphens: manual; overflow-wrap: break-word; }
h2 { font-weight: 700; font-size: clamp(28px, 3.4vw, 40px); line-height: 1.1; letter-spacing: -0.022em; margin: 0 0 12px; }
h3 { color: var(--pg-ink); }
.lead { font-size: 20px; line-height: 1.5; color: var(--pg-ink-soft); margin: 0; }
.hero { display: grid; grid-template-columns: minmax(0, 1fr); gap: 32px; padding-top: 40px; }
.hero .hero-text { max-width: 820px; }
.hero h1 { font-weight: 800; font-size: clamp(44px, 6vw, 76px); line-height: 0.98; letter-spacing: -0.035em; margin: 0 0 20px; }
.hero .lead { font-size: 21px; max-width: 46ch; margin-bottom: 18px; }
.meta { font-size: 14px; color: var(--pg-muted); line-height: 1.55; margin: 0; }
@media (max-width: 900px) { .hero { gap: 26px; padding-top: 32px; } }
.d-guide .hero-text { max-width: none; background: var(--pg-mist); border-radius: 20px; padding: 48px 40px; }
.d-guide .hero h1 { font-size: clamp(34px, 4.4vw, 54px); }
@media (max-width: 640px) { .d-guide .hero-text { padding: 28px 22px; } }
section.cover { padding-top: 0; }
section.cover .blk { margin-top: 0; }
section.cover .img img { max-height: none; aspect-ratio: 21 / 9; object-fit: cover; border-radius: 20px; }
.blk { margin-top: 26px; }
.panel { background: var(--pg-mist); border-radius: 20px; padding: 24px; }
.panel svg { display: block; width: 100%; height: auto; }
figure { margin: 0; }
figcaption { font-size: 14px; color: var(--pg-muted); margin-top: 10px; line-height: 1.5; }
.img img { display: block; width: 100%; height: auto; border-radius: 14px; }
.blk > .img img { max-height: 440px; object-fit: cover; }
ul.bul { margin: 0; padding-left: 24px; list-style: disc; max-width: 760px; }
ul.bul li { margin: 6px 0; }
ul.bul li::marker { color: var(--pg-accent); }
.prose { margin: 0; max-width: 720px; }
.hl { display: flex; align-items: center; gap: 30px; padding: 26px 30px; background: var(--pg-fill); color: #fff; border-radius: 20px; }
.hl .k { font-style: italic; font-size: 48px; line-height: 1.05; font-weight: 500; overflow-wrap: anywhere; flex-shrink: 0; max-width: 60%; }
.hl .x { font-size: 18px; line-height: 1.5; color: rgba(255, 255, 255, 0.92); }
@media (max-width: 600px) { .hl { flex-direction: column; align-items: flex-start; gap: 12px; } .hl .k { font-size: 38px; max-width: none; } }
.grid { display: grid; gap: 18px; }
.g1 { grid-template-columns: minmax(0, 1fr); }
.g2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.g3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.g4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
@media (max-width: 900px) { .g4 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .g2, .g3, .g4 { grid-template-columns: minmax(0, 1fr); } }
.cell { background: var(--pg-cell); border-radius: 14px; padding: 16px; }
.cell h3 { font-size: 17px; font-weight: 700; line-height: 1.3; margin: 0 0 4px; }
.cell p { font-size: 16px; line-height: 1.5; color: var(--pg-ink-soft); margin: 0; }
.ic { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center; margin-bottom: 10px; font-size: 18px; }
.ic.check { background: var(--pg-good-bg); color: var(--pg-good); }
.ic.x { background: var(--pg-bad-bg); color: var(--pg-bad); }
.ic.warning { background: var(--pg-warn-bg); color: var(--pg-warn); }
.ic.info, .ic.idea { background: var(--pg-mist); color: var(--pg-accent); }
.num { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: var(--pg-fill); color: #fff; font-weight: 700; font-size: 14px; margin-bottom: 10px; }
.fig-n .v { font-size: 40px; font-weight: 800; letter-spacing: -0.02em; color: var(--pg-accent); line-height: 1.1; }
.fig-n .l { font-size: 15px; color: var(--pg-ink-soft); margin-top: 4px; }
.barrow { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 16px; align-items: center; padding: 12px 0; border-bottom: 2px solid var(--pg-cell); }
.barrow:last-child { border-bottom: none; }
.barrow .bl { font-weight: 600; font-size: 16px; }
.barrow .bt { font-size: 14px; color: var(--pg-ink-soft); }
.track { display: flex; align-items: center; gap: 10px; }
.track > i { display: block; height: 14px; border-radius: 99px; background: var(--pg-fill); min-width: 4px; }
.track > b { font-size: 15px; font-variant-numeric: tabular-nums; }
@media (max-width: 640px) { .barrow { grid-template-columns: minmax(0, 1fr); } }
.tbl { overflow-x: auto; border-radius: 14px; }
table { width: 100%; border-collapse: collapse; background: var(--pg-cell); font-size: 16px; line-height: 1.5; }
th { text-align: left; font-weight: 700; padding: 13px 16px; border-bottom: 2px solid var(--pg-ink); vertical-align: bottom; }
td { padding: 12px 16px; border-bottom: 2px solid var(--pg-mist); vertical-align: top; }
tr:last-child td { border-bottom: none; }
td:first-child { font-weight: 600; color: var(--pg-muted); }
.legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 14px; color: var(--pg-ink-soft); margin-top: 8px; }
.legend i { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.legend i.s0 { background: var(--pg-fill); }
.legend i.s1 { background: var(--pg-amber); }
svg .grid-line { stroke: var(--pg-line); }
svg .axis { fill: var(--pg-muted); font-family: inherit; font-size: 12px; }
svg .axis-title { fill: var(--pg-ink-soft); font-family: inherit; font-weight: 600; font-size: 12px; }
svg .s0 { stroke: var(--pg-fill); }
svg .s1 { stroke: var(--pg-amber); }
svg .bar { fill: var(--pg-fill); }
svg .dot { fill: var(--pg-cell); stroke: var(--pg-fill); }
svg .mm-edge { stroke: var(--pg-soft); fill: none; }
svg .mm-node { fill: var(--pg-cell); stroke: var(--pg-fill); }
svg .mm-node-text { fill: var(--pg-ink); font-family: inherit; font-weight: 700; font-size: 13px; }
svg a { cursor: pointer; }
svg a:hover .mm-node { stroke: var(--pg-accent); }
svg .mm-center { fill: var(--pg-fill); }
svg .mm-center-text { fill: #fff; font-family: inherit; font-weight: 800; }
svg .cw { font-family: inherit; }
svg .cw0 { fill: var(--pg-accent); font-weight: 800; }
svg .cw1 { fill: var(--pg-fill); font-weight: 600; opacity: 0.85; }
svg .cw2 { fill: var(--pg-soft); font-weight: 600; }
.quote { border-left: 4px solid var(--pg-accent); padding: 4px 0 4px 20px; font-size: 22px; line-height: 1.45; margin: 0; max-width: 760px; }
.quote b { color: var(--pg-accent); font-weight: 700; }
ul.check { list-style: none; margin: 0; padding: 0; max-width: 760px; }
ul.check li { position: relative; padding: 8px 0 8px 32px; border-bottom: 2px solid var(--pg-mist); }
ul.check li:last-child { border-bottom: none; }
ul.check li::before { content: ""; position: absolute; left: 0; top: 13px; width: 16px; height: 16px; border: 2px solid var(--pg-accent); border-radius: 4px; }
dl.defs { margin: 0; max-width: 760px; }
dl.defs dt { font-weight: 700; margin-top: 14px; }
dl.defs dt:first-child { margin-top: 0; }
dl.defs dd { margin: 2px 0 0; color: var(--pg-ink-soft); }
.acc details { border-bottom: 2px solid var(--pg-line); padding: 12px 0; }
.acc details:last-child { border-bottom: none; }
.acc summary { font-weight: 700; cursor: pointer; }
.acc p { margin: 8px 0 0; color: var(--pg-ink-soft); }
ol.steps, ol.cycle { list-style: none; margin: 0; padding: 0; counter-reset: s; }
ol.steps li, ol.cycle li { counter-increment: s; position: relative; padding: 0 0 0 44px; margin-top: 18px; }
ol.steps li:first-child, ol.cycle li:first-child { margin-top: 0; }
ol.steps li::before, ol.cycle li::before { content: counter(s); position: absolute; left: 0; top: 0; width: 28px; height: 28px; border-radius: 50%; background: var(--pg-fill); color: #fff; font-weight: 700; font-size: 14px; display: flex; align-items: center; justify-content: center; }
ol.steps h3, ol.cycle h3 { margin: 0 0 2px; font-size: 17px; }
ol.steps p, ol.cycle p { margin: 0; color: var(--pg-ink-soft); font-size: 16px; }
.cycle-center { font-weight: 700; color: var(--pg-accent); margin: 0 0 14px; }
ul.tl { list-style: none; margin: 0; padding: 0 0 0 24px; border-left: 2px solid var(--pg-line); }
ul.tl li { position: relative; padding: 0 0 0 18px; margin-bottom: 20px; }
ul.tl li:last-child { margin-bottom: 0; }
ul.tl li::before { content: ""; position: absolute; left: -31px; top: 6px; width: 12px; height: 12px; border-radius: 50%; background: var(--pg-cell); border: 2px solid var(--pg-accent); }
ul.tl .date { font-weight: 700; color: var(--pg-accent); font-size: 15px; }
ul.tl h3 { margin: 2px 0; font-size: 17px; }
ul.tl p { margin: 0; color: var(--pg-ink-soft); font-size: 16px; }
.tree-root { font-weight: 800; font-size: 20px; margin: 0 0 14px; color: var(--pg-accent); }
ul.tree { list-style: none; margin: 0; padding: 0; }
ul.tree > li { border-top: 2px solid var(--pg-line); padding: 12px 0; }
ul.tree > li:first-child { border-top: none; }
ul.tree > li > b { display: block; }
ul.tree > li > span { display: block; color: var(--pg-ink-soft); font-size: 16px; }
ol.levels { list-style: none; margin: 0; padding: 0; }
ol.levels li { background: var(--pg-cell); border-radius: 12px; padding: 14px 16px; margin-top: 10px; }
ol.levels li:first-child { margin-top: 0; }
ol.levels h3 { margin: 0 0 2px; font-size: 17px; }
ol.levels p { margin: 0; color: var(--pg-ink-soft); font-size: 16px; }
.scale .rail { position: relative; height: 4px; background: var(--pg-line); border-radius: 99px; margin: 40px 0 10px; }
.scale .pin { position: absolute; top: -6px; width: 16px; height: 16px; border-radius: 50%; background: var(--pg-fill); transform: translateX(-50%); }
.scale .pin span { position: absolute; bottom: 22px; left: 50%; transform: translateX(-50%); white-space: nowrap; font-size: 13px; color: var(--pg-ink-soft); }
.scale .poles { display: flex; justify-content: space-between; font-size: 14px; font-weight: 600; color: var(--pg-accent); }
.sides { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.sides.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
@media (max-width: 640px) { .sides, .sides.three { grid-template-columns: minmax(0, 1fr); } }
.side { background: var(--pg-cell); border-radius: 14px; padding: 16px; }
.side h3 { margin: 0 0 8px; font-size: 17px; }
.side ul { margin: 0; padding-left: 20px; }
.side li { margin: 4px 0; font-size: 16px; }
.side.good { border-top: 4px solid var(--pg-good); }
.side.bad { border-top: 4px solid var(--pg-bad); }
.both { margin-top: 14px; background: var(--pg-cell); border-radius: 14px; padding: 16px; }
.both h3 { margin: 0 0 8px; font-size: 17px; }
.matrix { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
@media (max-width: 640px) { .matrix { grid-template-columns: minmax(0, 1fr); } }
.axes { display: flex; justify-content: space-between; font-size: 14px; font-weight: 600; color: var(--pg-accent); margin-bottom: 10px; }
.formula .key { font-size: 26px; font-weight: 700; color: var(--pg-accent); margin: 0 0 8px; overflow-wrap: anywhere; }
.formula p { margin: 0 0 10px; }
.formula ul { margin: 0; padding-left: 20px; }
.formula .ex { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 15px; background: var(--pg-cell); border-radius: 10px; padding: 12px 14px; margin-top: 10px; }
.formula .ex div { margin: 2px 0; }
ul.mistakes { list-style: none; margin: 0; padding: 0; }
ul.mistakes li { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 12px; }
ul.mistakes li:first-child { margin-top: 0; }
@media (max-width: 640px) { ul.mistakes li { grid-template-columns: minmax(0, 1fr); } }
ul.mistakes .wrong { background: var(--pg-bad-bg); color: var(--pg-bad); border-radius: 12px; padding: 12px 14px; font-size: 16px; }
ul.mistakes .right { background: var(--pg-good-bg); color: var(--pg-good); border-radius: 12px; padding: 12px 14px; font-size: 16px; }
.example h3 { margin: 0 0 8px; font-size: 19px; }
.example ol { margin: 10px 0; padding-left: 22px; }
.example .result { font-weight: 700; color: var(--pg-accent); margin: 0; }
.mm-list { list-style: none; margin: 14px 0 0; padding: 0; }
.mm-list > li { padding: 10px 0; border-top: 2px solid var(--pg-line); }
.mm-list > li:first-child { border-top: none; }
.mm-list b { color: var(--pg-accent); }
.mm-list span { display: block; font-size: 15px; color: var(--pg-ink-soft); }
.pfoot { margin-top: 96px; padding: 28px 0 100px; border-top: 2px solid var(--pg-mist); font-size: 14.5px; color: var(--pg-muted); }
.pfoot p { margin: 0; }
.cards-list { list-style: none; margin: 0; padding: 0; }
.overview { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; margin-top: 32px; }
.overview a { display: block; text-decoration: none; color: inherit; background: var(--pg-mist); border-radius: 18px; overflow: hidden; }
.overview img { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; }
.overview .cap { padding: 16px 18px 20px; }
.overview h2 { font-size: 20px; margin: 0 0 6px; }
.overview p { margin: 0; font-size: 15px; color: var(--pg-ink-soft); }
@media print {
  section { padding-top: 28px; }
  figure, table, .panel, svg, li { break-inside: avoid; }
  h1, h2, h3, h2 + p { break-after: avoid; }
  body { font-size: 12pt; }
}
@media (prefers-color-scheme: dark) {
  :root {
    --pg-ink: #e8eef3; --pg-ink-soft: #b7c3cd; --pg-muted: #8d9aa6;
    --pg-accent: #7cc3e4; --pg-fill: #1d7fa8; --pg-mist: #1a222b;
    --pg-line: #2c3844; --pg-cell: #111820; --pg-soft: #4b7f98;
    --pg-good-bg: #10301f; --pg-bad-bg: #351614; --pg-warn-bg: #332509;
    --pg-good: #6fd49b; --pg-bad: #f29189; --pg-warn: #e5bb62;
    --pg-bg: #0b1016;
  }
}
"""
