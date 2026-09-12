"""Phase 6 — weekly recap generator (SPEC.md §5 Tier 1, §7).

Generates reports/gw{N}.md for every finalized gameweek: gameweek winner,
biggest blowout, biggest upset, unluckiest/luckiest of the week, and a
Midtable Crisis (owner) report. Tier 1 has no confidence gate — it's shown
from GW1 — but every number is still labeled Fact or Computed per CLAUDE.md
rule 3, and "risers/fallers" is honestly reported as unavailable rather than
guessed, because it needs two consecutive standings snapshots and only one
exists so far (see data_issues: GW1-2 snapshots are a permanent gap).

"Biggest upset" formula (SPEC.md §5 doesn't give one precisely, just "largest
positive gap between winner's deficit in season-to-date average points and
the result" — read literally: rank each win by how far below the loser's
prior season-to-date average the winner's prior average was). Documented here
so it's falsifiable:

    upset_gap = loser.avg_pf_before_this_gw - winner.avg_pf_before_this_gw

A positive gap means the winner had the lower average coming in — the bigger
the gap, the bigger the upset. Undefined for GW1 (no "before" data exists).
SPEC.md itself calls this "thin" before GW4, and it's labeled as such here.

Usage:
    python -m src.recap
"""

from __future__ import annotations

import sys

from . import config, ingest


def biggest_upset(conn, gw: int) -> tuple | None:
    if gw == 1:
        return None
    rows = conn.execute(
        """
        SELECT h.winner, h.manager_a, h.manager_b, h.margin
        FROM raw_h2h_matches h WHERE h.gw_id = ? AND h.status = 'final' AND h.winner IS NOT NULL
        """,
        (gw,),
    ).fetchall()
    best = None
    for winner, a, b, margin in rows:
        loser = b if winner == a else a
        w_avg = conn.execute(
            "SELECT avg_pf FROM derived_manager_season WHERE manager_id = ? AND through_gw = ?",
            (winner, gw - 1),
        ).fetchone()
        l_avg = conn.execute(
            "SELECT avg_pf FROM derived_manager_season WHERE manager_id = ? AND through_gw = ?",
            (loser, gw - 1),
        ).fetchone()
        if not w_avg or not l_avg:
            continue
        gap = l_avg[0] - w_avg[0]
        if best is None or gap > best[0]:
            best = (gap, winner, loser, margin)
    return best


def manager_name(conn, manager_id: int) -> str:
    row = conn.execute("SELECT display_name FROM managers WHERE manager_id = ?", (manager_id,)).fetchone()
    return row[0] if row else f"manager {manager_id}"


