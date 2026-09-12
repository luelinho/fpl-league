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
      <button class="tab" data-tab="analytics">Analytics</button>
      <button class="tab" data-tab="history">History</button>
    </nav>
  </div>
</header>

<main class="container">
  <section id="page-home" class="page active"></section>
  <section id="page-myteam" class="page"></section>
  <section id="page-league" class="page"></section>
  <section id="page-analytics" class="page"></section>
  <section id="page-history" class="page"></section>
</main>

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
  --bg: #0a0a0d;
  --card: #17181d;
  --card-2: #1d1f26;
  --ink: #f2f3f6;
  --ink-soft: #91929e;
  --border: rgba(255,255,255,0.08);
  --accent: #d6fb3d;
  --accent-ink: #0a0a0d;
  --accent-soft: rgba(214,251,61,0.13);
  --purple: #9b7bff;
  --purple-soft: rgba(155,123,255,0.15);
  --coral: #ff6b6b;
  --coral-soft: rgba(255,107,107,0.15);
  --win: var(--accent);
  --win-soft: var(--accent-soft);
  --loss: var(--coral);
  --loss-soft: var(--coral-soft);
  --draw: var(--purple);
  --draw-soft: var(--purple-soft);
  --locked: #6c6e7a;
  --shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 12px 28px rgba(0,0,0,0.35);
}
* { box-sizing: border-box; }
body {
  margin: 0; color: var(--ink);
  background:
    radial-gradient(circle at 12% -10%, rgba(155,123,255,0.10), transparent 38%),
    radial-gradient(circle at 90% 10%, rgba(214,251,61,0.06), transparent 32%),
    var(--bg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px; line-height: 1.45;
}
.topbar {
  background: rgba(10,10,13,0.85); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10;
}
.topbar-inner {
  max-width: 1080px; margin: 0 auto; padding: 16px 20px;
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
}
.brand-name { font-weight: 700; font-size: 17px; display: block; color: var(--ink); letter-spacing: -0.01em; }
.brand-sub { color: var(--ink-soft); font-size: 12.5px; }
.tabs { display: flex; gap: 4px; background: var(--card); padding: 5px; border-radius: 999px; border: 1px solid var(--border); }
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
@media (max-width: 720px) { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 20px;
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
tbody tr:hover td { background: rgba(255,255,255,0.02); }
tr.owner-row td { background: var(--accent-soft); }
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
  border: 1px dashed var(--border); border-radius: 20px; padding: 26px; text-align: center; color: var(--ink-soft);
}
.locked-card .lock-icon { font-size: 22px; filter: grayscale(1) brightness(1.6); }
.progress-bar { height: 6px; background: rgba(255,255,255,0.08); border-radius: 999px; margin: 12px auto; max-width: 240px; overflow: hidden; }
.progress-fill { height: 100%; background: var(--accent); }
.roster-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px solid var(--border); color: var(--ink); }
.roster-row:last-child { border-bottom: none; }
.roster-row.bench { opacity: 0.5; }
.armband { font-weight: 800; font-size: 11px; background: var(--accent); color: var(--accent-ink); border-radius: 5px; padding: 1px 5px; }
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
"""


JS = """
function fmtPct(v) { return v === null || v === undefined ? '—' : v.toFixed(1) + '%'; }
function el(tag, cls, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; }

function resultBadge(w, d, l) {
  return `<span class="badge badge-w">${w}W</span> <span class="badge badge-d">${d}D</span> <span class="badge badge-l">${l}L</span>`;
}

