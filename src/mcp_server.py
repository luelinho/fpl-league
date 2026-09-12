"""Read-only MCP server over db/league.sqlite (SPEC.md §7, "Optional later").

Lets any MCP client (Claude Desktop, Claude Code) query the league without a
terminal session — the same reviewed queries the queries/*.sql library
already vets, exposed as typed tools, plus one guarded escape hatch for
anything the fixed tools don't cover.

Runs locally only, launched by the MCP client as a subprocess over stdio.
Nothing is written, nothing is exposed to the network — the DB connection
itself is opened read-only (SQLite's own mode=ro, not just "we don't call
.execute() with INSERT"), so even a bug here can't corrupt the database.

Usage (see .mcp.json for how Claude Code launches this automatically):
    python -m src.mcp_server
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "league.sqlite"

mcp = MCPServer(
    name="fpl-league",
    instructions=(
        "Read-only access to one FPL head-to-head league's historical database "
        "(683383, 'Almost All Americans'). Every number returned is either a "
        "stored fact or a documented computed aggregate — never invent or "
        "estimate a number beyond what a tool returns. If a tool returns an "
        "empty result, say so plainly rather than guessing. Start with "
        "list_managers and league_status to resolve names to entry_ids and "
        "see which gameweeks are finalized before calling the other tools."
    ),
)


def _connect() -> sqlite3.Connection:
    # uri=True + mode=ro: the OS/SQLite layer refuses writes outright, not
    # just "the code happens not to issue any" — a real safety boundary.
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.execute(sql, params or {})
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@mcp.tool()
def list_managers() -> list[dict[str, Any]]:
    """All 18 managers in the league with their FPL entry_id, display name,
    and team name. Other tools take entry_id, not a name — call this first
    to resolve who you're being asked about."""
    return _rows(
        "SELECT m.entry_id, m.display_name, m.is_owner, tn.team_name "
        "FROM managers m JOIN team_names tn ON tn.manager_id = m.manager_id "
        "ORDER BY m.display_name"
    )


@mcp.tool()
def league_status() -> dict[str, Any]:
    """Which gameweeks are finalized (data-checked) vs still live, and
    whether the Tier 3 (luck/power rankings, needs 10 GWs) and Tier 5
    (projections, needs 15 GWs) confidence gates are unlocked yet. Always
    call this before asking for luck/power/projection data — those are
    correctly withheld below their gate, not silently zero."""
    gws = _rows(
        "SELECT gw_id, is_finished, is_data_checked FROM gameweeks "
        "WHERE season_id = 1 ORDER BY gw_id"
    )
    data_checked = [g["gw_id"] for g in gws if g["is_data_checked"]]
    through_gw = max(data_checked) if data_checked else 0
    return {
        "data_checked_gameweeks": data_checked,
        "latest_finalized_gw": through_gw or None,
        "luck_and_power_rankings": "unlocked" if through_gw >= 10
            else f"insufficient sample — {through_gw} gameweeks, need 10",
        "projections": "unlocked" if through_gw >= 15
            else f"insufficient sample — {through_gw} gameweeks, need 15",
    }


@mcp.tool()
def standings_at_gw(gw: int) -> list[dict[str, Any]]:
    """League standings after the given gameweek. `rank` is null for GW1-2:
    those rows are reconstructed from raw match data (W/D/L/points are
    exact), but FPL's H2H tiebreak rule was never empirically verified, so
    asserting a rank would mean guessing — see `source` on each row."""
    return _rows(
        """
        SELECT s.rank, m.display_name, tn.team_name, s.wins, s.draws, s.losses,
               s.league_points, s.points_for, s.points_against, s.streak, s.source
        FROM standings_snapshots s
        JOIN managers m ON m.manager_id = s.manager_id
        JOIN team_names tn ON tn.manager_id = m.manager_id
        WHERE s.gw_id = :gw
        ORDER BY (s.rank IS NULL), s.rank, s.league_points DESC, s.points_for DESC
        """,
        {"gw": gw},
    )


