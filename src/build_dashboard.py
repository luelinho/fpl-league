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

import json
import sys

from . import config
from .digest import build_digest

OUT_PATH_NAME = "dashboard.html"


def render(digest: dict) -> str:
    data_json = json.dumps(digest)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{digest['league']['name']} — League Dashboard</title>
<style>
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
  --bg: #0a070f;
  --card: rgba(26,22,34,0.6);
  --card-2: rgba(32,27,42,0.65);
  --ink: #f5f4f8;
  --ink-soft: #9997a8;
  --border: rgba(255,255,255,0.09);
  --accent: #d6fb3d;
  --accent-ink: #0a0a0d;
  --accent-soft: rgba(214,251,61,0.14);
  --purple: #c3b3f7;
  --purple-soft: rgba(195,179,247,0.16);
  --coral: #ff7a70;
  --coral-soft: rgba(255,122,112,0.15);
  --win: var(--accent);
  --win-soft: var(--accent-soft);
  --loss: var(--coral);
  --loss-soft: var(--coral-soft);
  --draw: var(--purple);
  --draw-soft: var(--purple-soft);
  --locked: #726f80;
  --shadow: 0 1px 0 rgba(255,255,255,0.06) inset, 0 20px 50px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.02);
  --blur: blur(24px);
}
* { box-sizing: border-box; }
body {
  margin: 0; color: var(--ink); min-height: 100vh;
  background:
    radial-gradient(ellipse 900px 650px at 6% -8%, rgba(130,70,210,0.38), transparent 55%),
    radial-gradient(ellipse 1000px 750px at 100% 105%, rgba(230,120,40,0.30), transparent 55%),
    radial-gradient(ellipse 700px 600px at 60% 30%, rgba(90,50,150,0.12), transparent 60%),
    var(--bg);
  background-attachment: fixed;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px; line-height: 1.45;
}
.topbar {
  background: rgba(10,7,15,0.55); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
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
.grid.align-top { align-items: start; }
.grid-2 { grid-template-columns: 1fr 1fr; }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }
@media (max-width: 720px) { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }
.card {
  background: var(--card); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
  border: 1px solid var(--border); border-radius: 20px; overflow-x: auto;
  padding: 20px 22px; box-shadow: var(--shadow);
}
.card h2 { margin: 0 0 12px; font-size: 15px; color: var(--ink); font-weight: 700; }
.card h3 { margin: 0 0 8px; font-size: 13px; color: var(--ink-soft); text-transform: uppercase; letter-spacing: 0.03em; }
.card.hero { background: var(--accent); color: var(--accent-ink); border-color: transparent; }
.card.hero h2 { color: var(--accent-ink); }
.card.hero b { color: var(--accent-ink); }
.card.hero p { color: rgba(10,10,13,0.75); }
.card.hero .muted { color: rgba(10,10,13,0.55); }
.stat { display: flex; flex-direction: column; gap: 3px; }
.stat .value { font-size: 27px; font-weight: 700; color: var(--ink); }
.stat .label { color: var(--ink-soft); font-size: 12.5px; }
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
.badge-w { background: var(--win-soft); color: var(--win); }
.badge-l { background: var(--loss-soft); color: var(--loss); }
.badge-d { background: var(--draw-soft); color: var(--draw); }
.pill { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; background: var(--purple-soft); color: var(--purple); }
.section-title { font-size: 19px; font-weight: 700; margin: 30px 0 14px; color: var(--ink); }
.section-title:first-child { margin-top: 0; }
.match-row {
  display: flex; align-items: center; justify-content: space-between; padding: 11px 0;
  border-bottom: 1px solid var(--border);
}
.match-row:last-child { border-bottom: none; }
.match-side { flex: 1; font-weight: 600; color: var(--ink); }
.match-side.right { text-align: right; }
.match-score { padding: 0 16px; font-weight: 700; color: var(--ink-soft); white-space: nowrap; }
.match-score .win { color: var(--win); }
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
.pitch {
  position: relative; display: flex; flex-direction: column; justify-content: space-around;
  gap: 14px; min-height: 380px; padding: 22px 8px; border-radius: 16px; overflow: hidden;
  border: 1px solid rgba(255,255,255,0.14);
  background:
    radial-gradient(ellipse 100% 70% at 50% 50%, transparent 45%, rgba(0,0,0,0.32) 100%),
    repeating-linear-gradient(180deg, rgba(255,255,255,0.055) 0 34px, rgba(0,0,0,0.05) 34px 68px),
    linear-gradient(180deg, #1f5c39 0%, #1a4f30 50%, #1f5c39 100%);
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
  width: 46px; height: 46px; position: relative;
  display: flex; align-items: center; justify-content: center;
}
.kit-img { width: 46px; height: 46px; object-fit: contain; filter: drop-shadow(0 3px 6px rgba(0,0,0,0.5)); }
.player-chip.bench .kit-img { filter: grayscale(0.6) opacity(0.85) drop-shadow(0 2px 4px rgba(0,0,0,0.4)); }
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
  margin-top: 6px; background: #f4f2ef; color: #171321; font-weight: 800; font-size: 10.5px;
  padding: 2px 7px; border-radius: 6px 6px 0 0; width: 100%;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.player-chip.bench .player-name { background: #dedad3; }
.player-pts {
  font-size: 10.5px; font-weight: 800; padding: 2px 7px; border-radius: 0 0 6px 6px; width: 100%; color: #fff;
}
.player-pts.tier-elite { background: var(--accent); color: var(--accent-ink); }
.player-pts.tier-great { background: #8fd645; color: #0a0a0d; }
.player-pts.tier-ok { background: #ffb04a; color: #2c1c00; }
.player-pts.tier-low { background: rgba(255,255,255,0.18); color: #fff; }
.player-pts.not-played { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.65); font-weight: 600; }
.bench-shelf {
  margin-top: 8px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
  border-radius: 14px; padding: 16px 12px;
}
.player-tooltip {
  position: fixed; z-index: 300; pointer-events: none; max-width: 240px;
  background: #16121e; border: 1px solid var(--border); border-radius: 10px;
  padding: 8px 12px; box-shadow: var(--shadow); opacity: 0; transform: translateY(4px);
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.player-tooltip.visible { opacity: 1; transform: translateY(0); }
.player-tooltip .pt-name { font-size: 12.5px; font-weight: 700; color: var(--ink); white-space: nowrap; }
.player-tooltip .pt-meta { font-size: 11.5px; color: var(--ink-soft); margin-top: 2px; line-height: 1.4; }
.bench-strip { margin-top: 14px; }
.bench-strip h3 { margin-bottom: 10px; }
.tabbtn-group { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.tabbtn-group button {
  border: 1px solid var(--border); background: var(--card); padding: 7px 15px; border-radius: 999px;
  font-size: 13px; font-weight: 600; cursor: pointer; color: var(--ink-soft);
}
.tabbtn-group button.active { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
.muted { color: var(--ink-soft); font-size: 12.5px; }
.countdown { font-size: 30px; font-weight: 800; color: var(--accent); letter-spacing: -0.01em; margin: 4px 0 8px; font-variant-numeric: tabular-nums; }
.stat-chips { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 4px; }
.chip { display: inline-block; padding: 5px 12px; border-radius: 999px; font-size: 12.5px; font-weight: 600; background: var(--card-2); border: 1px solid var(--border); color: var(--ink); }
.divider { height: 1px; background: var(--border); margin: 18px 0 14px; }
.footer { text-align: center; color: var(--ink-soft); font-size: 12px; padding: 20px; }
.match-row.clickable { cursor: pointer; border-radius: 10px; transition: background 0.1s; }
.match-row.clickable:hover { background: rgba(255,255,255,0.04); }
.modal-overlay {
  position: fixed; inset: 0; background: rgba(5,3,8,0.72); backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px); z-index: 100; display: flex; align-items: flex-start;
  justify-content: center; padding: 40px 16px; overflow-y: auto;
}
.modal-card {
  position: relative; background: #16121e; border: 1px solid var(--border); border-radius: 20px;
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
.h2h-pitches .player-jersey, .h2h-pitches .kit-img { width: 34px; height: 34px; }
.h2h-pitches .player-name, .h2h-pitches .player-pts { font-size: 9px; padding: 2px 4px; }
.h2h-pitches .player-armband { width: 15px; height: 15px; font-size: 8px; }
.h2h-pitches .player-flag { width: 13px; height: 13px; font-size: 7px; }
"""


JS = """
function fmtPct(v) { return v === null || v === undefined ? '—' : v.toFixed(1) + '%'; }
const MANAGER_ID_BY_NAME = {};
DIGEST.managers.forEach(m => { MANAGER_ID_BY_NAME[m.display_name] = m.manager_id; });
function el(tag, cls, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; }

function resultBadge(w, d, l) {
  return `<span class="badge badge-w">${w}W</span> <span class="badge badge-d">${d}D</span> <span class="badge badge-l">${l}L</span>`;
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

function playerChip(p, isBench) {
  const chip = el('div', `player-chip${isBench ? ' bench' : ''}`);
  const kit = DIGEST.club_kits[p.club_id];
  const kitSrc = kit ? (p.position === 'GKP' ? kit.gk : kit.out) : null;
  const jerseyContent = kitSrc ? `<img src="${kitSrc}" alt="${p.position}" class="kit-img">` : p.position;
  const hasPlayed = (p.minutes || 0) > 0;
  const armClass = p.armband === 'C' ? 'cap' : p.armband === 'VC' ? 'vice' : null;
  const armHtml = armClass ? `<span class="player-armband ${armClass}">${p.armband === 'C' ? 'C' : 'V'}</span>` : '';
  const flagged = p.status && p.status !== 'a';
  const flagTitle = flagged ? `${FLAG_STATUS_TEXT[p.status] || 'Flagged'}${p.news ? ' — ' + p.news : ''}` : '';
  const flagHtml = flagged ? `<span class="player-flag" title="${flagTitle}">&#9888;</span>` : '';
  const posLabel = isBench ? `<div class="player-pos-label">${p.position}</div>` : '';
  chip.innerHTML = `
    ${posLabel}
    <div class="player-jersey">${jerseyContent}${armHtml}${flagHtml}</div>
    <div class="player-name">${p.name}</div>
    <div class="player-pts ${pointsTierClass(p, hasPlayed)}" title="${hasPlayed ? '' : 'Hasn’t played yet'}">${p.raw_points}${p.multiplier > 1 ? `×${p.multiplier}` : ''}</div>
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
  container.appendChild(pitch);

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

    const header = el('div', 'h2h-header');
    header.innerHTML = `<div class="gw-label">Gameweek ${gw}${isLive ? ' <span class="badge badge-l">LIVE</span>' : ''}</div>`;
    body.appendChild(header);

    const sideExtrasA = `
      <div class="side-extra">Captain: ${capA ? `${capA.name} (${capA.raw_points}×${capA.multiplier})` : '—'}</div>
      <div class="side-extra">Bench: ${gA ? gA.bench_points : '—'}</div>
    `;
    const sideExtrasB = `
      <div class="side-extra">Captain: ${capB ? `${capB.name} (${capB.raw_points}×${capB.multiplier})` : '—'}</div>
      <div class="side-extra">Bench: ${gB ? gB.bench_points : '—'}</div>
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

    const pitches = el('div', 'h2h-pitches');
    pitches.style.marginTop = '18px';
    const colA = el('div', null, `<h3>${nameA}</h3>`);
    const colB = el('div', null, `<h3>${nameB}</h3>`);
    if (rosterA.length) renderPitch(colA, rosterA); else colA.appendChild(el('p', 'muted', 'Roster not available.'));
    if (rosterB.length) renderPitch(colB, rosterB); else colB.appendChild(el('p', 'muted', 'Roster not available.'));
    pitches.appendChild(colA);
    pitches.appendChild(colB);
    body.appendChild(pitches);
  }
  document.getElementById('matchup-modal').style.display = 'flex';
}

function closeMatchupModal() {
  document.getElementById('matchup-modal').style.display = 'none';
}

function renderHome(root) {
  const d = DIGEST;
  root.innerHTML = '';

  const grid = el('div', 'grid grid-2 align-top');

  const standingsCard = el('div', 'card');
  standingsCard.appendChild(el('h2', null, `Standings — after GW${d.standings_gw}`));
  let rows = d.standings.map(s => `
    <tr class="${s.is_owner ? 'owner-row' : ''}">
      <td>${s.rank}</td><td>${s.display_name}<div class="muted">${s.team_name}</div></td>
      <td>${resultBadge(s.wins, s.draws, s.losses)}</td><td>${s.league_points}</td><td>${s.streak || '—'}</td>
    </tr>`).join('');
  const standingsScroll = el('div', 'table-scroll', `<table><thead><tr><th>#</th><th>Manager</th><th>Record</th><th>Pts</th><th>Streak</th></tr></thead><tbody>${rows}</tbody></table>`);
  standingsCard.appendChild(standingsScroll);
  grid.appendChild(standingsCard);

  const fixturesCard = el('div', 'card');
  const uf = d.upcoming_fixtures;
  const fixturesLive = uf.matches.some(m => m.live);
  fixturesCard.appendChild(el('h2', null, uf.gw
    ? `This week's fixtures — GW${uf.gw}${fixturesLive ? ' <span class="badge badge-l">LIVE</span>' : ''}`
    : 'No upcoming fixtures'));
  uf.matches.forEach(m => fixturesCard.appendChild(
    m.a.win_pct !== undefined ? projectedMatchRow(uf.gw, m) : matchRow(uf.gw, m, true)
  ));
  grid.appendChild(fixturesCard);
  root.appendChild(grid);

  const VISIBLE_STANDINGS_ROWS = 9;
  const standingsBodyRows = standingsScroll.querySelectorAll('tbody tr');
  if (standingsBodyRows.length > VISIBLE_STANDINGS_ROWS) {
    const thead = standingsScroll.querySelector('thead');
    let fitHeight = thead.offsetHeight;
    for (let i = 0; i < VISIBLE_STANDINGS_ROWS; i++) fitHeight += standingsBodyRows[i].offsetHeight;
    standingsScroll.style.maxHeight = fitHeight + 'px';
  }

  const grid2 = el('div', 'grid grid-2');
  const resultsCard = el('div', 'card');
  const lr = d.last_results;
  resultsCard.appendChild(el('h2', null, lr ? `Last results — GW${lr.gw}` : 'No results yet'));
  if (lr) lr.matches.forEach(m => resultsCard.appendChild(matchRow(lr.gw, m, false)));
  grid2.appendChild(resultsCard);

  const nextCard = el('div', 'card');
  const o = d.owner;
  const nextGw = d.gw_status.next_gw;
  nextCard.appendChild(el('h2', null, nextGw ? `Next up — GW${nextGw}` : 'Season complete'));
  if (nextGw && o) {
    const opp = d.owner_next_opponent;
    const lastFinalGw = [...o.gw_history].reverse().find(g => g.is_final);
    const squadIsForNextGw = o.latest_roster.gw === nextGw;
    let html = `<div class="countdown" data-deadline="${d.gw_status.next_gw_deadline}">—</div>
      <p class="muted" style="margin:0 0 10px">Deadline: ${formatDeadline(d.gw_status.next_gw_deadline)}</p>`;
    if (opp) html += `<p class="muted"><b style="color:var(--ink)">${o.team_name}</b> vs <b style="color:var(--ink)">${opp.name}</b> (${opp.team})</p>`;
    html += `<div class="stat-chips">
      <span class="chip">Rank #${o.rank ?? '—'}</span>
      <span class="chip">${o.ledger.w}-${o.ledger.d}-${o.ledger.l}</span>
      <span class="chip">${o.ledger.league_points} league pts</span>
      ${lastFinalGw ? `<span class="chip">Last week: ${lastFinalGw.net_points} pts (rank ${lastFinalGw.rank})</span>` : ''}
    </div>
    <div class="divider"></div>
    <h3>Your squad — GW${o.latest_roster.gw}${squadIsForNextGw ? ' <span class="badge badge-l">LIVE</span>' : ''}</h3>
    <p class="muted" style="margin:0 0 10px">${squadIsForNextGw
      ? 'Locked in — live. Points update as matches are played, and are final once FPL data-checks this gameweek.'
      : `Transfers made before the GW${nextGw} deadline won't show here yet.`}</p>`;
    nextCard.innerHTML += html;
    renderPitch(nextCard, o.latest_roster.players);
  } else {
    nextCard.innerHTML += '<p class="muted">No upcoming gameweek.</p>';
  }
  grid2.appendChild(nextCard);
  root.appendChild(grid2);

  const pm = d.price_movers;
  const priceCard = el('div', 'card');
  priceCard.style.marginTop = '16px';
  priceCard.appendChild(el('h2', null, 'Price movers'));
  if (!pm.available) {
    priceCard.appendChild(el('p', 'muted',
      'Price history needs at least two days of snapshots to show movement — ' +
      `only ${pm.latest_date || 'today'} has been captured so far. Check back after tomorrow's sync.`));
  } else {
    const fmtPrice = t => `£${(t / 10).toFixed(1)}m`;
    const moverRow = m => `
      <div class="match-row">
        <div class="match-side">${m.name}<div class="muted">${m.club}</div></div>
        <div class="match-score ${m.delta_tenths > 0 ? 'win' : ''}" style="${m.delta_tenths < 0 ? 'color:var(--loss)' : ''}">
          ${m.delta_tenths > 0 ? '+' : ''}${fmtPrice(m.delta_tenths)}
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

function formatDeadline(iso) {
  if (!iso) return '—';
  const dt = new Date(iso);
  if (isNaN(dt.getTime())) return '—';
  return dt.toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    timeZone: 'UTC', timeZoneName: 'short',
  });
}

function updateCountdowns() {
  document.querySelectorAll('[data-deadline]').forEach(node => {
    const deadline = new Date(node.dataset.deadline).getTime();
    const diff = deadline - Date.now();
    if (!node.dataset.deadline || isNaN(deadline)) { node.textContent = '—'; return; }
    if (diff <= 0) { node.textContent = 'Deadline passed — squad locked in'; return; }
    const s = Math.floor(diff / 1000);
    const days = Math.floor(s / 86400), hrs = Math.floor((s % 86400) / 3600),
          mins = Math.floor((s % 3600) / 60), secs = s % 60;
    node.textContent = `${days}d ${hrs}h ${mins}m ${secs}s`;
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
    statsGrid.appendChild(el('div', 'card stat', `<div class="value">${value}</div><div class="label">${label}</div>`));
  });
  root.appendChild(statsGrid);

  const histCard = el('div', 'card');
  histCard.style.marginTop = '16px';
  histCard.appendChild(el('h2', null, 'Gameweek history'));
  histCard.appendChild(el('p', 'muted', 'Click a row to see the roster and transfers for that gameweek below.'));
  let rows = o.gw_history.map(g => `
    <tr class="clickable-row" data-gw="${g.gw}"><td>GW${g.gw}${g.is_final ? '' : ' <span class="badge badge-l">LIVE</span>'}</td><td>${g.net_points}${g.hit_cost ? ` <span class="muted">(-${g.hit_cost})</span>` : ''}</td>
    <td>${g.rank ?? '—'}</td><td>${g.bench_points}</td><td>${g.chip || '—'}</td>
    <td>${fmtPct(g.captain_efficiency_pct)}</td><td>${fmtPct(g.xi_efficiency_pct)}</td></tr>`).join('');
  histCard.innerHTML += `<table><thead><tr><th>GW</th><th>Net</th><th>Rank</th><th>Bench</th><th>Chip</th><th>Cap Eff</th><th>XI Eff</th></tr></thead><tbody>${rows}</tbody></table>`;
  root.appendChild(histCard);

  const rosterCard = el('div', 'card');
  rosterCard.style.marginTop = '16px';
  const transfersCard = el('div', 'card');
  transfersCard.style.marginTop = '16px';

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

    transfersCard.innerHTML = '';
    transfersCard.appendChild(el('h2', null, `Transfers — GW${gw}`));
    const gwTransfers = o.transfers.filter(t => t.gw === gw);
    if (gwTransfers.length) {
      let trows = gwTransfers.map(t => `<tr><td>${t.player_in} in</td><td>${t.player_out} out</td></tr>`).join('');
      transfersCard.innerHTML += `<table><tbody>${trows}</tbody></table>`;
    } else {
      transfersCard.appendChild(el('p', 'muted', 'No transfers made this gameweek.'));
    }

    histCard.querySelectorAll('tr[data-gw]').forEach(tr => {
      tr.classList.toggle('row-selected', +tr.dataset.gw === gw);
    });
  }

  histCard.querySelector('tbody').addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-gw]');
    if (tr) showGwDetail(+tr.dataset.gw);
  });

  root.appendChild(rosterCard);
  root.appendChild(transfersCard);
  showGwDetail(o.latest_roster.gw);
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
    <select id="manager-select" style="width:100%; padding:10px 12px; border-radius:10px; background:var(--card-2); color:var(--ink); border:1px solid var(--border); font-size:14px;">
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
  const table = el('div', 'card');
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

function renderAnalytics(root) {
  const d = DIGEST;
  root.innerHTML = '';
  root.appendChild(el('div', 'section-title', 'Manager skill leaderboard'));
  const card = el('div', 'card');
  root.appendChild(card);
  const rows = d.leaderboard.map(m => [m.display_name, m.team_name, `${m.w}-${m.d}-${m.l}`, m.league_points,
    m.captain_efficiency_pct, m.xi_efficiency_pct, m.bench_points, m.is_owner]);
  sortableTable(card,
    ['Manager', 'Team', 'Record', 'Pts', 'Cap Eff %', 'XI Eff %', 'Bench'],
    rows,
    r => `<tr class="${r[7] ? 'owner-row' : ''}"><td>${r[0]}</td><td class="muted">${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td><td>${fmtPct(r[4])}</td><td>${fmtPct(r[5])}</td><td>${r[6]}</td></tr>`
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

    const recapCard = el('div', 'card hero');
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

const RENDERERS = { home: renderHome, myteam: renderMyTeam, league: renderLeague, managers: renderManagers, analytics: renderAnalytics, history: renderHistory };
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
updateCountdowns();
setInterval(updateCountdowns, 1000);

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
