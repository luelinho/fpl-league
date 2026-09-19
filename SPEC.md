# Almost All Americans — League Intelligence System
## Locked Specification v1.0

**Date:** 11 September 2026
**Season:** 2026/27
**League:** Almost all Americans — FPL-native Head-to-Head, ID `683383`, 18 managers
**Owner:** Luel Waktola — *Midtable Crisis*
**Status:** Design locked. Phases 0–7 complete (2026-09-12) — verified API, schema, league reconstruction, historical backfill, automation, Tier 0–2 analytics, Claude query interface, and the dashboard are all built and running, plus ongoing dashboard/pipeline refinements since (see §8, §11). Phase 8 (Tier 3–5) is gated until GW10/GW15 and hasn't started.

---

## 0. Confirmed Requirements

Settled during the requirements interview:

| Topic | Decision |
|---|---|
| League type | FPL-native H2H. FPL owns the fixture schedule and the W/D/L table. |
| Scoring | Standard FPL. Match score = GW points **minus transfer hits**. 3 / 1 / 0. |
| Custom rules | None. No money, no side pots, no custom tiebreakers. |
| Start | All 18 joined before GW1. No late entrants, no schedule holes. |
| Knockout rounds | **Unknown.** Read from league data in Phase 1, not guessed. |
| Seasons | 2026/27 only. Schema multi-season, but no backfill of prior seasons. |
| Update frequency | **Once daily.** No live in-match polling. |
| Credentials | **None.** No FPL login, no secrets, no auth module. |
| Audience | Owner only. No sharing, no multi-user, no publishing. |
| Analytics priority | Ledger → Recap → **Manager skill** → Luck (GW10+) → Power rankings (GW10+) → Projections (GW15+) |
| Stack | Python + SQLite + Git, queried through Claude Code. |

### Standing constraint

**This chat has no network access.** Code, schema, and logic can be built and tested here against mock data. Every real FPL request must run on your machine or a cloud runner. No endpoint in this document has been verified. Phase 1 exists specifically to verify them.

---

## 1. Product Specification

### What it is

A local, file-based database that accumulates a complete and permanent record of one FPL H2H league, plus a derived analytics layer, queried in natural language through Claude Code.

### What it must do

1. Record, permanently and without overwriting, what every manager owned, started, captained, benched and transferred in every gameweek.
2. Record every H2H result and the standings after every gameweek.
3. Compute manager-skill metrics that are exact rather than estimated.
4. Compute luck and strength metrics, but withhold them until the sample supports them.
5. Answer natural-language questions against real stored data.
6. Never present an estimate as a fact, and never invent a number.

### What it explicitly will not do

- Live in-match scoring.
- Anything requiring an FPL login.
- Prior seasons.
- Multi-user access, sharing, or publishing.
- Player recommendations or transfer advice as a core feature. (Possible later; not scoped.)

### The three layers, kept separate

| Layer | Definition | Storage | Mutability |
|---|---|---|---|
| **Raw** | What FPL reported. | `raw_*` tables | Append-only once finalized |
| **Derived** | What our code computed from raw. | `derived_*` tables | Recomputable from scratch |
| **Interpretation** | What Claude says about it. | Never stored as fact | Ephemeral |

Rule: derived tables must be fully reproducible by deleting them and rerunning the calculators over raw. If that ever fails, something has leaked between layers.

---

## 2. Data Source Architecture

### Source

The public JSON API behind the official FPL website. Base: `https://fantasy.premierleague.com/api/`

No authentication, no API key, no documented terms of service, no published rate limit, no stability guarantee. It can change without notice. That risk is accepted, and mitigated by archiving raw payloads (§3.6) so we can replay ingestion after a schema change.

### Endpoints — VERIFIED (Phase 1, 2026-09-12)

All 10 endpoints responded 200 and unauthenticated, exactly as hoped. Full evidence in `phase1_output/VERIFICATION_REPORT.md` and `findings.json`. One 404 was observed and it was the *expected* one (§ pre-deadline visibility below), not a design failure.

| Path | Purpose | Status |
|---|---|---|
| `bootstrap-static/` | Players, PL clubs, gameweek list, positions, chip definitions | Verified — 656 players, 20 clubs, 38 events |
| `fixtures/` | PL fixtures, kickoff times, results | Verified — 380 fixtures |
| `event/{GW}/live/` | Per-player stats and points for a gameweek | Verified — far more stat fields than expected (see below) |
| `entry/{entry_id}/` | Manager profile, team name, current standing | Verified |
| `entry/{entry_id}/history/` | Per-GW summary for a manager, plus chips played | Verified |
| `entry/{entry_id}/event/{GW}/picks/` | Squad, XI/bench, captain, multipliers, autosubs | Verified — 15 picks, `active_chip`, `automatic_subs` all present |
| `entry/{entry_id}/transfers/` | Every transfer with gameweek and cost | Verified |
| `leagues-h2h/{league_id}/standings/` | H2H table + league configuration object | Verified — 18 entries |
| `leagues-h2h-matches/league/{league_id}/` | H2H fixtures and results, paginated | Verified — 315 matches across 7 pages |
| `element-summary/{player_id}/` | Per-player history and fixtures | Verified |

### Phase 1 findings — the five unknowns, resolved

1. **Knockout configuration: HAS knockout rounds.** `league.ko_rounds = 3`. This is not a pure title race — §7 projections must be playoff odds, not title-race odds. `h2h_ko_matches_created` on the event object will flip once FPL seeds the bracket (not yet, at GW3).
2. **Fixture structure: 34-week double round-robin + 1 extra week, then 3 knockout rounds.** The matches endpoint currently returns the full pre-scheduled regular season: GW1–35, 9 matches/GW, 315 total. Of the 153 distinct pairings (C(18,2)), 144 meet twice and 9 meet a third time — that's the double round-robin (34 weeks) plus one extra week of 9 fixtures to reach 35. GW36–38 are the 3 knockout rounds, not yet generated by FPL.
3. **Pre-deadline visibility: confirmed not visible.** Requesting another manager's GW4 picks before the GW4 deadline returned `404`, not an empty/masked payload. Design assumption (post-deadline capture only) holds.
4. **Finalization signal: `data_checked` is real and authoritative.** Present on every event; agreed with `finished` for all of GW1–3 (no divergence observed yet, but `data_checked` remains the gate per the original design — it's the field that's actually documented as meaning "bonus points and autosubs are final").
5. **Pagination: `?page=N` with a `has_next` boolean, page size 50.** Straightforward; 7 pages for 315 matches.

