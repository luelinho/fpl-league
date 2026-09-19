"""Phase 7 — dashboard builder (SPEC.md §8).

Renders dashboard.html: a single self-contained file with the digest JSON
baked directly into a <script> tag rather than fetched at runtime. SPEC.md
says the dashboard "reads digest/season.json" — a literal fetch() of a
sibling file fails when the page is opened via file:// (no server, which is
exactly how SPEC.md says this should be used), so the data is embedded
instead. digest/season.json is still generated separately by src/digest.py,
for any future consumer that isn't this specific rendering approach.

Usage:
    python -m src.build_dashboard
"""

from __future__ import annotations

import base64
import json
import sys

from . import config
from .digest import build_digest

OUT_PATH_NAME = "dashboard.html"
FONT_PATH = config.REPO_ROOT / "assets" / "fonts" / "inter-variable-latin.woff2"


def _font_face_css() -> str:
    """Inter, embedded as base64 — chosen for mobile legibility (tall
    x-height, open apertures, designed and widely used for UI text at small
    sizes) over relying only on each OS's own system font. Picked 2026-09-19
    after comparing it live against Manrope, Nunito Sans, Work Sans, and
    Poppins — one font per Home card, then Inter vs. Work Sans head-to-head
    across the whole page (the two strongest candidates) — before settling
    on Inter for the density of tables/numbers this dashboard is built from.
    Embedded rather than linked from Google Fonts to keep the page fully
    self-contained (no network access needed to open it, same reasoning as
    every other asset here). It's the variable-weight file (one file covers
    400-900, every weight this stylesheet actually uses) and the latin-only
    subset (Google's own CSS2 API split by unicode range; this dashboard
    only ever renders Latin text) to keep it small — 47KB, versus several
    hundred KB for the full multi-script file. Falls back to the existing
    system-font stack if the file is ever missing.
    """
    if not FONT_PATH.exists():
        return ""
    data = base64.b64encode(FONT_PATH.read_bytes()).decode()
    return f"""
@font-face {{
  font-family: 'Inter';
  font-style: normal;
  font-weight: 400 900;
  font-display: swap;
  src: url(data:font/woff2;base64,{data}) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC,
    U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215,
    U+FEFF, U+FFFD;
}}
"""


def render(digest: dict) -> str:
    data_json = json.dumps(digest)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{digest['league']['name']} — League Dashboard</title>
<style>
{_font_face_css()}
{CSS}
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <span class="brand-name">{digest['league']['name']}</span>
      <span class="brand-sub">{digest['league']['season']} · League {digest['league'].get('id', '')}</span>
    </div>
    <nav class="tabs" id="tabs">
      <button class="tab active" data-tab="home">Home</button>
      <button class="tab" data-tab="myteam">My Team</button>
      <button class="tab" data-tab="league">League</button>
      <button class="tab" data-tab="managers">Managers</button>
      <button class="tab" data-tab="players">Players</button>
      <button class="tab" data-tab="analytics">Analytics</button>
      <button class="tab" data-tab="history">History</button>
    </nav>
  </div>
</header>

<main class="container">
  <section id="page-home" class="page active"></section>
  <section id="page-myteam" class="page"></section>
  <section id="page-league" class="page"></section>
  <section id="page-managers" class="page"></section>
  <section id="page-players" class="page"></section>
  <section id="page-analytics" class="page"></section>
  <section id="page-history" class="page"></section>
</main>

<div id="matchup-modal" class="modal-overlay" style="display:none">
  <div class="modal-card">
    <button class="modal-close" id="modal-close-btn" aria-label="Close">✕</button>
    <div id="modal-body"></div>
  </div>
</div>

<footer class="footer">
  Generated {digest['generated_at']} · Fact = stored raw data. Computed = derived by a documented formula.
</footer>

<script>
const DIGEST = {data_json};
{JS}
</script>
</body>
</html>
"""


CSS = """
:root {
  /* EPL-inspired palette, adopted 2026-09-19 — real colors sampled from
     premierleague.com's own live stylesheet, not guessed: #37003c (their
     signature purple), #ff2882 (pink), #00ff87 (their neon green).
     Replaced the original near-black/lime palette after a live
     side-by-side comparison. */
  --bg: #1a0020;
  --card: rgba(65,5,75,0.55);
  --card-2: rgba(84,30,93,0.5);
  --ink: #f5f4f8;
  --ink-soft: #c3b2c4;
  --border: rgba(255,255,255,0.10);
  --accent: #00ff87;
  --accent-ink: #051b10;
  --accent-soft: rgba(0,255,135,0.14);
  --purple: #ff2882;
  --purple-soft: rgba(255,40,130,0.16);
  --coral: #ff7a70;
  --coral-soft: rgba(255,122,112,0.15);
  --win: var(--accent);
  --win-soft: var(--accent-soft);
  --loss: var(--coral);
  --loss-soft: var(--coral-soft);
  --draw: var(--purple);
  --draw-soft: var(--purple-soft);
  --locked: #9b809d;
  --shadow: 0 1px 0 rgba(255,255,255,0.06) inset, 0 20px 50px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.02);
  --blur: blur(24px);
}
* { box-sizing: border-box; }
body {
  margin: 0; color: var(--ink); min-height: 100vh;
  background:
    radial-gradient(ellipse 900px 650px at 6% -8%, rgba(130,20,150,0.42), transparent 55%),
    radial-gradient(ellipse 1000px 750px at 100% 105%, rgba(255,40,130,0.22), transparent 55%),
    radial-gradient(ellipse 700px 600px at 60% 30%, rgba(0,255,135,0.08), transparent 60%),
    var(--bg);
  background-attachment: fixed;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px; line-height: 1.45;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
.topbar {
  background: rgba(26,0,32,0.55); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10;
}
.topbar-inner {
  max-width: 1080px; margin: 0 auto; padding: 16px 20px;
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
}
.brand-name { font-weight: 700; font-size: 17px; display: block; color: var(--ink); letter-spacing: -0.01em; }
.brand-sub { color: var(--ink-soft); font-size: 12.5px; }
.tabs { display: flex; gap: 4px; background: var(--card); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); padding: 5px; border-radius: 999px; border: 1px solid var(--border); max-width: 100%; min-width: 0; overflow-x: auto; -webkit-overflow-scrolling: touch; }
.tab {
  border: none; background: transparent; padding: 9px 16px; border-radius: 999px;
  font-size: 13.5px; font-weight: 600; color: var(--ink-soft); cursor: pointer;
}
.tab.active { background: var(--accent); color: var(--accent-ink); }
.tab:hover:not(.active) { color: var(--ink); }
.container { max-width: 1080px; margin: 0 auto; padding: 24px 20px 60px; }
.page { display: none; }
.page.active { display: block; }
.grid { display: grid; gap: 16px; }
.grid-2 { grid-template-columns: 1fr 1fr; }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }
.home-top-grid {
  display: grid; gap: 16px; grid-template-columns: 1fr 1fr;
  grid-template-areas: "standings fixtures" "results next";
}
.home-top-grid > .gc-standings { grid-area: standings; align-self: start; }
.home-top-grid > .gc-fixtures { grid-area: fixtures; }
.home-top-grid > .gc-results { grid-area: results; }
.home-top-grid > .gc-next { grid-area: next; }
@media (max-width: 720px) {
  .home-top-grid {
    grid-template-columns: 1fr;
    grid-template-areas: "fixtures" "results" "standings" "next";
  }
}
@media (max-width: 720px) { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }
@media (max-width: 720px) {
  .tab[data-tab="myteam"] { display: none; }
  .container { padding-bottom: 90px; }
  /* backdrop-filter on .topbar (an ancestor of #tabs) creates a new containing
     block for fixed-position descendants, so #tabs's "bottom: 0" would resolve
     against .topbar instead of the viewport unless this is dropped here. */
  .topbar { backdrop-filter: none; -webkit-backdrop-filter: none; background: rgba(26,0,32,0.92); }
  #tabs {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 15;
    background: rgba(26,0,32,0.92); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
    border-top: 1px solid var(--border); border-radius: 0; max-width: none;
    padding: 6px 4px calc(6px + env(safe-area-inset-bottom)); justify-content: space-around;
  }
  #tabs .tab { flex: 1; text-align: center; padding: 8px 2px; font-size: 11px; }
  /* The 8 manager stat tiles (Record, League points, ... Hit cost) — compact
     them to a 2-column grid with smaller type so Gameweek history's heading
     comes into view sooner instead of needing to scroll past 8 full-width rows. */
  .grid-4 { grid-template-columns: 1fr 1fr; gap: 8px; }
  .grid-4 .card.stat { padding: 10px 12px; border-radius: 14px; }
  .grid-4 .stat .value { font-size: 18px; }
  .grid-4 .stat .label { font-size: 10.5px; }

  /* Tighter card/section rhythm — desktop's padding and heading margins were
     tuned for a wide canvas and eat too much of a phone's width/height. */
  .container { padding-left: 14px; padding-right: 14px; }
  .card { padding: 16px 14px; border-radius: 16px; }
  .locked-card { padding: 20px 16px; }
  .section-title { font-size: 17px; margin: 24px 0 12px; }
  table { font-size: 13px; }
  th, td { padding: 9px 7px; }

  /* Record badges (3W 0D 0L) can force some table columns down to their
     min-content width, which used to wrap each badge onto its own line and
     triple a row's height. record-badges keeps them one nowrap unit instead —
     the column just takes its natural width and the table scrolls sideways. */
  .record-badges .badge { padding: 2px 6px; font-size: 10.5px; }

  /* Tables with more columns than a phone can show at once (League/Analytics
     standings, gameweek history) still scroll horizontally via .card's own
     overflow-x — this just makes that discoverable instead of looking like a
     cut-off layout bug. A mask paints the fade without adding any box to the
     layout: an absolutely-positioned ::after here (an earlier attempt at this
     same fade) expanded the container's own scrollable area and made these
     tables load pre-scrolled, hiding the # and Manager columns by default. */
  .wide-table {
    mask-image: linear-gradient(to right, black calc(100% - 24px), transparent 100%);
    -webkit-mask-image: linear-gradient(to right, black calc(100% - 24px), transparent 100%);
  }

  /* Bump touch targets that were sized for a mouse cursor up toward the ~40px+
     minimum that's comfortable to hit with a thumb. */
  .modal-close { width: 40px; height: 40px; font-size: 15px; top: 12px; right: 12px; }
  .gw-nav-arrow { width: 42px; height: 42px; font-size: 17px; }
  .gw-nav-select { padding: 9px 14px; min-height: 42px; }
  .tabbtn-group button { padding: 10px 16px; min-height: 40px; }
  #manager-select { min-height: 44px; padding: 11px 12px !important; }
  th { padding-top: 11px; padding-bottom: 11px; }

  /* The modal's fixed side padding was tuned for desktop's 920px card; on a
     360-400px phone it was taking a visible bite out of already-tight content
     width. */
  .modal-overlay { padding: 16px 8px; }
  .modal-card { padding: 20px 14px 22px; border-radius: 16px; }
}
/* Visible keyboard/switch-control focus ring — the buttons, tabs and rows
   below are otherwise borderless with no default focus indication. Applies
   at every width; it only ever shows for non-pointer input. */
