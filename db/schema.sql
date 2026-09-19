-- ===========================================================================
-- SCHEMA — corrected against Phase 1 findings (2026-09-12), ready for Phase 2
--
-- Every field below has been observed in a real response from
-- fantasy.premierleague.com/api. See phase1_output/VERIFICATION_REPORT.md and
-- findings.json for the raw evidence. Changes made in this pass:
--
--   - raw_player_gw_stats: added the extra `event/{GW}/live/` stat columns
--     that were not anticipated (influence, creativity, threat, ict_index,
--     clearances_blocks_interceptions, recoveries, tackles, starts,
--     expected_goal_involvements, expected_goals_conceded, in_dreamteam,
--     played). `defensive_contribution` is confirmed real and always present.
--   - raw_h2h_matches: added seed_value, tiebreak, is_bye, knockout_name —
--     all real fields on `leagues-h2h-matches`, needed once GW36-38 (the
--     confirmed 3 knockout rounds, ko_rounds=3) start producing matches.
--   - leagues.ko_rounds is no longer nullable-by-ignorance: this league's
--     value is 3, confirmed live. Column stays nullable for future seasons
--     only.
--
-- Untouched: manager/pick/transfer shapes matched the design as drafted.
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- --- Reference -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS seasons (
  season_id     INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  start_date    DATE,
  end_date      DATE,
  status        TEXT NOT NULL CHECK (status IN ('upcoming','active','complete'))
);

