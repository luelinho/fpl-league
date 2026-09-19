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

**Bug found and fixed 2026-09-19**: `daily_sync.incomplete_gameweeks()`
decided whether a data-checked gw needed re-ingesting by row *count* alone
(18 managers present, 15 picks each, stats exist) — it never checked
`is_final`. A gw that reached full row counts *while still provisional*
(captured the moment its deadline passed) looked permanently "complete"
from then on, even after FPL data-checked it, so it never got re-ingested
with `is_final=True` and stayed stuck at `is_final=0` forever. Caught live:
GW4 sat at `is_final=0` across `raw_manager_gw`/`raw_manager_gw_picks`/
`raw_player_gw_stats` despite being in `data_checked_gws`, showing a stale
**LIVE** badge on the Managers page days after the gameweek actually
finished. Fixed by also checking `COUNT(*) WHERE is_final = 0` per gw in
`incomplete_gameweeks()`; re-running `daily_sync` immediately flipped GW4
correctly (the existing `WHERE is_final = 0` upsert guard allows exactly
this one 0→1 transition, then blocks all further writes). Worth
remembering: row presence and finality are different facts — never assume
one implies the other when deciding what needs re-ingesting.

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
  `player_id`, same pattern as `pl_clubs.badge_code`) builds the photo URL.
  `digest.player_photos()` only fetches players who've actually appeared in
  a league roster (not FPL's full ~660-player universe) and resizes each
  down via Pillow (now a real dependency, not a one-off tool) before
  caching — the source photo is ~100KB and this project can see 150-250
  distinct rostered players in a season, so embedding at native size would
  multiply the dashboard's file size several times over. Kits are still
  fetched and used as the fallback image for any player a photo wasn't
  found for.
- The photo source is the **main premierleague.com** photo bucket
  (`resources.premierleague.com/premierleague25/photos/players/110x140/
  {code}.png`, same `code` as above, no `p` prefix), not FPL Fantasy's own
  bucket (`.../premierleague/.../p{code}.png`) — switched same day after
  finding Fantasy's bucket lags behind FPL's own team-assignment data post-
  transfer (three real players confirmed showing their *previous* club's
  kit there, despite `bootstrap-static` already reporting the current one;
  the premierleague.com bucket had all three correct). 120/122 (98%)
  coverage across every currently-rostered player before switching over.
- The dashboard's font is **Inter**, embedded as base64
  (`assets/fonts/inter-variable-latin.woff2`, Google's own variable-weight
  latin-only subset file, 47KB) rather than linked from Google Fonts, to
  keep the page fully self-contained. Picked 2026-09-19 after live-
  comparing it against Manrope, Nunito Sans, Work Sans, and Poppins one
  per Home card, then a full-page Inter-vs-Work-Sans head-to-head, before
  settling on Inter for this dashboard's table/number density.
- The color palette is **EPL-inspired purple**, adopted 2026-09-19,
  replacing the original near-black/lime theme — real colors sampled from
  premierleague.com's own live stylesheet, not guessed: `#37003c`-family
  purple for backgrounds, `#00ff87` (their neon green) as the primary
  accent (wins, active tab, captain badge), `#ff2882` (their pink) as the
  secondary accent (draws, vice-captain, gradient frame). Every hardcoded
  near-black in the stylesheet (topbar, modal, tooltip backgrounds) was
  also shifted to match, not just the `:root` custom properties, so there
  are no leftover near-black surfaces anywhere in the page.
- The full-size pitch (My Team, Managers, League Dream Team, and each
  side of the mobile H2H tab view) renders at ~85% of its desktop
  dimensions on mobile — fonts, jersey/photo images, gaps, and padding
  all scaled together, not just font-size, since the images are fixed px
  and dominate the height. Scoped to stay clear of the H2H modal's own
  separately-tuned compact side-by-side sizing (34x42 images), which is
  more specific in CSS and always wins regardless of viewport.
- CSS gotcha, hit three times now: a `@media (max-width: 720px)` override
  placed *before* its same-selector base rule in source order loses the
  cascade tiebreak regardless of the media query matching — the later
  base rule silently wins. Bit `.h2h-header`/`.h2h-score`/`.h2h-record`
  first, then `.modal-overlay`/`.modal-card` (found 2026-09-19 via the
  owner comparing a live render against a manually zoomed-out screenshot,
  "field looks wider" — the H2H modal had been rendering at full desktop
  padding on every phone since an earlier "audit fixes" commit), then —
  same day, same root cause — almost the *entire* original mobile-shrink
  block: `.card`, `.locked-card`, `.section-title`, `table`, `th,td`,
  `.modal-close`, `.gw-nav-arrow`, `.gw-nav-select`, `.tabbtn-group
  button` had all been no-ops site-wide since whenever each was first
  written (`#manager-select` survived only because it used `!important`;
  a few others survived on higher specificity, e.g. `.grid-4 .stat
  .value`). All of it is now consolidated at the very end of the
  stylesheet, after every base rule, and pushed noticeably smaller than
  the original (broken) attempt — not just fixed in place — per the
  owner's 2026-09-19 ask to shrink every page to the H2H modal's density.
  Confirmed via `getComputedStyle`, not by eye. **Any future mobile-only
  CSS added to this file goes at the end of the stylesheet, after every
  base rule it touches — never inline near a related feature — and gets
  verified with a computed-style check, not just a screenshot.**
- The dashboard refreshes every 5 minutes during live matches via
  `.github/workflows/live.yml`, added 2026-09-19 (owner's ask: "quickest
  we can update without breaking"). 5 minutes is GitHub Actions' practical
  floor for a `schedule` trigger — a queued run can lag further under
  platform load, so it's a target cadence, not a guarantee. Scoped to
  broad matchday windows (Fri evening, all-day Sat/Sun, Mon Night
  Football, midweek Tue-Thu evenings) rather than 24/7, both because a
  window firing when no match is actually on wastes nothing but a few
  no-op API calls and because it keeps the schedule legible — this repo
  is public so Actions minutes themselves are free either way. Shares
  `daily.yml`'s exact five-command pipeline and its `daily-sync`
  concurrency group (both write `db/league.sqlite` and `dashboard.html`
  and push to `main`, so they must never run concurrently). Safe to run
  this often only because `daily_sync.py` is upsert-on-natural-key
  idempotent per §6/§7 — a no-op poll costs ~3-4 cheap API calls, not a
  bad write.
- Standings `rank` for GW1–2 is permanently unknown (`standings_snapshots.source
  = 'reconstructed'`), not just missing. The live standings endpoint only ever
  exposes current state, and FPL's H2H tiebreak rule for ties was never
  empirically verified — see SPEC.md §13 for how to eventually confirm it once
  a future gameweek produces a real tie. W/D/L/points for those two gameweeks
  ARE exact, reconstructed from immutable raw match data — only rank is gated.
- Manager names are click-throughs to their Managers-page detail view —
  the League page's standings rows (`goToManagerPage()`, added
  2026-09-19) and each side's name at the top of the H2H modal
  (`.side-name-link`). Both reuse the Managers tab's own lazy-render +
  `<select>` machinery rather than duplicating it, so there's one code
  path for "show this manager's detail."
- The League page's "All matchups" section and the Home page's
  "results" card (arrow-navigable, added 2026-09-19) both cover every
  gameweek in `raw_h2h_matches` — not just finalized ones — via
  `digest.season_matchups_by_gw()`. FPL generates the whole double
  round-robin schedule upfront, so future pairings are already real
  stored fact (`status='scheduled'`, no score), just not previously
  surfaced. Each gw is labeled `final` (immutable score from
  `raw_h2h_matches` itself), `live` (the one gw currently being
  provisionally tracked — score comes from `raw_manager_gw`'s `is_final
  =0` rows via `fixtures_for_gw()`, same source the Home page's live
  fixtures card already used), or `upcoming` (pairing only). This is
  separate from the older `all_matchups_by_gw` (final-only), which stays
  as-is because `allTimeRecord()` and the History page's per-gw recap
  both need it restricted to real, finalized results.
- The topbar shows the owner-supplied logo (added 2026-09-19), split into
  two cropped assets — `assets/images/logo-icon.png` (the goal/diving-
  player mark) and `logo-wordmark.png` (the "Almost All Americans" text) —
  rather than the single full lockup, so they can sit side by side at
  header height instead of the source art's tall stacked layout.
  Background removed from the source PNG (a flat white square) via a
  brightness-ramp alpha, not a hard chroma-key cutoff, so the anti-aliased
  edges stay smooth instead of haloed. We tried to identify and reuse the
  wordmark's actual typeface for the plain-text title first (rendered
  "Jost," the closest geometric-sans Google Font candidate, side by side
  against the real wordmark) but the letterforms didn't match closely
  enough to be confident — so per the owner's call, the wordmark image
  itself replaces the text instead of guessing a substitute font. The
  brand+tabs are centered as one group on every width (`justify-content:
  center` on `.topbar-inner`) — briefly tried hugging the brand left on
  desktop with the tabs right after it, but the owner asked to go back to
  centering both. The subtitle under the wordmark shows only the season
  (e.g. "2026/27") — the league ID was dropped as clutter once the
  wordmark image made the league name itself redundant to restate.
- Switching tabs (or `goToManagerPage()`'s programmatic tab switch from
  the League table / H2H modal) always resets scroll to the top
  (`window.scrollTo(0, 0)`) — added 2026-09-19 after the owner found a
  new page could open mid-scroll, inheriting the previous page's
  position.
- Home's Standings card projects live standings while a gameweek is in
  progress, via `digest.live_standings_projection()`: a **Computed**
  projection per CLAUDE.md §3 (labeled "GW{n} LIVE" in the UI, never
  presented as fact), built from `raw_manager_gw`'s live net_points
  applied on top of the last finalized standings snapshot. Each
  manager's rank movement vs. the pre-live-gw snapshot shows as ▲
  (green, moved up), ▼ (red, moved down), or no icon (unchanged) — never
  invented for a tie: equal projected league points keep each manager's
  previous relative order rather than asserting FPL's own unverified H2H
  tiebreak rule (see §9 standings-rank note / SPEC.md §13). Falls back to
  the plain finalized-standings view outside of a live gameweek. To fit
  all 18 managers in the card without it growing much taller than its
  neighbor (the fixtures card), the table is scoped compact
  (`.gc-standings table/th/td`, single-line manager+team) rather than
  touching the shared `table`/`th,td` rules the League/Analytics
  standings tables also use — sized (13.5px table font, 7px/9px cell
  padding) specifically to land close to the fixtures card's own
  natural height once its `.proj-card` rows were also trimmed slightly,
  so the two boxes read as a matched pair rather than one dwarfing the
  other. Both were tuned together, by measuring actual rendered height,
  not by eyeballing — if either card's content changes later (a new
  standings column, a taller fixture row), re-measure and adjust both
  rather than just one.
- The League page's "All matchups" section uses the same prev/next-arrow
  + `<select>` gameweek picker as the Players page and Home's results
  card, not one button per gameweek — a 35-button row stopped being
  usable once every gameweek (not just finalized ones) got a tab (see
  `season_matchups_by_gw` above).

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

Two GitHub Actions workflows run all five in order: `daily.yml` once a day
at 06:05 UTC, and `live.yml` every 5 minutes during typical Premier League
kickoff windows (Fri evening, all-day Sat/Sun, Mon Night Football, midweek
evenings) — see §9 for why 5 minutes and why windowed rather than 24/7. If
you edit `src/build_dashboard.py`, always run `build_dashboard` again
afterward and re-open the file — editing the generator does not change the
already-written `dashboard.html` on disk.

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
