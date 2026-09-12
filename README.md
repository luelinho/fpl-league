# Almost All Americans — League Intelligence

Private analytics system for FPL head-to-head league **683383** (2026/27 season).

Owner: Luel Waktola — *Midtable Crisis*

Full design: [`SPEC.md`](SPEC.md)

---

## Current status

| Phase | State |
|---|---|
| 0 — Environment & scaffold | **Complete** |
| 1 — Verify the FPL API | **Complete** (2026-09-12) |
| 2 — Schema & league reconstruction | **Complete** (2026-09-12) |
| 3 — Historical backfill | **Complete** (2026-09-12) |
| 4 — Automation | **Complete** (2026-09-12), not yet scheduled |
| 5 — Tier 0–2 analytics | **Complete** (2026-09-12) |
| 6 — Claude interface | **Complete** (2026-09-12) |
| 7 — Dashboard | **Complete** (2026-09-12) |
| 8+ | Not started |

GW1–3 fully backfilled: 656 players, 20 clubs, 1,890 player-gameweek stat rows,
54 manager-gameweek summaries, 810 picks, 16 autosubs, 36 transfers, 27 H2H
matches, one current standings snapshot. All validators pass. Cross-checked
`net_points` against every reported H2H match score (27 matches × 2 managers) —
zero mismatches. Spot-checked against the Phase 1 archived payloads exactly.
**Update 2026-09-12:** GW1–2 standings started as a full gap (the live endpoint
only exposes current state) but `ingest.reconstruct_gap_standings` now fills
in W/D/L, league points, and points for/against exactly from stored match
data. Only `rank` stays genuinely unknown for those two gameweeks — FPL's H2H
tiebreak rule for ties was never verified, so a rank number there would be
guessed rather than computed. `standings_snapshots.source` distinguishes
`fpl_h2h_endpoint` rows from `reconstructed` ones. See SPEC.md §11 and §13.

`src/daily_sync.py` (Phase 4) proved idempotent over 3 consecutive runs — every
data table byte-identical, only the append-only `raw_payloads`/`ingest_runs`
logs grew. It is not yet wired to a scheduler (no GitHub Actions / cron), and
`src/calculate.py` (Phase 5) computes `derived_manager_gw` and
`derived_manager_season` for every finalized gameweek — captain efficiency,
XI efficiency, bench points, score rank/percentile. Two managers hand-verified
by independent reconstruction from raw tables, plus a live check against the
FPL site itself (owner's GW3 captain points and bench points read directly off
the site's pitch view, matching exactly). Tier 3–5 (luck, power rankings,
projections) are deliberately left NULL — Phase 8's job. Close/blowout match
counts are now computed with owner-set thresholds (close < 5pts, blowout >
20pts). This repo
is now under git (see below); GitHub Actions is configured but the repo isn't
pushed anywhere yet.

`queries/` (Phase 6) now holds 10 named, parameterized SQL files for the
common questions — roster by gameweek, captains league-wide, H2H history and
aggregate record between two managers, standings at a gameweek, season
ledger, manager-skill summary, weekly extremes (winner/blowout/upset/luckiest/
unluckiest), open data issues, and confidence-gate status. All vetted against
live data with `src/vet_queries.py`. `src/recap.py` generates
`reports/gw{N}.md` for every finalized gameweek.

`dashboard.html` (Phase 7) is a single self-contained file — open it directly,
no server needed. Design choices (clean modern style, top tabs, locked-with-
progress gated metrics) were the owner's explicit calls. Data is baked in at
generation time rather than fetched, since a local `file://` page can't fetch
a sibling JSON (see "Running Phase 7" below and SPEC.md §8). Verified in a
real browser against a local preview server, not just by reading the
generated HTML — caught and fixed a real active-tab/content mismatch bug in
the League page during that check.

**Update 2026-09-12:** added a **Managers** tab — a dropdown over all 18
managers, each getting the exact same ledger/gameweek-history/roster/
transfers view the owner sees on My Team (same rendering function, just
parameterized instead of hardcoded). `digest.py` gained `manager_detail()`
(the old owner-only query, generalized) and a `managers_detail` map covering
everyone; `owner_block()` is now a thin wrapper over it, so My Team's output
is unchanged. This roughly quadrupled `dashboard.html`'s size (~220KB) since
every manager's picks/transfers are now embedded — still trivial for a local
file. Verified with `node --check` on the extracted `<script>` block before
opening it in a browser this time, to catch any repeat of the earlier
Python-string-escaping bug before it reached the page.