**Bonus finding, not originally listed as an unknown:** `event/{GW}/live/` returns far more per-player stats than anticipated — `influence`, `creativity`, `threat`, `ict_index`, `clearances_blocks_interceptions`, `recoveries`, `tackles`, `starts`, `expected_goal_involvements`, `expected_goals_conceded`, `in_dreamteam`, `played`, in addition to the expected fields. `defensive_contribution` is confirmed real and present on every player. Schema updated in §3.3 to capture all of them rather than discard them.

**Cosmetic finding:** the roster hint for Andrew Romani's team used a straight apostrophe (`Rock 'n Iraola`); FPL's live data uses curly quotes (`Rock ‘n’ Iraola`). Same manager, same entry — `config.py` corrected to match. No real membership change.

### Fallback

If the H2H matches endpoint proves unreliable, matchups are reconstructed from league membership plus each manager's net gameweek score, with results recomputed under 3/1/0. This runs as a **cross-check even when the endpoint works** — any disagreement between reported and reconstructed results is logged as a data issue rather than silently resolved.

### Politeness

Sequential requests, ~1 second apart, identifying User-Agent, exponential backoff on failure. A full daily sync is roughly 25–40 requests. This is a negligible load and should stay that way.

---

## 3. Database Schema

SQLite, written Postgres-shaped so a later migration is a translation rather than a rewrite. Integer primary keys, foreign keys enforced, no SQLite-only types.

Naming: `raw_` = as reported by FPL. `derived_` = computed by us. No prefix = reference/config.

### 3.1 Reference

```sql
CREATE TABLE seasons (
  season_id     INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,      -- '2026/27'
  start_date    DATE,
  end_date      DATE,
  status        TEXT NOT NULL              -- upcoming | active | complete
);

CREATE TABLE leagues (
  league_id       INTEGER PRIMARY KEY,     -- 683383, FPL's own ID
  season_id       INTEGER NOT NULL REFERENCES seasons(season_id),
  name            TEXT NOT NULL,
  league_type     TEXT NOT NULL,           -- 'h2h'
  scoring         TEXT NOT NULL,           -- 'standard'
  start_event     INTEGER NOT NULL,        -- 1
  ko_rounds       INTEGER,                 -- NULL until read from FPL
  admin_entry_id  INTEGER,
  config_json     TEXT,                    -- full league object as returned
  last_verified   TIMESTAMP
);

CREATE TABLE gameweeks (
  gw_id            INTEGER NOT NULL,
  season_id        INTEGER NOT NULL REFERENCES seasons(season_id),
  deadline_utc     TIMESTAMP NOT NULL,
  is_finished      BOOLEAN NOT NULL DEFAULT 0,
  is_data_checked  BOOLEAN NOT NULL DEFAULT 0,   -- gates permanent storage
  avg_score        INTEGER,
  highest_score    INTEGER,
  PRIMARY KEY (season_id, gw_id)
);

CREATE TABLE pl_clubs (
  club_id    INTEGER NOT NULL,
  season_id  INTEGER NOT NULL REFERENCES seasons(season_id),
  name       TEXT NOT NULL,
  short_name TEXT NOT NULL,
  PRIMARY KEY (season_id, club_id)
);

CREATE TABLE players (
  player_id     INTEGER NOT NULL,          -- FPL element id
  season_id     INTEGER NOT NULL REFERENCES seasons(season_id),
  first_name    TEXT,
  last_name     TEXT,
  web_name      TEXT NOT NULL,
  position      TEXT NOT NULL,             -- GKP | DEF | MID | FWD
  club_id       INTEGER NOT NULL,
  PRIMARY KEY (season_id, player_id),
  FOREIGN KEY (season_id, club_id) REFERENCES pl_clubs(season_id, club_id)
);
```

Player *identity* is stable; player *state* (price, form, ownership, injury) is not, so state is snapshotted daily rather than overwritten:

```sql
CREATE TABLE raw_player_snapshots (
  season_id      INTEGER NOT NULL,
  player_id      INTEGER NOT NULL,
  snapshot_date  DATE NOT NULL,
  price_tenths   INTEGER NOT NULL,         -- 75 = £7.5m, integer to avoid float drift
  status         TEXT,                     -- a | d | i | s | u
  news           TEXT,
  chance_next_rd INTEGER,
  selected_by    REAL,
  form           REAL,
  total_points   INTEGER,
  fetched_at     TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, player_id, snapshot_date)
);
```

### 3.2 Managers

Managers are kept separate from teams so a renamed team never rewrites history.

```sql
CREATE TABLE managers (
  manager_id    INTEGER PRIMARY KEY,       -- our surrogate key
  entry_id      INTEGER NOT NULL UNIQUE,   -- FPL entry id
  player_first  TEXT,
  player_last   TEXT,
  display_name  TEXT NOT NULL,             -- 'Luel Waktola'
  is_owner      BOOLEAN NOT NULL DEFAULT 0 -- exactly one row true
);

CREATE TABLE team_names (
  manager_id   INTEGER NOT NULL REFERENCES managers(manager_id),
  season_id    INTEGER NOT NULL,
  team_name    TEXT NOT NULL,
  first_seen   DATE NOT NULL,
  last_seen    DATE NOT NULL,
  PRIMARY KEY (manager_id, season_id, team_name)
);

