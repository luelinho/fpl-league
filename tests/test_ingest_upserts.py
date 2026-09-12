"""Regression tests for the "upsert until final" guarantee added when
provisional-gameweek capture was built (see SPEC.md, Phase 4 update).

CLAUDE.md rule 5: rows with is_final=1 are immutable. src.ingest enforces
this in the SQL itself via `ON CONFLICT ... DO UPDATE ... WHERE <table>.
is_final = 0`, not just in application logic — these tests exist so a future
change to that WHERE clause (or a reversion to plain ON CONFLICT DO NOTHING,
which would silently stop provisional rows from ever being finalized) fails
loudly instead of only being caught by luck during a live gameweek.

Uses a temporary, in-memory database built from the real db/schema.sql and
a fake FPL client double - never touches db/league.sqlite.
"""

import sqlite3
from pathlib import Path

import pytest

from src import ingest
from src.fpl_client import FetchResult

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


class FakeClient:
    """Minimal stand-in for FPLClient: returns canned responses, never hits the network."""

    def __init__(self, responses: dict):
        self.responses = responses

    def get(self, path: str, archive: bool = True) -> FetchResult:
        if path not in self.responses:
            return FetchResult(url=path, ok=False, error=f"no fake response registered for {path}")
        return FetchResult(url=path, ok=True, status_code=200, json_body=self.responses[path])


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(SCHEMA_PATH.read_text())
    c.execute(
        "INSERT INTO managers (manager_id, entry_id, display_name, is_owner) VALUES (1, 12345, 'Test Manager', 1)"
    )
    c.commit()
    yield c
    c.close()


def full_stats(total_points: int) -> dict:
    """A complete event/{gw}/live/ stats block - every NOT NULL column covered,
    so tests exercise the same shape as a real response rather than skipping
    fields the real ingest code would never see missing."""
    return {
        "minutes": 90, "goals_scored": 0, "assists": 0, "clean_sheets": 0,
        "goals_conceded": 1, "own_goals": 0, "penalties_saved": 0, "penalties_missed": 0,
        "saves": 0, "yellow_cards": 0, "red_cards": 0, "bonus": 0, "bps": 20,
        "defensive_contribution": 0, "expected_goals": 0.1, "expected_assists": 0.0,
        "expected_goal_involvements": 0.1, "expected_goals_conceded": 1.2,
        "influence": 10.0, "creativity": 5.0, "threat": 3.0, "ict_index": 1.8,
        "clearances_blocks_interceptions": 2, "recoveries": 3, "tackles": 1, "starts": 1,
        "in_dreamteam": False, "played": True, "total_points": total_points,
    }


def test_player_gw_stats_provisional_row_can_be_updated(conn):
    client = FakeClient({"event/1/live/": {"elements": [{"id": 100, "stats": full_stats(2)}]}})
    ingest.load_player_gw_stats(conn, client, 1, is_final=False)

    row = conn.execute(
        "SELECT total_points, is_final FROM raw_player_gw_stats WHERE gw_id=1 AND player_id=100"
    ).fetchone()
    assert row == (2, 0)

    # Re-run with different (still provisional) data - a live score changing
    # as a match is played. The row must update, not be left stale.
    client2 = FakeClient({"event/1/live/": {"elements": [{"id": 100, "stats": full_stats(7)}]}})
    ingest.load_player_gw_stats(conn, client2, 1, is_final=False)

    row = conn.execute(
        "SELECT total_points, is_final FROM raw_player_gw_stats WHERE gw_id=1 AND player_id=100"
    ).fetchone()
    assert row == (7, 0)


def test_player_gw_stats_final_row_is_immutable(conn):
    client = FakeClient({"event/1/live/": {"elements": [{"id": 100, "stats": full_stats(7)}]}})
    ingest.load_player_gw_stats(conn, client, 1, is_final=False)

    # Gameweek gets data-checked: finalize with the settled score.
    client_final = FakeClient({"event/1/live/": {"elements": [{"id": 100, "stats": full_stats(9)}]}})
    ingest.load_player_gw_stats(conn, client_final, 1, is_final=True)

    row = conn.execute(
        "SELECT total_points, is_final FROM raw_player_gw_stats WHERE gw_id=1 AND player_id=100"
    ).fetchone()
    assert row == (9, 1)

    # Any later call - even claiming to also be final, even with different
    # numbers - must never change a row once is_final=1.
    client_bad = FakeClient({"event/1/live/": {"elements": [{"id": 100, "stats": full_stats(999)}]}})
    ingest.load_player_gw_stats(conn, client_bad, 1, is_final=True)

    row = conn.execute(
        "SELECT total_points, is_final FROM raw_player_gw_stats WHERE gw_id=1 AND player_id=100"
    ).fetchone()
    assert row == (9, 1)