@mcp.tool()
def roster_by_gw(entry_id: int, gw: int) -> list[dict[str, Any]]:
    """One manager's 15-man squad for a specific gameweek: starter/bench,
    captain/vice, and each player's raw points vs. points after their
    multiplier was applied."""
    return _rows(
        """
        SELECT pl.web_name, pl.position, p.slot,
               CASE WHEN p.is_starter THEN 'XI' ELSE 'Bench' END AS status,
               CASE WHEN p.is_captain THEN 'C' WHEN p.is_vice THEN 'VC' ELSE '' END AS armband,
               p.multiplier, s.total_points AS raw_points, p.points_scored AS points_with_multiplier
        FROM raw_manager_gw_picks p
        JOIN managers m ON m.manager_id = p.manager_id
        JOIN players pl ON pl.season_id = p.season_id AND pl.player_id = p.player_id
        JOIN raw_player_gw_stats s ON s.season_id = p.season_id AND s.gw_id = p.gw_id AND s.player_id = p.player_id
        WHERE m.entry_id = :entry_id AND p.gw_id = :gw
        ORDER BY p.slot
        """,
        {"entry_id": entry_id, "gw": gw},
    )


@mcp.tool()
def captains_by_gw(gw: int) -> list[dict[str, Any]]:
    """Who every manager captained in a gameweek, and what that captain
    actually returned (raw points and the multiplied contribution)."""
    return _rows(
        """
        SELECT m.display_name, tn.team_name, pl.web_name AS captain, p.multiplier,
               s.total_points AS raw_points, p.points_scored AS captain_contribution
        FROM raw_manager_gw_picks p
        JOIN managers m ON m.manager_id = p.manager_id
        JOIN team_names tn ON tn.manager_id = m.manager_id
        JOIN players pl ON pl.season_id = p.season_id AND pl.player_id = p.player_id
        JOIN raw_player_gw_stats s ON s.season_id = p.season_id AND s.gw_id = p.gw_id AND s.player_id = p.player_id
        WHERE p.gw_id = :gw AND p.is_captain = 1
        ORDER BY p.points_scored DESC
        """,
        {"gw": gw},
    )


@mcp.tool()
def h2h_history(entry_a: int, entry_b: int) -> list[dict[str, Any]]:
    """Every finalized head-to-head match between two managers, in
    gameweek order, from entry_a's point of view (my_score/opponent_score)."""
    return _rows(
        """
        SELECT h.gw_id,
               CASE WHEN ma.entry_id = :entry_a THEN h.score_a ELSE h.score_b END AS my_score,
               CASE WHEN ma.entry_id = :entry_a THEN h.score_b ELSE h.score_a END AS opponent_score,
               CASE
                   WHEN h.winner IS NULL THEN 'Draw'
                   WHEN (ma.entry_id = :entry_a AND h.winner = h.manager_a)
                     OR (mb.entry_id = :entry_a AND h.winner = h.manager_b) THEN 'Won'
                   ELSE 'Lost'
               END AS result,
               h.margin
        FROM raw_h2h_matches h
        JOIN managers ma ON ma.manager_id = h.manager_a
        JOIN managers mb ON mb.manager_id = h.manager_b
        WHERE h.status = 'final'
          AND ((ma.entry_id = :entry_a AND mb.entry_id = :entry_b)
           OR  (ma.entry_id = :entry_b AND mb.entry_id = :entry_a))
        ORDER BY h.gw_id
        """,
        {"entry_a": entry_a, "entry_b": entry_b},
    )