CREATE TABLE IF NOT EXISTS leagues (
  league_id      INTEGER PRIMARY KEY,
  season_id      INTEGER NOT NULL REFERENCES seasons(season_id),
  name           TEXT NOT NULL,
  league_type    TEXT NOT NULL,
  scoring        TEXT NOT NULL,
  start_event    INTEGER NOT NULL,
  ko_rounds      INTEGER,
  admin_entry_id INTEGER,
  config_json    TEXT,
  last_verified  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gameweeks (
  season_id       INTEGER NOT NULL REFERENCES seasons(season_id),
  gw_id           INTEGER NOT NULL,
  deadline_utc    TIMESTAMP NOT NULL,
  is_finished     BOOLEAN NOT NULL DEFAULT 0,
  is_data_checked BOOLEAN NOT NULL DEFAULT 0,
  avg_score       INTEGER,
  highest_score   INTEGER,
  PRIMARY KEY (season_id, gw_id)
);

CREATE TABLE IF NOT EXISTS pl_clubs (
  season_id  INTEGER NOT NULL REFERENCES seasons(season_id),
  club_id    INTEGER NOT NULL,
  name       TEXT NOT NULL,
  short_name TEXT NOT NULL,
  -- badge_code: FPL's own per-club code (distinct from club_id), used to build
  -- the badge image URL: resources.premierleague.com/premierleague/badges/50/t{badge_code}.png
  -- Added 2026-09-12; confirmed live (HTTP 200, ~6.6KB/badge) before use.
  badge_code INTEGER,
  PRIMARY KEY (season_id, club_id)
);

-- Real-world Premier League fixtures — `fixtures/` endpoint, confirmed live
-- 2026-09-13 (HTTP 200, 380 fixtures for the season). team_h/team_a are the
-- same club_id space as pl_clubs (both come from bootstrap-static's team.id).
-- gw_id is nullable: a fixture not yet slotted into a gameweek (postponement,
-- or simply not yet scheduled that far out) genuinely has none, not a value
-- we failed to capture. Upserted every sync since scores/difficulty/kickoff
-- time can all change (postponements, re-scheduling) right up to kickoff.
CREATE TABLE IF NOT EXISTS raw_pl_fixtures (
  season_id         INTEGER NOT NULL REFERENCES seasons(season_id),
  fixture_id        INTEGER NOT NULL,
  gw_id             INTEGER,
  team_h            INTEGER NOT NULL,
  team_a            INTEGER NOT NULL,
  team_h_score      INTEGER,
  team_a_score      INTEGER,
  team_h_difficulty INTEGER,
  team_a_difficulty INTEGER,
  kickoff_time      TEXT,
  finished          BOOLEAN NOT NULL DEFAULT 0,
  fetched_at        TEXT NOT NULL,
  PRIMARY KEY (season_id, fixture_id),
  FOREIGN KEY (season_id, team_h) REFERENCES pl_clubs(season_id, club_id),
  FOREIGN KEY (season_id, team_a) REFERENCES pl_clubs(season_id, club_id)
);

CREATE TABLE IF NOT EXISTS players (
  season_id  INTEGER NOT NULL REFERENCES seasons(season_id),
  player_id  INTEGER NOT NULL,
  first_name TEXT,
  last_name  TEXT,
  web_name   TEXT NOT NULL,
  position   TEXT NOT NULL CHECK (position IN ('GKP','DEF','MID','FWD')),
  club_id    INTEGER NOT NULL,
  -- code: FPL's own per-player code (distinct from player_id), used to build
  -- the headshot photo URL: resources.premierleague.com/premierleague/photos/
  -- players/110x140/p{code}.png. Added 2026-09-19; confirmed live (HTTP 200)
  -- before use, same pattern as pl_clubs.badge_code for kit images.
  code       INTEGER,
  PRIMARY KEY (season_id, player_id),
  FOREIGN KEY (season_id, club_id) REFERENCES pl_clubs(season_id, club_id)
);

-- Player state changes constantly, so it is snapshotted, never overwritten.
CREATE TABLE IF NOT EXISTS raw_player_snapshots (
  season_id      INTEGER NOT NULL,
  player_id      INTEGER NOT NULL,
  snapshot_date  DATE NOT NULL,
  price_tenths   INTEGER NOT NULL,
  status         TEXT,
  news           TEXT,
  chance_next_rd INTEGER,
  selected_by    REAL,
  form           REAL,
  total_points   INTEGER,
  fetched_at     TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, player_id, snapshot_date),
  FOREIGN KEY (season_id, player_id) REFERENCES players(season_id, player_id)
);

-- --- Managers --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS managers (
  manager_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_id     INTEGER NOT NULL UNIQUE,
  player_first TEXT,
  player_last  TEXT,
  display_name TEXT NOT NULL,
  is_owner     BOOLEAN NOT NULL DEFAULT 0
);

-- Team names change mid-season; history must survive a rename.
CREATE TABLE IF NOT EXISTS team_names (
  manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
  season_id  INTEGER NOT NULL,
  team_name  TEXT NOT NULL,
  first_seen DATE NOT NULL,
  last_seen  DATE NOT NULL,
  PRIMARY KEY (manager_id, season_id, team_name)
);

CREATE TABLE IF NOT EXISTS league_memberships (
  league_id    INTEGER NOT NULL REFERENCES leagues(league_id),
  season_id    INTEGER NOT NULL,
  manager_id   INTEGER NOT NULL REFERENCES managers(manager_id),
  joined_event INTEGER,
  is_active    BOOLEAN NOT NULL DEFAULT 1,
  PRIMARY KEY (league_id, season_id, manager_id)
);

-- --- Raw gameweek facts ----------------------------------------------------

CREATE TABLE IF NOT EXISTS raw_player_gw_stats (
  season_id      INTEGER NOT NULL,
  gw_id          INTEGER NOT NULL,
  player_id      INTEGER NOT NULL,
  minutes        INTEGER NOT NULL DEFAULT 0,
  goals          INTEGER NOT NULL DEFAULT 0,
  assists        INTEGER NOT NULL DEFAULT 0,
  clean_sheets   INTEGER NOT NULL DEFAULT 0,
  goals_conceded INTEGER NOT NULL DEFAULT 0,
  own_goals      INTEGER NOT NULL DEFAULT 0,
  pens_saved     INTEGER NOT NULL DEFAULT 0,
  pens_missed    INTEGER NOT NULL DEFAULT 0,
  saves          INTEGER NOT NULL DEFAULT 0,
  yellow_cards   INTEGER NOT NULL DEFAULT 0,
  red_cards      INTEGER NOT NULL DEFAULT 0,
  bonus          INTEGER NOT NULL DEFAULT 0,
  bps            INTEGER NOT NULL DEFAULT 0,
  defensive_contribution INTEGER,   -- confirmed real, present in all Phase 1 samples
  expected_goals   REAL,
  expected_assists REAL,
  expected_goal_involvements REAL,
  expected_goals_conceded    REAL,
  influence      REAL,
  creativity     REAL,
  threat         REAL,
  ict_index      REAL,
  clearances_blocks_interceptions INTEGER,
  recoveries     INTEGER,
  tackles        INTEGER,
  starts         INTEGER,
  in_dreamteam   BOOLEAN NOT NULL DEFAULT 0,
  played         BOOLEAN,
  total_points   INTEGER NOT NULL,
  is_final       BOOLEAN NOT NULL DEFAULT 0,
  source         TEXT NOT NULL,
  fetched_at     TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, gw_id, player_id)
);