CREATE TABLE league_memberships (
  league_id    INTEGER NOT NULL REFERENCES leagues(league_id),
  season_id    INTEGER NOT NULL,
  manager_id   INTEGER NOT NULL REFERENCES managers(manager_id),
  joined_event INTEGER,
  is_active    BOOLEAN NOT NULL DEFAULT 1,
  PRIMARY KEY (league_id, season_id, manager_id)
);
```

Known roster to resolve to entry IDs in Phase 2 (18, including the owner): Rock 'n Iraola (Andrew Romani), CMazz (Chris Mazzatta), Erik's Team (Erik Baxter), Blue Bloods (Jordan Fernholz), Game of Throw-In (Craig Allen), Bruno's Bros (Joe Gannitello), #GOAT (Isaac Sotelo), Big Cannon Energy (Ryan Smith), Hoevoeloe (Yorick Stoepker), millers minions (Chris Miller), Kick'in the balls (Brian Moran), Ophelia Balls (Danilo Arroyo), Championship side (Brady Baxter), Toffee Machine (Kirk Baxter), Keiner Bobby Dazzler (Reggie Mazz), Midtable Crisis (Luel Waktola), OliveOilMoneh (Harry Daskalopoulos), FOGGING ESTANDARDS (Iain Abshier).

**These names are treated as a hint, not truth.** Entry IDs come from the league standings response. Any mismatch between this list and live data is reported, not reconciled silently.

### 3.3 Raw gameweek facts

```sql
CREATE TABLE raw_player_gw_stats (
  season_id     INTEGER NOT NULL,
  gw_id         INTEGER NOT NULL,
  player_id     INTEGER NOT NULL,
  minutes       INTEGER NOT NULL DEFAULT 0,
  goals         INTEGER NOT NULL DEFAULT 0,
  assists       INTEGER NOT NULL DEFAULT 0,
  clean_sheets  INTEGER NOT NULL DEFAULT 0,
  goals_conceded INTEGER NOT NULL DEFAULT 0,
  own_goals     INTEGER NOT NULL DEFAULT 0,
  pens_saved    INTEGER NOT NULL DEFAULT 0,
  pens_missed   INTEGER NOT NULL DEFAULT 0,
  saves         INTEGER NOT NULL DEFAULT 0,
  yellow_cards  INTEGER NOT NULL DEFAULT 0,
  red_cards     INTEGER NOT NULL DEFAULT 0,
  bonus         INTEGER NOT NULL DEFAULT 0,
  bps           INTEGER NOT NULL DEFAULT 0,
  defensive_contribution INTEGER,          -- confirmed real, Phase 1
  expected_goals   REAL,
  expected_assists REAL,
  expected_goal_involvements REAL,         -- confirmed real, Phase 1
  expected_goals_conceded    REAL,         -- confirmed real, Phase 1
  influence     REAL,                      -- confirmed real, Phase 1
  creativity    REAL,                      -- confirmed real, Phase 1
  threat        REAL,                      -- confirmed real, Phase 1
  ict_index     REAL,                      -- confirmed real, Phase 1
  clearances_blocks_interceptions INTEGER, -- confirmed real, Phase 1
  recoveries    INTEGER,                   -- confirmed real, Phase 1
  tackles       INTEGER,                   -- confirmed real, Phase 1
  starts        INTEGER,                   -- confirmed real, Phase 1
  in_dreamteam  BOOLEAN NOT NULL DEFAULT 0, -- confirmed real, Phase 1
  played        BOOLEAN,                   -- confirmed real, Phase 1
  total_points  INTEGER NOT NULL,
  is_final      BOOLEAN NOT NULL DEFAULT 0,
  source        TEXT NOT NULL,
  fetched_at    TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, gw_id, player_id)
);
```

Phase 1 found `event/{GW}/live/` returns considerably more per-player stats than originally expected (the fields above marked "confirmed real, Phase 1"). They're captured rather than discarded since they're free and may feed later analytics.

Manager gameweek summary. **Gross and net are stored separately** — this is the H2H-specific detail most tools blur, and every margin calculation depends on it:

```sql
CREATE TABLE raw_manager_gw (
  season_id       INTEGER NOT NULL,
  gw_id           INTEGER NOT NULL,
  manager_id      INTEGER NOT NULL REFERENCES managers(manager_id),
  gross_points    INTEGER NOT NULL,        -- before hits
  hit_cost        INTEGER NOT NULL DEFAULT 0,
  net_points      INTEGER NOT NULL,        -- gross - hit_cost; the H2H match score
  bench_points    INTEGER NOT NULL DEFAULT 0,
  transfers_made  INTEGER NOT NULL DEFAULT 0,
  chip_played     TEXT,                    -- wildcard | bboost | 3xc | freehit | NULL
  squad_value     INTEGER,
  bank            INTEGER,
  overall_rank    INTEGER,
  is_final        BOOLEAN NOT NULL DEFAULT 0,
  source          TEXT NOT NULL,
  fetched_at      TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, gw_id, manager_id)
);
```

**The historical-integrity table.** One row per manager per gameweek per player held:

```sql
CREATE TABLE raw_manager_gw_picks (
  season_id     INTEGER NOT NULL,
  gw_id         INTEGER NOT NULL,
  manager_id    INTEGER NOT NULL REFERENCES managers(manager_id),
  player_id     INTEGER NOT NULL,
  slot          INTEGER NOT NULL,          -- 1-15 as returned by FPL
  is_starter    BOOLEAN NOT NULL,          -- slot <= 11 after autosubs applied
  is_captain    BOOLEAN NOT NULL DEFAULT 0,
  is_vice       BOOLEAN NOT NULL DEFAULT 0,
  multiplier    INTEGER NOT NULL,          -- 0 bench, 1 normal, 2 captain, 3 TC
  points_scored INTEGER,                   -- joined from player stats × multiplier
  is_final      BOOLEAN NOT NULL DEFAULT 0,
  fetched_at    TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, gw_id, manager_id, player_id)
);

CREATE TABLE raw_autosubs (
  season_id   INTEGER NOT NULL,
  gw_id       INTEGER NOT NULL,
  manager_id  INTEGER NOT NULL,
  player_in   INTEGER NOT NULL,
  player_out  INTEGER NOT NULL,
  PRIMARY KEY (season_id, gw_id, manager_id, player_in, player_out)
);