@mcp.tool()
def manager_vs_manager_record(entry_a: int, entry_b: int) -> dict[str, Any]:
    """Aggregate W/D/L and points for/against between two managers across
    every finalized meeting. Use h2h_history for the match-by-match list."""
    rows = _rows(
        """
        SELECT
            COUNT(*) AS matches_played,
            SUM(CASE
                WHEN h.winner IS NOT NULL
                 AND ((ma.entry_id = :entry_a AND h.winner = h.manager_a)
                   OR (mb.entry_id = :entry_a AND h.winner = h.manager_b))
                THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN h.winner IS NULL THEN 1 ELSE 0 END) AS draws,
            SUM(CASE
                WHEN h.winner IS NOT NULL
                 AND NOT ((ma.entry_id = :entry_a AND h.winner = h.manager_a)
                      OR (mb.entry_id = :entry_a AND h.winner = h.manager_b))
                THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN ma.entry_id = :entry_a THEN h.score_a ELSE h.score_b END) AS my_points_for,
            SUM(CASE WHEN ma.entry_id = :entry_a THEN h.score_b ELSE h.score_a END) AS my_points_against
        FROM raw_h2h_matches h
        JOIN managers ma ON ma.manager_id = h.manager_a
        JOIN managers mb ON mb.manager_id = h.manager_b
        WHERE h.status = 'final'
          AND ((ma.entry_id = :entry_a AND mb.entry_id = :entry_b)
           OR  (ma.entry_id = :entry_b AND mb.entry_id = :entry_a))
        """,
        {"entry_a": entry_a, "entry_b": entry_b},
    )
    return rows[0] if rows else {"matches_played": 0}


@mcp.tool()
def ledger_manager_season(entry_id: int, through_gw: int) -> dict[str, Any]:
    """Tier 0 ledger for one manager as of a gameweek — points for/against,
    W/D/L, close/blowout counts, bench points, hit cost. Exact from GW1,
    no confidence gate. `gws_played` states the sample size."""
    rows = _rows(
        """
        SELECT ds.through_gw, ds.gws_played, ds.points_for, ds.points_against,
               ROUND(ds.avg_pf, 1) AS avg_points_for, ROUND(ds.avg_pa, 1) AS avg_points_against,
               ds.actual_w, ds.actual_d, ds.actual_l, ds.actual_league_pts,
               ds.close_w, ds.close_l, ds.blowout_w, ds.blowout_l,
               ds.total_bench_points, ds.total_hit_cost
        FROM derived_manager_season ds
        JOIN managers m ON m.manager_id = ds.manager_id
        WHERE m.entry_id = :entry_id AND ds.through_gw = :through_gw
        """,
        {"entry_id": entry_id, "through_gw": through_gw},
    )
    return rows[0] if rows else {}


@mcp.tool()
def manager_skill_summary(entry_id: int, through_gw: int) -> dict[str, Any]:
    """Tier 2 manager-skill metrics: captain efficiency (actual vs. the best
    possible captain in that squad) and XI efficiency (actual XI vs. the
    best legal XI from the same 15), season summary plus a per-gameweek
    breakdown. Computed from stored facts by a documented formula, not an
    estimate — see src/calculate.py."""
    season = _rows(
        """
        SELECT ds.through_gw, ROUND(ds.season_captain_efficiency * 100, 1) AS captain_efficiency_pct,
               ROUND(ds.season_xi_efficiency * 100, 1) AS xi_efficiency_pct,
               ds.total_bench_points, ds.total_hit_cost
        FROM derived_manager_season ds
        JOIN managers m ON m.manager_id = ds.manager_id
        WHERE m.entry_id = :entry_id AND ds.through_gw = :through_gw
        """,
        {"entry_id": entry_id, "through_gw": through_gw},
    )
    per_gw = _rows(
        """
        SELECT dg.gw_id, dg.score_rank, ROUND(dg.score_percentile, 1) AS score_percentile,
               dg.captain_points, dg.optimal_captain_points,
               ROUND(dg.captain_efficiency * 100, 1) AS captain_efficiency_pct,
               dg.bench_points, dg.xi_points, dg.optimal_xi_points,
               ROUND(dg.xi_efficiency * 100, 1) AS xi_efficiency_pct
        FROM derived_manager_gw dg
        JOIN managers m ON m.manager_id = dg.manager_id
        WHERE m.entry_id = :entry_id
        ORDER BY dg.gw_id
        """,
        {"entry_id": entry_id},
    )
    return {"season": season[0] if season else {}, "per_gameweek": per_gw}