-- gross vs net: net is the H2H match score. Never conflate them.
CREATE TABLE IF NOT EXISTS raw_manager_gw (
  season_id      INTEGER NOT NULL,
  gw_id          INTEGER NOT NULL,
  manager_id     INTEGER NOT NULL REFERENCES managers(manager_id),
  gross_points   INTEGER NOT NULL,
  hit_cost       INTEGER NOT NULL DEFAULT 0,
  net_points     INTEGER NOT NULL,
  bench_points   INTEGER NOT NULL DEFAULT 0,
  transfers_made INTEGER NOT NULL DEFAULT 0,
  chip_played    TEXT,
  squad_value    INTEGER,
  bank           INTEGER,
  overall_rank   INTEGER,
  is_final       BOOLEAN NOT NULL DEFAULT 0,
  source         TEXT NOT NULL,
  fetched_at     TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, gw_id, manager_id),
  CHECK (net_points = gross_points - hit_cost)
);

-- The historical-integrity table. One row per player held, per GW, forever.
CREATE TABLE IF NOT EXISTS raw_manager_gw_picks (
  season_id     INTEGER NOT NULL,
  gw_id         INTEGER NOT NULL,
  manager_id    INTEGER NOT NULL REFERENCES managers(manager_id),
  player_id     INTEGER NOT NULL,
  slot          INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 15),
  is_starter    BOOLEAN NOT NULL,
  is_captain    BOOLEAN NOT NULL DEFAULT 0,
  is_vice       BOOLEAN NOT NULL DEFAULT 0,
  multiplier    INTEGER NOT NULL CHECK (multiplier BETWEEN 0 AND 3),
  points_scored INTEGER,
  is_final      BOOLEAN NOT NULL DEFAULT 0,
  fetched_at    TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, gw_id, manager_id, player_id)
);

CREATE TABLE IF NOT EXISTS raw_autosubs (
  season_id  INTEGER NOT NULL,
  gw_id      INTEGER NOT NULL,
  manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
  player_in  INTEGER NOT NULL,
  player_out INTEGER NOT NULL,
  PRIMARY KEY (season_id, gw_id, manager_id, player_in, player_out)
);

-- Hit cost is NOT stored here: FPL reports it per gameweek, so attributing a
-- -4 to one transfer within a multi-transfer week would be an invention.
CREATE TABLE IF NOT EXISTS raw_transfers (
  transfer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id     INTEGER NOT NULL,
  gw_id         INTEGER NOT NULL,
  manager_id    INTEGER NOT NULL REFERENCES managers(manager_id),
  player_in     INTEGER NOT NULL,
  player_out    INTEGER NOT NULL,
  price_in      INTEGER,
  price_out     INTEGER,
  transfer_time TIMESTAMP,
  fetched_at    TIMESTAMP NOT NULL,
  UNIQUE (season_id, gw_id, manager_id, player_in, player_out)
);

