# Phase 1 — FPL API Verification Report

- Run at: `2026-09-12T00:18:36.038709+00:00`
- League: `683383`
- Requests made: 17

## Warnings

- Membership differs from config: 1 expected team(s) not found, 1 unrecognised team(s) present. Team names may simply have been changed — review before Phase 2.

## Endpoint results

| Endpoint | Status | Time | Result |
|---|---|---|---|
| `bootstrap-static/` | OK 200 | 3150ms | HTTP 200 in 3150ms |
| `fixtures/` | OK 200 | 3041ms | HTTP 200 in 3041ms |
| `leagues-h2h/683383/standings/` | OK 200 | 778ms | HTTP 200 in 778ms |
| `leagues-h2h-matches/league/683383/?page=1` | OK 200 | 702ms | HTTP 200 in 702ms |
| `event/3/live/` | OK 200 | 699ms | HTTP 200 in 699ms |
| `entry/3023365/` | OK 200 | 828ms | HTTP 200 in 828ms |
| `entry/3023365/history/` | OK 200 | 1025ms | HTTP 200 in 1025ms |
| `entry/3023365/event/3/picks/` | OK 200 | 787ms | HTTP 200 in 787ms |
| `entry/3023365/transfers/` | OK 200 | 915ms | HTTP 200 in 915ms |
| `entry/2235025/event/4/picks/` | FAIL 404 | 802ms | HTTP 404 — not found |
| `element-summary/1/` | OK 200 | 666ms | HTTP 200 in 666ms |

## The blocking unknowns

### 1. Knockout configuration

Found field `ko_rounds` = `3`.

The league HAS knockout rounds. Projections become playoff odds.

### 2. Fixture structure (18 managers, 38 gameweeks)

- Gameweeks covered: 1-35
- Distinct pairings: 153
- Times each pairing occurs: `{2: 144, 3: 9}`
- Fixtures per manager: `{35: 18}`
- Knockout-flagged gameweeks: []

### 3. Pre-deadline visibility of other managers' picks

- Probed: Rock ‘n’ Iraola (entry 2235025), GW4
- HTTP status: 404
- Visible: **False**
- Not visible, as expected. Post-deadline capture only, which is what the design already assumes.

### 4. Finalization flag

- `data_checked` field present: **True**
- Finished gameweeks: `[1, 2, 3]`
- Data-checked gameweeks: `[1, 2, 3]`
- Flags disagree on: `[]`
- Current GW: 3 — Next GW: 4

Available event fields:

```
id, name, deadline_time, release_time, average_entry_score, finished, data_checked, highest_scoring_entry, deadline_time_epoch, deadline_time_game_offset, highest_score, is_previous, is_current, is_next, cup_leagues_created, h2h_ko_matches_created, can_enter, can_manage, released, ranked_count, overrides, chip_plays, most_selected, most_transferred_in, top_element, top_element_info, transfers_made, most_captained, most_vice_captained
```

### 5. Pagination

- Mechanism: ?page=N with has_next boolean
- Page size: 50
- Pages pulled: 7
- Total matches seen: 315

## Membership cross-check

- Matched teams: 17
- Manager-name mismatches: 0
- Expected but missing: 1
- Present but unexpected: 1
  - MISSING: `Rock 'n Iraola` (Andrew Romani)
  - NEW: `Rock ‘n’ Iraola` (Andrew Romani) entry 2235025

## Observed field names

### `bootstrap-static/`

**top_level_keys**

```
[
  "chips",
  "events",
  "game_settings",
  "game_config",
  "phases",
  "teams",
  "total_players",
  "element_stats",
  "element_types",
  "elements"
]
```

**element_field_check**

```
{
  "id": "present in all 200",
  "first_name": "present in all 200",
  "second_name": "present in all 200",
  "web_name": "present in all 200",
  "element_type": "present in all 200",
  "team": "present in all 200",
  "now_cost": "present in all 200",
  "status": "present in all 200",
  "news": "present in all 200",
  "chance_of_playing_next_round": "present, 77/200 non-null",
  "selected_by_percent": "present in all 200",
  "form": "present in all 200",
  "total_points": "present in all 200",
  "expected_goals": "present in all 200",
  "expected_assists": "present in all 200",
  "defensive_contribution": "present in all 200"
}
```

### `leagues-h2h/683383/standings/`

**league_object_keys**

```
[
  "id",
  "name",
  "created",
  "closed",
  "max_entries",
  "league_type",
  "scoring",
  "admin_entry",
  "start_event",
  "code_privacy",
  "has_cup",
  "cup_league",
  "ko_rounds"
]
```

**standings_keys**