def picks_response(points: int, transfers_cost: int = 0) -> dict:
    return {
        "active_chip": None,
        "automatic_subs": [],
        "entry_history": {
            "points": points, "event_transfers_cost": transfers_cost,
            "points_on_bench": 4, "event_transfers": 0, "value": 1000, "bank": 0,
            "overall_rank": 1000000,
        },
        "picks": [
            {"element": i, "position": i, "multiplier": 1 if i <= 11 else 0,
             "is_captain": i == 1, "is_vice_captain": i == 2}
            for i in range(1, 16)
        ],
    }


def test_manager_gw_provisional_row_can_be_updated(conn):
    """A provisional row's gross_points is computed from the live per-player
    points already joined into each pick (11 starters × multiplier 1, per
    picks_response), not from entry_history.points — that FPL field has been
    observed to lag behind event/{gw}/live/ during live play (2026-09-12,
    real GW4), so it's deliberately ignored while is_final=False. eh.points
    is set to a nonsense 999 here specifically to prove it's ignored.
    """
    live_points_1 = {i: 2 for i in range(1, 12)}
    client = FakeClient({"entry/12345/event/1/picks/": picks_response(999)})
    ingest.load_manager_gw(conn, client, 1, manager_id=1, entry_id=12345, player_points=live_points_1, is_final=False)

    row = conn.execute("SELECT gross_points, is_final FROM raw_manager_gw WHERE gw_id=1 AND manager_id=1").fetchone()
    assert row == (22, 0)

    live_points_2 = {i: 5 for i in range(1, 12)}
    client2 = FakeClient({"entry/12345/event/1/picks/": picks_response(999)})
    ingest.load_manager_gw(conn, client2, 1, manager_id=1, entry_id=12345, player_points=live_points_2, is_final=False)

    row = conn.execute("SELECT gross_points, is_final FROM raw_manager_gw WHERE gw_id=1 AND manager_id=1").fetchone()
    assert row == (55, 0)


def test_manager_gw_final_row_is_immutable(conn):
    client = FakeClient({"entry/12345/event/1/picks/": picks_response(55)})
    ingest.load_manager_gw(conn, client, 1, manager_id=1, entry_id=12345, player_points={}, is_final=False)

    client_final = FakeClient({"entry/12345/event/1/picks/": picks_response(67)})
    ingest.load_manager_gw(conn, client_final, 1, manager_id=1, entry_id=12345, player_points={}, is_final=True)

    row = conn.execute("SELECT gross_points, is_final FROM raw_manager_gw WHERE gw_id=1 AND manager_id=1").fetchone()
    assert row == (67, 1)

    client_bad = FakeClient({"entry/12345/event/1/picks/": picks_response(1)})
    ingest.load_manager_gw(conn, client_bad, 1, manager_id=1, entry_id=12345, player_points={}, is_final=True)

    row = conn.execute("SELECT gross_points, is_final FROM raw_manager_gw WHERE gw_id=1 AND manager_id=1").fetchone()
    assert row == (67, 1), "a finalized raw_manager_gw row must never change, even via another is_final=True call"


def test_manager_gw_picks_final_rows_are_immutable(conn):
    client = FakeClient({"entry/12345/event/1/picks/": picks_response(55)})
    ingest.load_manager_gw(conn, client, 1, manager_id=1, entry_id=12345, player_points={"1": 5}, is_final=True)

    captain_before = conn.execute(
        "SELECT player_id FROM raw_manager_gw_picks WHERE gw_id=1 AND manager_id=1 AND is_captain=1"
    ).fetchone()
    assert captain_before == (1,)

    # A buggy re-run that would (incorrectly) swap the captain must not be
    # able to touch already-final pick rows.
    bad_response = picks_response(55)
    for p in bad_response["picks"]:
        p["is_captain"] = (p["element"] == 5)
    client_bad = FakeClient({"entry/12345/event/1/picks/": bad_response})
    ingest.load_manager_gw(conn, client_bad, 1, manager_id=1, entry_id=12345, player_points={}, is_final=True)

    captain_after = conn.execute(
        "SELECT player_id FROM raw_manager_gw_picks WHERE gw_id=1 AND manager_id=1 AND is_captain=1"
    ).fetchone()
    assert captain_after == (1,), "finalized picks must never be overwritten by a later call"