-- --- H2H -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw_h2h_matches (
  match_id             INTEGER PRIMARY KEY,
  league_id            INTEGER NOT NULL REFERENCES leagues(league_id),
  season_id            INTEGER NOT NULL,
  gw_id                INTEGER NOT NULL,
  manager_a            INTEGER NOT NULL REFERENCES managers(manager_id),
  manager_b            INTEGER NOT NULL REFERENCES managers(manager_id),
  score_a              INTEGER,
  score_b              INTEGER,
  winner               INTEGER REFERENCES managers(manager_id),
  is_draw              BOOLEAN,
  margin               INTEGER,
  league_pts_a         INTEGER,
  league_pts_b         INTEGER,
  is_knockout          BOOLEAN NOT NULL DEFAULT 0,
  knockout_name        TEXT,    -- e.g. 'Semi-Final', 'Final'; real field, null outside GW36-38
  seed_value           INTEGER, -- knockout bracket seed; real field, null in regular season
  tiebreak             TEXT,    -- real field, observed null through GW3
  is_bye               BOOLEAN NOT NULL DEFAULT 0,  -- real field; possible with odd bracket sizes
  status               TEXT NOT NULL CHECK (status IN ('scheduled','provisional','final')),
  source               TEXT NOT NULL,
  reconstructed_agrees BOOLEAN,
  fetched_at           TIMESTAMP NOT NULL,
  UNIQUE (league_id, season_id, gw_id, manager_a, manager_b)
);

CREATE TABLE IF NOT EXISTS standings_snapshots (
  league_id      INTEGER NOT NULL REFERENCES leagues(league_id),
  season_id      INTEGER NOT NULL,
  gw_id          INTEGER NOT NULL,
  manager_id     INTEGER NOT NULL REFERENCES managers(manager_id),
  -- rank is nullable: for a 'reconstructed' row (see source below) we do not
  -- know FPL's H2H tiebreak rule, so rank is genuinely unknown rather than
  -- invented. prev_rank/rank_change follow the same logic (added 2026-09-12).
  rank           INTEGER,
  prev_rank      INTEGER,
  rank_change    INTEGER,
  wins           INTEGER NOT NULL,
  draws          INTEGER NOT NULL,
  losses         INTEGER NOT NULL,
  league_points  INTEGER NOT NULL,
  points_for     INTEGER NOT NULL,
  points_against INTEGER NOT NULL,
  streak         TEXT,
  -- 'fpl_h2h_endpoint' = fetched live, rank is FPL's own reported value.
  -- 'reconstructed' = computed by us from raw_h2h_matches/raw_manager_gw
  -- because the live standings endpoint only ever exposes current state and
  -- this gameweek had already passed by the time this system existed.
  -- W/D/L/points fields are exact either way; only rank differs in provenance.
  source         TEXT NOT NULL DEFAULT 'fpl_h2h_endpoint' CHECK (source IN ('fpl_h2h_endpoint','reconstructed')),
  created_at     TIMESTAMP NOT NULL,
  PRIMARY KEY (league_id, season_id, gw_id, manager_id)
);

-- --- Derived ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS derived_manager_gw (
  season_id              INTEGER NOT NULL,
  gw_id                  INTEGER NOT NULL,
  manager_id             INTEGER NOT NULL REFERENCES managers(manager_id),
  score_rank             INTEGER NOT NULL,
  score_percentile       REAL NOT NULL,
  allplay_w              INTEGER NOT NULL,
  allplay_d              INTEGER NOT NULL,
  allplay_l              INTEGER NOT NULL,
  beat_median            BOOLEAN NOT NULL,
  captain_points         INTEGER,
  optimal_captain_points INTEGER,
  captain_efficiency     REAL,
  bench_points           INTEGER,
  xi_points              INTEGER,
  optimal_xi_points      INTEGER,
  xi_efficiency          REAL,
  expected_h2h_pts       REAL,
  calc_version           TEXT NOT NULL,
  calculated_at          TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, gw_id, manager_id)
);