```
[
  "id",
  "division",
  "entry",
  "player_name",
  "rank",
  "last_rank",
  "rank_sort",
  "total",
  "entry_name",
  "matches_played",
  "matches_won",
  "matches_drawn",
  "matches_lost",
  "points_for"
]
```

### `leagues-h2h-matches/league/683383/?page=1`

**top_level_keys**

```
[
  "has_next",
  "page",
  "results"
]
```

**match_keys**

```
[
  "id",
  "entry_1_entry",
  "entry_1_name",
  "entry_1_player_name",
  "entry_1_points",
  "entry_1_win",
  "entry_1_draw",
  "entry_1_loss",
  "entry_1_total",
  "entry_2_entry",
  "entry_2_name",
  "entry_2_player_name",
  "entry_2_points",
  "entry_2_win",
  "entry_2_draw",
  "entry_2_loss",
  "entry_2_total",
  "is_knockout",
  "league",
  "winner",
  "seed_value",
  "event",
  "tiebreak",
  "is_bye",
  "knockout_name"
]
```

### `event/3/live/`

**element_keys**

```
[
  "id",
  "stats",
  "explain",
  "modified"
]
```

**stats_keys**

```
[
  "minutes",
  "goals_scored",
  "assists",
  "clean_sheets",
  "goals_conceded",
  "own_goals",
  "penalties_saved",
  "penalties_missed",
  "yellow_cards",
  "red_cards",
  "saves",
  "bonus",
  "bps",
  "influence",
  "creativity",
  "threat",
  "ict_index",
  "clearances_blocks_interceptions",
  "recoveries",
  "tackles",
  "defensive_contribution",
  "starts",
  "expected_goals",
  "expected_assists",
  "expected_goal_involvements",
  "expected_goals_conceded",
  "total_points",
  "in_dreamteam",
  "played"
]
```

**stats_field_check**

```
{
  "minutes": "present in all 200",
  "goals_scored": "present in all 200",
  "assists": "present in all 200",
  "clean_sheets": "present in all 200",
  "goals_conceded": "present in all 200",
  "own_goals": "present in all 200",
  "penalties_saved": "present in all 200",
  "penalties_missed": "present in all 200",
  "saves": "present in all 200",
  "yellow_cards": "present in all 200",
  "red_cards": "present in all 200",
  "bonus": "present in all 200",
  "bps": "present in all 200",
  "total_points": "present in all 200",
  "expected_goals": "present in all 200",
  "expected_assists": "present in all 200",
  "defensive_contribution": "present in all 200"
}
```

### `entry/3023365/history/`

**top_level_keys**

```
[
  "current",
  "past",
  "chips"
]
```

**current_keys**

```
[
  "event",
  "points",
  "total_points",
  "rank",
  "rank_sort",
  "overall_rank",
  "percentile_rank",
  "overall_rank_percentage",
  "bank",
  "value",
  "event_transfers",
  "event_transfers_cost",
  "points_on_bench"
]
```

**history_field_check**

```
{
  "event": "present in all 3",
  "points": "present in all 3",
  "total_points": "present in all 3",
  "event_transfers": "present in all 3",
  "event_transfers_cost": "present in all 3",
  "points_on_bench": "present in all 3",
  "value": "present in all 3",
  "bank": "present in all 3",
  "overall_rank": "present in all 3",
  "rank": "present in all 3"
}
```

### `entry/3023365/event/3/picks/`

**top_level_keys**

```
[
  "active_chip",
  "automatic_subs",
  "entry_history",
  "picks"
]
```

**pick_keys**

```
[
  "element",
  "position",
  "multiplier",
  "is_captain",
  "is_vice_captain",
  "element_type"
]
```

**entry_history_keys**

```
[
  "event",
  "points",
  "total_points",
  "rank",
  "rank_sort",
  "overall_rank",
  "percentile_rank",
  "overall_rank_percentage",
  "bank",
  "value",
  "event_transfers",
  "event_transfers_cost",
  "points_on_bench"
]
```

### `entry/3023365/transfers/`

**transfer_keys**

```
[
  "element_in",
  "element_in_cost",
  "element_out",
  "element_out_cost",
  "entry",
  "event",
  "time"
]
```

## Full league object

```json
{
  "id": 683383,
  "name": "Almost all Americans",
  "created": "2026-08-08T01:24:49.531640Z",
  "closed": true,
  "max_entries": null,
  "league_type": "x",
  "scoring": "h",
  "admin_entry": 3311925,
  "start_event": 1,
  "code_privacy": "p",
  "has_cup": false,
  "cup_league": null,
  "ko_rounds": 3
}
```

---

Paste this report back into Claude. The spec's data-source section gets
rewritten to match these observations before Phase 2 creates any table.