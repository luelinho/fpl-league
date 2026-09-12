"""Phase 2 — create the database, resolve the league to real entry IDs.

Scope, per SPEC.md §11 Phase 2 exit criteria: create every table from
db/schema.sql, record the league's own configuration, and resolve all 18
managers to their FPL entry IDs from live standings — nothing more. Historical
backfill (players, picks, gameweek stats, matches) is Phase 3.

Every write here is an upsert on a natural key (entry_id / league_id), so
running this twice produces identical state.

Usage:
    python -m src.build_db
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone

from . import config
from .fpl_client import FPLClient


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    schema_path = config.REPO_ROOT / "db" / "schema.sql"
    conn.executescript(schema_path.read_text())
    conn.commit()


def upsert_season(conn: sqlite3.Connection) -> int:
    season_id = 1
    conn.execute(
        """
        INSERT INTO seasons (season_id, name, status)
        VALUES (?, ?, 'active')
        ON CONFLICT (season_id) DO UPDATE SET
            name = excluded.name,
            status = excluded.status
        """,
        (season_id, config.SEASON_NAME),
    )
    return season_id


def upsert_league(conn: sqlite3.Connection, season_id: int, league_obj: dict) -> None:
    conn.execute(
        """
        INSERT INTO leagues
            (league_id, season_id, name, league_type, scoring, start_event,
             ko_rounds, admin_entry_id, config_json, last_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (league_id) DO UPDATE SET
            season_id = excluded.season_id,
            name = excluded.name,
            league_type = excluded.league_type,
            scoring = excluded.scoring,
            start_event = excluded.start_event,
            ko_rounds = excluded.ko_rounds,
            admin_entry_id = excluded.admin_entry_id,
            config_json = excluded.config_json,
            last_verified = excluded.last_verified
        """,
        (
            config.LEAGUE_ID,
            season_id,
            league_obj.get("name"),
            league_obj.get("league_type"),
            league_obj.get("scoring"),
            league_obj.get("start_event"),
            league_obj.get("ko_rounds"),
            league_obj.get("admin_entry"),
            json.dumps(league_obj),
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def upsert_manager(conn: sqlite3.Connection, entry_id: int, first: str, last: str,
                    is_owner: bool) -> int:
    display_name = f"{first} {last}".strip()
    conn.execute(
        """
        INSERT INTO managers (entry_id, player_first, player_last, display_name, is_owner)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (entry_id) DO UPDATE SET
            player_first = excluded.player_first,
            player_last = excluded.player_last,
            display_name = excluded.display_name,
            is_owner = excluded.is_owner
        """,
        (entry_id, first, last, display_name, int(is_owner)),
    )
    row = conn.execute(
        "SELECT manager_id FROM managers WHERE entry_id = ?", (entry_id,)
    ).fetchone()
    return row[0]


def upsert_team_name(conn: sqlite3.Connection, manager_id: int, season_id: int,
                      team_name: str, today: str) -> None:
    existing = conn.execute(
        """
        SELECT last_seen FROM team_names
        WHERE manager_id = ? AND season_id = ? AND team_name = ?
        """,
        (manager_id, season_id, team_name),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE team_names SET last_seen = ?
            WHERE manager_id = ? AND season_id = ? AND team_name = ?
            """,
            (today, manager_id, season_id, team_name),
        )
    else:
        conn.execute(
            """
            INSERT INTO team_names (manager_id, season_id, team_name, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            """,
            (manager_id, season_id, team_name, today, today),
        )


def upsert_membership(conn: sqlite3.Connection, season_id: int, manager_id: int,
                       joined_event: int) -> None:
    conn.execute(
        """
        INSERT INTO league_memberships (league_id, season_id, manager_id, joined_event, is_active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT (league_id, season_id, manager_id) DO UPDATE SET
            joined_event = excluded.joined_event,
            is_active = 1
        """,
        (config.LEAGUE_ID, season_id, manager_id, joined_event),
    )


