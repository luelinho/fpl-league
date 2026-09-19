# Operating rules for this repository

This is a data-integrity project first and an analytics project second. The value
of the database is that it can be trusted. These rules protect that.

Read `SPEC.md` for the full design. Read this file before answering any question
about the league.

---

## 1. The three layers

| Layer | Meaning | Where it lives |
|---|---|---|
| **Raw** | What FPL actually reported | `raw_*` tables |
| **Derived** | What our code computed from raw | `derived_*` tables |
| **Interpretation** | Analysis, opinion, banter | Your response only — never stored as fact |

Never let these mix. Derived tables must be fully reproducible by deleting them
and rerunning the calculators over raw data. If that stops being true, something
has leaked.

## 2. Never invent a number

If the answer isn't in the database, the answer is "that isn't in the database."

- Do not estimate to fill a gap.
- Do not infer a statistic that wasn't computed.
- Do not produce a number for banter or narrative that no query returns.
- If a query returns nothing, say it returned nothing.

A wrong number stated confidently is the worst possible failure mode here. An
admission of missing data is a completely acceptable one.

## 3. Separate what happened from what's estimated

Always label which of these you're doing:

- **Fact** — stored raw data. "You scored 62 in GW3."
- **Computed** — derived from facts by a documented formula. "Your captain
  efficiency is 71%."
- **Projection** — a model output with assumptions. "Simulations give you a 34%
  title chance."
- **Opinion** — your read. Say so.

Never present a projection in the grammar of a fact.

## 4. Confidence gates

Every derived row carries `gws_played` and `is_provisional`. Respect them.

| Metrics | Minimum GWs | Below that |
|---|---|---|
| Ledger, recap, manager-skill | 1 | Show normally |
| Luck, all-play, expected wins, power rankings | 10 | **Withhold** |
| Playoff and title projections | 15 | **Withhold** |

Below the threshold, say "insufficient sample — N gameweeks, need M." Do not
show the number with a caveat attached. The owner chose to wait rather than see
noisy estimates early. Honor that.

## 5. Never overwrite finalized history

Rows with `is_final = 1` are immutable. Do not UPDATE them. Do not "correct"
them. If FPL's current data disagrees with a finalized row, write a
`data_issues` row and surface it — that's a real event worth seeing, not a
discrepancy to smooth over.

The entire point of this database is answering "what was true in GW3" correctly,
years later.

**Provisional gameweeks.** Once a gameweek's deadline passes but before FPL
data-checks it, `daily_sync.py` captures its squads/captains/live points with
`is_final = 0` — real data, just not settled yet (points can still change as
matches are played). These rows are upserted on every run until FPL finalizes
the gameweek, at which point `is_final` flips to 1 and the row stops changing
forever, enforced by a `WHERE <table>.is_final = 0` guard on the upsert itself
— not just application logic. A provisional gameweek's `rank`,
`captain_efficiency`, and `xi_efficiency` are genuinely `NULL` (no
`derived_manager_gw` row exists yet), not zero or estimated. The dashboard
shows these gameweeks with a red **LIVE** badge.

## 6. Idempotency

Every write is an upsert on a natural key. Running any job twice must produce
identical state. If you add a write path, it must satisfy this.

## 7. Don't guess at the FPL API

Until Phase 1 has run, every endpoint in the spec is an assumption. Do not write
code that depends on a field existing until it's been observed in a real
response. Use `.get()` with defaults. Fail loudly on missing critical fields
rather than defaulting to zero — a silent zero becomes a wrong statistic forever.

## 8. Phase discipline

Do not start a phase before the previous one is verified working. "Verified"
means observed output, not an expectation that it should work.

Never claim something works unless it has actually been run.

## 9. Key facts about this league

- FPL-native H2H, league ID `683383`, 18 managers, all joined at GW1
- Match score = gameweek points **minus transfer hits**. 3 win / 1 draw / 0 loss
- Standard scoring. No custom rules, no money, no custom tiebreakers
- 2026/27 only. No prior-season data will ever exist
- Owner is Luel Waktola, *Midtable Crisis*
- Knockout configuration: **`ko_rounds = 3`**, confirmed live in Phase 1 (2026-09-12).
  This is a playoff league, not a pure title race — projections in Tier 5 are
  playoff odds. Regular season is GW1–35 (34-week double round-robin + 1 extra
  week); GW36–38 are the 3 knockout rounds, not yet seeded by FPL.
- "Close" match margin is **under 5 points**; "blowout" is **over 20 points**
  (owner's decision, 2026-09-12 — SPEC.md never defined these, so they were
  not guessed). Used by `derived_manager_season.close_w/close_l/blowout_w/blowout_l`.
- Each of the 4 chips (Wildcard, Bench Boost, Triple Captain, Free Hit) is
  available **twice this season**, once per half — first copy must be played
  by the GW19 deadline, second copy refreshes for GW20–38 (confirmed via
  premierleague.com, 2026-09-13). `raw_manager_gw.chip_played` only ever
  records *that* a chip was played in a given gameweek, not which half's copy
  — the dashboard's Chip tracker (League page) lists every gameweek a chip
  was played rather than asserting a remaining count, since the schema alone
  can't distinguish first-half vs second-half usage.
