"""Phase 7 — digest export for the dashboard (SPEC.md §8).

Builds digest/season.json: a compact, current-state snapshot of everything
the dashboard needs, so the dashboard itself never touches SQL. Every number
here traces back to a raw or derived table — nothing is computed fresh here
beyond simple aggregation (e.g. sorting a leaderboard).

Usage:
    python -m src.digest
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timezone

import requests

from . import config, ingest
from .recap import biggest_upset, manager_name

KIT_CACHE_DIR = config.REPO_ROOT / "digest" / ".kit_cache"
KIT_URL = "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_{code}-66.png"
KIT_GK_URL = "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_{code}_1-66.png"


def league_info(conn) -> dict:
    row = conn.execute(
        "SELECT name, ko_rounds, start_event FROM leagues WHERE league_id = ?", (config.LEAGUE_ID,)
    ).fetchone()
    season = conn.execute("SELECT name FROM seasons WHERE season_id = 1").fetchone()
    return {"name": row[0], "id": config.LEAGUE_ID, "ko_rounds": row[1], "start_event": row[2], "season": season[0]}


def gw_status(conn) -> dict:
    rows = conn.execute(
        "SELECT gw_id, is_finished, is_data_checked FROM gameweeks WHERE season_id = 1 ORDER BY gw_id"
    ).fetchall()
    data_checked = [gw for gw, _f, dc in rows if dc]
    current = max(data_checked) if data_checked else None
    next_gw = (current + 1) if current and current < 38 else None
    next_deadline = None
    if next_gw:
        row = conn.execute(
            "SELECT deadline_utc FROM gameweeks WHERE season_id = 1 AND gw_id = ?", (next_gw,)
        ).fetchone()
        next_deadline = row[0] if row else None
    return {
        "data_checked_gws": data_checked, "current_gw": current, "next_gw": next_gw,
        "next_gw_deadline": next_deadline,
    }


def gates(gws_played: int) -> dict:
    return {
        "luck_and_power_rankings": {
            "unlocked": gws_played >= config.GATE_LUCK_METRICS,
            "have": gws_played, "need": config.GATE_LUCK_METRICS,
        },
        "projections": {
            "unlocked": gws_played >= config.GATE_PROJECTIONS,
            "have": gws_played, "need": config.GATE_PROJECTIONS,
        },
    }


def standings(conn, gw: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.rank, m.display_name, tn.team_name, s.wins, s.draws, s.losses,
               s.league_points, s.points_for, s.points_against, s.streak, m.is_owner, s.source
        FROM standings_snapshots s
        JOIN managers m ON m.manager_id = s.manager_id
        JOIN team_names tn ON tn.manager_id = m.manager_id
        WHERE s.gw_id = ?
        ORDER BY (s.rank IS NULL), s.rank, s.league_points DESC, s.points_for DESC
        """,
        (gw,),
    ).fetchall()
    return [
        {"rank": r, "display_name": n, "team_name": t, "wins": w, "draws": d, "losses": l,
         "league_points": lp, "points_for": pf, "points_against": pa, "streak": s,
         "is_owner": bool(o), "reconstructed": src == "reconstructed"}
        for r, n, t, w, d, l, lp, pf, pa, s, o, src in rows
    ]


