"""Shared ingestion logic used by both Phase 3 (src/backfill.py, always
processes every data-checked gameweek) and Phase 4 (src/daily_sync.py, skips
per-manager fetches for gameweeks already fully stored).

Every write here is an upsert on a natural key. Rows already written with
is_final = 1 are never UPDATEd on a rerun (CLAUDE.md rule 5) — the ON CONFLICT
clauses on those tables are DO NOTHING, not DO UPDATE.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from . import config
from .fpl_client import FPLClient


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def archive(conn: sqlite3.Connection, endpoint: str, params: Optional[str],
            gw_id: Optional[int], body: Any) -> None:
    blob = gzip.compress(json.dumps(body).encode("utf-8"))
    conn.execute(
        "INSERT INTO raw_payloads (endpoint, params, fetched_at, gw_id, body_gzip) "
        "VALUES (?, ?, ?, ?, ?)",
        (endpoint, params, now(), gw_id, blob),
    )


def log_issue(conn: sqlite3.Connection, severity: str, category: str,
              description: str, gw_id: Optional[int] = None,
              manager_id: Optional[int] = None) -> None:
    conn.execute(
        """
        INSERT INTO data_issues (detected_at, severity, category, season_id, gw_id, manager_id, description)
        VALUES (?, ?, ?, 1, ?, ?, ?)
        """,
        (now(), severity, category, gw_id, manager_id, description),
    )
    print(f"  !! [{severity}] {description}")


# --- reference data ----------------------------------------------------------

def load_reference_data(conn: sqlite3.Connection, client: FPLClient) -> dict:
    print("Reference data (bootstrap-static)")
    res = client.get("bootstrap-static/")
    if not res.ok:
        raise RuntimeError(f"bootstrap-static failed: {res.summary()}")
    b = res.json_body
    archive(conn, "bootstrap-static/", None, None, b)

    pos_by_id = {et["id"]: et["singular_name_short"] for et in b.get("element_types", [])}

    for club in b.get("teams", []):
        conn.execute(
            """
            INSERT INTO pl_clubs (season_id, club_id, name, short_name) VALUES (1, ?, ?, ?)
            ON CONFLICT (season_id, club_id) DO UPDATE SET name = excluded.name, short_name = excluded.short_name
            """,
            (club["id"], club["name"], club["short_name"]),
        )

    for el in b.get("elements", []):
        conn.execute(
            """
            INSERT INTO players (season_id, player_id, first_name, last_name, web_name, position, club_id)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (season_id, player_id) DO UPDATE SET
                first_name = excluded.first_name, last_name = excluded.last_name,
                web_name = excluded.web_name, position = excluded.position, club_id = excluded.club_id
            """,
            (el["id"], el.get("first_name"), el.get("second_name"), el["web_name"],
             pos_by_id[el["element_type"]], el["team"]),
        )
        conn.execute(
            """
            INSERT INTO raw_player_snapshots
                (season_id, player_id, snapshot_date, price_tenths, status, news,
                 chance_next_rd, selected_by, form, total_points, fetched_at)
            VALUES (1, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (season_id, player_id, snapshot_date) DO UPDATE SET
                price_tenths = excluded.price_tenths, status = excluded.status, news = excluded.news,
                chance_next_rd = excluded.chance_next_rd, selected_by = excluded.selected_by,
                form = excluded.form, total_points = excluded.total_points, fetched_at = excluded.fetched_at
            """,
            (el["id"], el["now_cost"], el.get("status"), el.get("news"),
             el.get("chance_of_playing_next_round"),
             float(el["selected_by_percent"]) if el.get("selected_by_percent") is not None else None,
             float(el["form"]) if el.get("form") is not None else None,
             el.get("total_points"), now()),
        )

    events = b.get("events", [])
    for ev in events:
        conn.execute(
            """
            INSERT INTO gameweeks (season_id, gw_id, deadline_utc, is_finished, is_data_checked, avg_score, highest_score)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (season_id, gw_id) DO UPDATE SET
                deadline_utc = excluded.deadline_utc, is_finished = excluded.is_finished,
                is_data_checked = excluded.is_data_checked, avg_score = excluded.avg_score,
                highest_score = excluded.highest_score
            """,
            (ev["id"], ev["deadline_time"], int(bool(ev.get("finished"))),
             int(bool(ev.get("data_checked"))), ev.get("average_entry_score"), ev.get("highest_score")),
        )
    conn.commit()

    data_checked = sorted(e["id"] for e in events if e.get("data_checked"))
    current = next((e["id"] for e in events if e.get("is_current")), None)
    next_gw = next((e["id"] for e in events if e.get("is_next")), None)
    print(f"  {len(b.get('elements', []))} players, {len(b.get('teams', []))} clubs, "
          f"{len(events)} gameweeks. Data-checked: {data_checked}. Current: {current}, next: {next_gw}.")
    return {"data_checked_gws": data_checked, "current_gw": current, "next_gw": next_gw}


# --- per-gameweek player stats ------------------------------------------------

STAT_COLS = [
    "minutes", "goals_scored", "assists", "clean_sheets", "goals_conceded",
    "own_goals", "penalties_saved", "penalties_missed", "saves", "yellow_cards",
    "red_cards", "bonus", "bps", "defensive_contribution", "expected_goals",
    "expected_assists", "expected_goal_involvements", "expected_goals_conceded",
    "influence", "creativity", "threat", "ict_index",
    "clearances_blocks_interceptions", "recoveries", "tackles", "starts",
    "in_dreamteam", "played",
]

COL_RENAME = {"goals_scored": "goals", "penalties_saved": "pens_saved",
              "penalties_missed": "pens_missed"}


def load_player_gw_stats(conn: sqlite3.Connection, client: FPLClient, gw: int) -> dict[int, int]:
    """Returns {player_id: total_points} for this gameweek, for use in pick scoring."""
    res = client.get(f"event/{gw}/live/")
    if not res.ok:
        raise RuntimeError(f"event/{gw}/live/ failed: {res.summary()}")
    body = res.json_body
    archive(conn, f"event/{gw}/live/", None, gw, body)

    points_by_player: dict[int, int] = {}
    db_cols = [COL_RENAME.get(c, c) for c in STAT_COLS]
    col_list = ", ".join(db_cols)
    placeholders = ", ".join("?" for _ in db_cols)

    for el in body.get("elements", []):
        pid = el["id"]
        stats = el.get("stats", {})
        points_by_player[pid] = stats.get("total_points", 0)
        values = [stats.get(c) for c in STAT_COLS]
        conn.execute(
            f"""
            INSERT INTO raw_player_gw_stats
                (season_id, gw_id, player_id, {col_list}, total_points, is_final, source, fetched_at)
            VALUES (1, ?, ?, {placeholders}, ?, 1, 'event_live', ?)
            ON CONFLICT (season_id, gw_id, player_id) DO NOTHING
            """,
            (gw, pid, *values, stats.get("total_points", 0), now()),
        )
    conn.commit()
    print(f"  GW{gw}: {len(body.get('elements', []))} player-stat rows")
    return points_by_player


# --- per-manager picks / gw summary / transfers -------------------------------

def load_manager_gw(conn: sqlite3.Connection, client: FPLClient, gw: int,
                     manager_id: int, entry_id: int,
                     player_points: dict[int, int]) -> Optional[int]:
    """Returns net_points stored, or None on failure. Also inserts picks/autosubs."""
    res = client.get(f"entry/{entry_id}/event/{gw}/picks/")
    if not res.ok:
        log_issue(conn, "error", "picks_fetch",
                   f"entry/{entry_id}/event/{gw}/picks/ failed: {res.summary()}", gw, manager_id)
        return None
    body = res.json_body
    archive(conn, f"entry/{{id}}/event/{{gw}}/picks/", f"entry={entry_id}", gw, body)

    eh = body.get("entry_history", {})
    picks = body.get("picks", [])
    active_chip = body.get("active_chip")
    autosubs = body.get("automatic_subs", [])

    gross_points = eh.get("points")
    hit_cost = eh.get("event_transfers_cost", 0)
    if gross_points is None:
        log_issue(conn, "error", "missing_field",
                   f"entry_history.points missing for entry {entry_id} GW{gw}", gw, manager_id)
        return None
    net_points = gross_points - hit_cost

    conn.execute(
        """
        INSERT INTO raw_manager_gw
            (season_id, gw_id, manager_id, gross_points, hit_cost, net_points, bench_points,
             transfers_made, chip_played, squad_value, bank, overall_rank, is_final, source, fetched_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'fpl_picks_endpoint', ?)
        ON CONFLICT (season_id, gw_id, manager_id) DO NOTHING
        """,
        (gw, manager_id, gross_points, hit_cost, net_points, eh.get("points_on_bench", 0),
         eh.get("event_transfers", 0), active_chip, eh.get("value"), eh.get("bank"),
         eh.get("overall_rank"), now()),
    )

    subbed_out = {a.get("element_out") for a in autosubs if a.get("element_out") is not None}
    subbed_in = {a.get("element_in") for a in autosubs if a.get("element_in") is not None}

    for pick in picks:
        pid = pick["element"]
        slot = pick["position"]
        multiplier = pick["multiplier"]
        is_starter = (slot <= 11 and pid not in subbed_out) or pid in subbed_in
        pts = player_points.get(pid, 0) * multiplier
        conn.execute(
            """
            INSERT INTO raw_manager_gw_picks
                (season_id, gw_id, manager_id, player_id, slot, is_starter, is_captain, is_vice,
                 multiplier, points_scored, is_final, fetched_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT (season_id, gw_id, manager_id, player_id) DO NOTHING
            """,
            (gw, manager_id, pid, slot, int(is_starter), int(pick["is_captain"]),
             int(pick["is_vice_captain"]), multiplier, pts, now()),
        )

    for a in autosubs:
        p_in, p_out = a.get("element_in"), a.get("element_out")
        if p_in is None or p_out is None:
            log_issue(conn, "warning", "autosub_shape",
                      f"Unexpected automatic_subs entry shape for entry {entry_id} GW{gw}: {a}", gw, manager_id)
            continue
        conn.execute(
            """
            INSERT INTO raw_autosubs (season_id, gw_id, manager_id, player_in, player_out)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT (season_id, gw_id, manager_id, player_in, player_out) DO NOTHING
            """,
            (gw, manager_id, p_in, p_out),
        )

    captain_count = sum(1 for p in picks if p["is_captain"])
    vice_count = sum(1 for p in picks if p["is_vice_captain"])
    if len(picks) != 15:
        log_issue(conn, "error", "pick_count",
                  f"entry {entry_id} GW{gw}: {len(picks)} picks, expected 15", gw, manager_id)
    if captain_count != 1:
        log_issue(conn, "error", "captain_count",
                  f"entry {entry_id} GW{gw}: {captain_count} captains, expected 1", gw, manager_id)
    if vice_count != 1:
        log_issue(conn, "error", "vice_count",
                  f"entry {entry_id} GW{gw}: {vice_count} vice-captains, expected 1", gw, manager_id)

    return net_points


def load_transfers(conn: sqlite3.Connection, client: FPLClient, manager_id: int, entry_id: int) -> None:
    res = client.get(f"entry/{entry_id}/transfers/")
    if not res.ok:
        log_issue(conn, "warning", "transfers_fetch",
                  f"entry/{entry_id}/transfers/ failed: {res.summary()}", manager_id=manager_id)
        return
    archive(conn, "entry/{id}/transfers/", f"entry={entry_id}", None, res.json_body)
    for t in res.json_body or []:
        conn.execute(
            """
            INSERT INTO raw_transfers
                (season_id, gw_id, manager_id, player_in, player_out, price_in, price_out, transfer_time, fetched_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (season_id, gw_id, manager_id, player_in, player_out) DO NOTHING
            """,
            (t["event"], manager_id, t["element_in"], t["element_out"],
             t.get("element_in_cost"), t.get("element_out_cost"), t.get("time"), now()),
        )


# --- H2H matches ---------------------------------------------------------------

def load_h2h_matches(conn: sqlite3.Connection, client: FPLClient,
                      entry_to_manager: dict[int, int], data_checked_gws: list[int]) -> None:
    print("H2H matches")
    page = 1
    all_matches = []
    while True:
        res = client.get(f"leagues-h2h-matches/league/{config.LEAGUE_ID}/?page={page}")
        if not res.ok:
            log_issue(conn, "error", "h2h_matches_fetch", f"page {page} failed: {res.summary()}")
            break
        body = res.json_body
        archive(conn, f"leagues-h2h-matches/league/{config.LEAGUE_ID}/", f"page={page}", None, body)
        all_matches.extend(body.get("results", []))
        if not body.get("has_next"):
            break
        page += 1

    written = 0
    for m in all_matches:
        gw = m.get("event")
        a_entry, b_entry = m.get("entry_1_entry"), m.get("entry_2_entry")
        if a_entry not in entry_to_manager or b_entry not in entry_to_manager:
            continue
        mgr_a, mgr_b = entry_to_manager[a_entry], entry_to_manager[b_entry]

        if gw in data_checked_gws:
            # Finalized: real scores, computed result, immutable (is_final logic
            # lives at the row level via ON CONFLICT DO NOTHING — never overwritten).
            score_a, score_b = m.get("entry_1_points"), m.get("entry_2_points")
            if score_a > score_b:
                pts_a, pts_b, winner = 3, 0, mgr_a
            elif score_a < score_b:
                pts_a, pts_b, winner = 0, 3, mgr_b
            else:
                pts_a, pts_b, winner = 1, 1, None
            is_draw, margin, status = int(score_a == score_b), abs(score_a - score_b), "final"
        else:
            # Not yet played: fixture only, no score/result to invent.
            score_a = score_b = winner = pts_a = pts_b = is_draw = margin = None
            status = "scheduled"

        conn.execute(
            """
            INSERT INTO raw_h2h_matches
                (match_id, league_id, season_id, gw_id, manager_a, manager_b, score_a, score_b,
                 winner, is_draw, margin, league_pts_a, league_pts_b, is_knockout, knockout_name,
                 seed_value, tiebreak, is_bye, status, source, fetched_at)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'fpl_h2h_endpoint', ?)
            ON CONFLICT (league_id, season_id, gw_id, manager_a, manager_b) DO UPDATE SET
                score_a = CASE WHEN raw_h2h_matches.status != 'final' THEN excluded.score_a ELSE raw_h2h_matches.score_a END,
                score_b = CASE WHEN raw_h2h_matches.status != 'final' THEN excluded.score_b ELSE raw_h2h_matches.score_b END,
                winner = CASE WHEN raw_h2h_matches.status != 'final' THEN excluded.winner ELSE raw_h2h_matches.winner END,
                is_draw = CASE WHEN raw_h2h_matches.status != 'final' THEN excluded.is_draw ELSE raw_h2h_matches.is_draw END,
                margin = CASE WHEN raw_h2h_matches.status != 'final' THEN excluded.margin ELSE raw_h2h_matches.margin END,
                league_pts_a = CASE WHEN raw_h2h_matches.status != 'final' THEN excluded.league_pts_a ELSE raw_h2h_matches.league_pts_a END,
                league_pts_b = CASE WHEN raw_h2h_matches.status != 'final' THEN excluded.league_pts_b ELSE raw_h2h_matches.league_pts_b END,
                status = CASE WHEN raw_h2h_matches.status != 'final' THEN excluded.status ELSE raw_h2h_matches.status END
            """,
            (m["id"], config.LEAGUE_ID, gw, mgr_a, mgr_b, score_a, score_b, winner,
             is_draw, margin, pts_a, pts_b,
             int(bool(m.get("is_knockout"))), m.get("knockout_name"), m.get("seed_value"),
             m.get("tiebreak"), int(bool(m.get("is_bye"))), status, now()),
        )
        written += 1
    conn.commit()
    print(f"  {written} H2H match rows considered across all scheduled+finalized GWs (upserts, may be no-ops; final rows never regress)")


def cross_check_h2h(conn: sqlite3.Connection, data_checked_gws: list[int]) -> None:
    print("Cross-check: raw_manager_gw.net_points vs raw_h2h_matches score")
    mismatches = 0
    for gw in data_checked_gws:
        rows = conn.execute(
            "SELECT match_id, manager_a, manager_b, score_a, score_b FROM raw_h2h_matches WHERE gw_id = ?",
            (gw,),
        ).fetchall()
        for match_id, mgr_a, mgr_b, score_a, score_b in rows:
            row_a = conn.execute(
                "SELECT net_points FROM raw_manager_gw WHERE gw_id = ? AND manager_id = ?", (gw, mgr_a)
            ).fetchone()
            row_b = conn.execute(
                "SELECT net_points FROM raw_manager_gw WHERE gw_id = ? AND manager_id = ?", (gw, mgr_b)
            ).fetchone()
            agrees = bool(row_a and row_a[0] == score_a and row_b and row_b[0] == score_b)
            conn.execute(
                "UPDATE raw_h2h_matches SET reconstructed_agrees = ? WHERE match_id = ?",
                (int(agrees), match_id),
            )
            if not agrees:
                mismatches += 1
                log_issue(conn, "error", "gross_net_mismatch",
                          f"GW{gw} match {match_id}: our net_points (a={row_a[0] if row_a else None}, "
                          f"b={row_b[0] if row_b else None}) vs H2H match score (a={score_a}, b={score_b}).",
                          gw)
    conn.commit()
    if mismatches == 0:
        print("  OK — net_points agrees with reported H2H scores for all managers, all gameweeks.")
    else:
        print(f"  {mismatches} MISMATCHES — see data_issues.")


# --- standings snapshot (current GW only) --------------------------------------

def load_current_standings_snapshot(conn: sqlite3.Connection, client: FPLClient,
                                     entry_to_manager: dict[int, int], latest_gw: int) -> None:
    print(f"Standings snapshot (GW{latest_gw}, current only)")
    res = client.get(f"leagues-h2h/{config.LEAGUE_ID}/standings/")
    if not res.ok:
        log_issue(conn, "error", "standings_fetch", f"failed: {res.summary()}")
        return
    body = res.json_body
    archive(conn, f"leagues-h2h/{config.LEAGUE_ID}/standings/", None, latest_gw, body)
    standings = (body.get("standings") or {}).get("results", [])

    for s in standings:
        entry_id = s["entry"]
        mgr = entry_to_manager.get(entry_id)
        if mgr is None:
            continue
        matches = conn.execute(
            """
            SELECT winner, manager_a, manager_b FROM raw_h2h_matches
            WHERE (manager_a = ? OR manager_b = ?) AND status = 'final' ORDER BY gw_id
            """,
            (mgr, mgr),
        ).fetchall()
        results = []
        for winner, a, b in matches:
            if winner is None:
                results.append("D")
            elif winner == mgr:
                results.append("W")
            else:
                results.append("L")
        streak = None
        if results:
            last = results[-1]
            n = 0
            for r in reversed(results):
                if r == last:
                    n += 1
                else:
                    break
            streak = f"{last}{n}"

        points_against = conn.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN manager_a = ? THEN score_b ELSE score_a END), 0)
            FROM raw_h2h_matches WHERE (manager_a = ? OR manager_b = ?) AND status = 'final'
            """,
            (mgr, mgr, mgr),
        ).fetchone()[0]

        conn.execute(
            """
            INSERT INTO standings_snapshots
                (league_id, season_id, gw_id, manager_id, rank, prev_rank, rank_change,
                 wins, draws, losses, league_points, points_for, points_against, streak,
                 source, created_at)
            VALUES (?, 1, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, 'fpl_h2h_endpoint', ?)
            ON CONFLICT (league_id, season_id, gw_id, manager_id) DO NOTHING
            """,
            (config.LEAGUE_ID, latest_gw, mgr, s["rank"], s["matches_won"], s["matches_drawn"],
             s["matches_lost"], s["total"], s["points_for"], points_against, streak, now()),
        )
    conn.commit()
    print(f"  {len(standings)} standings rows considered for GW{latest_gw} (upserts, may be no-ops)")


def reconstruct_gap_standings(conn: sqlite3.Connection, data_checked_gws: list[int],
                               latest_gw: int) -> list[int]:
    """For any data-checked gameweek other than the latest with no snapshot at
    all, reconstruct wins/draws/losses/league_points/points_for/points_against
    and streak from raw_h2h_matches — exact, since every match result for a
    data-checked gameweek is immutable and already stored.

    rank/prev_rank/rank_change are left NULL. FPL's H2H tiebreak rule for
    ties has never been empirically verified (see SPEC.md §13) — computing a
    rank here would mean asserting a tiebreak method we haven't confirmed.
    source='reconstructed' distinguishes these from genuinely FPL-reported
    rows (source='fpl_h2h_endpoint'), so they're never confused with each
    other downstream.
    """
    managers = conn.execute("SELECT manager_id FROM managers").fetchall()
    filled = []
    for gw in data_checked_gws:
        if gw == latest_gw:
            continue
        existing = conn.execute(
            "SELECT COUNT(*) FROM standings_snapshots WHERE gw_id = ?", (gw,)
        ).fetchone()[0]
        if existing:
            continue

        for (mgr,) in managers:
            matches = conn.execute(
                """
                SELECT winner, manager_a, manager_b, score_a, score_b, league_pts_a, league_pts_b
                FROM raw_h2h_matches
                WHERE (manager_a = ? OR manager_b = ?) AND status = 'final' AND gw_id <= ?
                ORDER BY gw_id
                """,
                (mgr, mgr, gw),
            ).fetchall()
            wins = draws = losses = league_points = points_for = points_against = 0
            results = []
            for winner, a, b, score_a, score_b, pa, pb in matches:
                league_points += pa if a == mgr else pb
                points_for += score_a if a == mgr else score_b
                points_against += score_b if a == mgr else score_a
                if winner is None:
                    draws += 1
                    results.append("D")
                elif winner == mgr:
                    wins += 1
                    results.append("W")
                else:
                    losses += 1
                    results.append("L")
            streak = None
            if results:
                last = results[-1]
                n = 0
                for r in reversed(results):
                    if r == last:
                        n += 1
                    else:
                        break
                streak = f"{last}{n}"

            conn.execute(
                """
                INSERT INTO standings_snapshots
                    (league_id, season_id, gw_id, manager_id, rank, prev_rank, rank_change,
                     wins, draws, losses, league_points, points_for, points_against, streak,
                     source, created_at)
                VALUES (?, 1, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, 'reconstructed', ?)
                ON CONFLICT (league_id, season_id, gw_id, manager_id) DO NOTHING
                """,
                (config.LEAGUE_ID, gw, mgr, wins, draws, losses, league_points,
                 points_for, points_against, streak, now()),
            )
        filled.append(gw)
    conn.commit()

    if filled:
        conn.execute(
            "UPDATE data_issues SET resolved = 1 WHERE category = 'historical_gap' "
            "AND resolved = 0 AND description LIKE '%permanently unavailable%'"
        )
        already_logged = conn.execute(
            "SELECT COUNT(*) FROM data_issues WHERE category = 'historical_gap' "
            "AND description LIKE 'W/D/L, league points%'"
        ).fetchone()[0]
        if not already_logged:
            log_issue(conn, "info", "historical_gap",
                      f"W/D/L, league points, points for/against, and streak for GW{filled} were "
                      f"reconstructed from raw match data (exact — every result is immutable and "
                      f"already stored). Rank is NOT available for these gameweeks: FPL's H2H "
                      f"tiebreak rule for ties has never been empirically verified, so computing a "
                      f"rank would mean asserting an unconfirmed method. Revisit once a future "
                      f"gameweek's real tie lets the tiebreak formula be validated against confirmed "
                      f"data (see SPEC.md §13).")
        conn.commit()
        print(f"  Reconstructed W/D/L/points/streak for GW {filled} (rank intentionally left NULL)")
    return filled


# --- validators ------------------------------------------------------------

def run_validators(conn: sqlite3.Connection, data_checked_gws: list[int]) -> list[str]:
    print("Validators")
    problems = []

    for gw in data_checked_gws:
        n = conn.execute("SELECT COUNT(*) FROM raw_manager_gw WHERE gw_id = ?", (gw,)).fetchone()[0]
        if n != config.EXPECTED_TEAM_COUNT:
            problems.append(f"GW{gw}: {n} raw_manager_gw rows, expected {config.EXPECTED_TEAM_COUNT}")

        n_picks = conn.execute(
            "SELECT manager_id, COUNT(*) FROM raw_manager_gw_picks WHERE gw_id = ? GROUP BY manager_id", (gw,)
        ).fetchall()
        for mgr, cnt in n_picks:
            if cnt != 15:
                problems.append(f"GW{gw} manager {mgr}: {cnt} picks, expected 15")

        bad_net = conn.execute(
            "SELECT manager_id FROM raw_manager_gw WHERE gw_id = ? AND net_points != gross_points - hit_cost",
            (gw,),
        ).fetchall()
        if bad_net:
            problems.append(f"GW{gw}: {len(bad_net)} rows fail net = gross - hits")

    for p in problems:
        print(f"  FAIL: {p}")
    if not problems:
        print("  All validators passed.")
    return problems


def log_run(conn: sqlite3.Connection, job_name: str, status: str,
            requests_made: int, rows_written: int = 0, error_text: Optional[str] = None) -> None:
    conn.execute(
        """
        INSERT INTO ingest_runs (started_at, finished_at, job_name, status, requests_made, rows_written, error_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (now(), now(), job_name, status, requests_made, rows_written, error_text),
    )
    conn.commit()