- `raw_pl_fixtures` holds the real-world Premier League schedule (kickoff
  time, home/away, FDR 1-5, score) from FPL's own `fixtures/` endpoint —
  separate from everything else in the DB, which is FPL-*league* data, not
  real-world match data. Added 2026-09-13; confirmed live (HTTP 200, 380
  fixtures for the season) before use, fetched and upserted every sync
  alongside `bootstrap-static/`. Powers Home's "Your squad's fixtures" card
  (`digest.squad_fixtures`), which replaced the old countdown/deadline
  "Next up" box — a club can have zero fixtures a gameweek (a blank) or two
  (a double), so that function always returns a list per player, never
  assumes exactly one.
- Player face photos replaced club kits as the primary pitch-chip image
  2026-09-19 (owner's call, reversing the earlier "no player photos"
  decision) — `players.code` (FPL's per-player code, distinct from
  `player_id`, same pattern as `pl_clubs.badge_code`) builds the URL
  `resources.premierleague.com/premierleague/photos/players/110x140/
  p{code}.png`; confirmed live before use. `digest.player_photos()` only
  fetches players who've actually appeared in a league roster (not FPL's
  full ~660-player universe) and resizes each down via Pillow (now a real
  dependency, not a one-off tool) before caching — the source photo is
  ~100KB and this project can see 150-250 distinct rostered players in a
  season, so embedding at native size would multiply the dashboard's file
  size several times over. Kits are still fetched and used as the fallback
  image for any player a photo wasn't found for.
- Standings `rank` for GW1–2 is permanently unknown (`standings_snapshots.source
  = 'reconstructed'`), not just missing. The live standings endpoint only ever
  exposes current state, and FPL's H2H tiebreak rule for ties was never
  empirically verified — see SPEC.md §13 for how to eventually confirm it once
  a future gameweek produces a real tie. W/D/L/points for those two gameweeks
  ARE exact, reconstructed from immutable raw match data — only rank is gated.

## 10. Gross vs net

`gross_points` is before hits. `net_points` is after, and is the H2H match score.
Margins, luck and ROI all use net. Getting this backwards silently corrupts most
of the analytics layer.

## 11. Chips change metric meaning

- Bench Boost weeks are excluded from "points left on bench" aggregates
- Triple Captain weeks use multiplier 3, not 2
- Free Hit squads revert the following week — a Free Hit squad is not evidence
  of a manager's ongoing roster
- Wildcard has no clean counterfactual; never report a single Wildcard ROI number

## 12. Tone

Direct and concrete. The owner is the only user and knows FPL well. Skip the
preamble, lead with the answer, keep caveats short but never drop the ones that
matter. Banter is welcome, but only over real numbers.

## 13. The dashboard

`dashboard.html` is a single self-contained file (data baked in, no server, no
network access needed to open it) with seven pages: Home, My Team, League,
Managers (every manager gets My Team's exact view via a dropdown), Players
(most-owned/most-captained among the 18 this gameweek, season transfer
activity — league-scoped, not full FPL-universe stats), Analytics, History.
Rosters render as a pitch (formation rows, player headshots — club kit
jerseys as the fallback when a photo isn't cached — with the armband/flag
overlays unchanged), and clicking any matchup anywhere opens a head-to-head
modal. A player who hasn't played yet this gameweek shows their next two
real-world fixtures (color-coded by difficulty) instead of a points pill;
once they've played, or once the gameweek is fully data-checked, it shows
points as normal — see `playerChip()`'s `gwIsFinal` check, which exists
specifically so an unused bench player in an already-finished gameweek
shows their real (possibly zero) points rather than stale fixtures.

It is a snapshot, not a live view — regenerate it after any data change:

```bash
python -m src.daily_sync   # or backfill.py for a full historical rebuild
python -m src.calculate
python -m src.recap
python -m src.digest
python -m src.build_dashboard
```

The GitHub Actions workflow runs all five in order already. If you edit
`src/build_dashboard.py`, always run `build_dashboard` again afterward and
re-open the file — editing the generator does not change the already-written
`dashboard.html` on disk.

## 14. The MCP server

`src/mcp_server.py` is SPEC.md §7's "optional later" MCP server, built now
that the data has proven correct across several gameweeks. It's read-only —
the DB connection is opened with SQLite's own `mode=ro`, so a write attempt
fails at the SQLite layer regardless of what the code does — and local-only,
launched by an MCP client (Claude Desktop, Claude Code) as a subprocess over
stdio via `.mcp.json`. No hosting, no network exposure, no new attack
surface; the opposite choice (a remote server reachable from a phone) was
considered and deliberately declined; see git history for that discussion.

Its tools mirror the vetted `queries/*.sql` library one-for-one, plus one
guarded `run_readonly_query` escape hatch (single SELECT only, enforced both
by a regex check and the read-only connection itself) for questions the
named tools don't cover. Same rule as everywhere else: never invent a number
past what a tool actually returns.