def fixtures_for_gw(conn, gw: int) -> list[dict]:
    """This gameweek's matchups. raw_h2h_matches itself never carries a score
    until the gameweek is finalized (CLAUDE.md rule 5 — no invented results),
    but once the deadline has passed, raw_manager_gw holds real provisional
    (is_final=0) net_points captured by daily_sync. Surface those here as a
    live score — still a stored fact, just not yet the final result — rather
    than making the owner wait for the fixture to leave "vs" until GW-end.
    """
    if gw is None:
        return []
    rows = conn.execute(
        """
        SELECT ma.display_name, ta.team_name, mb.display_name, tb.team_name,
               ga.net_points, ga.is_final, gb.net_points, gb.is_final
        FROM raw_h2h_matches h
        JOIN managers ma ON ma.manager_id = h.manager_a
        JOIN managers mb ON mb.manager_id = h.manager_b
        JOIN team_names ta ON ta.manager_id = h.manager_a
        JOIN team_names tb ON tb.manager_id = h.manager_b
        LEFT JOIN raw_manager_gw ga ON ga.gw_id = h.gw_id AND ga.manager_id = h.manager_a
        LEFT JOIN raw_manager_gw gb ON gb.gw_id = h.gw_id AND gb.manager_id = h.manager_b
        WHERE h.gw_id = ?
        """,
        (gw,),
    ).fetchall()
    out = []
    for an, at, bn, bt, sa, fa, sb, fb in rows:
        m = {"a": {"name": an, "team": at}, "b": {"name": bn, "team": bt}}
        if sa is not None and sb is not None and not fa and not fb:
            m["a"]["score"], m["b"]["score"], m["live"] = sa, sb, True
            if sa != sb:
                m["winner"] = "a" if sa > sb else "b"
        out.append(m)
    return out