CREATE TABLE raw_transfers (
  transfer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id     INTEGER NOT NULL,
  gw_id         INTEGER NOT NULL,          -- gameweek the transfer applies to
  manager_id    INTEGER NOT NULL,
  player_in     INTEGER NOT NULL,
  player_out    INTEGER NOT NULL,
  price_in      INTEGER,
  price_out     INTEGER,
  transfer_time TIMESTAMP,
  fetched_at    TIMESTAMP NOT NULL,
  UNIQUE (season_id, gw_id, manager_id, player_in, player_out)
);
```

Hit cost is **not** stored per transfer — FPL reports it per gameweek, so attributing a -4 to one specific transfer in a multi-transfer week would be an invention. Cost lives on `raw_manager_gw`, and transfer ROI (§5) handles gameweek transfer batches as a unit.

### 3.4 H2H matchups and standings

```sql
CREATE TABLE raw_h2h_matches (
  match_id        INTEGER PRIMARY KEY,     -- FPL's id where available
  league_id       INTEGER NOT NULL,
  season_id       INTEGER NOT NULL,
  gw_id           INTEGER NOT NULL,
  manager_a       INTEGER NOT NULL REFERENCES managers(manager_id),
  manager_b       INTEGER NOT NULL REFERENCES managers(manager_id),
  score_a         INTEGER,                 -- net points
  score_b         INTEGER,
  winner          INTEGER,                 -- manager_id, or NULL
  is_draw         BOOLEAN,
  margin          INTEGER,                 -- abs(score_a - score_b)
  league_pts_a    INTEGER,
  league_pts_b    INTEGER,
  is_knockout     BOOLEAN NOT NULL DEFAULT 0,
  knockout_name   TEXT,                    -- confirmed real, Phase 1; e.g. 'Semi-Final'
  seed_value      INTEGER,                 -- confirmed real, Phase 1; bracket seed
  tiebreak        TEXT,                    -- confirmed real, Phase 1
  is_bye          BOOLEAN NOT NULL DEFAULT 0, -- confirmed real, Phase 1
  status          TEXT NOT NULL,           -- scheduled | provisional | final
  -- 'scheduled' rows (added Phase 7, for the dashboard's "this week's fixtures")
  -- carry manager_a/manager_b only — score/winner/margin/league_pts are NULL,
  -- never invented. A row is upgraded scheduled -> final once its gameweek is
  -- data-checked; a 'final' row is never regressed back (CLAUDE.md rule 5).
  source          TEXT NOT NULL,           -- 'fpl_h2h_endpoint' | 'reconstructed'
  reconstructed_agrees BOOLEAN,            -- cross-check result
  fetched_at      TIMESTAMP NOT NULL,
  UNIQUE (league_id, season_id, gw_id, manager_a, manager_b)
);

CREATE TABLE standings_snapshots (
  league_id      INTEGER NOT NULL,
  season_id      INTEGER NOT NULL,
  gw_id          INTEGER NOT NULL,         -- standings AFTER this gameweek
  manager_id     INTEGER NOT NULL,
  rank           INTEGER NOT NULL,
  prev_rank      INTEGER,
  rank_change    INTEGER,
  wins           INTEGER NOT NULL,
  draws          INTEGER NOT NULL,
  losses         INTEGER NOT NULL,
  league_points  INTEGER NOT NULL,
  points_for     INTEGER NOT NULL,
  points_against INTEGER NOT NULL,
  streak         TEXT,                     -- 'W3', 'L2', 'D1'
  created_at     TIMESTAMP NOT NULL,
  PRIMARY KEY (league_id, season_id, gw_id, manager_id)
);
```

One snapshot row per manager per gameweek, forever. "Who was first after GW5" is a `WHERE gw_id = 5 AND rank = 1` lookup, not a reconstruction.

### 3.5 Derived

```sql
CREATE TABLE derived_manager_gw (
  season_id          INTEGER NOT NULL,
  gw_id              INTEGER NOT NULL,
  manager_id         INTEGER NOT NULL,
  -- exact from GW1
  score_rank         INTEGER NOT NULL,     -- 1-18 that week
  score_percentile   REAL NOT NULL,
  allplay_w          INTEGER NOT NULL,     -- vs all 17 others
  allplay_d          INTEGER NOT NULL,
  allplay_l          INTEGER NOT NULL,
  beat_median        BOOLEAN NOT NULL,
  captain_points     INTEGER,
  optimal_captain_points INTEGER,          -- best in own 15
  captain_efficiency REAL,
  bench_points       INTEGER,
  xi_points          INTEGER,
  optimal_xi_points  INTEGER,              -- best legal XI from own 15
  xi_efficiency      REAL,
  -- provisional, gated
  expected_h2h_pts   REAL,
  calc_version       TEXT NOT NULL,
  calculated_at      TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, gw_id, manager_id)
);

CREATE TABLE derived_manager_season (
  season_id        INTEGER NOT NULL,
  manager_id       INTEGER NOT NULL,
  through_gw       INTEGER NOT NULL,
  gws_played       INTEGER NOT NULL,       -- confidence gate for every estimate
  points_for       INTEGER, points_against INTEGER,
  avg_pf REAL, avg_pa REAL, median_score REAL, stdev_score REAL,
  actual_w INTEGER, actual_d INTEGER, actual_l INTEGER, actual_league_pts INTEGER,
  allplay_w INTEGER, allplay_d INTEGER, allplay_l INTEGER, allplay_pct REAL,
  expected_wins REAL, expected_league_pts REAL,
  luck_index REAL,                         -- actual - expected league points
  sos_played REAL, sos_remaining REAL,
  form_3gw REAL, form_5gw REAL,
  close_w INTEGER, close_l INTEGER, blowout_w INTEGER, blowout_l INTEGER,
  total_bench_points INTEGER,
  season_captain_efficiency REAL,
  season_xi_efficiency REAL,
  total_hit_cost INTEGER, transfer_roi REAL,
  is_provisional BOOLEAN NOT NULL,         -- true below the GW threshold
  calc_version TEXT NOT NULL,
  calculated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, manager_id, through_gw)
);
```

Plus `derived_transfer_roi`, `derived_chip_roi`, `derived_power_rankings` (model-versioned), `derived_projections`. Defined in Phase 5/8 rather than pre-specified here, because their shape should follow the data we actually observe.

### 3.6 Operations

```sql
CREATE TABLE ingest_runs (
  run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at    TIMESTAMP NOT NULL,
  finished_at   TIMESTAMP,
  job_name      TEXT NOT NULL,
  status        TEXT NOT NULL,             -- success | partial | failed
  requests_made INTEGER,
  rows_written  INTEGER,
  error_text    TEXT
);

