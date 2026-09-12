"""Phase 5 — Tier 0-2 analytics (SPEC.md §5): ledger and manager skill.

Computes derived_manager_gw (one row per manager per finalized gameweek) and
derived_manager_season (one row per manager per through_gw — a permanent
snapshot of season-to-date state as of that gameweek, never overwritten later).

Scope deliberately excludes Tier 3-5 (allplay-vs-season, expected wins, luck
index, strength of schedule, form, power rankings, projections) — that's
Phase 8, gated until GW10/15 per CLAUDE.md rule 4. Building it now, even
though the columns exist in derived_manager_season, would be starting a phase
before its prerequisites (10-15 finalized gameweeks) exist. Those columns are
left NULL here, not estimated.

close_w/close_l/blowout_w/blowout_l use thresholds SPEC.md never defined —
the owner set them 2026-09-12: close = margin < 5, blowout = margin > 20.
See CLOSE_MARGIN/BLOWOUT_MARGIN below.

Transfer ROI needs a 5-gameweek horizon (config.TRANSFER_ROI_HORIZON_GWS) per
the confidence gate table (ROI: H+1 minimum). With only 3 gameweeks elapsed,
it is always NULL right now — not a bug, just not yet computable.

Usage:
    python -m src.calculate
"""

from __future__ import annotations

import statistics
import sys
from itertools import product

from . import config, ingest


CALC_VERSION = "v1"

# Match-margin thresholds for close_w/close_l/blowout_w/blowout_l — not defined
# in SPEC.md, so left undefined until the owner specified them (2026-09-12):
# a "close" match has a margin under 5 points; a "blowout" has a margin over
# 20 points. Draws are neither (schema has no close_d/blowout_d column).
CLOSE_MARGIN = 5
BLOWOUT_MARGIN = 20


def best_xi_points(players: list[tuple[str, int]]) -> int:
    """players: list of (position, raw_points) for all 15 in the squad.
    Returns the highest-scoring legal XI total: 1 GKP, 3-5 DEF, 2-5 MID, 1-3 FWD.
    """
    by_pos = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for pos, pts in players:
        by_pos[pos].append(pts)
    for pos in by_pos:
        by_pos[pos].sort(reverse=True)

    def prefix_sums(vals: list[int]) -> list[int]:
        out = [0]
        for v in vals:
            out.append(out[-1] + v)
        return out

    gkp_best = max(by_pos["GKP"]) if by_pos["GKP"] else 0
    def_pref = prefix_sums(by_pos["DEF"])
    mid_pref = prefix_sums(by_pos["MID"])
    fwd_pref = prefix_sums(by_pos["FWD"])

    best = 0
    for d, m, f in product(range(3, 6), range(2, 6), range(1, 4)):
        if d + m + f != 10:
            continue
        if d >= len(def_pref) or m >= len(mid_pref) or f >= len(fwd_pref):
            continue
        total = gkp_best + def_pref[d] + mid_pref[m] + fwd_pref[f]
        best = max(best, total)
    return best