def results_for_gw(conn, gw: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT ma.display_name, h.score_a, mb.display_name, h.score_b, h.margin, h.winner, h.manager_a
        FROM raw_h2h_matches h
        JOIN managers ma ON ma.manager_id = h.manager_a
        JOIN managers mb ON mb.manager_id = h.manager_b
        WHERE h.gw_id = ? AND h.status = 'final'
        """,
        (gw,),
    ).fetchall()
    out = []
    for an, sa, bn, sb, margin, winner, mgr_a in rows:
        result = "Draw" if winner is None else ("a" if winner == mgr_a else "b")
        out.append({"a": {"name": an, "score": sa}, "b": {"name": bn, "score": sb},
                    "margin": margin, "winner": result})
    return out


ALERTS_SHOWN_LIMIT = 5


def alerts(conn) -> dict:
    """Capped so the Home page can't grow an unbounded list over a season —
    most severe and most recent first. `total` lets the UI say "N more" for
    anything past the cap rather than silently dropping it."""
    total = conn.execute("SELECT COUNT(*) FROM data_issues WHERE resolved = 0").fetchone()[0]
    rows = conn.execute(
        "SELECT severity, category, description FROM data_issues WHERE resolved = 0 "
        "ORDER BY severity = 'error' DESC, severity = 'warning' DESC, detected_at DESC "
        "LIMIT ?",
        (ALERTS_SHOWN_LIMIT,),
    ).fetchall()
    items = [{"severity": sev, "category": cat, "description": desc} for sev, cat, desc in rows]
    return {"items": items, "total_unresolved": total}


PRICE_MOVERS_SHOWN = 5


def price_movers(conn) -> dict:
    """Risers/fallers since the previous daily snapshot. raw_player_snapshots
    has been captured since Phase 3, but comparing prices needs at least two
    distinct snapshot dates — until a second day exists this is honestly
    reported as unavailable, not backfilled with a guess or left silently
    empty. Self-heals the day after this first runs on a new date.
    """
    dates = conn.execute(
        "SELECT DISTINCT snapshot_date FROM raw_player_snapshots ORDER BY snapshot_date DESC LIMIT 2"
    ).fetchall()
    if len(dates) < 2:
        return {"available": False, "latest_date": dates[0][0] if dates else None, "risers": [], "fallers": []}

    latest, previous = dates[0][0], dates[1][0]
    rows = conn.execute(
        """
        SELECT pl.web_name, c.short_name, s1.price_tenths - s2.price_tenths AS delta, s1.price_tenths
        FROM raw_player_snapshots s1
        JOIN raw_player_snapshots s2 ON s2.player_id = s1.player_id AND s2.season_id = s1.season_id
                                     AND s2.snapshot_date = ?
        JOIN players pl ON pl.season_id = s1.season_id AND pl.player_id = s1.player_id
        JOIN pl_clubs c ON c.season_id = pl.season_id AND c.club_id = pl.club_id
        WHERE s1.snapshot_date = ? AND s1.price_tenths != s2.price_tenths
        ORDER BY delta DESC
        """,
        (previous, latest),
    ).fetchall()
    movers = [{"name": n, "club": c, "delta_tenths": d, "price_tenths": p} for n, c, d, p in rows]
    risers = [m for m in movers if m["delta_tenths"] > 0][:PRICE_MOVERS_SHOWN]
    fallers = list(reversed([m for m in movers if m["delta_tenths"] < 0][-PRICE_MOVERS_SHOWN:]))
    return {"available": True, "latest_date": latest, "previous_date": previous, "risers": risers, "fallers": fallers}


def _fetch_and_cache(url: str, cache_path) -> str | None:
    if not cache_path.exists():
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)
        except requests.RequestException:
            return None
    return "data:image/png;base64," + base64.b64encode(cache_path.read_bytes()).decode()


def club_kits(conn) -> dict[str, dict[str, str]]:
    """{club_id: {'out': data-uri, 'gk': data-uri}} for every PL club — real
    club kit jerseys (outfield + goalkeeper variant), no player photos
    (owner's explicit call). Downloaded once and cached to disk
    (KIT_CACHE_DIR) so repeat digest builds don't re-fetch 40 images from
    FPL's own CDN every time; verified live 2026-09-12 (HTTP 200, both
    variants, all 20 clubs) before this was built. Replaces the earlier
    badge-in-circle chip (owner's call, 2026-09-12) with actual shirt art —
    the GK kit visibly differs from the outfield kit, which a badge never
    could show.
    """
    KIT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    rows = conn.execute("SELECT club_id, badge_code FROM pl_clubs WHERE season_id = 1").fetchall()
    kits: dict[str, dict[str, str]] = {}
    for club_id, code in rows:
        if code is None:
            continue
        out = _fetch_and_cache(KIT_URL.format(code=code), KIT_CACHE_DIR / f"shirt_{code}.png")
        gk = _fetch_and_cache(KIT_GK_URL.format(code=code), KIT_CACHE_DIR / f"shirt_{code}_gk.png")
        if out is None:
            continue
        kits[str(club_id)] = {"out": out, "gk": gk or out}
    return kits


def all_managers(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT m.manager_id, m.entry_id, m.display_name, tn.team_name, m.is_owner
        FROM managers m JOIN team_names tn ON tn.manager_id = m.manager_id
        ORDER BY m.display_name
        """
    ).fetchall()
    return [{"manager_id": mid, "entry_id": eid, "display_name": n, "team_name": t, "is_owner": bool(o)}
             for mid, eid, n, t, o in rows]


def leaderboard(conn, through_gw: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT m.display_name, tn.team_name, ds.actual_w, ds.actual_d, ds.actual_l,
               ds.actual_league_pts, ds.points_for, ds.points_against,
               ds.season_captain_efficiency, ds.season_xi_efficiency, ds.total_bench_points,
               ds.close_w, ds.close_l, ds.blowout_w, ds.blowout_l, m.is_owner
        FROM derived_manager_season ds
        JOIN managers m ON m.manager_id = ds.manager_id
        JOIN team_names tn ON tn.manager_id = m.manager_id
        WHERE ds.through_gw = ?
        ORDER BY ds.actual_league_pts DESC, ds.points_for DESC
        """,
        (through_gw,),
    ).fetchall()
    out = []
    for n, t, w, d, l, lp, pf, pa, cap_eff, xi_eff, bench, cw, cl, bw, bl, owner in rows:
        out.append({
            "display_name": n, "team_name": t, "w": w, "d": d, "l": l, "league_points": lp,
            "points_for": pf, "points_against": pa,
            "captain_efficiency_pct": round(cap_eff * 100, 1) if cap_eff is not None else None,
            "xi_efficiency_pct": round(xi_eff * 100, 1) if xi_eff is not None else None,
            "bench_points": bench, "close_w": cw, "close_l": cl, "blowout_w": bw, "blowout_l": bl,
            "is_owner": bool(owner),
        })
    return out


def gw_recap_summary(conn, gw: int) -> dict:
    winner_row = conn.execute(
        """
        SELECT m.display_name, rmg.net_points FROM raw_manager_gw rmg
        JOIN managers m ON m.manager_id = rmg.manager_id
        WHERE rmg.gw_id = ? ORDER BY rmg.net_points DESC LIMIT 1
        """, (gw,),
    ).fetchone()
    blowout = conn.execute(
        """
        SELECT ma.display_name, h.score_a, mb.display_name, h.score_b, h.margin
        FROM raw_h2h_matches h
        JOIN managers ma ON ma.manager_id = h.manager_a
        JOIN managers mb ON mb.manager_id = h.manager_b
        WHERE h.gw_id = ? AND h.status = 'final' ORDER BY h.margin DESC LIMIT 1
        """, (gw,),
    ).fetchone()
    unluckiest = conn.execute(
        """
        SELECT m.display_name, rmg.net_points
        FROM raw_h2h_matches h
        JOIN managers m ON m.manager_id = CASE WHEN h.winner = h.manager_a THEN h.manager_b
                                                WHEN h.winner = h.manager_b THEN h.manager_a END
        JOIN raw_manager_gw rmg ON rmg.gw_id = h.gw_id AND rmg.manager_id = m.manager_id
        WHERE h.gw_id = ? AND h.status = 'final' AND h.winner IS NOT NULL
        ORDER BY rmg.net_points DESC LIMIT 1
        """, (gw,),
    ).fetchone()
    luckiest = conn.execute(
        """
        SELECT m.display_name, rmg.net_points
        FROM raw_h2h_matches h
        JOIN managers m ON m.manager_id = h.winner
        JOIN raw_manager_gw rmg ON rmg.gw_id = h.gw_id AND rmg.manager_id = m.manager_id
        WHERE h.gw_id = ? AND h.status = 'final' AND h.winner IS NOT NULL
        ORDER BY rmg.net_points ASC LIMIT 1
        """, (gw,),
    ).fetchone()
    upset = biggest_upset(conn, gw)
    upset_out = None
    if upset:
        gap, winner_id, loser_id, margin = upset
        upset_out = {"winner": manager_name(conn, winner_id), "loser": manager_name(conn, loser_id),
                     "gap": round(gap, 1), "thin_sample": gw < 4}

    return {
        "gw": gw,
        "winner": {"name": winner_row[0], "net_points": winner_row[1]} if winner_row else None,
        "blowout": {"a": blowout[0], "score_a": blowout[1], "b": blowout[2], "score_b": blowout[3],
                    "margin": blowout[4]} if blowout else None,
        "unluckiest": {"name": unluckiest[0], "net_points": unluckiest[1]} if unluckiest else None,
        "luckiest": {"name": luckiest[0], "net_points": luckiest[1]} if luckiest else None,
        "upset": upset_out,
    }


def manager_detail(conn, mgr_id: int, latest_gw: int) -> dict:
    """Same shape as the old owner-only block, generalized to any manager_id.
    Used both for the owner (My Team tab) and for every manager (Managers tab)."""
    entry_id, name = conn.execute(
        "SELECT entry_id, display_name FROM managers WHERE manager_id = ?", (mgr_id,)
    ).fetchone()
    team = conn.execute("SELECT team_name FROM team_names WHERE manager_id = ?", (mgr_id,)).fetchone()[0]
    rank_row = conn.execute(
        "SELECT rank FROM standings_snapshots WHERE manager_id = ? AND gw_id = ?", (mgr_id, latest_gw)
    ).fetchone()
    rank = rank_row[0] if rank_row else None

    ledger = conn.execute(
        """
        SELECT points_for, points_against, avg_pf, avg_pa, actual_w, actual_d, actual_l,
               actual_league_pts, close_w, close_l, blowout_w, blowout_l, total_bench_points, total_hit_cost
        FROM derived_manager_season WHERE manager_id = ? AND through_gw = ?
        """, (mgr_id, latest_gw),
    ).fetchone()

    skill = conn.execute(
        "SELECT season_captain_efficiency, season_xi_efficiency FROM derived_manager_season "
        "WHERE manager_id = ? AND through_gw = ?", (mgr_id, latest_gw),
    ).fetchone()

    # LEFT JOIN, not JOIN: a provisional (is_final=0) gameweek has a
    # raw_manager_gw row but no derived_manager_gw row yet (Phase 5's
    # calculate.py only processes data-checked gameweeks) — score_rank/
    # captain_efficiency/xi_efficiency are genuinely unknown for it, not
    # values we failed to compute, so they come back NULL rather than absent.
    gw_history = conn.execute(
        """
        SELECT rmg.gw_id, rmg.net_points, rmg.gross_points, rmg.hit_cost, rmg.bench_points,
               rmg.chip_played, dg.score_rank, dg.captain_efficiency, dg.xi_efficiency, rmg.is_final
        FROM raw_manager_gw rmg
        LEFT JOIN derived_manager_gw dg ON dg.manager_id = rmg.manager_id AND dg.gw_id = rmg.gw_id
        WHERE rmg.manager_id = ? ORDER BY rmg.gw_id
        """, (mgr_id,),
    ).fetchall()

    # owned_pct/form come from the player's most recent snapshot, not one dated
    # to that historical gameweek — raw_player_snapshots only goes back to
    # when daily_sync started capturing it. Labeled "current" in the UI so a
    # GW1 roster's ownership figure is never mistaken for what it was in GW1.
    all_picks = conn.execute(
        """
        SELECT p.gw_id, p.player_id, pl.web_name, pl.position, pl.club_id, p.slot, p.is_starter, p.is_captain, p.is_vice,
               p.multiplier, s.total_points, s.minutes,
               (SELECT rs.selected_by FROM raw_player_snapshots rs
                WHERE rs.season_id = p.season_id AND rs.player_id = p.player_id
                ORDER BY rs.snapshot_date DESC LIMIT 1) AS owned_pct,
               (SELECT rs.form FROM raw_player_snapshots rs
                WHERE rs.season_id = p.season_id AND rs.player_id = p.player_id
                ORDER BY rs.snapshot_date DESC LIMIT 1) AS form
        FROM raw_manager_gw_picks p
        JOIN players pl ON pl.season_id = p.season_id AND pl.player_id = p.player_id
        JOIN raw_player_gw_stats s ON s.season_id = p.season_id AND s.gw_id = p.gw_id AND s.player_id = p.player_id
        WHERE p.manager_id = ? ORDER BY p.gw_id, p.slot
        """, (mgr_id,),
    ).fetchall()
    rosters_by_gw: dict[int, list[dict]] = {}
    for gw, player_id, name_, pos, club_id, slot, starter, cap, vice, mult, pts, mins, owned, frm in all_picks:
        rosters_by_gw.setdefault(gw, []).append({
            "player_id": player_id, "name": name_, "position": pos, "club_id": club_id, "slot": slot,
            "is_starter": bool(starter),
            "armband": "C" if cap else ("VC" if vice else ""), "multiplier": mult, "raw_points": pts,
            "minutes": mins, "owned_pct": owned, "form": frm,
            "gw": gw, "owner_manager_id": mgr_id,
        })
    # The most recent gameweek with ANY picks — final or provisional — not
    # necessarily latest_gw (the newest FINALIZED one). Once a gameweek's
    # deadline passes we have real picks for it well before it's data-checked.
    newest_gw_with_picks = max(rosters_by_gw.keys()) if rosters_by_gw else latest_gw
    latest_roster = rosters_by_gw.get(newest_gw_with_picks, [])

    transfers = conn.execute(
        """
        SELECT t.gw_id, pin.web_name, pout.web_name, t.transfer_time
        FROM raw_transfers t
        JOIN players pin ON pin.season_id = 1 AND pin.player_id = t.player_in
        JOIN players pout ON pout.season_id = 1 AND pout.player_id = t.player_out
        WHERE t.manager_id = ? ORDER BY t.transfer_time
        """, (mgr_id,),
    ).fetchall()

    return {
        "manager_id": mgr_id, "entry_id": entry_id, "display_name": name, "team_name": team, "rank": rank,
        "ledger": {
            "points_for": ledger[0], "points_against": ledger[1],
            "avg_pf": round(ledger[2], 1), "avg_pa": round(ledger[3], 1),
            "w": ledger[4], "d": ledger[5], "l": ledger[6], "league_points": ledger[7],
            "close_w": ledger[8], "close_l": ledger[9], "blowout_w": ledger[10], "blowout_l": ledger[11],
            "total_bench_points": ledger[12], "total_hit_cost": ledger[13],
        } if ledger else None,
        "skill": {
            "captain_efficiency_pct": round(skill[0] * 100, 1) if skill and skill[0] is not None else None,
            "xi_efficiency_pct": round(skill[1] * 100, 1) if skill and skill[1] is not None else None,
        } if skill else None,
        "gw_history": [
            {"gw": gw, "net_points": net, "gross_points": gross, "hit_cost": hits, "bench_points": bench,
             "chip": chip, "rank": rank,
             "captain_efficiency_pct": round(ce * 100, 1) if ce is not None else None,
             "xi_efficiency_pct": round(xe * 100, 1) if xe is not None else None,
             "is_final": bool(is_final)}
            for gw, net, gross, hits, bench, chip, rank, ce, xe, is_final in gw_history
        ],
        "latest_roster": {
            "gw": newest_gw_with_picks, "players": latest_roster,
            "is_final": newest_gw_with_picks <= latest_gw,
        },
        "rosters_by_gw": {str(gw): players for gw, players in rosters_by_gw.items()},
        "transfers": [
            {"gw": gw, "player_in": pin, "player_out": pout, "time": t}
            for gw, pin, pout, t in transfers
        ],
    }


def owner_block(conn, latest_gw: int) -> dict:
    mgr_id = conn.execute("SELECT manager_id FROM managers WHERE is_owner = 1").fetchone()[0]
    return manager_detail(conn, mgr_id, latest_gw)


def all_managers_detail(conn, latest_gw: int) -> dict:
    ids = conn.execute("SELECT manager_id FROM managers").fetchall()
    return {str(mgr_id): manager_detail(conn, mgr_id, latest_gw) for (mgr_id,) in ids}


def owner_next_fixture(upcoming_matches: list[dict], owner_name: str) -> dict | None:
    for m in upcoming_matches:
        if m["a"]["name"] == owner_name:
            return m["b"]
        if m["b"]["name"] == owner_name:
            return m["a"]
    return None


def build_digest() -> dict:
    conn = ingest.connect()
    status = gw_status(conn)
    latest = status["current_gw"]

    owner_blk = owner_block(conn, latest) if latest else None
    upcoming_matches = fixtures_for_gw(conn, status["next_gw"])

    d = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "league": league_info(conn),
        "gw_status": status,
        "gates": gates(latest or 0),
        "standings": standings(conn, latest) if latest else [],
        "standings_gw": latest,
        "upcoming_fixtures": {"gw": status["next_gw"], "matches": upcoming_matches},
        "last_results": {"gw": latest, "matches": results_for_gw(conn, latest)} if latest else None,
        "alerts": alerts(conn),
        "managers": all_managers(conn),
        "leaderboard": leaderboard(conn, latest) if latest else [],
        "recaps": [gw_recap_summary(conn, gw) for gw in status["data_checked_gws"]],
        "owner": owner_blk,
        "owner_next_opponent": owner_next_fixture(upcoming_matches, owner_blk["display_name"]) if owner_blk else None,
        "managers_detail": all_managers_detail(conn, latest) if latest else {},
        "all_matchups_by_gw": {str(gw): results_for_gw(conn, gw) for gw in status["data_checked_gws"]},
        "all_standings_by_gw": {str(gw): standings(conn, gw) for gw in status["data_checked_gws"]},
        "club_kits": club_kits(conn),
        "price_movers": price_movers(conn),
    }
    conn.close()
    return d


def run() -> int:
    print("Phase 7 — digest export\n")
    digest = build_digest()
    config.DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.DIGEST_DIR / "season.json"
    out_path.write_text(json.dumps(digest, indent=2))
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(run())
