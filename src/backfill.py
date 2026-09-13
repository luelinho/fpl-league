"""Phase 3 — historical backfill.

Ingests every data-checked gameweek from GW1 through current, unconditionally
(unlike Phase 4's daily_sync, which skips gameweeks already fully stored).
Intended to be run once to establish history, or re-run after a schema change
to rebuild derived-from-raw state — safe either way since every write is an
upsert on a natural key and is_final=1 rows are never overwritten.

Loaders live in src/ingest.py, shared with src/daily_sync.py (Phase 4).

Usage:
    python -m src.backfill
"""

from __future__ import annotations

import sys

from . import config, ingest
from .fpl_client import FPLClient


def run() -> int:
    print("Phase 3 — historical backfill\n")
    conn = ingest.connect()
    client = FPLClient(verbose=False)

    ref = ingest.load_reference_data(conn, client)
    data_checked_gws = ref["data_checked_gws"]
    ingest.load_fixtures(conn, client)

    managers = conn.execute("SELECT manager_id, entry_id FROM managers").fetchall()
    entry_to_manager = {entry_id: mgr_id for mgr_id, entry_id in managers}
    if len(managers) != config.EXPECTED_TEAM_COUNT:
        raise RuntimeError(
            f"Expected {config.EXPECTED_TEAM_COUNT} managers in DB, found {len(managers)}. Run Phase 2 first."
        )

    print(f"\nPer-gameweek player stats for GW {data_checked_gws}")
    player_points_by_gw = {}
    for gw in data_checked_gws:
        player_points_by_gw[gw] = ingest.load_player_gw_stats(conn, client, gw)

    print(f"\nPer-manager picks, gameweek summaries, transfers ({len(managers)} managers)")
    for mgr_id, entry_id in managers:
        for gw in data_checked_gws:
            ingest.load_manager_gw(conn, client, gw, mgr_id, entry_id, player_points_by_gw[gw])
        ingest.load_transfers(conn, client, mgr_id, entry_id)
        conn.commit()
    print(f"  Done for all {len(managers)} managers.")

    ingest.load_h2h_matches(conn, client, entry_to_manager, data_checked_gws)
    ingest.cross_check_h2h(conn, data_checked_gws)
    ingest.load_current_standings_snapshot(conn, client, entry_to_manager, max(data_checked_gws))
    ingest.reconstruct_gap_standings(conn, data_checked_gws, max(data_checked_gws))

    problems = ingest.run_validators(conn, data_checked_gws)
    ingest.log_run(conn, "phase3_backfill", "success" if not problems else "partial", client.request_count)
    conn.close()

    print(f"\nTotal requests made: {client.request_count}")
    print("Phase 3 complete." if not problems else f"Phase 3 complete WITH {len(problems)} validator failures.")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(run())