def calculate_manager_gw(conn, gw: int, manager_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT p.player_id, p.slot, p.is_starter, p.is_captain, p.multiplier,
               pl.position, s.total_points
        FROM raw_manager_gw_picks p
        JOIN players pl ON pl.season_id = 1 AND pl.player_id = p.player_id
        JOIN raw_player_gw_stats s ON s.season_id = 1 AND s.gw_id = p.gw_id AND s.player_id = p.player_id
        WHERE p.season_id = 1 AND p.gw_id = ? AND p.manager_id = ?
        """,
        (gw, manager_id),
    ).fetchall()

    squad = [(pos, pts) for (_pid, _slot, _starter, _cap, _mult, pos, pts) in rows]
    starters_raw = [pts for (_pid, _slot, starter, _cap, _mult, _pos, pts) in rows if starter]
    xi_points = sum(starters_raw)
    optimal_xi = best_xi_points(squad)

    captain_row = next((r for r in rows if r[3]), None)  # is_captain
    captain_multiplier = captain_row[4] if captain_row else 2
    captain_raw = captain_row[6] if captain_row else 0
    best_raw_in_squad = max((pts for _pos, pts in squad), default=0)
    captain_points = captain_raw * captain_multiplier
    optimal_captain_points = best_raw_in_squad * captain_multiplier
    captain_efficiency = (captain_points / optimal_captain_points) if optimal_captain_points else None

    xi_efficiency = (xi_points / optimal_xi) if optimal_xi else None

    return {
        "captain_points": captain_points,
        "optimal_captain_points": optimal_captain_points,
        "captain_efficiency": captain_efficiency,
        "xi_points": xi_points,
        "optimal_xi_points": optimal_xi,
        "xi_efficiency": xi_efficiency,
    }


def calculate_gw(conn, gw: int) -> None:
    mgr_scores = conn.execute(
        "SELECT manager_id, net_points, bench_points FROM raw_manager_gw WHERE gw_id = ?", (gw,)
    ).fetchall()
    if not mgr_scores:
        return

    scores_sorted = sorted(mgr_scores, key=lambda r: r[1], reverse=True)
    rank_by_mgr = {mgr: i + 1 for i, (mgr, _net, _bench) in enumerate(scores_sorted)}
    n = len(mgr_scores)
    median_net = statistics.median(net for _mgr, net, _bench in mgr_scores)

    for manager_id, net_points, bench_points in mgr_scores:
        rank = rank_by_mgr[manager_id]
        percentile = (n - rank) / (n - 1) * 100 if n > 1 else 100.0
        beat_median = net_points > median_net

        skill = calculate_manager_gw(conn, gw, manager_id)

        conn.execute(
            """
            INSERT INTO derived_manager_gw
                (season_id, gw_id, manager_id, score_rank, score_percentile,
                 allplay_w, allplay_d, allplay_l, beat_median,
                 captain_points, optimal_captain_points, captain_efficiency,
                 bench_points, xi_points, optimal_xi_points, xi_efficiency,
                 expected_h2h_pts, calc_version, calculated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            ON CONFLICT (season_id, gw_id, manager_id) DO UPDATE SET
                score_rank = excluded.score_rank, score_percentile = excluded.score_percentile,
                allplay_w = excluded.allplay_w, allplay_d = excluded.allplay_d, allplay_l = excluded.allplay_l,
                beat_median = excluded.beat_median,
                captain_points = excluded.captain_points, optimal_captain_points = excluded.optimal_captain_points,
                captain_efficiency = excluded.captain_efficiency,
                bench_points = excluded.bench_points, xi_points = excluded.xi_points,
                optimal_xi_points = excluded.optimal_xi_points, xi_efficiency = excluded.xi_efficiency,
                calc_version = excluded.calc_version, calculated_at = excluded.calculated_at
            """,
            # allplay_w/d/l are NOT NULL by schema but are a Tier 3 concept (all-play
            # vs the field) — computed here as a per-week fact (not gated for storage,
            # per CLAUDE.md rule 4: computed from GW1, only DISPLAY is gated at GW10).
            (gw, manager_id, rank, percentile,
             sum(1 for _m, other_net, _b in mgr_scores if net_points > other_net and _m != manager_id),
             sum(1 for _m, other_net, _b in mgr_scores if net_points == other_net and _m != manager_id),
             sum(1 for _m, other_net, _b in mgr_scores if net_points < other_net and _m != manager_id),
             int(beat_median),
             skill["captain_points"], skill["optimal_captain_points"], skill["captain_efficiency"],
             bench_points, skill["xi_points"], skill["optimal_xi_points"], skill["xi_efficiency"],
             CALC_VERSION, ingest.now()),
        )
    conn.commit()


def calculate_season(conn, through_gw: int) -> None:
    managers = conn.execute("SELECT manager_id FROM managers").fetchall()

    for (manager_id,) in managers:
        gw_rows = conn.execute(
            """
            SELECT rmg.gw_id, rmg.net_points, rmg.hit_cost, rmg.bench_points, rmg.chip_played,
                   dmg.captain_points, dmg.optimal_captain_points, dmg.xi_points, dmg.optimal_xi_points
            FROM raw_manager_gw rmg
            JOIN derived_manager_gw dmg ON dmg.season_id = 1 AND dmg.gw_id = rmg.gw_id AND dmg.manager_id = rmg.manager_id
            WHERE rmg.season_id = 1 AND rmg.manager_id = ? AND rmg.gw_id <= ?
            ORDER BY rmg.gw_id
            """,
            (manager_id, through_gw),
        ).fetchall()
        if not gw_rows:
            continue

        gws_played = len(gw_rows)
        nets = [r[1] for r in gw_rows]
        points_for = sum(nets)
        avg_pf = points_for / gws_played
        median_score = statistics.median(nets)
        stdev_score = statistics.stdev(nets) if gws_played > 1 else 0.0
        total_hit_cost = sum(r[2] for r in gw_rows)
        total_bench_points = sum(r[3] for r in gw_rows if r[4] != "bboost")
        sum_cap = sum(r[5] for r in gw_rows)
        sum_opt_cap = sum(r[6] for r in gw_rows)
        sum_xi = sum(r[7] for r in gw_rows)
        sum_opt_xi = sum(r[8] for r in gw_rows)
        season_captain_efficiency = (sum_cap / sum_opt_cap) if sum_opt_cap else None
        season_xi_efficiency = (sum_xi / sum_opt_xi) if sum_opt_xi else None

        match_rows = conn.execute(
            """
            SELECT winner, manager_a, manager_b, score_a, score_b, league_pts_a, league_pts_b, margin
            FROM raw_h2h_matches
            WHERE (manager_a = ? OR manager_b = ?) AND gw_id <= ?
            """,
            (manager_id, manager_id, through_gw),
        ).fetchall()
        actual_w = actual_d = actual_l = actual_league_pts = 0
        close_w = close_l = blowout_w = blowout_l = 0
        points_against = 0
        for winner, a, b, score_a, score_b, pa, pb, margin in match_rows:
            mine_pts = pa if a == manager_id else pb
            actual_league_pts += mine_pts
            points_against += score_b if a == manager_id else score_a
            if winner is None:
                actual_d += 1
            elif winner == manager_id:
                actual_w += 1
                if margin < CLOSE_MARGIN:
                    close_w += 1
                elif margin > BLOWOUT_MARGIN:
                    blowout_w += 1
            else:
                actual_l += 1
                if margin < CLOSE_MARGIN:
                    close_l += 1
                elif margin > BLOWOUT_MARGIN:
                    blowout_l += 1
        avg_pa = points_against / gws_played if gws_played else None

        conn.execute(
            """
            INSERT INTO derived_manager_season
                (season_id, manager_id, through_gw, gws_played, points_for, points_against,
                 avg_pf, avg_pa, median_score, stdev_score,
                 actual_w, actual_d, actual_l, actual_league_pts,
                 allplay_w, allplay_d, allplay_l, allplay_pct,
                 expected_wins, expected_league_pts, luck_index, sos_played, sos_remaining,
                 form_3gw, form_5gw, close_w, close_l, blowout_w, blowout_l,
                 total_bench_points, season_captain_efficiency, season_xi_efficiency,
                 total_hit_cost, transfer_roi, is_provisional, calc_version, calculated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, NULL, 1, ?, ?)
            ON CONFLICT (season_id, manager_id, through_gw) DO UPDATE SET
                gws_played = excluded.gws_played, points_for = excluded.points_for,
                points_against = excluded.points_against, avg_pf = excluded.avg_pf, avg_pa = excluded.avg_pa,
                median_score = excluded.median_score, stdev_score = excluded.stdev_score,
                actual_w = excluded.actual_w, actual_d = excluded.actual_d, actual_l = excluded.actual_l,
                actual_league_pts = excluded.actual_league_pts,
                close_w = excluded.close_w, close_l = excluded.close_l,
                blowout_w = excluded.blowout_w, blowout_l = excluded.blowout_l,
                total_bench_points = excluded.total_bench_points,
                season_captain_efficiency = excluded.season_captain_efficiency,
                season_xi_efficiency = excluded.season_xi_efficiency,
                total_hit_cost = excluded.total_hit_cost,
                calc_version = excluded.calc_version, calculated_at = excluded.calculated_at
            """,
            (manager_id, through_gw, gws_played, points_for, points_against, avg_pf, avg_pa,
             median_score, stdev_score, actual_w, actual_d, actual_l, actual_league_pts,
             close_w, close_l, blowout_w, blowout_l,
             total_bench_points, season_captain_efficiency, season_xi_efficiency,
             total_hit_cost, CALC_VERSION, ingest.now()),
        )
    conn.commit()


def run() -> int:
    print("Phase 5 — Tier 0-2 analytics\n")
    conn = ingest.connect()

    data_checked_gws = sorted(
        gw for (gw,) in conn.execute(
            "SELECT gw_id FROM gameweeks WHERE season_id = 1 AND is_data_checked = 1"
        ).fetchall()
    )
    if not data_checked_gws:
        print("No finalized gameweeks yet — nothing to calculate.")
        conn.close()
        return 0

    print(f"Calculating derived_manager_gw for GW {data_checked_gws}")
    for gw in data_checked_gws:
        calculate_gw(conn, gw)
        print(f"  GW{gw}: done")

    print(f"\nCalculating derived_manager_season through each of GW {data_checked_gws}")
    for gw in data_checked_gws:
        calculate_season(conn, gw)
        print(f"  through_gw={gw}: done")

    print(f"\nclose/blowout thresholds: close < {CLOSE_MARGIN}pts, blowout > {BLOWOUT_MARGIN}pts")
    print("NOTE: Tier 3-5 columns (allplay season pct, expected_wins, luck_index, SOS, form,")
    print("transfer_roi) left NULL — gated to Phase 8 (GW10+) / insufficient horizon.")

    conn.close()
    print("\nPhase 5 calculation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
