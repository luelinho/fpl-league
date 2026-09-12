"""Phase 4 — the one daily job (SPEC.md §6).

Unlike Phase 3's backfill (which always re-processes every data-checked
gameweek), this skips the expensive per-manager fetch for any gameweek
already fully stored — so a normal day where nothing new has finalized costs
about 3 requests (bootstrap, H2H matches, standings) instead of ~30. A missed
day self-heals: the next run just finds more incomplete gameweeks to catch up.

Steps (SPEC.md §6), and their status here:

  1. Fetch bootstrap-static, update reference data, snapshot player state — done
  2. Determine gameweek status — done
  3. For any data-checked gameweek not yet finalized here, ingest it — done
  4. Fetch H2H matches + standings; cross-check against our own scores — done
  5. Write standings snapshot — done (current gameweek only; see ingest.py)
  6. Run validators — done
  7. Recompute derived tables for affected gameweeks — NOT YET: Phase 5 doesn't
     exist yet. Logged, not silently skipped.
  8. Regenerate recap/digest for newly finalized gameweeks — NOT YET: Phase 6/7
     don't exist yet. Logged, not silently skipped.
  9. Log the run — done

Usage:
    python -m src.daily_sync
"""

from __future__ import annotations

import sys

from . import config, ingest
from .fpl_client import FPLClient


def incomplete_gameweeks(conn, data_checked_gws: list[int]) -> list[int]:
    """A data-checked GW is 'complete' here if every manager has a raw_manager_gw
    row, every one of them has all 15 picks, and player stats exist for it."""
    incomplete = []
    for gw in data_checked_gws:
        n_mgr = conn.execute("SELECT COUNT(*) FROM raw_manager_gw WHERE gw_id = ?", (gw,)).fetchone()[0]
        n_stats = conn.execute("SELECT COUNT(*) FROM raw_player_gw_stats WHERE gw_id = ?", (gw,)).fetchone()[0]
        n_bad_picks = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT manager_id FROM raw_manager_gw_picks WHERE gw_id = ?
                GROUP BY manager_id HAVING COUNT(*) != 15
            )
            """,
            (gw,),
        ).fetchone()[0]
        if n_mgr < config.EXPECTED_TEAM_COUNT or n_stats == 0 or n_bad_picks > 0:
            incomplete.append(gw)
    return incomplete


def run() -> int:
    print("Phase 4 — daily sync\n")
    conn = ingest.connect()
    client = FPLClient(verbose=False)

    ref = ingest.load_reference_data(conn, client)
    data_checked_gws = ref["data_checked_gws"]

    managers = conn.execute("SELECT manager_id, entry_id FROM managers").fetchall()
    entry_to_manager = {entry_id: mgr_id for mgr_id, entry_id in managers}
    if len(managers) != config.EXPECTED_TEAM_COUNT:
        raise RuntimeError(
            f"Expected {config.EXPECTED_TEAM_COUNT} managers in DB, found {len(managers)}. Run Phase 2 first."
        )

    todo = incomplete_gameweeks(conn, data_checked_gws)
    if todo:
        print(f"\n{len(todo)} gameweek(s) need ingestion: {todo}")
        player_points_by_gw = {}
        for gw in todo:
            player_points_by_gw[gw] = ingest.load_player_gw_stats(conn, client, gw)
        for mgr_id, entry_id in managers:
            for gw in todo:
                ingest.load_manager_gw(conn, client, gw, mgr_id, entry_id, player_points_by_gw[gw])
            ingest.load_transfers(conn, client, mgr_id, entry_id)
            conn.commit()
        print(f"  Ingested {len(todo)} gameweek(s) for all {len(managers)} managers.")
    else:
        print("\nNo new data-checked gameweeks since last run — nothing to ingest.")

    ingest.load_h2h_matches(conn, client, entry_to_manager, data_checked_gws)
    ingest.cross_check_h2h(conn, data_checked_gws)
    ingest.load_current_standings_snapshot(conn, client, entry_to_manager, max(data_checked_gws))
    ingest.reconstruct_gap_standings(conn, data_checked_gws, max(data_checked_gws))

    problems = ingest.run_validators(conn, data_checked_gws)

    print("\nDerived-table recompute: not run — Phase 5 (analytics) does not exist yet.")
    print("Recap/digest regeneration: not run — Phase 6/7 do not exist yet.")

    status = "success" if not problems else "partial"
    ingest.log_run(conn, "daily_sync", status, client.request_count)
    conn.close()

    print(f"\nTotal requests made: {client.request_count}")
    print("Daily sync complete." if not problems else f"Daily sync complete WITH {len(problems)} validator failures.")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(run())