CREATE TABLE data_issues (
  issue_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  detected_at  TIMESTAMP NOT NULL,
  severity     TEXT NOT NULL,              -- info | warning | error
  category     TEXT NOT NULL,
  season_id INTEGER, gw_id INTEGER, manager_id INTEGER,
  description  TEXT NOT NULL,
  resolved     BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE raw_payloads (
  payload_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint     TEXT NOT NULL,
  params       TEXT,
  fetched_at   TIMESTAMP NOT NULL,
  gw_id        INTEGER,
  body_gzip    BLOB NOT NULL
);
```

`raw_payloads` is the insurance policy. Every response is archived compressed, so if a parser bug is found in GW20 we can replay GW1–19 without re-requesting anything. Estimated cost for a full season: a few hundred MB at most, likely far less.

---

## 4. Historical Integrity

Five mechanisms, in order of importance:

1. **Finalization gate.** Nothing is written to a permanent table until the gameweek's data-checked flag is true. Before that, rows carry `is_final = 0` and are freely replaceable. After, they are immutable.

2. **Application-level immutability.** The writer refuses to UPDATE any row with `is_final = 1`. An attempt logs an `error`-severity data issue instead. If FPL retroactively changes a settled stat, that becomes a visible, reviewed event — not a silent rewrite.

3. **Natural keys everywhere.** Every raw table's primary key is its natural key, so every write is an idempotent upsert. Running the daily sync ten times produces identical state.

4. **Snapshot, don't mutate.** Prices, standings and player state are dated rows, never overwritten fields.

5. **Provenance.** `source` and `fetched_at` on every raw row. Every stored number can be traced to an endpoint and a moment.

Target questions, all answerable by direct query:

- *"What was my roster in GW3?"* → `raw_manager_gw_picks` where gw=3
- *"Who was first after GW5?"* → `standings_snapshots` where gw=5, rank=1
- *"Who did I captain against CMazz in GW7?"* → join picks to `raw_h2h_matches`

---

## 5. Analytics — Methodology

Every non-obvious metric, stated explicitly. No metric ships without its formula documented here.

### Tier 0 — Ledger (exact, from GW1)

Arithmetic on stored facts. Points for/against, hits, margins, bench points, captain points, rank movement. No assumptions.

### Tier 1 — Weekly recap (from GW1)

Narrative over Tier 0. Gameweek winner, biggest blowout, biggest upset, unluckiest team of the week, risers/fallers, Midtable Crisis report.

- **Biggest upset:** largest positive gap between winner's deficit in season-to-date average points and the result. Below GW4 this is labeled as thin.
- **Unluckiest of the week:** highest net score among losers.
- **Luckiest of the week:** lowest net score among winners.
- **Banter:** generated only from stored numbers. A statistic that cannot be produced by a query does not go in the recap.

### Tier 2 — Manager skill (exact, from GW1) — *your priority tier*

**Captain efficiency** = captain points earned ÷ points the best possible captain choice in that same 15-man squad would have earned. Measures decision quality against your own realistic options, not against hindsight-perfect league-wide choices. Reported alongside league captain distribution so a differential captain that paid off is visible as such.

**Points left on bench** = sum of points scored by players with multiplier 0, excluding those brought on by autosub. Bench Boost weeks are excluded from the season aggregate and reported separately, since there is no bench to leave points on.

**Starting XI efficiency** = actual XI points ÷ highest-scoring legal XI from the same 15, respecting formation constraints (1 GKP, 3–5 DEF, 2–5 MID, 1–3 FWD). Computed by brute-force search over legal formations — trivially fast at this scale.

**Transfer ROI.** Per gameweek batch, not per transfer, because hit costs are reported per gameweek. For each batch: (sum of points scored by players brought in, over horizon H) − (sum of points scored by players sent out, over the same H) − hit cost. Default H = 5 gameweeks, configurable. Players transferred again inside the window terminate their leg early. Reported with H stated, and as incomplete until H gameweeks have elapsed.

**Chip ROI.** Per chip:
- *Triple Captain:* points gained vs a normal captaincy = captain's raw score × 1.
- *Bench Boost:* points contributed by the four bench players.
- *Free Hit:* Free Hit team's score minus the score the unchanged previous squad would have scored — a counterfactual, so labeled estimate.
- *Wildcard:* no clean counterfactual exists. Reported as squad value and points change over the following 5 gameweeks, explicitly not as a single ROI number.

**Differentials and overlap.** Ownership of each player across the 18, and pairwise roster similarity (Jaccard over 15-man squads).

### Tier 3 — Luck and true strength (computed from GW1, **hidden until GW10**)

**All-play record.** For each gameweek, compare a manager's net score against all 17 others. Produces a W/D/L out of 17 per week. This is the neutral-schedule baseline and it matters especially here, because 18 managers over 38 gameweeks cannot produce a balanced double round-robin — the real fixture list is uneven, so some rivalries occur more often than others.

**Expected wins** = Σ over gameweeks of (opponents beaten that week ÷ 17). The number of wins a manager would average against a random opponent each week.

**Expected league points** = Σ of [3 × (beaten ÷ 17) + 1 × (tied ÷ 17)].

**Luck index** = actual league points − expected league points. Positive means the schedule has been kind. This is a description of what happened, not a claim about skill.

**Record vs league median:** W/L against each week's median score. Simpler and more robust than all-play; reported alongside as a sanity check.

**Strength of schedule** = mean of opponents' season-to-date average points for, played and remaining. Remaining SOS uses current form and is therefore a projection.

**Gate:** none of this is surfaced below 10 completed gameweeks. Computed and stored from GW1, so the history exists the moment the gate opens, but a query before GW10 returns "insufficient sample (n gameweeks, need 10)" rather than a number.

### Tier 4 — Power rankings (GW10+)

Four selectable models, each documented with its weights:

1. **Statistical:** points-for percentile, all-play percentage, consistency (inverse stdev), schedule-adjusted scoring.
2. **Form:** rolling 3- and 5-gameweek weighted scoring, recent all-play.
3. **Roster strength:** current squad's forward-looking strength — player form, upcoming fixture difficulty, injury flags, squad value.
4. **Hybrid:** weighted blend, weights exposed and adjustable.

Rankings are stored with their model name and version, so a ranking can always be reproduced and explained.

### Tier 5 — Projections (GW15+)

Monte Carlo over the remaining fixture list. Each manager's weekly score is sampled from their own observed distribution (mean and stdev, with shrinkage toward the league mean to avoid overfitting a small sample), the remaining schedule is simulated 10,000+ times, and frequencies are reported: playoff/title probability, seed distribution, likely wins needed, best and worst possible finish, most impactful remaining fixtures.

Always labeled as projection. Always reported with the assumption set and the sample size behind it. Never stated as a prediction of fact.

### Confidence gating — the rule that enforces the fact/estimate split

| Tier | Minimum gameweeks | Below threshold |
|---|---|---|
| 0 Ledger | 1 | Always shown |
| 1 Recap | 1 | Always shown |
| 2 Skill | 1 (ROI: H+1) | Shown; ROI marked incomplete |
| 3 Luck | 10 | **Withheld** |
| 4 Power | 10 | **Withheld** |
| 5 Projections | 15 | **Withheld** |

Every derived row carries `gws_played` and `is_provisional`. The query layer refuses to present gated metrics without the label.

---

## 6. Automation

### One daily job

A single idempotent run, scheduled daily. Recommended time: shortly after 06:00 UTC, which is after the previous day's matches have settled and before most European price changes land.

Steps:

1. Fetch `bootstrap-static/`. Update gameweeks, players, clubs; snapshot player state.
2. Determine gameweek status: which are data-checked, which is current, which is next.
3. For any data-checked gameweek not yet finalized: fetch live stats, all 18 managers' picks, histories and transfers; write with `is_final = 1`.
4. Fetch H2H matches and standings; reconstruct results independently; compare; log disagreements.
5. Write standings snapshot.
6. Run validators (§ below).
7. Recompute derived tables for affected gameweeks.
8. Regenerate the recap and digest for any newly finalized gameweek.
9. Log the run.

Because the job is idempotent, a missed day self-heals: the next run detects unfinalized gameweeks and catches up. No gameweek is ever missed by a late run, only delayed.

### Where it runs

**Recommendation: GitHub Actions on a schedule, with the SQLite file committed to a private repo.** No machine needs to be awake, and the commit history becomes a second audit trail of exactly what each run wrote.

Two honest caveats: scheduled Actions on the free tier are best-effort and can drift by tens of minutes — irrelevant for a daily job. And GitHub disables schedules in repos with no activity for 60 days, which self-resolves here because each run commits data.

Local cron is the alternative if you'd rather keep everything on one machine. Same code either way.

### Validation

- Every expected gameweek present, no gaps.
- Exactly 18 managers per gameweek.
- Exactly 15 picks per manager per gameweek, exactly one captain, exactly one vice.
- Multipliers legal for the chip played.
- Net points = gross − hits.
- Scores within plausible bounds; flag anything outside a sane range for review rather than rejecting it.
- Every manager appears exactly once per gameweek's fixture list.
- Reported H2H results agree with reconstructed results.
- Standings points reconcile against the sum of match results.

Any failure writes a `data_issues` row. Errors surface at the top of the next query session. **Unverifiable data is reported as unverifiable — never filled in, never guessed.**

---

## 7. Claude Integration

### Primary interface: Claude Code against the repo

Claude Code is a terminal agent with direct local file access — it reads and writes the repo, runs shell commands, and speaks MCP natively. That means it can run the collector, query the SQLite file with real SQL, and answer questions off live data in one session. No export step, no upload, no hosted API, no keys.

The repo carries a `CLAUDE.md` containing: the schema, the raw/derived/interpretation separation, the confidence gates, the metric definitions from §5, and one hard rule — **if a number isn't in the database, say so; never estimate to fill a gap.**

Supporting structure:

- `queries/` — a library of vetted, named SQL for the common questions, so routine asks hit reviewed queries rather than improvised ones.
- `reports/gw{N}.md` — generated recaps, committed per gameweek.
- `digest/season.json` — compact current-state export for the dashboard.

Every question in your original list maps to a query over this schema. "What did my roster look like in GW5", "who did everyone captain this week", "show me every Midtable Crisis matchup", "how have I done against Andrew" are all direct lookups. The luck and projection questions return the gate message until their thresholds are met.

### Mobile

Claude Code is reachable from the Claude mobile app, so Sunday-night questions don't need a laptop.

### Optional later: an MCP server

A small read-only MCP server over the database would let plain claude.ai — web or mobile, no terminal — query the league directly. Genuinely optional. Build it only after the data has proven correct for several gameweeks.

---

## 8. Dashboard

A single self-contained HTML file. **Built 2026-09-12** as `dashboard.html`, generated by `src/build_dashboard.py`.

**Deviation from the literal spec, decided deliberately:** this section originally said the HTML file "reads `digest/season.json`" at runtime. Opening a local file via `file://` cannot `fetch()` a sibling JSON file — browsers block it as cross-origin. Since the owner confirmed the primary use case is double-clicking a local file with no server, `src/build_dashboard.py` embeds the digest data directly into a `<script>` tag at generation time instead of fetching it. `src/digest.py` still produces `digest/season.json` as a standalone artifact (useful for anything else that wants the current-state export), but the dashboard itself is fully self-contained. Regenerate both after any data refresh: `python -m src.digest && python -m src.build_dashboard`.

Design decisions the owner made 2026-09-12: clean modern styling (not bare-bones utilitarian), top-tab navigation between the 5 pages, and gated metrics (luck/power rankings before GW10, projections before GW15) shown as a locked card with a progress bar and "unlocks in N more gameweeks" rather than fully hidden.

Pages, as built: **Home** (standings, this week's fixtures, last results, alerts, price movers, a live countdown + roster + key stats for the owner's next fixture) · **My Team** (owner's ledger stats, gameweek-by-gameweek history — click a row to see that week's roster and transfers below) · **League** (full standings table, all matchups browsable by gameweek) · **Managers** (a dropdown over all 18 managers, each getting the exact same ledger/history/roster/transfers view as My Team — reuses the same rendering function, parameterized by manager instead of hardcoded to the owner) · **Analytics** (sortable manager-skill leaderboard; luck/power-rankings and projections shown locked-with-progress) · **History** (gameweek selector showing that week's standings — W/D/L/points reconstructed for GW1-2, rank honestly shown as unknown for those two — plus its recap highlights and matchups).

**Provisional gameweeks in My Team / Managers.** Once a gameweek's deadline passes, its row appears in the Gameweek History table tagged with a red **LIVE** badge — rank/captain-efficiency/XI-efficiency correctly render as `—` rather than a wrong or invented value, since `derived_manager_gw` genuinely has no row for it yet. Clicking it shows the actual locked-in squad and an explicit "not yet scored" note instead of stale prior-week data. History and League deliberately do NOT show this gameweek — it isn't data-checked, so it stays out of anything presented as finalized standings/results.

**Head-to-head matchup modal.** Every matchup row anywhere in the dashboard (Home's fixtures and results, League's and History's matchup lists) is clickable, opening a modal with both managers' names/teams, the score (or a "vs" placeholder pre-kickoff), an all-time head-to-head tally computed client-side from data already loaded (no new digest fields needed), captain/bench comparison chips justified to each side under the manager/team name, and both managers' actual rosters for that gameweek as side-by-side pitches reusing `renderPitch`. Rosters render correctly even for a still-live gameweek (captains, formations, live 0-point state, all consistent with the rest of the dashboard). Closes via the × button, clicking the backdrop, or Escape.

**Club kit jerseys on every pitch chip.** Roster chips show the player's real club kit, not a player photo — deliberately: no player face photos anywhere in the dashboard. `pl_clubs.badge_code` (FPL's own per-club image code, distinct from `club_id`) doubles as the shirt code; both the outfield and goalkeeper kit variants were verified live against `fantasy.premierleague.com/dist/img/shirts/standard/shirt_{code}-66.png` and `..._1-66.png` (HTTP 200, all 20 clubs, both variants — the GK kit is visibly a different jersey, not a duplicate). `digest.py` downloads both variants per club once, caches them to `digest/.kit_cache/` (gitignored), and embeds them as base64 data URIs in the digest (`club_kits`, keyed by `club_id`, each `{out, gk}`). Every roster player object carries `club_id` and `position`; `playerChip()` picks the goalkeeper kit for `GKP` and the outfield kit otherwise, replacing the earlier badge-in-circle chip, with the captain/vice armband still overlaid on top. This replaced an initial badge-in-circle design (owner's original call, 2026-09-12) after a side-by-side mockup showed the kit reading as an actual roster on a pitch rather than an icon badge — the owner's decision, 2026-09-12.

**Update, 2026-09-19 — reversed to player headshots.** The "no player photos" rule above was the owner's original call, but was explicitly reversed after seeing a reference design: pitch chips now show each player's real headshot as the primary image, resized down via Pillow and cached the same way kits are (`digest/.photo_cache/`, gitignored), scoped to only players who've actually appeared in a league roster this season rather than FPL's full player universe. Club kit stays as the fallback image for any player a photo fetch fails for.

First implementation used FPL Fantasy's own photo bucket (`resources.premierleague.com/premierleague/photos/players/110x140/p{code}.png`) and hit a real problem the same day: that bucket lags behind FPL's own team-assignment data after a real transfer — three specific players (Semenyo, Rogers, Mbeumo) all showed their *previous* club's kit despite `bootstrap-static` already reporting their current club, confirmed by downloading and visually inspecting the actual images. Switched same-day to the main premierleague.com site's photo bucket instead — same numeric `code`, no `p` prefix, path is `premierleague25/photos/players/110x140/{code}.png` (found by inspecting a real player page's image, then confirmed the ID was literally FPL's own `code` value by cross-checking Saliba: code 462424, image filename 462424.png). Re-downloaded and visually re-verified all three previously-wrong players — all three now show their correct, current kit — and checked coverage across every currently-rostered player (120/122, 98%) before switching PHOTO_URL over and clearing the stale cache.

Same gameweek's pitch chip also shows a player's next two real-world fixtures (color-coded by difficulty, reusing the FDR pill styling from Home's squad-fixtures card) in place of the points pill, for exactly as long as they haven't played yet *and* the gameweek itself isn't fully data-checked — `playerChip()`'s `gwIsFinal` check exists specifically so an unused bench player in an already-finished historical gameweek shows their real (possibly zero) points rather than fixtures that happened in the past relative to that view. Fixture lookup is `digest.club_fixtures_list()`, embedded once for the whole season and filtered client-side (`nextFixtures()`) rather than computed per-roster, so it's robust to blank gameweeks (a club with zero fixtures that week).

**Price movers (Home).** A risers/fallers card built from `raw_player_snapshots`, gated honestly: it needs two distinct `snapshot_date`s to show rank movement, and shows an "unavailable" message rather than a guess until a second snapshot date exists.

**Alerts (Home).** The unresolved `data_issues` list is capped to the 5 most severe/recent, with a "+N more not shown" note when more exist — an unbounded list was never the intent, just an artifact of not having enough issues yet to notice.

Gated metrics render with their confidence label or as locked, matching the query layer. Verified in-browser (not just by reading the generated HTML): every figure spot-checked against the same data verified in Phases 5-6, and one real bug was found and fixed during that check — the League tab's gameweek-filter buttons showed GW1 as visually "active" while actually displaying GW3's data on initial load, since the highlighted button and the initial `showGw()` call used different indices.

---

## 9. Security

Almost nothing to secure, which is the point of the design.

- **No credentials anywhere.** No FPL login, no API keys, no tokens, no `.env`.
- **No PII beyond public league data** — names and team names already visible to all 18.
- **Private repo** regardless, since it's yours.
- **Read-only external access:** the system only ever GETs from FPL. It cannot modify your FPL team. No transfer can be made by this code, accidentally or otherwise.
- **No inbound surface.** Nothing listens on a port. Nothing is exposed to the internet.
- **Backups:** the database is one file in Git, versioned on every run.

---

## 10. Cost

| Component | Cost |
|---|---|
| FPL API | Free |
| Python, SQLite | Free, open source |
| GitHub private repo + Actions | Free tier, far below limits |
| Claude Code | Included in your existing Claude subscription |
| Hosting | None required |
| **Ongoing** | **$0** |

Storage: a full season lands in the low tens of MB, plus archived payloads. Actions minutes: a few per day against a free-tier monthly allowance measured in thousands.

The only genuine cost is your time, and the roadmap is built to keep that in small, verifiable pieces.

---

## 11. Roadmap

Each phase has an exit criterion. **No phase begins until the previous one is verified working.**

**Phase 0 — Environment.** Confirm Python 3.11+, Git, Claude Code. Initialize repo.
*Exit: `claude --version` works, repo created.*

**Phase 1 — Verify the API.** A script that hits every endpoint in §2 and reports what actually came back. Answers: knockout config, fixture structure, finalization flag, pagination, pre-deadline visibility.
*Exit: a verification report of observed reality, and §2 rewritten to match. **Nothing is built on an unverified endpoint.*** **✅ Complete 2026-09-12 — 17 requests, zero errors, one cosmetic warning (curly-quote team name, corrected). See `phase1_output/VERIFICATION_REPORT.md`.**

**Phase 2 — Schema and league reconstruction.** Create the database. Resolve all 18 managers to entry IDs from live standings. Reconcile against the known roster and report any mismatch.
*Exit: 18 managers stored, IDs confirmed, league config recorded.*

**Phase 3 — Historical backfill.** Ingest GW1 through current: player stats, picks, transfers, matches, standings snapshots. Run every validator.
*Exit: every gameweek present, all validators pass, roster/standings spot-checks match the FPL site.* **✅ Complete 2026-09-12.** GW1–3 backfilled (84 requests). All validators passed; `net_points` cross-checked against every reported H2H score with zero mismatches; owner's GW1–3 figures spot-checked exactly against Phase 1's archived payloads. See `src/backfill.py`. GW1-2 standings were originally a full gap (the live standings endpoint only exposes current state); `ingest.reconstruct_gap_standings` fills in W/D/L, league points, points for/against, and streak for those two gameweeks exactly, since every match result is immutable and already stored. `rank` is deliberately left NULL for these rows — FPL's H2H tiebreak rule for ties was never empirically verified (see §13), so asserting a rank would mean guessing at an unconfirmed method. `standings_snapshots` carries a `source` column (`fpl_h2h_endpoint` vs `reconstructed`) so the two kinds of row are never confused; see `src/migrate_standings_schema.py` for the one-off schema migration this required.

**Phase 4 — Automation.** Daily job, idempotent, scheduled. Run it repeatedly and confirm the database is unchanged.
*Exit: three consecutive clean automated runs.* **✅ Complete 2026-09-12.** `src/daily_sync.py` ran 3 consecutive times (9 requests each — it skips per-manager fetches for gameweeks already fully stored, unlike Phase 3's unconditional backfill). Every data table was byte-identical across all 3 runs; only the two designed-to-be-append-only logs (`raw_payloads`, `ingest_runs`) grew, exactly as intended. Scheduled via the GitHub Actions workflow at `.github/workflows/daily.yml`, which chains all five pipeline scripts and commits the results. Once a gameweek's deadline passes but before FPL data-checks it, its picks (captain, lineup, transfers) and live/partial points are captured every daily run too — `raw_manager_gw`, `raw_manager_gw_picks`, and `raw_player_gw_stats` all support `is_final=0` upserts, and every write is "upsert until finalized," enforced by a `WHERE <table>.is_final = 0` clause on the upsert itself, so a row already marked final can never be overwritten (CLAUDE.md rule 5). Verified live against GW4: deadline passed 2026-09-12 12:30 UTC, captured minutes later showing real locked-in squads (transfers reflected) with 0 points across the board — honest, since no matches had kicked off yet, not an invented placeholder.

**Phase 5 — Tier 0–2 analytics.** Ledger and manager-skill metrics. Hand-verify captain efficiency, bench points and XI efficiency for at least two managers against the FPL site.
*Exit: manually verified correct.* **✅ Complete 2026-09-12.** `derived_manager_gw` and `derived_manager_season` populated for GW1–3. Two managers independently hand-verified by reconstructing captain/XI/bench figures from raw tables by hand (not just re-running the calculator) — exact match both times. The owner's GW3 captain points (27, Haaland on Triple Captain) and bench points (24) were additionally confirmed by loading the live FPL site and reading them directly off the pitch view. `close_w/close_l/blowout_w/blowout_l` now computed — owner set the thresholds 2026-09-12: close = margin < 5, blowout = margin > 20. Tier 3–5 columns remain deliberately NULL — see `src/calculate.py` docstring for why.

**Phase 6 — Claude interface.** `CLAUDE.md`, query library, recap generator.
*Exit: your question list answered accurately from real data, with gated metrics correctly withheld.* **✅ Complete 2026-09-12.** 10 named, parameterized queries in `queries/` covering roster lookups, captain choices, H2H history/records, standings, ledger, manager skill, weekly extremes, open data issues, and gate status — every one executed against live data with `src/vet_queries.py` (both a real positive match and a true-negative "haven't played yet" case for the H2H queries). `src/recap.py` generates `reports/gw{N}.md` for every finalized gameweek, labeling every line Fact or Computed, honestly reporting risers/fallers as unavailable (needs 2 standings snapshots, only 1 exists), and documenting its "biggest upset" formula in the module docstring since SPEC.md's own wording for it is ambiguous. Recap figures spot-checked against raw/derived tables by hand — exact matches.

**Phase 7 — Dashboard.** HTML + digest JSON.
*Exit: opens, renders current state, gates respected.* **✅ Complete 2026-09-12.** `dashboard.html` opens standalone (no server needed — data is embedded, not fetched), all 5 pages verified in-browser against a local HTTP preview, gates render locked-with-progress as the owner specified. See §8 for the full writeup, including a real bug found and fixed during verification.

**Phase 8 — Tier 3–5.** Luck framework, power rankings, projections. Unlocks at GW10 and GW15 respectively.
*Exit: methodology documented, outputs labeled, sample sizes stated.*

Phases 1–6 are achievable well before GW10, which is when the luck layer becomes meaningful. The timing works out.

---

## 12. MVP

**Phases 1–3 plus a minimal query layer.** Verified endpoints, populated database, complete GW1-to-now history, and the ability to ask Claude Code "what was my roster in GW3" and get a correct answer.

That alone satisfies the irreplaceable requirement: **history not captured now is gone forever.** Everything above the MVP can be added at any time from stored data. Everything below it cannot be recovered later.

---

## 13. Open Items and Assumptions

**Resolved in Phase 1 (2026-09-12):** every endpoint path and response shape confirmed; knockout configuration (`ko_rounds = 3`, playoff odds not title-race odds); the fixture structure (34-week double round-robin + 1 extra week, then 3 knockout GWs); the finalization flag (`data_checked`); H2H matches pagination (`?page=N`, size 50); expected-stats and defensive-contribution fields confirmed present on every player, plus additional live-stat fields not originally anticipated (see §3.3).

**Assumptions, stated plainly:**
- FPL keeps its public API open and roughly stable this season.
- Other managers' picks are readable only after each deadline.
- The 18 names supplied are current, pending live confirmation.
- Standard FPL H2H tiebreaks apply: overall rank, then fewer transfers. **Unverified**, and it's exactly the assumption blocking GW1-2's `rank` reconstruction (§11 Phase 3). To confirm it: wait for a future gameweek where two managers are actually tied on league points, and compare FPL's real reported order for that tie against this rule's prediction. GW3 already has one tie (rank 14, Kirk Baxter and Reggie Mazz) but a single data point isn't enough to rule out coincidence.

**Accepted risks:** the FPL API is undocumented and can change or close without notice — mitigated by payload archiving. Free-tier Actions scheduling drifts — irrelevant daily. Single SQLite file — mitigated by Git.

**Deliberately excluded:** live in-match scoring, authentication, prior seasons, multi-user access, transfer recommendations.

---

*Design locked 11 September 2026. No code written. No endpoint verified. Approval required before Phase 0.*
