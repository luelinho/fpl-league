"""One-off migration (2026-09-12): standings_snapshots.rank becomes nullable,
plus a new `source` column, to support reconstructing GW1-2's W/D/L/points
from raw match data while honestly leaving rank unknown (FPL's H2H tiebreak
rule was never verified). See db/schema.sql for the column comments.

SQLite can't ALTER a column's NOT NULL constraint in place, so this recreates
the table and copies the existing rows across (all of them genuinely FPL-
reported today, so they all get source='fpl_h2h_endpoint').

Safe to run once; running it again is a no-op if standings_snapshots already
has a `source` column.

Usage:
    python -m src.migrate_standings_schema
"""

from __future__ import annotations

import sys

from . import ingest


def run() -> int:
    conn = ingest.connect()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(standings_snapshots)").fetchall()]
    if "source" in cols:
        print("standings_snapshots already migrated (source column present). No-op.")
        conn.close()
        return 0

    print("Migrating standings_snapshots: rank -> nullable, + source column")
    conn.execute("ALTER TABLE standings_snapshots RENAME TO standings_snapshots_old")
    conn.executescript("""
        CREATE TABLE standings_snapshots (
          league_id      INTEGER NOT NULL REFERENCES leagues(league_id),
          season_id      INTEGER NOT NULL,
          gw_id          INTEGER NOT NULL,
          manager_id     INTEGER NOT NULL REFERENCES managers(manager_id),
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
          source         TEXT NOT NULL DEFAULT 'fpl_h2h_endpoint' CHECK (source IN ('fpl_h2h_endpoint','reconstructed')),
          created_at     TIMESTAMP NOT NULL,
          PRIMARY KEY (league_id, season_id, gw_id, manager_id)
        );
    """)
    n = conn.execute(
        """
        INSERT INTO standings_snapshots
            (league_id, season_id, gw_id, manager_id, rank, prev_rank, rank_change,
             wins, draws, losses, league_points, points_for, points_against, streak,
             source, created_at)
        SELECT league_id, season_id, gw_id, manager_id, rank, prev_rank, rank_change,
               wins, draws, losses, league_points, points_for, points_against, streak,
               'fpl_h2h_endpoint', created_at
        FROM standings_snapshots_old
        """
    ).rowcount
    conn.execute("DROP TABLE standings_snapshots_old")
    conn.commit()
    conn.close()
    print(f"Migrated {n} existing row(s), tagged source='fpl_h2h_endpoint'.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