CREATE TABLE IF NOT EXISTS derived_manager_season (
  season_id                 INTEGER NOT NULL,
  manager_id                INTEGER NOT NULL REFERENCES managers(manager_id),
  through_gw                INTEGER NOT NULL,
  gws_played                INTEGER NOT NULL,
  points_for                INTEGER,
  points_against            INTEGER,
  avg_pf                    REAL,
  avg_pa                    REAL,
  median_score              REAL,
  stdev_score               REAL,
  actual_w INTEGER, actual_d INTEGER, actual_l INTEGER,
  actual_league_pts         INTEGER,
  allplay_w INTEGER, allplay_d INTEGER, allplay_l INTEGER,
  allplay_pct               REAL,
  expected_wins             REAL,
  expected_league_pts       REAL,
  luck_index                REAL,
  sos_played                REAL,
  sos_remaining             REAL,
  form_3gw                  REAL,
  form_5gw                  REAL,
  close_w INTEGER, close_l INTEGER,
  blowout_w INTEGER, blowout_l INTEGER,
  total_bench_points        INTEGER,
  season_captain_efficiency REAL,
  season_xi_efficiency      REAL,
  total_hit_cost            INTEGER,
  transfer_roi              REAL,
  is_provisional            BOOLEAN NOT NULL,
  calc_version              TEXT NOT NULL,
  calculated_at             TIMESTAMP NOT NULL,
  PRIMARY KEY (season_id, manager_id, through_gw)
);

-- --- Operations ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingest_runs (
  run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at    TIMESTAMP NOT NULL,
  finished_at   TIMESTAMP,
  job_name      TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('success','partial','failed')),
  requests_made INTEGER,
  rows_written  INTEGER,
  error_text    TEXT
);

CREATE TABLE IF NOT EXISTS data_issues (
  issue_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  detected_at TIMESTAMP NOT NULL,
  severity    TEXT NOT NULL CHECK (severity IN ('info','warning','error')),
  category    TEXT NOT NULL,
  season_id   INTEGER,
  gw_id       INTEGER,
  manager_id  INTEGER,
  description TEXT NOT NULL,
  resolved    BOOLEAN NOT NULL DEFAULT 0
);

-- Insurance: every response archived compressed, so parsing can be redone
-- offline after a bug is found, without re-requesting anything.
CREATE TABLE IF NOT EXISTS raw_payloads (
  payload_id INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint   TEXT NOT NULL,
  params     TEXT,
  fetched_at TIMESTAMP NOT NULL,
  gw_id      INTEGER,
  body_gzip  BLOB NOT NULL
);

-- --- Indexes ---------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_picks_manager_gw
  ON raw_manager_gw_picks (manager_id, gw_id);
CREATE INDEX IF NOT EXISTS idx_picks_player
  ON raw_manager_gw_picks (season_id, gw_id, player_id);
CREATE INDEX IF NOT EXISTS idx_h2h_gw
  ON raw_h2h_matches (season_id, gw_id);
CREATE INDEX IF NOT EXISTS idx_h2h_manager_a
  ON raw_h2h_matches (manager_a);
CREATE INDEX IF NOT EXISTS idx_h2h_manager_b
  ON raw_h2h_matches (manager_b);
CREATE INDEX IF NOT EXISTS idx_standings_gw
  ON standings_snapshots (season_id, gw_id, rank);
CREATE INDEX IF NOT EXISTS idx_transfers_manager
  ON raw_transfers (manager_id, gw_id);