@mcp.tool()
def gw_extremes(gw: int) -> dict[str, Any]:
    """Weekly-recap building blocks for one gameweek: winner, last place,
    biggest blowout, unluckiest loser (highest score among that week's
    losers), and luckiest winner (lowest score among that week's winners).
    No confidence gate — single-week facts are shown from GW1."""
    scores = _rows(
        """
        SELECT m.display_name, tn.team_name, rmg.net_points, rmg.gross_points, rmg.hit_cost
        FROM raw_manager_gw rmg
        JOIN managers m ON m.manager_id = rmg.manager_id
        JOIN team_names tn ON tn.manager_id = m.manager_id
        WHERE rmg.gw_id = :gw
        ORDER BY rmg.net_points DESC
        """,
        {"gw": gw},
    )
    blowout = _rows(
        """
        SELECT h.gw_id, ma.display_name AS side_a, h.score_a, mb.display_name AS side_b, h.score_b, h.margin
        FROM raw_h2h_matches h
        JOIN managers ma ON ma.manager_id = h.manager_a
        JOIN managers mb ON mb.manager_id = h.manager_b
        WHERE h.gw_id = :gw AND h.status = 'final'
        ORDER BY h.margin DESC LIMIT 1
        """,
        {"gw": gw},
    )
    unluckiest = _rows(
        """
        SELECT m.display_name, rmg.net_points
        FROM raw_h2h_matches h
        JOIN managers m ON m.manager_id = CASE WHEN h.winner = h.manager_a THEN h.manager_b
                                                WHEN h.winner = h.manager_b THEN h.manager_a END
        JOIN raw_manager_gw rmg ON rmg.gw_id = h.gw_id AND rmg.manager_id = m.manager_id
        WHERE h.gw_id = :gw AND h.status = 'final' AND h.winner IS NOT NULL
        ORDER BY rmg.net_points DESC LIMIT 1
        """,
        {"gw": gw},
    )
    luckiest = _rows(
        """
        SELECT m.display_name, rmg.net_points
        FROM raw_h2h_matches h
        JOIN managers m ON m.manager_id = h.winner
        JOIN raw_manager_gw rmg ON rmg.gw_id = h.gw_id AND rmg.manager_id = m.manager_id
        WHERE h.gw_id = :gw AND h.status = 'final' AND h.winner IS NOT NULL
        ORDER BY rmg.net_points ASC LIMIT 1
        """,
        {"gw": gw},
    )
    return {
        "winner": scores[0] if scores else None,
        "last_place": scores[-1] if scores else None,
        "biggest_blowout": blowout[0] if blowout else None,
        "unluckiest_loser": unluckiest[0] if unluckiest else None,
        "luckiest_winner": luckiest[0] if luckiest else None,
    }


@mcp.tool()
def open_data_issues() -> list[dict[str, Any]]:
    """Every logged data-quality issue, unresolved first. Includes
    documented permanent gaps (e.g. the GW1-2 standings rank gap) labeled
    severity='info', not just genuine errors — this is the honest record of
    what's known-imperfect about the data, not a bug tracker."""
    return _rows(
        "SELECT detected_at, severity, category, season_id, gw_id, manager_id, description, resolved "
        "FROM data_issues "
        "ORDER BY resolved ASC, severity = 'error' DESC, severity = 'warning' DESC, detected_at DESC"
    )


_SELECT_ONLY = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


@mcp.tool()
def run_readonly_query(sql: str) -> list[dict[str, Any]]:
    """Escape hatch for a question none of the other tools cover — run your
    own SQL against the schema (see CLAUDE.md / SPEC.md §3 for table
    definitions). Must be a single SELECT statement; the connection itself
    is opened read-only, so any write attempt fails at the SQLite layer
    regardless. Prefer the named tools above when one already fits — they're
    the reviewed, vetted queries; this is for genuinely novel questions."""
    if not _SELECT_ONLY.match(sql):
        raise ValueError("Only a single SELECT statement is allowed.")
    if ";" in sql.strip().rstrip(";"):
        raise ValueError("Only a single statement is allowed — remove the extra ';'.")
    return _rows(sql)


if __name__ == "__main__":
    mcp.run(transport="stdio")