.tab:focus-visible, .tabbtn-group button:focus-visible, .gw-nav-arrow:focus-visible,
.modal-close:focus-visible, .h2h-team-tabs button:focus-visible, th:focus-visible,
.match-row.clickable:focus-visible, tr.clickable-row:focus-visible, .proj-card:focus-visible,
select:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px;
}
.card {
  background: var(--card); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
  border: 1px solid var(--border); border-radius: 20px; overflow-x: auto;
  padding: 20px 22px; box-shadow: var(--shadow);
}
.card h2 { margin: 0 0 12px; font-size: 15px; color: var(--ink); font-weight: 700; }
.card h3 { margin: 0 0 8px; font-size: 13px; color: var(--ink-soft); text-transform: uppercase; letter-spacing: 0.03em; }
.recap-card { border-left: 3px solid var(--accent); }
.recap-card h2 { color: var(--accent); }
.recap-card p { margin: 0 0 10px; line-height: 1.5; }
.recap-card p:last-child { margin-bottom: 0; }
.stat { display: flex; flex-direction: column; gap: 3px; }
.stat .value { font-size: 27px; font-weight: 700; color: var(--ink); }
.stat .label { color: var(--ink-soft); font-size: 12.5px; }
.stat-tier-elite { color: var(--accent) !important; }
.stat-tier-great { color: #8fd645 !important; }
.stat-tier-ok { color: #ffb04a !important; }
.stat-tier-low { color: var(--coral) !important; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th, td { text-align: left; padding: 10px 10px; border-bottom: 1px solid var(--border); }
th { color: var(--ink-soft); font-weight: 600; font-size: 11.5px; text-transform: uppercase;
     letter-spacing: 0.04em; cursor: pointer; user-select: none; }
th:hover { color: var(--ink); }
.table-scroll { max-height: 380px; overflow-y: auto; }
.table-scroll table { margin: 0; }
.table-scroll thead th { position: sticky; top: 0; background: var(--card); z-index: 1; }
tbody tr:hover td { background: rgba(255,255,255,0.02); }
tr.owner-row td { background: var(--accent-soft); }
tr.clickable-row { cursor: pointer; }
tr.row-selected td { background: var(--accent-soft); }
tr:last-child td { border-bottom: none; }
.badge {
  display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 700;
}
.record-badges { display: inline-flex; gap: 3px; white-space: nowrap; }
.badge-w { background: var(--win-soft); color: var(--win); }
.badge-l { background: var(--loss-soft); color: var(--loss); }
.badge-d { background: var(--draw-soft); color: var(--draw); }
.pill { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; background: var(--purple-soft); color: var(--purple); }
.section-title { font-size: 19px; font-weight: 700; margin: 30px 0 14px; color: var(--ink); }
.section-title:first-child { margin-top: 0; }
.plist { display: flex; flex-direction: column; gap: 10px; }
.plist h3 { margin: 0 0 2px; }
.plist-row { display: flex; align-items: center; gap: 10px; }
.plist-kit { width: 26px; height: 26px; object-fit: contain; flex: none; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.5)); }
.plist-name { display: flex; flex-direction: column; width: 130px; flex: none; min-width: 0; }
.plist-name.wide { width: auto; flex: 1; }
.plist-name .pname { font-weight: 600; font-size: 13px; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.plist-sub { font-size: 10.5px; color: var(--ink-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.plist-bar-track { flex: 1; height: 8px; border-radius: 999px; background: rgba(255,255,255,0.08); overflow: hidden; }
.plist-bar-fill { height: 100%; background: var(--accent); border-radius: 999px; }
.plist-bar-fill.faller { background: var(--coral); }
.plist-count { font-size: 12px; font-weight: 700; color: var(--ink-soft); width: 56px; text-align: right; flex: none; }
.plist-count.wide { width: auto; white-space: nowrap; }
.gw-nav { display: flex; align-items: center; gap: 10px; }
.gw-nav-arrow {
  width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--border); background: var(--card-2);
  color: var(--ink); font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center;
}
.gw-nav-arrow:disabled { opacity: 0.3; cursor: not-allowed; }
.gw-nav-arrow:hover:not(:disabled) { background: rgba(255,255,255,0.08); }
.gw-nav-select {
  background: var(--card-2); border: 1px solid var(--border); color: var(--ink); border-radius: 999px;
  padding: 7px 14px; font-size: 13.5px; font-weight: 600; cursor: pointer;
}
.match-row {
  display: flex; align-items: center; justify-content: space-between; padding: 11px 0;
  border-bottom: 1px solid var(--border);
}
.match-row:last-child { border-bottom: none; }
.match-side { flex: 1; font-weight: 600; color: var(--ink); }
.match-side.right { text-align: right; }
.match-score { padding: 0 16px; font-weight: 700; color: var(--ink-soft); white-space: nowrap; }
.match-score .win { color: var(--win); }
.transfer-gw-box { margin-bottom: 14px; }
.transfer-gw-box:last-child { margin-bottom: 0; }
.transfer-gw-box h3 { margin-bottom: 6px; }
.transfer-row {
  display: flex; justify-content: space-between; gap: 12px; padding: 6px 0;
  border-bottom: 1px solid var(--border); font-size: 13px; color: var(--ink);
}
.transfer-row:last-child { border-bottom: none; }
.transfer-in::before { content: '+ '; color: var(--win); font-weight: 700; }
.transfer-out::before { content: '− '; color: var(--loss); font-weight: 700; }
.proj-card {
  padding: 10px 14px; border-radius: 12px; background: var(--card-2); border: 1px solid var(--border);
  cursor: pointer; margin-bottom: 6px; transition: background 0.1s;
}
.proj-card:last-child { margin-bottom: 0; }
.proj-card:hover { background: rgba(255,255,255,0.05); }
.proj-score-row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; gap: 10px; }
.proj-score-side { display: flex; align-items: baseline; gap: 5px; min-width: 0; }
.proj-score-side.right { flex-direction: row-reverse; }
.proj-live { font-size: 20px; font-weight: 800; font-variant-numeric: tabular-nums; color: var(--ink); line-height: 1; }
.proj-live.win { color: var(--accent); }
.proj-total { font-size: 10.5px; color: var(--ink-soft); white-space: nowrap; }
.proj-bar-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-soft); text-align: center; margin-bottom: 3px; opacity: 0.75; }
.proj-bar-row { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }
.proj-pct { font-size: 10px; color: var(--ink-soft); font-variant-numeric: tabular-nums; white-space: nowrap; }
.proj-bar-track { flex: 1; height: 6px; border-radius: 999px; background: rgba(255,255,255,0.08); overflow: hidden; display: flex; }
.proj-bar-seg { height: 100%; }
.proj-bar-seg.lead { background: var(--accent); }
.proj-bar-seg.trail { background: rgba(255,255,255,0.16); }
.proj-bottom-row { display: flex; justify-content: space-between; gap: 10px; }
.proj-info { font-size: 11px; color: var(--ink-soft); min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.proj-info.right { text-align: right; }
.proj-info b { font-weight: 700; color: var(--ink); }
.proj-caveat { font-size: 10px; color: #ffb04a; margin-top: 6px; text-align: center; }
.alert {
  padding: 12px 14px; border-radius: 12px; margin-bottom: 8px; font-size: 13px; color: var(--ink);
  border-left: 3px solid var(--locked); background: var(--card-2);
}
.alert-info { border-color: var(--locked); }
.alert-warning { background: var(--purple-soft); border-color: var(--purple); }
.alert-error { background: var(--coral-soft); border-color: var(--coral); }
.locked-card {
  background:
    repeating-linear-gradient(135deg, transparent, transparent 12px, rgba(255,255,255,0.025) 12px, rgba(255,255,255,0.025) 24px),
    var(--card);
  backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
  border: 1px dashed var(--border); border-radius: 20px; padding: 26px; text-align: center; color: var(--ink-soft);
}
.locked-card .lock-icon { font-size: 22px; filter: grayscale(1) brightness(1.6); }
.progress-bar { height: 6px; background: rgba(255,255,255,0.08); border-radius: 999px; margin: 12px auto; max-width: 240px; overflow: hidden; }
.progress-fill { height: 100%; background: var(--accent); }
.roster-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px solid var(--border); color: var(--ink); }
.roster-row:last-child { border-bottom: none; }
.roster-row.bench { opacity: 0.5; }
.armband { font-weight: 800; font-size: 11px; background: var(--accent); color: var(--accent-ink); border-radius: 5px; padding: 1px 5px; }
.pitch-frame {
  position: relative; border-radius: 20px; padding: 3px;
  background: linear-gradient(135deg, var(--accent) 0%, var(--purple) 50%, #6fd6ff 100%);
  box-shadow: 0 10px 40px -8px rgba(214,251,61,0.25), 0 10px 40px -8px rgba(195,179,247,0.2);
}
.pitch {
  position: relative; display: flex; flex-direction: column; justify-content: space-around;
  gap: 14px; min-height: 380px; padding: 22px 8px; border-radius: 17px; overflow: hidden;
  background:
    radial-gradient(ellipse 90% 60% at 50% 42%, rgba(255,255,255,0.10) 0%, transparent 55%),
    radial-gradient(ellipse 100% 70% at 50% 50%, transparent 40%, rgba(0,0,0,0.34) 100%),
    repeating-linear-gradient(180deg, rgba(255,255,255,0.06) 0 34px, rgba(0,0,0,0.05) 34px 68px),
    linear-gradient(180deg, #227048 0%, #1a4f30 50%, #227048 100%);
}
.pitch::before {
  content: ''; position: absolute; left: 4%; right: 4%; top: 50%; height: 1px;
  background: rgba(255,255,255,0.3); transform: translateY(-50%);
}
.pitch::after {
  content: ''; position: absolute; left: 50%; top: 50%; width: 84px; height: 84px;
  border: 1px solid rgba(255,255,255,0.3); border-radius: 50%; transform: translate(-50%,-50%);
}
.pitch-spot {
  position: absolute; width: 4px; height: 4px; border-radius: 50%;
  background: rgba(255,255,255,0.38); transform: translate(-50%,-50%);
}
.pitch-corner {
  position: absolute; width: 20px; height: 20px; border: 1.5px solid rgba(255,255,255,0.3);
  border-radius: 50%; pointer-events: none;
}
.pitch-corner.tl { top: -10px; left: -10px; }
.pitch-corner.tr { top: -10px; right: -10px; }
.pitch-corner.bl { bottom: -10px; left: -10px; }
.pitch-corner.br { bottom: -10px; right: -10px; }
.pitch-box-top, .pitch-box-bottom {
  position: absolute; left: 22%; right: 22%; height: 16%;
  border: 1px solid rgba(255,255,255,0.3); border-top: none;
}
.pitch-box-top { top: 0; border-top: none; border-bottom: none; border-radius: 0 0 4px 4px; }
.pitch-box-bottom { bottom: 0; border-bottom: none; border-radius: 4px 4px 0 0; }
.pitch-box-top-small, .pitch-box-bottom-small {
  position: absolute; left: 37%; right: 37%; height: 7%;
  border: 1px solid rgba(255,255,255,0.24);
}
.pitch-box-top-small { top: 0; border-top: none; }
.pitch-box-bottom-small { bottom: 0; border-bottom: none; }
.pitch-row { display: flex; justify-content: space-evenly; align-items: flex-start; gap: 6px; position: relative; z-index: 1; flex-wrap: wrap; }
.player-chip { display: flex; flex-direction: column; align-items: center; width: 84px; text-align: center; cursor: pointer; }
.player-pos-label {
  font-size: 9px; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase;
  color: rgba(255,255,255,0.55); margin-bottom: 3px;
}
.player-jersey {
  width: 46px; height: 58px; position: relative;
  display: flex; align-items: center; justify-content: center;
}
.kit-img {
  width: 46px; height: 46px; object-fit: contain; border-radius: 10px;
  filter: drop-shadow(0 3px 6px rgba(0,0,0,0.5));
  box-shadow: 0 0 0 4px rgba(255,255,255,0.07);
}
.player-chip.bench .kit-img { filter: grayscale(0.6) opacity(0.85) drop-shadow(0 2px 4px rgba(0,0,0,0.4)); }
.player-photo-img {
  width: 46px; height: 58px; object-fit: cover; border-radius: 10px;
  filter: drop-shadow(0 3px 6px rgba(0,0,0,0.5));
  box-shadow: 0 0 0 4px rgba(255,255,255,0.07);
}
.player-chip.bench .player-photo-img { filter: grayscale(0.6) opacity(0.85) drop-shadow(0 2px 4px rgba(0,0,0,0.4)); }
.player-armband {
  position: absolute; top: -3px; left: -3px; width: 18px; height: 18px; border-radius: 50%;
  font-size: 10px; font-weight: 800; display: flex; align-items: center; justify-content: center;
  border: 2px solid rgba(10,10,13,0.5); box-shadow: 0 2px 4px rgba(0,0,0,0.4);
}
.player-armband.cap { background: var(--accent); color: var(--accent-ink); }
.player-armband.vice { background: #b18aff; color: #1a0f2e; }
.player-flag {
  position: absolute; top: -4px; right: -4px; width: 16px; height: 16px; border-radius: 50%;
  background: #ffb04a; color: #3a2400; font-size: 9px; display: flex; align-items: center; justify-content: center;
  border: 2px solid rgba(10,10,13,0.5); cursor: help;
}
.player-name {
  margin-top: 8px; background: #f4f2ef; color: #171321; font-weight: 900; font-size: 10.5px;
  letter-spacing: -0.01em; padding: 3px 7px; border-radius: 9px 9px 0 0; width: 100%;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.player-chip.bench .player-name { background: #dedad3; }
.player-pts {
  font-size: 10.5px; font-weight: 900; padding: 3px 7px; border-radius: 0 0 9px 9px; width: 100%; color: #fff;
}
.player-pts.tier-elite { background: var(--accent); color: var(--accent-ink); }
.player-pts.tier-great { background: #8fd645; color: #0a0a0d; }
.player-pts.tier-ok { background: #ffb04a; color: #2c1c00; }
.player-pts.tier-low { background: rgba(255,255,255,0.18); color: #fff; }
.player-pts.not-played { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.65); font-weight: 600; }
.player-fixtures {
  display: flex; flex-direction: column; gap: 1px; width: 100%;
  border-radius: 0 0 9px 9px; overflow: hidden;
}
.fdr-pill.mini { display: block; width: 100%; padding: 2px 3px; font-size: 8.5px; font-weight: 800; border-radius: 0; text-align: center; }
.bench-shelf {
  margin-top: 8px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
  border-radius: 14px; padding: 16px 12px;
}
.player-tooltip {
  position: fixed; z-index: 300; pointer-events: none; max-width: 240px;
  background: #26102b; border: 1px solid var(--border); border-radius: 10px;
  padding: 8px 12px; box-shadow: var(--shadow); opacity: 0; transform: translateY(4px);
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.player-tooltip.visible { opacity: 1; transform: translateY(0); }
.player-tooltip .pt-name { font-size: 12.5px; font-weight: 700; color: var(--ink); white-space: nowrap; }
.player-tooltip .pt-meta { font-size: 11.5px; color: var(--ink-soft); margin-top: 2px; line-height: 1.4; }
.bench-strip { margin-top: 14px; }
.bench-strip h3 { margin-bottom: 10px; }
/* Mobile-only: the full-size pitch (My Team, Managers, League Dream Team,
   and each side of the mobile H2H tab view — everywhere except the H2H
   modal's own side-by-side compact mode, which already has its own
   smaller sizing below) at ~85% of desktop scale, so the whole formation
   plus bench fits with less scrolling on a phone. Scaling font-size alone
   wouldn't do this — the images are fixed px and dominate the height — so
   this scales the jersey/photo dimensions, gaps and padding together with
   the text, roughly 85% of every value above. */
@media (max-width: 720px) {
  .pitch { gap: 12px; min-height: 320px; padding: 19px 7px; }
  .pitch-row { gap: 5px; }
  .player-chip { width: 71px; }
  .player-pos-label { font-size: 7.5px; }
  .player-jersey { width: 39px; height: 49px; }
  .kit-img { width: 39px; height: 39px; }
  .player-photo-img { width: 39px; height: 49px; }
  .player-armband { width: 15px; height: 15px; font-size: 8.5px; }
  .player-flag { width: 14px; height: 14px; font-size: 7.5px; }
  .player-name { margin-top: 7px; font-size: 9px; padding: 2.5px 6px; }
  .player-pts { font-size: 9px; padding: 2.5px 6px; }
  .fdr-pill.mini { font-size: 7px; padding: 1.5px 2px; }
  .bench-shelf { margin-top: 7px; padding: 14px 10px; }
  .bench-strip { margin-top: 12px; }
}
.tabbtn-group { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.tabbtn-group button {
  border: 1px solid var(--border); background: var(--card); padding: 7px 15px; border-radius: 999px;
  font-size: 13px; font-weight: 600; cursor: pointer; color: var(--ink-soft);
}
.tabbtn-group button.active { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
.muted { color: var(--ink-soft); font-size: 12.5px; }
.stat-chips { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 4px; }
.chip { display: inline-block; padding: 5px 12px; border-radius: 999px; font-size: 12.5px; font-weight: 600; background: var(--card-2); border: 1px solid var(--border); color: var(--ink); }
.bench-row { opacity: 0.55; }
.fixture-cell { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; flex: 1; min-width: 0; }
.fdr-pill { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.fdr-1 { background: #0b8a43; color: #fff; }
.fdr-2 { background: #5cc95c; color: #0a0a0d; }
.fdr-3 { background: #e0e04a; color: #2c1c00; }
.fdr-4 { background: #ff8a50; color: #2c1c00; }
.fdr-5 { background: #c0392b; color: #fff; }
.divider { height: 1px; background: var(--border); margin: 18px 0 14px; }
.footer { text-align: center; color: var(--ink-soft); font-size: 12px; padding: 20px; }
.match-row.clickable { cursor: pointer; border-radius: 10px; transition: background 0.1s; }
.match-row.clickable:hover { background: rgba(255,255,255,0.04); }
.modal-overlay {
  position: fixed; inset: 0; background: rgba(20,0,26,0.72); backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px); z-index: 100; display: flex; align-items: flex-start;
  justify-content: center; padding: 40px 16px; overflow-y: auto;
}
.modal-card {
  position: relative; background: #26102b; border: 1px solid var(--border); border-radius: 20px;
  max-width: 920px; width: 100%; padding: 26px 26px 30px; box-shadow: var(--shadow);
}
.modal-close {
  position: absolute; top: 16px; right: 16px; width: 32px; height: 32px; border-radius: 50%;
  border: 1px solid var(--border); background: var(--card-2); color: var(--ink); font-size: 14px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
}
.modal-close:hover { background: var(--coral-soft); color: var(--coral); }
.h2h-header { text-align: center; margin-bottom: 6px; }
.h2h-header .gw-label { color: var(--ink-soft); font-size: 12.5px; text-transform: uppercase; letter-spacing: 0.05em; }
.h2h-score {
  display: flex; align-items: center; justify-content: center; gap: 24px; margin: 10px 0 4px;
}
.h2h-score .side-name { font-size: 17px; font-weight: 700; flex: 1; }
.h2h-score .side-name.right { text-align: right; }
.h2h-score .score-box { font-size: 30px; font-weight: 800; color: var(--ink); white-space: nowrap; }
.h2h-score .score-box .win { color: var(--accent); }
.h2h-score .side-extra { font-size: 12px; font-weight: 500; color: var(--ink-soft); margin-top: 4px; }
.h2h-record {
  text-align: center; color: var(--ink-soft); font-size: 13px; margin-bottom: 18px;
}
.h2h-record b { color: var(--ink); }
.h2h-pitches { display: flex; gap: 18px; flex-wrap: wrap; }
.h2h-pitches > div { flex: 1; min-width: 340px; }
.h2h-pitches h3 { text-align: center; }
/* A 5-a-side line (max legal DEF or MID count) must fit one row at this
   half-width, or the 5th chip wraps onto the pitch markings and the two
   teams' formation lines stop lining up with each other. */
.h2h-pitches .pitch-row { gap: 4px; }
.h2h-pitches .player-chip { width: 60px; }
.h2h-pitches .player-jersey { width: 34px; height: 42px; }
.h2h-pitches .kit-img { width: 34px; height: 34px; }
.h2h-pitches .player-photo-img { width: 34px; height: 42px; }
.h2h-pitches .player-name, .h2h-pitches .player-pts { font-size: 9px; padding: 2px 4px; }
.h2h-pitches .fdr-pill.mini { font-size: 6.5px; padding: 1px 2px; }
.h2h-pitches .player-armband { width: 15px; height: 15px; font-size: 8px; }
.h2h-pitches .player-flag { width: 13px; height: 13px; font-size: 7px; }
.h2h-team-tabs { display: none; }
@media (max-width: 720px) {
  .h2h-team-tabs {
    display: flex; gap: 0; margin-bottom: 14px; border-bottom: 1px solid var(--border);
  }
  .h2h-team-tabs button {
    flex: 1; background: none; border: none; border-bottom: 2px solid transparent;
    padding: 10px 4px; font-size: 14.5px; font-weight: 600; color: var(--ink-soft); cursor: pointer;
  }
  .h2h-team-tabs button.active { color: var(--ink); border-bottom-color: var(--accent); }
  .h2h-pitches { gap: 0; }
  .h2h-pitches > div.h2h-team { display: none; min-width: 0; }
  .h2h-pitches > div.h2h-team.active { display: block; }
  .h2h-pitches > div.h2h-team h3 { display: none; }
}
"""


JS = """
function fmtPct(v) { return v === null || v === undefined ? '—' : v.toFixed(1) + '%'; }
const MANAGER_ID_BY_NAME = {};
DIGEST.managers.forEach(m => { MANAGER_ID_BY_NAME[m.display_name] = m.manager_id; });
function el(tag, cls, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; }
function makeActivatable(elm) {
  elm.tabIndex = 0;
  elm.setAttribute('role', 'button');
  elm.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); elm.click(); }
  });
  return elm;
}

function resultBadge(w, d, l) {
  return `<span class="record-badges"><span class="badge badge-w">${w}W</span> <span class="badge badge-d">${d}D</span> <span class="badge badge-l">${l}L</span></span>`;
}

function matchRow(gw, m, showTeam) {
  const hasScore = m.a.score !== undefined && m.a.score !== null;
  const aWin = m.winner === 'a', bWin = m.winner === 'b';
  const row = el('div', 'match-row clickable', `
    <div class="match-side">${m.a.name}${showTeam ? `<div class="muted">${m.a.team}</div>` : ''}</div>
    <div class="match-score">${hasScore
      ? `<span class="${aWin ? 'win' : ''}">${m.a.score}</span> - <span class="${bWin ? 'win' : ''}">${m.b.score}</span>`
      : 'vs'}</div>
    <div class="match-side right">${m.b.name}${showTeam ? `<div class="muted">${m.b.team}</div>` : ''}</div>
  `);
  row.onclick = () => openMatchupModal(+gw, m.a.name, m.b.name);
  makeActivatable(row);
  return row;
}

function seasonRecordStr(r) { return r ? `${r.w}-${r.d}-${r.l}` : '—'; }

function projectedMatchRow(gw, m) {
  const aLeads = m.a.win_pct >= m.b.win_pct;
  const card = el('div', 'proj-card');
  card.title = `${m.a.name}: played ${m.a.played}, yet to play ${m.a.yet_to_play}\n${m.b.name}: played ${m.b.played}, yet to play ${m.b.yet_to_play}`;
  card.innerHTML = `
    <div class="proj-score-row">
      <div class="proj-score-side">
        <span class="proj-live${m.winner === 'a' ? ' win' : ''}">${m.a.score}</span>
        <span class="proj-total">proj ${m.a.projected_total}</span>
      </div>
      <div class="proj-score-side right">
        <span class="proj-live${m.winner === 'b' ? ' win' : ''}">${m.b.score}</span>
        <span class="proj-total">proj ${m.b.projected_total}</span>
      </div>
    </div>
    <div class="proj-bar-label">Win probability</div>
    <div class="proj-bar-row">
      <span class="proj-pct">${m.a.win_pct}%</span>
      <div class="proj-bar-track">
        <div class="proj-bar-seg ${aLeads ? 'lead' : 'trail'}" style="width:${m.a.win_pct}%"></div>
        <div class="proj-bar-seg ${aLeads ? 'trail' : 'lead'}" style="width:${m.b.win_pct}%"></div>
      </div>
      <span class="proj-pct">${m.b.win_pct}%</span>
    </div>
    <div class="proj-bottom-row">
      <div class="proj-info"><b>${m.a.team}</b> — ${m.a.name} · ${seasonRecordStr(m.a.season_record)}</div>
      <div class="proj-info right"><b>${m.b.team}</b> — ${m.b.name} · ${seasonRecordStr(m.b.season_record)}</div>
    </div>
    ${m.has_unproven_players ? '<div class="proj-caveat">Includes a player with no scoring history yet</div>' : ''}
  `;
  card.onclick = () => openMatchupModal(+gw, m.a.name, m.b.name);
  makeActivatable(card);
  return card;
}

let playerTooltipEl = null;
let playerTooltipPinnedChip = null;

function ensurePlayerTooltip() {
  if (!playerTooltipEl) {
    playerTooltipEl = el('div', 'player-tooltip');
    document.body.appendChild(playerTooltipEl);
  }
  return playerTooltipEl;
}

function leagueOwnersOf(gw, playerId, excludeManagerId) {
  const owners = [];
  Object.values(DIGEST.managers_detail).forEach(m => {
    if (m.manager_id === excludeManagerId) return;
    const roster = m.rosters_by_gw && m.rosters_by_gw[gw];
    if (roster && roster.some(pl => pl.player_id === playerId)) owners.push(m.display_name);
  });
  return owners;
}

function showPlayerTooltip(chip, p) {
  const t = ensurePlayerTooltip();
  const owned = p.owned_pct !== null && p.owned_pct !== undefined ? `${p.owned_pct.toFixed(1)}% owned` : 'ownership unavailable';
  const form = p.form !== null && p.form !== undefined ? `Form ${p.form.toFixed(1)}` : null;
  let leagueLine = '';
  if (p.gw !== undefined && p.player_id !== undefined) {
    const others = leagueOwnersOf(p.gw, p.player_id, p.owner_manager_id);
    leagueLine = others.length === 0
      ? 'Not owned by anyone else in the league'
      : others.length <= 5
        ? `Also owned by: ${others.join(', ')}`
        : `Also owned by ${others.length} others in the league`;
  }
  const formLine = p.recent_form && p.recent_form.length
    ? `Last ${p.recent_form.length} GW${p.recent_form.length > 1 ? 's' : ''} into this one: ${p.recent_form.join(', ')}`
    : (p.gw === 1 ? '' : 'No gameweeks played before this one');
  t.innerHTML = `
    <div class="pt-name">${p.name}</div>
    <div class="pt-meta">${p.position} · ${owned}${form ? ' · ' + form : ''} <span style="opacity:.6">(current)</span></div>
    ${leagueLine ? `<div class="pt-meta">${leagueLine}</div>` : ''}
    ${formLine ? `<div class="pt-meta">${formLine}</div>` : ''}
  `;
  t.classList.add('visible');
  const rect = chip.getBoundingClientRect();
  const tw = t.offsetWidth, th = t.offsetHeight;
  let left = rect.left + rect.width / 2 - tw / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));
  let top = rect.top - th - 8;
  if (top < 8) top = rect.bottom + 8;
  t.style.left = left + 'px';
  t.style.top = top + 'px';
}

function hidePlayerTooltip() {
  if (playerTooltipEl) playerTooltipEl.classList.remove('visible');
  playerTooltipPinnedChip = null;
}

document.addEventListener('click', () => { if (playerTooltipPinnedChip) hidePlayerTooltip(); });
window.addEventListener('scroll', hidePlayerTooltip, true);
window.addEventListener('resize', hidePlayerTooltip);

const FLAG_STATUS_TEXT = { d: 'Doubtful', i: 'Injured', s: 'Suspended', u: 'Unavailable' };

function pointsTierClass(p, hasPlayed) {
  if (!hasPlayed) return 'not-played';
  const total = p.raw_points * (p.multiplier || 1);
  if (total >= 12) return 'tier-elite';
  if (total >= 7) return 'tier-great';
  if (total >= 3) return 'tier-ok';
  return 'tier-low';
}

function nextFixtures(clubId, fromGw, count) {
  const list = DIGEST.club_fixtures[clubId] || [];
  return list.filter(f => f.gw >= fromGw).slice(0, count);
}

function fixturePillMini(f) {
  return `<span class="fdr-pill mini fdr-${f.difficulty || 3}">${f.opponent} (${f.is_home ? 'H' : 'A'})</span>`;
}

function playerChip(p, isBench) {
  const chip = el('div', `player-chip${isBench ? ' bench' : ''}`);
  const photo = DIGEST.player_photos[p.player_id];
  const kit = DIGEST.club_kits[p.club_id];
  const kitSrc = kit ? (p.position === 'GKP' ? kit.gk : kit.out) : null;
  const jerseyContent = photo
    ? `<img src="${photo}" alt="${p.name}" class="player-photo-img">`
    : (kitSrc ? `<img src="${kitSrc}" alt="${p.position}" class="kit-img">` : p.position);
  const hasPlayed = (p.minutes || 0) > 0;
  // A gameweek FPL has already data-checked is settled history — a 0-minute
  // bench player there genuinely didn't feature, full stop, not "hasn't
  // played yet." Fixtures-instead-of-points only makes sense for the
  // current/future gameweek, where hasPlayed is a real "not started" signal.
  const gwIsFinal = DIGEST.gw_status.data_checked_gws.includes(p.gw);
  const armClass = p.armband === 'C' ? 'cap' : p.armband === 'VC' ? 'vice' : null;
  const armHtml = armClass ? `<span class="player-armband ${armClass}">${p.armband === 'C' ? 'C' : 'V'}</span>` : '';
  const flagged = p.status && p.status !== 'a';
  const flagTitle = flagged ? `${FLAG_STATUS_TEXT[p.status] || 'Flagged'}${p.news ? ' — ' + p.news : ''}` : '';
  const flagHtml = flagged ? `<span class="player-flag" title="${flagTitle}">&#9888;</span>` : '';
  const posLabel = isBench ? `<div class="player-pos-label">${p.position}</div>` : '';

  let bottomHtml;
  if (!gwIsFinal && !hasPlayed) {
    const fixtures = nextFixtures(p.club_id, p.gw, 2);
    bottomHtml = fixtures.length
      ? `<div class="player-fixtures" title="Hasn’t played yet — showing next fixture(s) instead of points">${fixtures.map(fixturePillMini).join('')}</div>`
      : `<div class="player-pts not-played" title="Hasn’t played yet">${p.raw_points}${p.multiplier > 1 ? `×${p.multiplier}` : ''}</div>`;
  } else {
    bottomHtml = `<div class="player-pts ${pointsTierClass(p, hasPlayed)}" title="${hasPlayed ? '' : 'Hasn’t played yet'}">${p.raw_points}${p.multiplier > 1 ? `×${p.multiplier}` : ''}</div>`;
  }

  chip.innerHTML = `
    ${posLabel}
    <div class="player-jersey">${jerseyContent}${armHtml}${flagHtml}</div>
    <div class="player-name">${p.name}</div>
    ${bottomHtml}
  `;
  chip.addEventListener('mouseenter', () => { if (!playerTooltipPinnedChip) showPlayerTooltip(chip, p); });
  chip.addEventListener('mouseleave', () => { if (!playerTooltipPinnedChip) hidePlayerTooltip(); });
  chip.addEventListener('click', (e) => {
    e.stopPropagation();
    if (playerTooltipPinnedChip === chip) { hidePlayerTooltip(); }
    else { playerTooltipPinnedChip = chip; showPlayerTooltip(chip, p); }
  });
  return chip;
}

function renderPitch(container, players) {
  const starters = players.filter(p => p.is_starter);
  const bench = players.filter(p => !p.is_starter).sort((a, b) => a.slot - b.slot);
  const rowOrder = ['FWD', 'MID', 'DEF', 'GKP'];

  const pitch = el('div', 'pitch');
  pitch.appendChild(el('div', 'pitch-box-top'));
  pitch.appendChild(el('div', 'pitch-box-top-small'));
  pitch.appendChild(el('div', 'pitch-box-bottom'));
  pitch.appendChild(el('div', 'pitch-box-bottom-small'));
  ['tl', 'tr', 'bl', 'br'].forEach(corner => pitch.appendChild(el('div', `pitch-corner ${corner}`)));
  [['50%', '11%'], ['50%', '89%'], ['50%', '50%']].forEach(([left, top]) => {
    const spot = el('div', 'pitch-spot');
    spot.style.left = left;
    spot.style.top = top;
    pitch.appendChild(spot);
  });
  rowOrder.forEach(pos => {
    const inRow = starters.filter(p => p.position === pos);
    if (!inRow.length) return;
    const row = el('div', 'pitch-row');
    inRow.forEach(p => row.appendChild(playerChip(p)));
    pitch.appendChild(row);
  });
  const frame = el('div', 'pitch-frame');
  frame.appendChild(pitch);
  container.appendChild(frame);

  if (bench.length) {
    const benchWrap = el('div', 'bench-strip');
    benchWrap.appendChild(el('h3', null, 'Bench'));
    const benchRow = el('div', 'pitch-row bench-shelf');
    bench.forEach(p => benchRow.appendChild(playerChip(p, true)));
    benchWrap.appendChild(benchRow);
    container.appendChild(benchWrap);
  }
}

function allTimeRecord(nameA, nameB) {
  let wA = 0, wB = 0, draws = 0, pfA = 0, pfB = 0, played = 0;
  Object.values(DIGEST.all_matchups_by_gw).forEach(matches => {
    matches.forEach(m => {
      const aIsA = m.a.name === nameA && m.b.name === nameB;
      const aIsB = m.a.name === nameB && m.b.name === nameA;
      if (!aIsA && !aIsB) return;
      played++;
      const scoreA = aIsA ? m.a.score : m.b.score;
      const scoreB = aIsA ? m.b.score : m.a.score;
      pfA += scoreA; pfB += scoreB;
      if (m.winner === 'Draw' || m.winner === null) draws++;
      else if ((aIsA && m.winner === 'a') || (aIsB && m.winner === 'b')) wA++;
      else wB++;
    });
  });
  return { played, wA, wB, draws, pfA, pfB };
}

function openMatchupModal(gw, nameA, nameB) {
  const mgrA = MANAGER_ID_BY_NAME[nameA], mgrB = MANAGER_ID_BY_NAME[nameB];
  const detailA = DIGEST.managers_detail[mgrA], detailB = DIGEST.managers_detail[mgrB];
  const body = document.getElementById('modal-body');
  body.innerHTML = '';
  if (!detailA || !detailB) {
    body.innerHTML = '<p class="muted">Manager data not available.</p>';
  } else {
    const gA = detailA.gw_history.find(g => g.gw === gw);
    const gB = detailB.gw_history.find(g => g.gw === gw);
    const rosterA = detailA.rosters_by_gw[gw] || [];
    const rosterB = detailB.rosters_by_gw[gw] || [];
    const hasScore = gA && gB;
    const aWin = hasScore && gA.net_points > gB.net_points;
    const bWin = hasScore && gB.net_points > gA.net_points;
    const isLive = hasScore && (!gA.is_final || !gB.is_final);
    const rec = allTimeRecord(nameA, nameB);
    const capA = rosterA.find(p => p.armband === 'C');
    const capB = rosterB.find(p => p.armband === 'C');
    const playStatus = (roster) => {
      const starters = roster.filter(p => p.is_starter);
      const played = starters.filter(p => p.minutes > 0).length;
      return { played, pending: starters.length - played };
    };
    const psA = playStatus(rosterA), psB = playStatus(rosterB);

    const header = el('div', 'h2h-header');
    header.innerHTML = `<div class="gw-label">Gameweek ${gw}${isLive ? ' <span class="badge badge-l">LIVE</span>' : ''}</div>`;
    body.appendChild(header);

    const sideExtrasA = `
      <div class="side-extra">Captain: ${capA ? `${capA.name} (${capA.raw_points}×${capA.multiplier})` : '—'}</div>
      <div class="side-extra">Bench: ${gA ? gA.bench_points : '—'}</div>
      ${isLive ? `<div class="side-extra">Played ${psA.played} · Yet to play ${psA.pending}</div>` : ''}
    `;
    const sideExtrasB = `
      <div class="side-extra">Captain: ${capB ? `${capB.name} (${capB.raw_points}×${capB.multiplier})` : '—'}</div>
      <div class="side-extra">Bench: ${gB ? gB.bench_points : '—'}</div>
      ${isLive ? `<div class="side-extra">Played ${psB.played} · Yet to play ${psB.pending}</div>` : ''}
    `;
    const scoreRow = el('div', 'h2h-score');
    scoreRow.innerHTML = `
      <div class="side-name">${nameA}<div class="muted">${detailA.team_name}</div>${sideExtrasA}</div>
      <div class="score-box">${hasScore
        ? `<span class="${aWin ? 'win' : ''}">${gA.net_points}</span> - <span class="${bWin ? 'win' : ''}">${gB.net_points}</span>`
        : 'vs'}</div>
      <div class="side-name right">${nameB}<div class="muted">${detailB.team_name}</div>${sideExtrasB}</div>
    `;
    body.appendChild(scoreRow);

    const recordEl = el('div', 'h2h-record');
    recordEl.innerHTML = rec.played
      ? `All-time: <b>${rec.wA}-${rec.draws}-${rec.wB}</b> (${nameA}-Draw-${nameB}) · ${rec.pfA}-${rec.pfB} pts across ${rec.played} meeting${rec.played === 1 ? '' : 's'}`
      : `First time these two have met.`;
    body.appendChild(recordEl);

    const teamTabs = el('div', 'h2h-team-tabs');
    const tabA = el('button', 'active', nameA);
    const tabB = el('button', null, nameB);
    teamTabs.appendChild(tabA);
    teamTabs.appendChild(tabB);
    body.appendChild(teamTabs);

    const pitches = el('div', 'h2h-pitches');
    pitches.style.marginTop = '18px';
    const colA = el('div', 'h2h-team active', `<h3>${nameA}</h3>`);
    const colB = el('div', 'h2h-team', `<h3>${nameB}</h3>`);
    if (rosterA.length) renderPitch(colA, rosterA); else colA.appendChild(el('p', 'muted', 'Roster not available.'));
    if (rosterB.length) renderPitch(colB, rosterB); else colB.appendChild(el('p', 'muted', 'Roster not available.'));
    pitches.appendChild(colA);
    pitches.appendChild(colB);
    body.appendChild(pitches);

    tabA.onclick = () => {
      tabA.classList.add('active'); tabB.classList.remove('active');
      colA.classList.add('active'); colB.classList.remove('active');
    };
    tabB.onclick = () => {
      tabB.classList.add('active'); tabA.classList.remove('active');
      colB.classList.add('active'); colA.classList.remove('active');
    };
  }
  document.getElementById('matchup-modal').style.display = 'flex';
}

function closeMatchupModal() {
  document.getElementById('matchup-modal').style.display = 'none';
}

function renderHome(root) {
  const d = DIGEST;
  root.innerHTML = '';

  const homeGrid = el('div', 'home-top-grid');

  const standingsCard = el('div', 'card gc-standings wide-table');
  standingsCard.appendChild(el('h2', null, `Standings — after GW${d.standings_gw}`));
  let rows = d.standings.map(s => `
    <tr class="${s.is_owner ? 'owner-row' : ''}">
      <td>${s.rank}</td><td>${s.display_name}<div class="muted">${s.team_name}</div></td>
      <td>${resultBadge(s.wins, s.draws, s.losses)}</td><td>${s.league_points}</td><td>${s.streak || '—'}</td>
    </tr>`).join('');
  const standingsScroll = el('div', 'table-scroll', `<table><thead><tr><th>#</th><th>Manager</th><th>Record</th><th>Pts</th><th>Streak</th></tr></thead><tbody>${rows}</tbody></table>`);
  standingsCard.appendChild(standingsScroll);
  homeGrid.appendChild(standingsCard);

  const fixturesCard = el('div', 'card gc-fixtures');
  const uf = d.upcoming_fixtures;
  const fixturesLive = uf.matches.some(m => m.live);
  fixturesCard.appendChild(el('h2', null, uf.gw
    ? `This week's fixtures — GW${uf.gw}${fixturesLive ? ' <span class="badge badge-l">LIVE</span>' : ''}`
    : 'No upcoming fixtures'));
  uf.matches.forEach(m => fixturesCard.appendChild(
    m.a.win_pct !== undefined ? projectedMatchRow(uf.gw, m) : matchRow(uf.gw, m, true)
  ));
  homeGrid.appendChild(fixturesCard);

  const resultsCard = el('div', 'card gc-results');
  const lr = d.last_results;
  resultsCard.appendChild(el('h2', null, lr ? `Last results — GW${lr.gw}` : 'No results yet'));
  if (lr) lr.matches.forEach(m => resultsCard.appendChild(matchRow(lr.gw, m, false)));
  homeGrid.appendChild(resultsCard);

  const nextCard = el('div', 'card gc-next');
  const o = d.owner;
  const sf = d.owner_squad_fixtures || [];
  nextCard.appendChild(el('h2', null, o ? `Your squad's fixtures — GW${o.latest_roster.gw}` : 'Fixtures'));
  if (o && sf.length) {
    nextCard.appendChild(el('p', 'muted',
      'Real Premier League fixtures for each player in your squad this gameweek — not the FPL head-to-head matchup.'));
    sf.forEach(p => nextCard.appendChild(squadFixtureRow(p)));
  } else {
    nextCard.innerHTML += '<p class="muted">No squad fixtures available yet.</p>';
  }
  homeGrid.appendChild(nextCard);
  root.appendChild(homeGrid);

  const VISIBLE_STANDINGS_ROWS = 9;
  const standingsBodyRows = standingsScroll.querySelectorAll('tbody tr');
  if (standingsBodyRows.length > VISIBLE_STANDINGS_ROWS) {
    const thead = standingsScroll.querySelector('thead');
    let fitHeight = thead.offsetHeight;
    for (let i = 0; i < VISIBLE_STANDINGS_ROWS; i++) fitHeight += standingsBodyRows[i].offsetHeight;
    standingsScroll.style.maxHeight = fitHeight + 'px';
  }

  const pm = d.price_movers;
  const priceCard = el('div', 'card');
  priceCard.style.marginTop = '16px';
  priceCard.appendChild(el('h2', null, 'Price movers'));
  if (!pm.available) {
    priceCard.appendChild(el('p', 'muted',
      'Price history needs at least two days of snapshots to show movement — ' +
      `only ${pm.latest_date || 'today'} has been captured so far. Check back after tomorrow's sync.`));
  } else {
    const fmtPrice = t => `£${(Math.abs(t) / 10).toFixed(1)}m`;
    const fmtDelta = t => `${t > 0 ? '+' : t < 0 ? '−' : ''}${fmtPrice(t)}`;
    const moverRow = m => `
      <div class="match-row">
        <div class="match-side">${m.name}<div class="muted">${m.club}</div></div>
        <div class="match-score ${m.delta_tenths > 0 ? 'win' : ''}" style="${m.delta_tenths < 0 ? 'color:var(--loss)' : ''}">
          ${fmtDelta(m.delta_tenths)}
        </div>
        <div class="match-side right muted">${fmtPrice(m.price_tenths)}</div>
      </div>`;
    const grid3 = el('div', 'grid grid-2');
    const risersCol = el('div', null, `<h3>Risers</h3>${pm.risers.length ? pm.risers.map(moverRow).join('') : '<p class="muted">No risers today.</p>'}`);
    const fallersCol = el('div', null, `<h3>Fallers</h3>${pm.fallers.length ? pm.fallers.map(moverRow).join('') : '<p class="muted">No fallers today.</p>'}`);
    grid3.appendChild(risersCol);
    grid3.appendChild(fallersCol);
    priceCard.appendChild(grid3);
  }
  root.appendChild(priceCard);

  if (d.alerts.items.length) {
    const box = el('div', 'card');
    box.style.marginTop = '16px';
    box.appendChild(el('h2', null, 'Alerts'));
    d.alerts.items.forEach(a => box.appendChild(el('div', `alert alert-${a.severity}`, a.description)));
    const hidden = d.alerts.total_unresolved - d.alerts.items.length;
    if (hidden > 0) box.appendChild(el('p', 'muted', `+${hidden} more not shown.`));
    root.appendChild(box);
  }
}

function fdrPill(fx) {
  const side = fx.is_home ? 'H' : 'A';
  const scoreText = fx.finished && fx.score ? ` · ${fx.score}` : '';
  return `<span class="fdr-pill fdr-${fx.difficulty || 3}">${fx.opponent} (${side})${scoreText}</span>`;
}

function squadFixtureRow(p) {
  const row = el('div', `plist-row${p.is_starter ? '' : ' bench-row'}`);
  const fixturesHtml = p.fixtures.length
    ? p.fixtures.map(fdrPill).join('')
    : '<span class="muted">No fixture</span>';
  row.innerHTML = `
    ${plistKitImg(p)}
    <div class="plist-name wide"><span class="pname">${p.name}</span><span class="plist-sub">${p.position}${p.is_starter ? '' : ' · bench'}</span></div>
    <div class="fixture-cell">${fixturesHtml}</div>
  `;
  return row;
}

function statTier(label, value) {
  if (label === 'Captain efficiency' || label === 'XI efficiency') {
    const pct = parseFloat(value);
    if (isNaN(pct)) return null;
    const cuts = label === 'Captain efficiency' ? [80, 60, 40] : [97, 92, 85];
    if (pct >= cuts[0]) return 'stat-tier-elite';
    if (pct >= cuts[1]) return 'stat-tier-great';
    if (pct >= cuts[2]) return 'stat-tier-ok';
    return 'stat-tier-low';
  }
  if (label === 'Bench points (season)') {
    const n = Number(value);
    if (n < 20) return 'stat-tier-elite';
    if (n <= 32) return 'stat-tier-ok';
    return 'stat-tier-low';
  }
  if (label === 'Hit cost (season)') {
    const n = Number(value);
    if (n === 0) return 'stat-tier-elite';
    if (n <= 8) return 'stat-tier-ok';
    return 'stat-tier-low';
  }
  return null;
}

function renderTransferHistory(container, transfers) {
  if (!transfers.length) {
    container.appendChild(el('p', 'muted', 'No transfers made this season.'));
    return;
  }
  const byGw = new Map();
  transfers.forEach(t => {
    if (!byGw.has(t.gw)) byGw.set(t.gw, []);
    byGw.get(t.gw).push(t);
  });
  [...byGw.keys()].sort((a, b) => b - a).forEach(gw => {
    const box = el('div', 'transfer-gw-box');
    box.appendChild(el('h3', null, `GW${gw}`));
    byGw.get(gw).forEach(t => box.appendChild(el('div', 'transfer-row', `
      <span class="transfer-in">${t.player_in} <span class="muted">in</span></span>
      <span class="transfer-out">${t.player_out} <span class="muted">out</span></span>
    `)));
    container.appendChild(box);
  });
}

function renderManagerCards(root, o) {
  const statsGrid = el('div', 'grid grid-4');
  const L = o.ledger;
  const stats = [
    ['Record', `${L.w}-${L.d}-${L.l}`],
    ['League points', L.league_points],
    ['Points for / against', `${L.points_for} / ${L.points_against}`],
    ['Avg PF / PA', `${L.avg_pf} / ${L.avg_pa}`],
    ['Captain efficiency', fmtPct(o.skill.captain_efficiency_pct)],
    ['XI efficiency', fmtPct(o.skill.xi_efficiency_pct)],
    ['Bench points (season)', L.total_bench_points],
    ['Hit cost (season)', L.total_hit_cost],
  ];
  stats.forEach(([label, value]) => {
    const tier = statTier(label, value);
    statsGrid.appendChild(el('div', 'card stat', `<div class="value${tier ? ' ' + tier : ''}">${value}</div><div class="label">${label}</div>`));
  });
  root.appendChild(statsGrid);

  const histCard = el('div', 'card wide-table');
  histCard.style.marginTop = '16px';
  histCard.appendChild(el('h2', null, 'Gameweek history'));
  histCard.appendChild(el('p', 'muted', 'Click a row to see the roster for that gameweek below.'));
  let rows = o.gw_history.map(g => `
    <tr class="clickable-row" data-gw="${g.gw}" tabindex="0" role="button"><td>GW${g.gw}${g.is_final ? '' : ' <span class="badge badge-l">LIVE</span>'}</td><td>${g.net_points}${g.hit_cost ? ` <span class="muted">(-${g.hit_cost})</span>` : ''}</td>
    <td>${g.rank ?? '—'}</td><td>${g.bench_points}</td><td>${g.chip || '—'}</td>
    <td>${fmtPct(g.captain_efficiency_pct)}</td><td>${fmtPct(g.xi_efficiency_pct)}</td></tr>`).join('');
  histCard.innerHTML += `<table><thead><tr><th>GW</th><th>Net</th><th>Rank</th><th>Bench</th><th>Chip</th><th>Cap Eff</th><th>XI Eff</th></tr></thead><tbody>${rows}</tbody></table>`;
  root.appendChild(histCard);

  const rosterCard = el('div', 'card');
  rosterCard.style.marginTop = '16px';

  function showGwDetail(gw) {
    const g = o.gw_history.find(x => x.gw === gw);
    const roster = o.rosters_by_gw[gw] || [];

    rosterCard.innerHTML = '';
    const liveBadge = g && !g.is_final ? ' <span class="badge badge-l">LIVE</span>' : '';
    rosterCard.appendChild(el('h2', null,
      `Roster — GW${gw}${g ? ` (${g.net_points} pts${g.rank ? `, rank ${g.rank}` : ''})` : ''}${liveBadge}`));
    if (g && !g.is_final) {
      rosterCard.appendChild(el('p', 'muted', 'Live score — still changing as matches are played; rank/efficiency unlock once FPL finalizes this gameweek.'));
    }
    if (g) {
      rosterCard.appendChild(el('div', 'stat-chips', `
        <span class="chip">Gross ${g.gross_points}${g.hit_cost ? ` (-${g.hit_cost})` : ''}</span>
        <span class="chip">Bench ${g.bench_points}</span>
        ${g.chip ? `<span class="chip">${g.chip}</span>` : ''}
        <span class="chip">Cap Eff ${fmtPct(g.captain_efficiency_pct)}</span>
        <span class="chip">XI Eff ${fmtPct(g.xi_efficiency_pct)}</span>
      `));
      rosterCard.appendChild(el('div', 'divider'));
    }
    renderPitch(rosterCard, roster);

    histCard.querySelectorAll('tr[data-gw]').forEach(tr => {
      tr.classList.toggle('row-selected', +tr.dataset.gw === gw);
    });
  }

  histCard.querySelector('tbody').addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-gw]');
    if (tr) showGwDetail(+tr.dataset.gw);
  });
  histCard.querySelector('tbody').addEventListener('keydown', (e) => {
    const tr = e.target.closest('tr[data-gw]');
    if (tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); showGwDetail(+tr.dataset.gw); }
  });

  root.appendChild(rosterCard);
  showGwDetail(o.latest_roster.gw);

  const transferHistCard = el('div', 'card');
  transferHistCard.style.marginTop = '16px';
  transferHistCard.appendChild(el('h2', null, 'Transfer history'));
  renderTransferHistory(transferHistCard, o.transfers);
  root.appendChild(transferHistCard);
}

function renderMyTeam(root) {
  const o = DIGEST.owner;
  root.innerHTML = '';
  if (!o) { root.appendChild(el('div', 'card', 'No owner data yet.')); return; }
  root.appendChild(el('div', 'section-title', `${o.display_name} — ${o.team_name}`));
  renderManagerCards(root, o);
}

function renderManagers(root) {
  root.innerHTML = '';
  const all = Object.values(DIGEST.managers_detail).sort((a, b) => a.team_name.localeCompare(b.team_name));
  if (!all.length) { root.appendChild(el('div', 'card', 'No manager data yet.')); return; }

  const selectorCard = el('div', 'card');
  const options = all.map(m => `<option value="${m.manager_id}">${m.team_name} — ${m.display_name}</option>`).join('');
  selectorCard.innerHTML = `
    <h3>Choose a manager</h3>
    <select id="manager-select" aria-label="Choose a manager" style="width:100%; padding:10px 12px; border-radius:10px; background:var(--card-2); color:var(--ink); border:1px solid var(--border); font-size:14px;">
      ${options}
    </select>
  `;
  root.appendChild(selectorCard);

  const titleEl = el('div', 'section-title');
  const detailRoot = el('div');
  root.appendChild(titleEl);
  root.appendChild(detailRoot);

  function show(managerId) {
    const m = DIGEST.managers_detail[managerId];
    if (!m) return;
    titleEl.textContent = `${m.display_name} — ${m.team_name}`;
    detailRoot.innerHTML = '';
    renderManagerCards(detailRoot, m);
  }

  const select = selectorCard.querySelector('#manager-select');
  select.value = DIGEST.owner.manager_id;
  select.addEventListener('change', () => show(select.value));
  show(select.value);
}

function renderLeague(root) {
  const d = DIGEST;
  root.innerHTML = '';
  root.appendChild(el('div', 'section-title', `Standings — after GW${d.standings_gw}`));
  const table = el('div', 'card wide-table');
  let rows = d.standings.map(s => `
    <tr class="${s.is_owner ? 'owner-row' : ''}">
      <td>${s.rank}</td><td>${s.display_name}<div class="muted">${s.team_name}</div></td>
      <td>${resultBadge(s.wins, s.draws, s.losses)}</td><td>${s.league_points}</td>
      <td>${s.points_for}</td><td>${s.points_against}</td><td>${s.streak || '—'}</td>
    </tr>`).join('');
  table.innerHTML = `<table><thead><tr><th>#</th><th>Manager</th><th>Record</th><th>Pts</th><th>PF</th><th>PA</th><th>Streak</th></tr></thead><tbody>${rows}</tbody></table>`;
  root.appendChild(table);

  root.appendChild(el('div', 'section-title', 'All matchups'));
  const gwKeys = Object.keys(d.all_matchups_by_gw).sort((a, b) => a - b);
  const btnGroup = el('div', 'tabbtn-group');
  const matchupsBody = el('div', 'card');
  function showGw(gw) {
    matchupsBody.innerHTML = '';
    (d.all_matchups_by_gw[gw] || []).forEach(m => matchupsBody.appendChild(matchRow(gw, m, false)));
  }
  gwKeys.forEach((gw, i) => {
    const b = el('button', i === gwKeys.length - 1 ? 'active' : '', `GW${gw}`);
    b.onclick = () => { btnGroup.querySelectorAll('button').forEach(x => x.classList.remove('active')); b.classList.add('active'); showGw(gw); };
    btnGroup.appendChild(b);
  });
  root.appendChild(btnGroup);
  root.appendChild(matchupsBody);
  if (gwKeys.length) showGw(gwKeys[gwKeys.length - 1]);

  root.appendChild(el('div', 'section-title', 'Chip tracker'));
  const chipCard = el('div', 'card wide-table');
  chipCard.appendChild(el('p', 'muted',
    'Each chip is available twice this season (once per half, split at GW19) — shows every gameweek it’s been played so far.'));
  const chipRows = d.standings.map(s => {
    const mgr = DIGEST.managers_detail[MANAGER_ID_BY_NAME[s.display_name]];
    return `<tr class="${s.is_owner ? 'owner-row' : ''}">
      <td>${s.display_name}<div class="muted">${s.team_name}</div></td>
      ${CHIP_ORDER.map(code => `<td>${chipTrackerCell(mgr, code)}</td>`).join('')}
    </tr>`;
  }).join('');
  chipCard.innerHTML += `<table><thead><tr><th>Manager</th>${CHIP_ORDER.map(c => `<th>${CHIP_LABELS[c]}</th>`).join('')}</tr></thead><tbody>${chipRows}</tbody></table>`;
  root.appendChild(chipCard);
}

const CHIP_LABELS = { wildcard: 'Wildcard', bboost: 'Bench Boost', '3xc': 'Triple Captain', freehit: 'Free Hit' };
const CHIP_ORDER = ['wildcard', 'bboost', '3xc', 'freehit'];

function chipTrackerCell(mgrDetail, code) {
  if (!mgrDetail) return '<span class="muted">—</span>';
  const gws = mgrDetail.gw_history.filter(g => g.chip === code).map(g => `<span class="chip">GW${g.gw}</span>`);
  return gws.length ? gws.join(' ') : '<span class="muted">—</span>';
}

function sortableTable(container, headers, rows, rowRenderer) {
  let sortCol = null, sortDir = 1;
  function draw() {
    let sorted = rows.slice();
    if (sortCol !== null) sorted.sort((a, b) => (a[sortCol] > b[sortCol] ? 1 : a[sortCol] < b[sortCol] ? -1 : 0) * sortDir);
    const thead = '<tr>' + headers.map((h, i) => `<th data-i="${i}">${h}</th>`).join('') + '</tr>';
    const tbody = sorted.map(rowRenderer).join('');
    container.innerHTML = `<table><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
    container.querySelectorAll('th').forEach(th => {
      th.onclick = () => {
        const i = +th.dataset.i;
        sortDir = (sortCol === i) ? -sortDir : -1;
        sortCol = i;
        draw();
      };
    });
  }
  draw();
}

function plistKitImg(p) {
  const kit = DIGEST.club_kits[p.club_id];
  const kitSrc = kit ? (p.position === 'GKP' ? kit.gk : kit.out) : null;
  return kitSrc ? `<img class="plist-kit" src="${kitSrc}" alt="${p.position}">` : '';
}

function playerListRows(container, list, opts) {
  opts = opts || {};
  if (!list.length) { container.appendChild(el('p', 'muted', opts.emptyText || 'No data yet.')); return; }
  const max = opts.maxScale || Math.max(...list.map(p => p.count));
  const unit = opts.unit ? ` ${opts.unit}` : '';
  list.forEach(p => {
    const row = el('div', 'plist-row');
    row.innerHTML = `
      ${plistKitImg(p)}
      <div class="plist-name"><span class="pname">${p.name}</span>${opts.subtitle ? `<span class="plist-sub">${opts.subtitle(p)}</span>` : ''}</div>
      <div class="plist-bar-track"><div class="plist-bar-fill" style="width:${(p.count / max * 100).toFixed(0)}%"></div></div>
      <div class="plist-count">${p.count}${unit}</div>
    `;
    container.appendChild(row);
  });
}

function moverListRows(container, list, direction) {
  if (!list.length) { container.appendChild(el('p', 'muted', direction === 'up' ? 'No risers this gameweek.' : 'No fallers this gameweek.')); return; }
  const max = Math.max(...list.map(p => Math.abs(p.delta)));
  list.forEach(p => {
    const pct = (Math.abs(p.delta) / max * 100).toFixed(0);
    const deltaStr = (p.delta > 0 ? '+' : '') + p.delta;
    const row = el('div', 'plist-row');
    row.innerHTML = `
      ${plistKitImg(p)}
      <div class="plist-name"><span class="pname">${p.name}</span><span class="plist-sub">now owned by ${p.count}</span></div>
      <div class="plist-bar-track"><div class="plist-bar-fill${direction === 'down' ? ' faller' : ''}" style="width:${pct}%"></div></div>
      <div class="plist-count">${deltaStr}</div>
    `;
    container.appendChild(row);
  });
}

function flaggedListRows(container, list) {
  if (!list.length) { container.appendChild(el('p', 'muted', 'No flagged players currently owned in the league.')); return; }
  list.forEach(p => {
    const label = FLAG_STATUS_TEXT[p.status] || 'Flagged';
    const row = el('div', 'plist-row');
    row.innerHTML = `
      ${plistKitImg(p)}
      <div class="plist-name wide"><span class="pname">${p.name} <span class="muted">(${label})</span></span><span class="plist-sub">${p.news || ''}</span></div>
      <div class="plist-count wide">Owned by ${p.owners}</div>
    `;
    container.appendChild(row);
  });
}

function poolLeaguePlayersForGw(gw) {
  const seen = new Map();
  Object.values(DIGEST.managers_detail).forEach(m => {
    const roster = m.rosters_by_gw[String(gw)];
    if (!roster) return;
    roster.forEach(p => { if (!seen.has(p.player_id)) seen.set(p.player_id, p); });
  });
  return [...seen.values()];
}

function bestXIFromPool(pool) {
  const byPos = { GKP: [], DEF: [], MID: [], FWD: [] };
  pool.forEach(p => byPos[p.position].push(p));
  Object.values(byPos).forEach(arr => arr.sort((a, b) => b.raw_points - a.raw_points));
  if (!byPos.GKP.length) return null;
  const gkp = byPos.GKP[0];
  const sum = arr => arr.reduce((s, p) => s + p.raw_points, 0);
  let best = null, bestTotal = -1;
  for (let d = 3; d <= 5; d++) {
    for (let mi = 2; mi <= 5; mi++) {
      for (let f = 1; f <= 3; f++) {
        if (d + mi + f !== 10) continue;
        if (d > byPos.DEF.length || mi > byPos.MID.length || f > byPos.FWD.length) continue;
        const defSel = byPos.DEF.slice(0, d), midSel = byPos.MID.slice(0, mi), fwdSel = byPos.FWD.slice(0, f);
        const total = gkp.raw_points + sum(defSel) + sum(midSel) + sum(fwdSel);
        if (total > bestTotal) { bestTotal = total; best = [gkp, ...defSel, ...midSel, ...fwdSel]; }
      }
    }
  }
  return best;
}

let playersSelectedGw = null;

function renderPlayers(root) {
  const d = DIGEST.players;
  root.innerHTML = '';
  if (!d || !d.gws || !d.gws.length) { root.appendChild(el('div', 'card', 'No player data yet.')); return; }
  if (playersSelectedGw === null || !d.gws.includes(playersSelectedGw)) playersSelectedGw = d.current_gw;
  const idx = d.gws.indexOf(playersSelectedGw);

  root.appendChild(el('div', 'section-title', 'Most owned & most captained'));
  const nav = el('div', 'gw-nav');
  const prevBtn = el('button', 'gw-nav-arrow', '&larr;');
  prevBtn.setAttribute('aria-label', 'Previous gameweek');
  prevBtn.disabled = idx <= 0;
  prevBtn.onclick = () => { playersSelectedGw = d.gws[idx - 1]; renderPlayers(root); };
  const select = document.createElement('select');
  select.className = 'gw-nav-select';
  select.setAttribute('aria-label', 'Select gameweek');
  d.gws.forEach(gw => {
    const opt = document.createElement('option');
    opt.value = gw;
    opt.textContent = `GW${gw}${gw === d.current_gw ? ' (current)' : ''}`;
    if (gw === playersSelectedGw) opt.selected = true;
    select.appendChild(opt);
  });
  select.onchange = () => { playersSelectedGw = Number(select.value); renderPlayers(root); };
  const nextBtn = el('button', 'gw-nav-arrow', '&rarr;');
  nextBtn.setAttribute('aria-label', 'Next gameweek');
  nextBtn.disabled = idx >= d.gws.length - 1;
  nextBtn.onclick = () => { playersSelectedGw = d.gws[idx + 1]; renderPlayers(root); };
  nav.appendChild(prevBtn);
  nav.appendChild(select);
  nav.appendChild(nextBtn);
  root.appendChild(nav);

  root.appendChild(el('div', 'section-title', 'League Dream Team'));
  const dreamCard = el('div', 'card');
  dreamCard.appendChild(el('p', 'muted',
    'The best valid XI (1 GKP, 3-5 DEF, 2-5 MID, 1-3 FWD) picked from every player owned by anyone in the league this gameweek — by raw points, captaincy not applied.'));
  const dreamXIRaw = bestXIFromPool(poolLeaguePlayersForGw(playersSelectedGw));
  const dreamXI = (dreamXIRaw || []).map(p => ({ ...p, is_starter: true, armband: '', multiplier: 1 }));
  if (dreamXI.length === 11) {
    renderPitch(dreamCard, dreamXI);
  } else {
    dreamCard.appendChild(el('p', 'muted', 'Not enough roster data for this gameweek yet.'));
  }
  root.appendChild(dreamCard);

  const gwData = d.by_gw[String(playersSelectedGw)] || {};

  const grid1 = el('div', 'grid grid-2');
  grid1.style.marginTop = '16px';
  const ownedCard = el('div', 'card plist');
  ownedCard.appendChild(el('h3', null, 'Most owned'));
  ownedCard.appendChild(el('p', 'muted', 'How many of the 18 managers have this player.'));
  playerListRows(ownedCard, gwData.most_owned || [], { maxScale: 18 });
  const capCard = el('div', 'card plist');
  capCard.appendChild(el('h3', null, 'Most captained'));
  playerListRows(capCard, gwData.most_captained || [], { maxScale: 18 });
  grid1.appendChild(ownedCard);
  grid1.appendChild(capCard);
  root.appendChild(grid1);

  const grid2 = el('div', 'grid grid-2');
  grid2.style.marginTop = '16px';
  const scorersCard = el('div', 'card plist');
  scorersCard.appendChild(el('h3', null, 'Top scorers'));
  scorersCard.appendChild(el('p', 'muted', 'Among players owned in this league.'));
  playerListRows(scorersCard, gwData.top_scorers || [], { unit: 'pts' });
  const benchedCard = el('div', 'card plist');
  benchedCard.appendChild(el('h3', null, 'Most benched'));
  benchedCard.appendChild(el('p', 'muted', 'Rostered, but not started.'));
  playerListRows(benchedCard, gwData.most_benched || [], { maxScale: 18 });
  grid2.appendChild(scorersCard);
  grid2.appendChild(benchedCard);
  root.appendChild(grid2);

  root.appendChild(el('div', 'section-title', 'Differential of the week'));
  const diffCard = el('div', 'card plist');
  diffCard.appendChild(el('p', 'muted', `Best-scoring players owned by ${d.differential_max_owners} or fewer of the 18 managers.`));
  playerListRows(diffCard, gwData.differential || [], {
    unit: 'pts',
    subtitle: p => `${p.owners} owner${p.owners === 1 ? '' : 's'}`,
    emptyText: 'No real differentials this gameweek.',
  });
  root.appendChild(diffCard);

  root.appendChild(el('div', 'section-title', 'Biggest ownership movers'));
  const movers = gwData.ownership_movers || { available: false };
  if (!movers.available) {
    root.appendChild(el('div', 'card muted', "Not available for the first gameweek in the data — there's no earlier week to compare against."));
  } else {
    const moversGrid = el('div', 'grid grid-2');
    const risersCard = el('div', 'card plist');
    risersCard.appendChild(el('h3', null, 'Gaining owners'));
    moverListRows(risersCard, movers.risers, 'up');
    const fallersCard = el('div', 'card plist');
    fallersCard.appendChild(el('h3', null, 'Losing owners'));
    moverListRows(fallersCard, movers.fallers, 'down');
    moversGrid.appendChild(risersCard);
    moversGrid.appendChild(fallersCard);
    root.appendChild(moversGrid);
  }

  root.appendChild(el('div', 'section-title', 'Currently flagged'));
  const flagCard = el('div', 'card plist');
  flagCard.appendChild(el('p', 'muted', 'Owned in the league, currently doubtful/injured/unavailable per FPL — not tied to the gameweek selected above.'));
  flaggedListRows(flagCard, d.flagged || []);
  root.appendChild(flagCard);

  root.appendChild(el('div', 'section-title', 'Transfer activity this season'));
  const grid3 = el('div', 'grid grid-2');
  const inCard = el('div', 'card plist');
  inCard.appendChild(el('h3', null, 'Most transferred in'));
  playerListRows(inCard, d.transfers.in);
  const outCard = el('div', 'card plist');
  outCard.appendChild(el('h3', null, 'Most transferred out'));
  playerListRows(outCard, d.transfers.out);
  grid3.appendChild(inCard);
  grid3.appendChild(outCard);
  root.appendChild(grid3);
}

function renderAnalytics(root) {
  const d = DIGEST;
  root.innerHTML = '';
  root.appendChild(el('div', 'section-title', 'Manager skill leaderboard'));
  const card = el('div', 'card wide-table');
  root.appendChild(card);
  const rows = d.leaderboard.map(m => [m.display_name, m.team_name, `${m.w}-${m.d}-${m.l}`, m.league_points,
    m.captain_efficiency_pct, m.xi_efficiency_pct, m.bench_points, m.is_owner]);
  sortableTable(card,
    ['Manager', 'Team', 'Record', 'Pts', 'Cap Eff %', 'XI Eff %', 'Bench'],
    rows,
    r => `<tr class="${r[7] ? 'owner-row' : ''}"><td>${r[0]}</td><td class="muted">${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td><td class="${statTier('Captain efficiency', r[4]) || ''}">${fmtPct(r[4])}</td><td class="${statTier('XI efficiency', r[5]) || ''}">${fmtPct(r[5])}</td><td class="${statTier('Bench points (season)', r[6]) || ''}">${r[6]}</td></tr>`
  );

  root.appendChild(el('div', 'section-title', 'Luck & power rankings'));
  root.appendChild(lockedCard(d.gates.luck_and_power_rankings));

  root.appendChild(el('div', 'section-title', 'Projections'));
  root.appendChild(lockedCard(d.gates.projections));
}

function lockedCard(gate) {
  if (gate.unlocked) return el('div', 'card', 'Unlocked.');
  const pct = Math.round(100 * gate.have / gate.need);
  return el('div', 'locked-card', `
    <div class="lock-icon">🔒</div>
    <p>Insufficient sample — ${gate.have} gameweek${gate.have === 1 ? '' : 's'}, need ${gate.need}</p>
    <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
    <p class="muted">Unlocks in ${gate.need - gate.have} more gameweek${gate.need - gate.have === 1 ? '' : 's'}</p>
  `);
}

function renderHistory(root) {
  const d = DIGEST;
  root.innerHTML = '';
  const gws = d.gw_status.data_checked_gws;
  const btnGroup = el('div', 'tabbtn-group');
  const body = el('div');
  root.appendChild(btnGroup);
  root.appendChild(body);

  function show(gw) {
    body.innerHTML = '';
    const grid = el('div', 'grid grid-2');

    const standingsCard = el('div', 'card');
    standingsCard.appendChild(el('h2', null, `Standings after GW${gw}`));
    const gwStandings = d.all_standings_by_gw[gw] || [];
    const reconstructed = gwStandings.length && gwStandings[0].reconstructed;
    if (reconstructed) {
      standingsCard.appendChild(el('p', 'muted', 'Rank unavailable for this gameweek — reconstructed from raw match data, sorted by league points. See Home → Alerts.'));
    }
    let rows = gwStandings.map(s => `<tr class="${s.is_owner ? 'owner-row' : ''}">
      <td>${s.rank ?? '—'}</td><td>${s.display_name}</td><td>${resultBadge(s.wins, s.draws, s.losses)}</td><td>${s.league_points}</td>
    </tr>`).join('');
    standingsCard.innerHTML += `<table><thead><tr><th>#</th><th>Manager</th><th>Record</th><th>Pts</th></tr></thead><tbody>${rows}</tbody></table>`;
    grid.appendChild(standingsCard);

    const recapCard = el('div', 'card recap-card');
    const recap = d.recaps.find(r => r.gw === gw);
    recapCard.appendChild(el('h2', null, `GW${gw} highlights`));
    if (recap) {
      let html = '';
      if (recap.winner) html += `<p><b>Winner:</b> ${recap.winner.name} ran away with it — ${recap.winner.net_points} points, best in the league this week.</p>`;
      if (recap.blowout) {
        const aWon = recap.blowout.score_a > recap.blowout.score_b;
        const beater = aWon ? recap.blowout.a : recap.blowout.b;
        const beaten = aWon ? recap.blowout.b : recap.blowout.a;
        html += `<p><b>Biggest blowout:</b> ${recap.blowout.a} ${recap.blowout.score_a} - ${recap.blowout.score_b} ${recap.blowout.b} — ${beater} put a ${recap.blowout.margin}-point beating on ${beaten}.</p>`;
      }
      if (recap.upset) html += `<p><b>Biggest upset${recap.upset.thin_sample ? ' <span class="muted">(thin sample)</span>' : ''}:</b> ${recap.upset.winner} played spoiler, beating ${recap.upset.loser} — who carried a ${recap.upset.gap}-point-higher season average into the match.</p>`;
      if (recap.unluckiest) html += `<p><b>Unluckiest:</b> ${recap.unluckiest.name} put up ${recap.unluckiest.net_points} points and still walked away with a loss. Brutal.</p>`;
      if (recap.luckiest) html += `<p><b>Luckiest:</b> ${recap.luckiest.name} escaped with the win on just ${recap.luckiest.net_points} points. Take it and run.</p>`;
      recapCard.innerHTML += html || '<p class="muted">No highlights computed.</p>';
    }
    grid.appendChild(recapCard);
    body.appendChild(grid);

    const matchupsCard = el('div', 'card');
    matchupsCard.style.marginTop = '16px';
    matchupsCard.appendChild(el('h2', null, `Matchups — GW${gw}`));
    (d.all_matchups_by_gw[gw] || []).forEach(m => matchupsCard.appendChild(matchRow(gw, m, false)));
    body.appendChild(matchupsCard);
  }

  gws.forEach((gw, i) => {
    const b = el('button', i === gws.length - 1 ? 'active' : '', `GW${gw}`);
    b.onclick = () => { btnGroup.querySelectorAll('button').forEach(x => x.classList.remove('active')); b.classList.add('active'); show(gw); };
    btnGroup.appendChild(b);
  });
  if (gws.length) show(gws[gws.length - 1]);
}

const RENDERERS = { home: renderHome, myteam: renderMyTeam, league: renderLeague, managers: renderManagers, players: renderPlayers, analytics: renderAnalytics, history: renderHistory };
const rendered = {};

document.getElementById('tabs').addEventListener('click', (e) => {
  const btn = e.target.closest('.tab');
  if (!btn) return;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const name = btn.dataset.tab;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (!rendered[name]) { RENDERERS[name](document.getElementById('page-' + name)); rendered[name] = true; }
});

renderHome(document.getElementById('page-home'));
rendered.home = true;

document.getElementById('modal-close-btn').addEventListener('click', closeMatchupModal);
document.getElementById('matchup-modal').addEventListener('click', (e) => {
  if (e.target.id === 'matchup-modal') closeMatchupModal();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeMatchupModal();
});
"""


def run() -> int:
    print("Phase 7 — building dashboard.html\n")
    digest = build_digest()
    html = render(digest)
    out_path = config.REPO_ROOT / OUT_PATH_NAME
    out_path.write_text(html)
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(run())