def log_data_issue(conn: sqlite3.Connection, severity: str, category: str,
                    description: str) -> None:
    conn.execute(
        """
        INSERT INTO data_issues (detected_at, severity, category, season_id, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        (datetime.now(timezone.utc).isoformat(), severity, category, 1, description),
    )


def cross_check_membership(live_teams: dict[str, int]) -> list[str]:
    """Compare live team names against config.EXPECTED_MEMBERS. Returns issue strings."""
    expected = {name.strip(): mgr for name, mgr in config.EXPECTED_MEMBERS}
    issues = []
    for team in expected:
        if team not in live_teams:
            issues.append(f"Expected team '{team}' not found in live standings.")
    for team in live_teams:
        if team not in expected:
            issues.append(f"Live team '{team}' (entry {live_teams[team]}) not in EXPECTED_MEMBERS.")
    return issues


def run() -> int:
    print("Phase 2 — schema + league reconstruction")
    print(f"Database: {config.DB_PATH}\n")

    conn = connect()
    apply_schema(conn)
    print("Schema applied.")

    client = FPLClient(verbose=True)

    res = client.get(f"leagues-h2h/{config.LEAGUE_ID}/standings/")
    if not res.ok:
        print(f"FAILED to fetch H2H standings: {res.summary()}")
        conn.close()
        return 1

    body = res.json_body
    league_obj = body.get("league") or {}
    standings = (body.get("standings") or {}).get("results") or []

    if len(standings) != config.EXPECTED_TEAM_COUNT:
        print(f"WARNING: {len(standings)} entries in standings, expected {config.EXPECTED_TEAM_COUNT}.")

    season_id = upsert_season(conn)
    upsert_league(conn, season_id, league_obj)
    print(f"League recorded: {league_obj.get('name')} (ko_rounds={league_obj.get('ko_rounds')})")

    today = datetime.now(timezone.utc).date().isoformat()
    live_teams: dict[str, int] = {}

    print(f"\nResolving {len(standings)} managers to entry IDs...")
    for entry in standings:
        entry_id = entry.get("entry")
        entry_name = (entry.get("entry_name") or "").strip()

        detail = client.get(f"entry/{entry_id}/")
        if not detail.ok:
            log_data_issue(
                conn, "error", "manager_resolution",
                f"Could not fetch entry/{entry_id}/ for team '{entry_name}': {detail.summary()}",
            )
            print(f"  [FAIL] entry {entry_id} ({entry_name}) — {detail.summary()}")
            continue

        d = detail.json_body or {}
        first = d.get("player_first_name") or ""
        last = d.get("player_last_name") or ""
        team_name = d.get("name") or entry_name
        is_owner = team_name.strip() == config.OWNER_TEAM_NAME

        manager_id = upsert_manager(conn, entry_id, first, last, is_owner)
        upsert_team_name(conn, manager_id, season_id, team_name, today)
        upsert_membership(conn, season_id, manager_id, league_obj.get("start_event") or 1)

        live_teams[team_name] = entry_id
        owner_tag = "  <- OWNER" if is_owner else ""
        print(f"  [OK  ] entry {entry_id}: {team_name} ({first} {last}){owner_tag}")

    conn.commit()

    issues = cross_check_membership(live_teams)
    for issue in issues:
        log_data_issue(conn, "warning", "membership_mismatch", issue)
        print(f"  !! {issue}")
    conn.commit()

    conn.execute(
        """
        INSERT INTO ingest_runs (started_at, finished_at, job_name, status, requests_made, rows_written)
        VALUES (?, ?, 'phase2_build_db', ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            "success" if not issues else "partial",
            client.request_count,
            len(standings),
        ),
    )
    conn.commit()

    manager_count = conn.execute("SELECT COUNT(*) FROM managers").fetchone()[0]
    owner_count = conn.execute("SELECT COUNT(*) FROM managers WHERE is_owner = 1").fetchone()[0]
    print(f"\n{manager_count} managers stored. is_owner=1 count: {owner_count}.")
    if manager_count != config.EXPECTED_TEAM_COUNT:
        print(f"WARNING: expected {config.EXPECTED_TEAM_COUNT} managers, stored {manager_count}.")
    if owner_count != 1:
        print(f"WARNING: expected exactly 1 owner, found {owner_count}.")

    conn.close()
    print("\nPhase 2 complete." if not issues else "\nPhase 2 complete, with issues logged to data_issues.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