**Update 2026-09-12:** once a gameweek's deadline passes, `daily_sync.py`
now captures its squads/captains/live points immediately — previously the
pipeline only ever touched a gameweek after FPL fully finalized it, which
left a real gap between "deadline passed" and "scored" (often several days).
`raw_manager_gw`/`raw_manager_gw_picks`/`raw_player_gw_stats` are upserted
with `is_final=0` for this gameweek and overwritten on every run until FPL
data-checks it — a `WHERE ... is_final = 0` guard on the upsert makes it
impossible for a genuinely final row to ever be overwritten, so this can't
regress a finalized week even if called incorrectly. My Team and Managers
show this gameweek with a red **LIVE** badge and nulled-out rank/efficiency
(honestly unknown, not zero or guessed); History and League don't show it at
all, since it isn't finalized standings/results. Verified against the real
GW4 deadline (passed 12:30 UTC) — captured locked-in squads for all 18
managers within the hour, correctly at 0 points since no matches had
kicked off yet.

**Later 2026-09-12 updates:** the dashboard was restyled twice more to match
owner-supplied reference images (dark glassmorphism — translucent blurred
panels over a vivid purple/amber gradient, lime + lavender + coral accents).
Rosters everywhere now render as an actual football pitch (`renderPitch()`)
instead of a flat list — formation rows, center circle, penalty boxes,
bench below. And every matchup row anywhere (Home, League, History) is
clickable, opening a head-to-head modal: both teams' names, the score, an
all-time record between them (computed client-side, no new digest data),
captain/bench comparison, and both rosters side-by-side as pitches.

Every pitch chip also shows the player's real club badge now (not a face
photo — that was explicitly ruled out) instead of a plain position letter.
`pl_clubs.badge_code` + a small download-once-and-cache step in `digest.py`
(`digest/.badge_cache/`, gitignored) embed all 20 club crests as base64 —
verified live against Premier League's badge CDN before building this,
~6.6KB per badge. No player photos anywhere, and no other layout or content
changed.

---

## Setup

Requires Python 3.11+ (tested against 3.13), macOS or Linux.

