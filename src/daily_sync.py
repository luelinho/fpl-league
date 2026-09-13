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
  7. Recompute derived tables for affected gameweeks — run manually via
     src/calculate.py (Phase 5), not yet auto-triggered from here
  8. Regenerate recap/digest for newly finalized gameweeks — run manually via
     src/recap.py / src/digest.py / src/build_dashboard.py (Phase 6/7), not
     yet auto-triggered from here
  9. Log the run — done

Also captures a provisional (is_final=0) snapshot of the *next* gameweek once
its deadline has passed but before FPL has data-checked it: squads, captains,
and live/incomplete points, overwritten on every run until finalized.

Usage:
    python -m src.daily_sync
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from . import config, ingest
from .fpl_client import FPLClient


def deadline_has_passed(conn, gw: int) -> bool:
    row = conn.execute(
        "SELECT deadline_utc FROM gameweeks WHERE season_id = 1 AND gw_id = ?", (gw,)
    ).fetchone()
    if not row or not row[0]:
        return False
    deadline = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    return deadline < datetime.now(timezone.utc)


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
    ingest.load_fixtures(conn, client)

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

    # The first gameweek we haven't finalized yet — NOT ref["next_gw"], which
    # is FPL's own is_next flag and can point further ahead (e.g. once GW4 is
    # underway, FPL considers GW4 "current" and GW5 "next", but GW4 is what we
    # still need a provisional snapshot of).
    next_gw = max(data_checked_gws) + 1 if data_checked_gws and max(data_checked_gws) < 38 else None
    if next_gw and deadline_has_passed(conn, next_gw):
        print(f"\nGW{next_gw} deadline has passed — capturing provisional squads and live points "
              f"(is_final=0; overwritten on every run until FPL data-checks this gameweek)")
        player_points = ingest.load_player_gw_stats(conn, client, next_gw, is_final=False)
        for mgr_id, entry_id in managers:
            ingest.load_manager_gw(conn, client, next_gw, mgr_id, entry_id, player_points, is_final=False)
        conn.commit()
        print(f"  Captured provisional GW{next_gw} for all {len(managers)} managers.")

    ingest.load_h2h_matches(conn, client, entry_to_manager, data_checked_gws)
    ingest.cross_check_h2h(conn, data_checked_gws)
    ingest.load_current_standings_snapshot(conn, client, entry_to_manager, max(data_checked_gws))
    ingest.reconstruct_gap_standings(conn, data_checked_gws, max(data_checked_gws))

    problems = ingest.run_validators(conn, data_checked_gws)

    print("\nDerived-table recompute and recap/digest regeneration are not auto-triggered "
          "from here yet — run src/calculate.py, src/recap.py, src/digest.py, and "
          "src/build_dashboard.py manually after this completes.")

    status = "success" if not problems else "partial"
    ingest.log_run(conn, "daily_sync", status, client.request_count)
    conn.close()

    print(f"\nTotal requests made: {client.request_count}")
    print("Daily sync complete." if not problems else f"Daily sync complete WITH {len(problems)} validator failures.")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(run())