def generate_gw_recap(conn, gw: int) -> str:
    L = []
    A = L.append
    A(f"# Gameweek {gw} Recap")
    A("")
    A("*Fact = stored raw data. Computed = derived by a documented formula. See CLAUDE.md.*")
    A("")

    scores = conn.execute(
        """
        SELECT m.display_name, tn.team_name, rmg.net_points, rmg.gross_points, rmg.hit_cost
        FROM raw_manager_gw rmg
        JOIN managers m ON m.manager_id = rmg.manager_id
        JOIN team_names tn ON tn.manager_id = m.manager_id
        WHERE rmg.gw_id = ? ORDER BY rmg.net_points DESC
        """,
        (gw,),
    ).fetchall()

    winner = scores[0]
    last = scores[-1]
    A(f"**Gameweek winner (Fact):** {winner[0]} ({winner[1]}) — {winner[2]} net points"
      + (f" ({winner[3]} gross, -{winner[4]} hit)" if winner[4] else ""))
    A(f"**Bottom of the week (Fact):** {last[0]} ({last[1]}) — {last[2]} net points")
    A("")

    blowout = conn.execute(
        """
        SELECT ma.display_name, h.score_a, mb.display_name, h.score_b, h.margin
        FROM raw_h2h_matches h
        JOIN managers ma ON ma.manager_id = h.manager_a
        JOIN managers mb ON mb.manager_id = h.manager_b
        WHERE h.gw_id = ? AND h.status = 'final' ORDER BY h.margin DESC LIMIT 1
        """,
        (gw,),
    ).fetchone()
    if blowout:
        a_name, sa, b_name, sb, margin = blowout
        A(f"**Biggest blowout (Fact):** {a_name} {sa} - {sb} {b_name} (margin {margin})")

    upset = biggest_upset(conn, gw)
    if upset:
        gap, winner_id, loser_id, margin = upset
        note = " — thin sample, treat cautiously" if gw < 4 else ""
        A(f"**Biggest upset (Computed{note}):** {manager_name(conn, winner_id)} beat "
          f"{manager_name(conn, loser_id)}, who had the {round(gap, 1)}-point-higher "
          f"season average coming in")
    else:
        A("**Biggest upset:** not computable — no prior-gameweek average exists yet (GW1)"
          if gw == 1 else "**Biggest upset:** not computable this week")

    unluckiest = conn.execute(
        """
        SELECT m.display_name, rmg.net_points
        FROM raw_h2h_matches h
        JOIN managers m ON m.manager_id = CASE WHEN h.winner = h.manager_a THEN h.manager_b
                                                WHEN h.winner = h.manager_b THEN h.manager_a END
        JOIN raw_manager_gw rmg ON rmg.gw_id = h.gw_id AND rmg.manager_id = m.manager_id
        WHERE h.gw_id = ? AND h.status = 'final' AND h.winner IS NOT NULL
        ORDER BY rmg.net_points DESC LIMIT 1
        """,
        (gw,),
    ).fetchone()
    luckiest = conn.execute(
        """
        SELECT m.display_name, rmg.net_points
        FROM raw_h2h_matches h
        JOIN managers m ON m.manager_id = h.winner
        JOIN raw_manager_gw rmg ON rmg.gw_id = h.gw_id AND rmg.manager_id = m.manager_id
        WHERE h.gw_id = ? AND h.status = 'final' AND h.winner IS NOT NULL
        ORDER BY rmg.net_points ASC LIMIT 1
        """,
        (gw,),
    ).fetchone()
    if unluckiest:
        A(f"**Unluckiest of the week (Fact):** {unluckiest[0]} — {unluckiest[1]} net points, still lost")
    if luckiest:
        A(f"**Luckiest of the week (Fact):** {luckiest[0]} — won with just {luckiest[1]} net points")
    A("")

    A("**Risers/fallers:** not available. Standings-rank movement needs two consecutive "
      "snapshots; only one exists so far (see data_issues: GW1-2 standings are a permanent gap).")
    A("")

    owner = conn.execute(
        """
        SELECT m.display_name, rmg.net_points, rmg.gross_points, rmg.hit_cost, rmg.bench_points,
               rmg.chip_played, dmg.score_rank, dmg.captain_efficiency, dmg.xi_efficiency
        FROM raw_manager_gw rmg
        JOIN managers m ON m.manager_id = rmg.manager_id
        JOIN derived_manager_gw dmg ON dmg.manager_id = rmg.manager_id AND dmg.gw_id = rmg.gw_id
        WHERE m.is_owner = 1 AND rmg.gw_id = ?
        """,
        (gw,),
    ).fetchone()
    if owner:
        name, net, gross, hits, bench, chip, rank, cap_eff, xi_eff = owner
        A(f"## Midtable Crisis report")
        A("")
        A(f"- Net points (Fact): {net} (rank {rank} of {len(scores)})")
        if hits:
            A(f"- Gross {gross}, took a -{hits} hit (Fact)")
        A(f"- Bench points (Fact): {bench}")
        if chip:
            A(f"- Chip played (Fact): {chip}")
        if cap_eff is not None:
            A(f"- Captain efficiency (Computed): {round(cap_eff * 100, 1)}%")
        if xi_eff is not None:
            A(f"- XI efficiency (Computed): {round(xi_eff * 100, 1)}%")

    return "\n".join(L) + "\n"


def run() -> int:
    print("Phase 6 — recap generation\n")
    conn = ingest.connect()

    data_checked_gws = sorted(
        gw for (gw,) in conn.execute(
            "SELECT gw_id FROM gameweeks WHERE season_id = 1 AND is_data_checked = 1"
        ).fetchall()
    )
    reports_dir = config.REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)

    for gw in data_checked_gws:
        content = generate_gw_recap(conn, gw)
        out_path = reports_dir / f"gw{gw}.md"
        out_path.write_text(content)
        print(f"  Wrote {out_path}")

    conn.close()
    print("\nRecap generation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