function renderHome(root) {
  const d = DIGEST;
  root.innerHTML = '';

  if (d.alerts.length) {
    const box = el('div', 'card');
    box.appendChild(el('h2', null, 'Alerts'));
    d.alerts.forEach(a => box.appendChild(el('div', `alert alert-${a.severity}`, a.description)));
    root.appendChild(box);
  }

  const grid = el('div', 'grid grid-2');

  const standingsCard = el('div', 'card');
  standingsCard.appendChild(el('h2', null, `Standings — after GW${d.standings_gw}`));
  let rows = d.standings.slice(0, 6).map(s => `
    <tr class="${s.is_owner ? 'owner-row' : ''}">
      <td>${s.rank}</td><td>${s.display_name}<div class="muted">${s.team_name}</div></td>
      <td>${resultBadge(s.wins, s.draws, s.losses)}</td><td>${s.league_points}</td><td>${s.streak || '—'}</td>
    </tr>`).join('');
  standingsCard.appendChild(el('div', null, `<table><thead><tr><th>#</th><th>Manager</th><th>Record</th><th>Pts</th><th>Streak</th></tr></thead><tbody>${rows}</tbody></table>`));
  grid.appendChild(standingsCard);

  const fixturesCard = el('div', 'card');
  const uf = d.upcoming_fixtures;
  fixturesCard.appendChild(el('h2', null, uf.gw ? `This week's fixtures — GW${uf.gw}` : 'No upcoming fixtures'));
  uf.matches.forEach(m => {
    fixturesCard.appendChild(el('div', 'match-row', `
      <div class="match-side">${m.a.name}<div class="muted">${m.a.team}</div></div>
      <div class="match-score">vs</div>
      <div class="match-side right">${m.b.name}<div class="muted">${m.b.team}</div></div>
    `));
  });
  grid.appendChild(fixturesCard);
  root.appendChild(grid);

  const grid2 = el('div', 'grid grid-2');
  const resultsCard = el('div', 'card');
  const lr = d.last_results;
  resultsCard.appendChild(el('h2', null, lr ? `Last results — GW${lr.gw}` : 'No results yet'));
  if (lr) lr.matches.forEach(m => {
    const aWin = m.winner === 'a', bWin = m.winner === 'b';
    resultsCard.appendChild(el('div', 'match-row', `
      <div class="match-side">${m.a.name}</div>
      <div class="match-score"><span class="${aWin ? 'win' : ''}">${m.a.score}</span> - <span class="${bWin ? 'win' : ''}">${m.b.score}</span></div>
      <div class="match-side right">${m.b.name}</div>
    `));
  });
  grid2.appendChild(resultsCard);

  const nextCard = el('div', 'card');
  const o = d.owner;
  const nextGw = d.gw_status.next_gw;
  nextCard.appendChild(el('h2', null, nextGw ? `Next up — GW${nextGw}` : 'Season complete'));
  if (nextGw && o) {
    const opp = d.owner_next_opponent;
    const lastGw = o.gw_history[o.gw_history.length - 1];
    let html = `<div class="countdown" data-deadline="${d.gw_status.next_gw_deadline}">—</div>
      <p class="muted" style="margin:0 0 10px">Deadline: ${formatDeadline(d.gw_status.next_gw_deadline)}</p>`;
    if (opp) html += `<p class="muted"><b style="color:var(--ink)">${o.team_name}</b> vs <b style="color:var(--ink)">${opp.name}</b> (${opp.team})</p>`;
    html += `<div class="stat-chips">
      <span class="chip">Rank #${o.rank ?? '—'}</span>
      <span class="chip">${o.ledger.w}-${o.ledger.d}-${o.ledger.l}</span>
      <span class="chip">${o.ledger.league_points} league pts</span>
      ${lastGw ? `<span class="chip">Last week: ${lastGw.net_points} pts (rank ${lastGw.rank})</span>` : ''}
    </div>
    <div class="divider"></div>
    <h3>Your squad — as of GW${o.latest_roster.gw}</h3>
    <p class="muted" style="margin:0 0 10px">Transfers made before the GW${nextGw} deadline won't show here yet.</p>`;
    nextCard.innerHTML += html;
    o.latest_roster.players.forEach(p => {
      nextCard.appendChild(el('div', `roster-row ${p.is_starter ? '' : 'bench'}`, `
        <span class="pill">${p.position}</span>
        ${p.armband ? `<span class="armband">${p.armband}</span>` : ''}
        <span style="flex:1">${p.name}</span>
      `));
    });
  } else {
    nextCard.innerHTML += '<p class="muted">No upcoming gameweek.</p>';
  }
  grid2.appendChild(nextCard);
  root.appendChild(grid2);
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

function renderMyTeam(root) {
  const o = DIGEST.owner;
  root.innerHTML = '';
  if (!o) { root.appendChild(el('div', 'card', 'No owner data yet.')); return; }

  root.appendChild(el('div', 'section-title', `${o.display_name} — ${o.team_name}`));

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
  let rows = o.gw_history.map(g => `
    <tr><td>GW${g.gw}</td><td>${g.net_points}${g.hit_cost ? ` <span class="muted">(-${g.hit_cost})</span>` : ''}</td>
    <td>${g.rank}</td><td>${g.bench_points}</td><td>${g.chip || '—'}</td>
    <td>${fmtPct(g.captain_efficiency_pct)}</td><td>${fmtPct(g.xi_efficiency_pct)}</td></tr>`).join('');
  histCard.innerHTML += `<table><thead><tr><th>GW</th><th>Net</th><th>Rank</th><th>Bench</th><th>Chip</th><th>Cap Eff</th><th>XI Eff</th></tr></thead><tbody>${rows}</tbody></table>`;
  root.appendChild(histCard);

  const rosterCard = el('div', 'card');
  rosterCard.style.marginTop = '16px';
  rosterCard.appendChild(el('h2', null, `Latest roster — GW${o.latest_roster.gw}`));
  o.latest_roster.players.forEach(p => {
    rosterCard.appendChild(el('div', `roster-row ${p.is_starter ? '' : 'bench'}`, `
      <span class="pill">${p.position}</span>
      ${p.armband ? `<span class="armband">${p.armband}</span>` : ''}
      <span style="flex:1">${p.name}</span>
      <span class="muted">${p.raw_points} pts × ${p.multiplier}</span>
    `));
  });
  root.appendChild(rosterCard);

  if (o.transfers.length) {
    const tCard = el('div', 'card');
    tCard.style.marginTop = '16px';
    tCard.appendChild(el('h2', null, 'Transfers'));
    let trows = o.transfers.map(t => `<tr><td>GW${t.gw}</td><td>${t.player_in} in</td><td>${t.player_out} out</td></tr>`).join('');
    tCard.innerHTML += `<table><tbody>${trows}</tbody></table>`;
    root.appendChild(tCard);
  }
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
    (d.all_matchups_by_gw[gw] || []).forEach(m => {
      const aWin = m.winner === 'a', bWin = m.winner === 'b';
      matchupsBody.appendChild(el('div', 'match-row', `
        <div class="match-side">${m.a.name}</div>
        <div class="match-score"><span class="${aWin ? 'win' : ''}">${m.a.score}</span> - <span class="${bWin ? 'win' : ''}">${m.b.score}</span></div>
        <div class="match-side right">${m.b.name}</div>
      `));
    });
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
      if (recap.winner) html += `<p><b>Winner:</b> ${recap.winner.name} (${recap.winner.net_points} pts)</p>`;
      if (recap.blowout) html += `<p><b>Biggest blowout:</b> ${recap.blowout.a} ${recap.blowout.score_a} - ${recap.blowout.score_b} ${recap.blowout.b}</p>`;
      if (recap.upset) html += `<p><b>Biggest upset:</b> ${recap.upset.winner} over ${recap.upset.loser}</p>`;
      recapCard.innerHTML += html || '<p class="muted">No highlights computed.</p>';
    }
    grid.appendChild(recapCard);
    body.appendChild(grid);

    const matchupsCard = el('div', 'card');
    matchupsCard.style.marginTop = '16px';
    matchupsCard.appendChild(el('h2', null, `Matchups — GW${gw}`));
    (d.all_matchups_by_gw[gw] || []).forEach(m => {
      const aWin = m.winner === 'a', bWin = m.winner === 'b';
      matchupsCard.appendChild(el('div', 'match-row', `
        <div class="match-side">${m.a.name}</div>
        <div class="match-score"><span class="${aWin ? 'win' : ''}">${m.a.score}</span> - <span class="${bWin ? 'win' : ''}">${m.b.score}</span></div>
        <div class="match-side right">${m.b.name}</div>
      `));
    });
    body.appendChild(matchupsCard);
  }

  gws.forEach((gw, i) => {
    const b = el('button', i === gws.length - 1 ? 'active' : '', `GW${gw}`);
    b.onclick = () => { btnGroup.querySelectorAll('button').forEach(x => x.classList.remove('active')); b.classList.add('active'); show(gw); };
    btnGroup.appendChild(b);
  });
  if (gws.length) show(gws[gws.length - 1]);
}

const RENDERERS = { home: renderHome, myteam: renderMyTeam, league: renderLeague, analytics: renderAnalytics, history: renderHistory };
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