```bash
cd fpl-league
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running Phase 1

```bash
source .venv/bin/activate
python -m src.verify_api
```

Takes roughly one to two minutes. It makes about 30 requests, spaced one second
apart, and writes:

- `phase1_output/VERIFICATION_REPORT.md` — human-readable findings
- `phase1_output/findings.json` — machine-readable version
- `phase1_output/payloads/*.json` — every raw response, for offline inspection

Paste the report back into Claude. The spec's data-source section then gets
rewritten to match observed reality before any table is created.

To check the script works without touching the network:

```bash
python -m src.verify_api --selftest
```

---

## Running Phase 2

```bash
source .venv/bin/activate
python -m src.build_db
```

Applies `db/schema.sql`, fetches live H2H standings, resolves all 18 managers to
entry IDs (one `entry/{id}/` request each), and records the league configuration
(`ko_rounds`, `admin_entry_id`, etc). Idempotent — every write is an upsert on a
natural key (`entry_id` for managers, `league_id` for the league row), so
running it again just refreshes the same rows rather than duplicating them.

Any mismatch between the live roster and `config.EXPECTED_MEMBERS` is written to
`data_issues`, not silently reconciled.

---

## Running Phase 3

```bash
source .venv/bin/activate
python -m src.backfill
```

Ingests every data-checked gameweek (currently GW1–3): reference data (players,
clubs, gameweeks), per-player gameweek stats, every manager's picks and summary,
transfers, H2H matches, and a standings snapshot for the latest gameweek only
(the standings endpoint has no history parameter — see the module docstring for
why GW1–2 snapshots are a permanent, logged gap rather than a bug).

Every raw-table write is an upsert on its natural key; `is_final = 1` rows are
never UPDATEd on a rerun. Validators check gameweek/manager/pick counts and the
`net = gross - hits` invariant, and a separate cross-check compares our
`net_points` against every reported H2H match score.

---

## Running Phase 4 (the daily job)

```bash
source .venv/bin/activate
python -m src.daily_sync
```

Same ingestion logic as Phase 3 (shared in `src/ingest.py`), but skips the
expensive per-manager fetch for any gameweek already fully stored — a normal
day costs ~9 requests (bootstrap, H2H matches, standings) instead of ~30+.
A missed day self-heals: the next run just finds more incomplete gameweeks.

A GitHub Actions workflow (`.github/workflows/daily.yml`) is committed and
runs this on a 06:05 UTC cron, committing `db/league.sqlite` only when it
changed. It won't actually run until this repo is pushed to GitHub — see
"Git and CI" below.

---

## Running Phase 5

```bash
source .venv/bin/activate
python -m src.calculate
```

Computes `derived_manager_gw` (score rank/percentile, captain efficiency, XI
efficiency, bench points) and `derived_manager_season` (season-to-date
aggregates, one permanent row per `through_gw`) for every finalized gameweek.
Tier 3–5 columns (luck, power rankings, projections) and the close/blowout
match-margin columns are left `NULL` on purpose — see the module docstring.

---

## Running Phase 6 (queries and recaps)

```bash
source .venv/bin/activate
python -m src.vet_queries   # re-run the query library against live data
python -m src.recap         # regenerate reports/gw{N}.md
```

`queries/*.sql` are named, parameterized (`:entry_id`, `:gw`, etc.) SQL files
meant to be the reviewed answer to a recurring question rather than an
improvised one each time. `src/vet_queries.py` is a standalone harness (not
part of the daily pipeline) that runs every query with real parameters so the
library stays provably working as the schema evolves.

---

## Running Phase 7 (dashboard)

```bash
source .venv/bin/activate
python -m src.digest            # writes digest/season.json
python -m src.build_dashboard   # writes dashboard.html, data baked in
```

Open `dashboard.html` directly in a browser — double-click it, no server
required. Re-run both commands after any data refresh (daily sync, a new
backfill, recalculated analytics) to pick up the changes; the dashboard is a
snapshot, not a live view. `digest/season.json` is also written standalone in
case anything else wants the current-state export.

---

## Git and CI

This repo is a local git repository (`git init`, not yet pushed anywhere).
To finish wiring up Phase 4's automation:

```bash
gh repo create fpl-league --private --source=. --remote=origin
git push -u origin main
```

(or create the private repo yourself on github.com and `git remote add origin
<url>` first). Once pushed, `.github/workflows/daily.yml` starts running on
its own — no further setup needed. GitHub Actions' default `GITHUB_TOKEN` has
write access to the repo it runs in, so no extra secrets are required for the
commit-back step.

---

## What Phase 1 is trying to learn

1. Which endpoints actually exist and respond without authentication
2. Whether the API is reachable at all, or blocked by bot protection
3. The league's knockout-round configuration
4. How 38 gameweeks of fixtures are structured for 18 managers
5. Which gameweek flag genuinely means "bonus and autosubs settled"
6. How the H2H matches endpoint paginates
7. Whether other managers' picks are visible before a deadline
8. Real field names, so the schema matches reality instead of memory

---

## Layout

```
src/config.py       League constants and request settings
src/fpl_client.py   Polite HTTP client — retries, backoff, archiving
src/verify_api.py   Phase 1 verification
src/build_db.py     Phase 2 — schema + league reconstruction
src/ingest.py       Shared loaders used by both backfill.py and daily_sync.py
src/backfill.py     Phase 3 — unconditional historical backfill
src/daily_sync.py   Phase 4 — the one daily job; skips already-complete GWs
src/calculate.py    Phase 5 — Tier 0-2 analytics (ledger + manager skill)
src/recap.py        Phase 6 — weekly recap generator
src/vet_queries.py  Phase 6 — runs queries/*.sql against live data
src/digest.py       Phase 7 — writes digest/season.json
src/build_dashboard.py  Phase 7 — writes dashboard.html (data baked in)
db/schema.sql       Schema, corrected against Phase 1 findings and executed
db/league.sqlite    The database (committed to git per SPEC.md §6 — the commit
                    history is a second audit trail)
queries/            Vetted SQL library (Phase 6)
reports/            Generated gameweek recaps (Phase 6)
digest/season.json  Dashboard JSON export (Phase 7)
dashboard.html      The dashboard itself — open directly, no server (Phase 7)
CLAUDE.md           Operating rules for Claude Code
```

## Ground rules

Written out in full in `CLAUDE.md`. The short version:

- Raw FPL data, derived metrics, and AI interpretation stay in separate layers
- Finalized history is never overwritten
- If a number isn't in the database, say so — never estimate to fill a gap
- Luck metrics are hidden until GW10, projections until GW15
