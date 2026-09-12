"""Phase 1 — verify the FPL API.

This script assumes nothing. It probes each endpoint the design depends on and
reports what actually came back: status, shape, field names, and whether the
specific unknowns blocking Phase 2 can be answered.

It writes NOTHING to a database. It creates no tables. Its only job is to
replace assumptions with observations.

Usage:
    python -m src.verify_api
    python -m src.verify_api --selftest     # no network; exercises reporting
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from . import config
from .fpl_client import FPLClient, FetchResult

REPORT_PATH = config.PHASE1_OUTPUT / "VERIFICATION_REPORT.md"
FINDINGS_PATH = config.PHASE1_OUTPUT / "findings.json"


# --- shape description ------------------------------------------------------

def describe(obj: Any, depth: int = 0, max_keys: int = 40) -> str:
    """Human-readable description of a JSON structure, without dumping data."""
    if isinstance(obj, dict):
        keys = list(obj.keys())[:max_keys]
        more = "" if len(obj) <= max_keys else f" (+{len(obj) - max_keys} more)"
        return "object with keys: " + ", ".join(f"`{k}`" for k in keys) + more
    if isinstance(obj, list):
        if not obj:
            return "empty list"
        head = obj[0]
        if isinstance(head, dict):
            keys = list(head.keys())[:max_keys]
            more = "" if len(head) <= max_keys else f" (+{len(head) - max_keys} more)"
            return (
                f"list of {len(obj)} objects; first item keys: "
                + ", ".join(f"`{k}`" for k in keys) + more
            )
        return f"list of {len(obj)} {type(head).__name__} values"
    return type(obj).__name__


def field_presence(items: list[dict], fields: list[str]) -> dict[str, str]:
    """For a list of records, report which of `fields` are present and non-null."""
    out = {}
    total = len(items)
    for f in fields:
        present = sum(1 for it in items if isinstance(it, dict) and f in it)
        nonnull = sum(
            1 for it in items
            if isinstance(it, dict) and it.get(f) is not None
        )
        if present == 0:
            out[f] = "ABSENT"
        elif nonnull == 0:
            out[f] = f"present but all null ({present}/{total})"
        elif nonnull < total:
            out[f] = f"present, {nonnull}/{total} non-null"
        else:
            out[f] = f"present in all {total}"
    return out


# --- the verifier -----------------------------------------------------------

class Verifier:
    def __init__(self, client: FPLClient):
        self.c = client
        self.findings: dict[str, Any] = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "league_id": config.LEAGUE_ID,
            "endpoints": {},
            "unknowns": {},
            "warnings": [],
            "errors": [],
        }
        self.bootstrap: Optional[dict] = None
        self.entries: list[dict] = []
        self.events: list[dict] = []

    def record(self, key: str, path: str, res: FetchResult,
               shape: Optional[str] = None, extra: Optional[dict] = None) -> None:
        entry = {
            "path": path,
            "ok": res.ok,
            "status": res.status_code,
            "elapsed_ms": res.elapsed_ms,
            "attempts": res.attempts,
            "summary": res.summary(),
            "shape": shape,
            "notes": res.notes,
        }
        if res.error:
            entry["error"] = res.error
        if extra:
            entry.update(extra)
        self.findings["endpoints"][key] = entry
        flag = "OK  " if res.ok else "FAIL"
        print(f"  [{flag}] {path} — {res.summary()}")

    def warn(self, msg: str) -> None:
        self.findings["warnings"].append(msg)
        print(f"  !! {msg}")

    def fail(self, msg: str) -> None:
        self.findings["errors"].append(msg)
        print(f"  XX {msg}")

    # -- probes ----------------------------------------------------------

    def probe_bootstrap(self) -> bool:
        print("\n[1/8] bootstrap-static")
        res = self.c.get("bootstrap-static/")
        shape = describe(res.json_body) if res.ok else None
        extra = {}
        if res.ok and isinstance(res.json_body, dict):
            b = res.json_body
            self.bootstrap = b
            self.events = b.get("events") or []
            extra = {
                "top_level_keys": list(b.keys()),
                "player_count": len(b.get("elements") or []),
                "club_count": len(b.get("teams") or []),
                "event_count": len(self.events),
            }
            elements = b.get("elements") or []
            if elements:
                extra["element_field_check"] = field_presence(
                    elements[:200],
                    ["id", "first_name", "second_name", "web_name",
                     "element_type", "team", "now_cost", "status", "news",
                     "chance_of_playing_next_round", "selected_by_percent",
                     "form", "total_points", "expected_goals",
                     "expected_assists", "defensive_contribution"],
                )
        self.record("bootstrap-static", "bootstrap-static/", res, shape, extra)

        if not res.ok:
            self.fail(
                "bootstrap-static failed. This is the root dependency — if it "
                "is unreachable, nothing else in the design works. Check "
                "whether the API is reachable from this machine at all."
            )
            return False
        return True

    def probe_events(self) -> None:
        print("\n[2/8] gameweek status flags")
        if not self.events:
            self.fail("No events in bootstrap-static; cannot determine gameweeks.")
            return

        sample_keys = list(self.events[0].keys())
        finished = [e for e in self.events if e.get("finished")]
        checked = [e for e in self.events if e.get("data_checked")]
        current = next((e for e in self.events if e.get("is_current")), None)
        nxt = next((e for e in self.events if e.get("is_next")), None)

        # Which flag actually means "settled"? Compare the two.
        divergent = [
            e.get("id") for e in self.events
            if bool(e.get("finished")) != bool(e.get("data_checked"))
        ]

        info = {
            "event_keys": sample_keys,
            "total_events": len(self.events),
            "finished_ids": [e.get("id") for e in finished],
            "data_checked_ids": [e.get("id") for e in checked],
            "current_event": current.get("id") if current else None,
            "next_event": nxt.get("id") if nxt else None,
            "flags_disagree_on": divergent,
            "has_data_checked_field": "data_checked" in sample_keys,
        }
        self.findings["unknowns"]["finalization_flag"] = info

        print(f"  finished: {info['finished_ids']}")
        print(f"  data_checked: {info['data_checked_ids']}")
        print(f"  current GW: {info['current_event']}  next GW: {info['next_event']}")

        if not info["has_data_checked_field"]:
            self.warn(
                "No `data_checked` field on events. The finalization gate must "
                "use a different signal — review the event keys listed in the "
                "report before building Phase 3."
            )
        elif divergent:
            print(f"  flags disagree on GWs: {divergent} (useful — shows they differ)")

    def probe_fixtures(self) -> None:
        print("\n[3/8] fixtures")
        res = self.c.get("fixtures/")
        shape = describe(res.json_body) if res.ok else None
        self.record("fixtures", "fixtures/", res, shape)

    def probe_league(self) -> None:
        print("\n[4/8] H2H league standings")
        path = f"leagues-h2h/{config.LEAGUE_ID}/standings/"
        res = self.c.get(path)
        shape = describe(res.json_body) if res.ok else None
        extra: dict[str, Any] = {}

        if res.ok and isinstance(res.json_body, dict):
            body = res.json_body
            league = body.get("league") or {}
            standings = (body.get("standings") or {}).get("results") or []
            self.entries = standings
            extra = {
                "league_object_keys": list(league.keys()),
                "league_object": league,
                "standings_count": len(standings),
                "standings_keys": list(standings[0].keys()) if standings else [],
                "has_next_page": (body.get("standings") or {}).get("has_next"),
            }

            # UNKNOWN 1: knockout configuration
            ko = None
            for candidate in ("ko_rounds", "knockout_rounds", "ko_round"):
                if candidate in league:
                    ko = {"field": candidate, "value": league[candidate]}
                    break
            self.findings["unknowns"]["knockout_config"] = ko or {
                "field": None,
                "value": None,
                "note": "No knockout field found in the league object. "
                        "Check the full league object in the report.",
            }

            # Membership cross-check
            if len(standings) != config.EXPECTED_TEAM_COUNT:
                self.warn(
                    f"League has {len(standings)} entries, expected "
                    f"{config.EXPECTED_TEAM_COUNT}. Membership has changed — "
                    "the roster in config.py needs updating."
                )
            self.findings["unknowns"]["membership"] = self._compare_membership(standings)

        self.record("h2h-standings", path, res, shape, extra)
        if not res.ok:
            self.fail(
                "H2H standings failed. Without this we cannot resolve manager "
                "entry IDs, which blocks every per-manager endpoint."
            )

    def _compare_membership(self, standings: list[dict]) -> dict:
        live = {
            (s.get("entry_name") or "").strip(): {
                "entry_id": s.get("entry"),
                "player_name": (s.get("player_name") or "").strip(),
            }
            for s in standings
        }
        expected = {name.strip(): mgr for name, mgr in config.EXPECTED_MEMBERS}

        matched, name_mismatch, missing, unexpected = [], [], [], []
        for team, mgr in expected.items():
            if team in live:
                if live[team]["player_name"].lower() != mgr.lower():
                    name_mismatch.append(
                        {"team": team, "expected_manager": mgr,
                         "live_manager": live[team]["player_name"]}
                    )
                matched.append({"team": team, "entry_id": live[team]["entry_id"]})
            else:
                missing.append({"team": team, "expected_manager": mgr})
        for team, data in live.items():
            if team not in expected:
                unexpected.append({"team": team, **data})

        if missing or unexpected:
            self.warn(
                f"Membership differs from config: {len(missing)} expected team(s) "
                f"not found, {len(unexpected)} unrecognised team(s) present. "
                "Team names may simply have been changed — review before Phase 2."
            )
        return {
            "matched": matched,
            "manager_name_mismatches": name_mismatch,
            "expected_but_missing": missing,
            "present_but_unexpected": unexpected,
        }

    def probe_h2h_matches(self) -> None:
        print("\n[5/8] H2H matches + fixture structure")
        path = f"leagues-h2h-matches/league/{config.LEAGUE_ID}/?page=1"
        res = self.c.get(path)
        shape = describe(res.json_body) if res.ok else None
        extra: dict[str, Any] = {}
        all_matches: list[dict] = []

        if res.ok and isinstance(res.json_body, dict):
            body = res.json_body
            results = body.get("results") or []
            all_matches = list(results)
            extra = {
                "top_level_keys": list(body.keys()),
                "page_size": len(results),
                "has_next": body.get("has_next"),
                "match_keys": list(results[0].keys()) if results else [],
            }

            # UNKNOWN 5: pagination behaviour
            pages_pulled = 1
            while body.get("has_next") and pages_pulled < 12:
                pages_pulled += 1
                nxt = self.c.get(
                    f"leagues-h2h-matches/league/{config.LEAGUE_ID}/?page={pages_pulled}"
                )
                if not nxt.ok or not isinstance(nxt.json_body, dict):
                    self.warn(f"Pagination stopped at page {pages_pulled}.")
                    break
                body = nxt.json_body
                all_matches.extend(body.get("results") or [])
            extra["pages_pulled"] = pages_pulled
            extra["total_matches_seen"] = len(all_matches)

            self.findings["unknowns"]["pagination"] = {
                "page_size": extra["page_size"],
                "pages_pulled": pages_pulled,
                "total_matches": len(all_matches),
                "mechanism": "?page=N with has_next boolean",
            }

            # UNKNOWN 2: how are 38 GWs structured for 18 managers?
            self.findings["unknowns"]["fixture_structure"] = self._analyse_fixtures(
                all_matches
            )

        self.record("h2h-matches", path, res, shape, extra)

    def _analyse_fixtures(self, matches: list[dict]) -> dict:
        if not matches:
            return {"note": "No matches returned; cannot analyse structure."}

        by_gw = Counter(m.get("event") for m in matches)
        gws = sorted(g for g in by_gw if g is not None)
        pairings = Counter()
        per_manager_gws = Counter()
        knockout_flagged = []

        for m in matches:
            a, b = m.get("entry_1_entry"), m.get("entry_2_entry")
            if a is not None and b is not None:
                pairings[tuple(sorted((a, b)))] += 1
            for side in (a, b):
                if side is not None:
                    per_manager_gws[side] += 1
            if m.get("is_knockout") or m.get("knockout_name"):
                knockout_flagged.append(m.get("event"))

        meeting_counts = Counter(pairings.values())
        return {
            "gameweeks_covered": gws,
            "gameweek_span": f"{min(gws)}-{max(gws)}" if gws else None,
            "matches_per_gameweek": dict(sorted(by_gw.items(), key=lambda x: (x[0] is None, x[0]))),
            "distinct_pairings": len(pairings),
            "times_each_pairing_occurs": dict(meeting_counts),
            "fixtures_per_manager": dict(Counter(per_manager_gws.values())),
            "knockout_flagged_gameweeks": sorted(set(knockout_flagged)),
            "interpretation": (
                "With 18 managers each has 17 opponents; a clean double "
                "round-robin is 34 gameweeks, so how the remaining gameweeks "
                "are filled is visible in `times_each_pairing_occurs`."
            ),
        }

    def probe_live(self) -> None:
        print("\n[6/8] live gameweek stats")
        finished = self.findings.get("unknowns", {}).get("finalization_flag", {})
        ids = finished.get("data_checked_ids") or finished.get("finished_ids") or []
        gw = ids[-1] if ids else 1
        path = f"event/{gw}/live/"
        res = self.c.get(path)
        shape = describe(res.json_body) if res.ok else None
        extra: dict[str, Any] = {"gameweek_probed": gw}

        if res.ok and isinstance(res.json_body, dict):
            elements = res.json_body.get("elements") or []
            extra["element_count"] = len(elements)
            if elements:
                first = elements[0]
                extra["element_keys"] = list(first.keys())
                stats = first.get("stats") or {}
                extra["stats_keys"] = list(stats.keys())
                sample = [e.get("stats", {}) for e in elements[:200]]
                extra["stats_field_check"] = field_presence(
                    sample,
                    ["minutes", "goals_scored", "assists", "clean_sheets",
                     "goals_conceded", "own_goals", "penalties_saved",
                     "penalties_missed", "saves", "yellow_cards", "red_cards",
                     "bonus", "bps", "total_points", "expected_goals",
                     "expected_assists", "defensive_contribution"],
                )
        self.record("event-live", path, res, shape, extra)

    def probe_entry_endpoints(self) -> None:
        print("\n[7/8] per-manager endpoints")
        if not self.entries:
            self.fail("No entries available — skipping per-manager probes.")
            return

        owner = next(
            (e for e in self.entries
             if (e.get("entry_name") or "").strip() == config.OWNER_TEAM_NAME),
            self.entries[0],
        )
        entry_id = owner.get("entry")
        print(f"  using entry {entry_id} ({owner.get('entry_name')})")

        res = self.c.get(f"entry/{entry_id}/")
        self.record("entry", f"entry/{entry_id}/", res,
                    describe(res.json_body) if res.ok else None)

        res = self.c.get(f"entry/{entry_id}/history/")
        extra: dict[str, Any] = {}
        if res.ok and isinstance(res.json_body, dict):
            h = res.json_body
            current = h.get("current") or []
            extra = {
                "top_level_keys": list(h.keys()),
                "gameweeks_in_history": len(current),
                "current_keys": list(current[0].keys()) if current else [],
                "chips_played": h.get("chips"),
                "history_field_check": field_presence(
                    current,
                    ["event", "points", "total_points", "event_transfers",
                     "event_transfers_cost", "points_on_bench", "value",
                     "bank", "overall_rank", "rank"],
                ) if current else {},
            }
        self.record("entry-history", f"entry/{entry_id}/history/", res,
                    describe(res.json_body) if res.ok else None, extra)

        # Picks for a finished gameweek
        ff = self.findings.get("unknowns", {}).get("finalization_flag", {})
        done = ff.get("data_checked_ids") or ff.get("finished_ids") or [1]
        gw = done[-1]
        path = f"entry/{entry_id}/event/{gw}/picks/"
        res = self.c.get(path)
        extra = {"gameweek_probed": gw}
        if res.ok and isinstance(res.json_body, dict):
            p = res.json_body
            picks = p.get("picks") or []
            extra.update({
                "top_level_keys": list(p.keys()),
                "pick_count": len(picks),
                "pick_keys": list(picks[0].keys()) if picks else [],
                "entry_history_keys": list((p.get("entry_history") or {}).keys()),
                "automatic_subs": p.get("automatic_subs"),
                "active_chip": p.get("active_chip"),
            })
            if len(picks) != 15:
                self.warn(f"Expected 15 picks, got {len(picks)} for GW{gw}.")
        self.record("entry-picks", path, res,
                    describe(res.json_body) if res.ok else None, extra)

        res = self.c.get(f"entry/{entry_id}/transfers/")
        extra = {}
        if res.ok and isinstance(res.json_body, list):
            extra = {
                "transfer_count": len(res.json_body),
                "transfer_keys": list(res.json_body[0].keys()) if res.json_body else [],
            }
        self.record("entry-transfers", f"entry/{entry_id}/transfers/", res,
                    describe(res.json_body) if res.ok else None, extra)

        # UNKNOWN 3: pre-deadline visibility of ANOTHER manager's picks
        other = next(
            (e for e in self.entries if e.get("entry") != entry_id), None
        )
        next_gw = ff.get("next_event")
        if other and next_gw:
            path = f"entry/{other.get('entry')}/event/{next_gw}/picks/"
            res = self.c.get(path)
            visible = bool(res.ok and (res.json_body or {}).get("picks"))
            self.findings["unknowns"]["pre_deadline_visibility"] = {
                "probed_entry": other.get("entry"),
                "probed_team": other.get("entry_name"),
                "upcoming_gameweek": next_gw,
                "status": res.status_code,
                "picks_visible_before_deadline": visible,
                "interpretation": (
                    "Visible — pre-deadline capture of other managers is possible."
                    if visible else
                    "Not visible, as expected. Post-deadline capture only, "
                    "which is what the design already assumes."
                ),
            }
            self.record("entry-picks-upcoming", path, res,
                        describe(res.json_body) if res.ok else None,
                        {"picks_visible": visible})
        else:
            self.findings["unknowns"]["pre_deadline_visibility"] = {
                "note": "Could not test — no upcoming gameweek identified."
            }

    def probe_element_summary(self) -> None:
        print("\n[8/8] element-summary")
        elements = (self.bootstrap or {}).get("elements") or []
        if not elements:
            return
        pid = elements[0].get("id")
        path = f"element-summary/{pid}/"
        res = self.c.get(path)
        self.record("element-summary", path, res,
                    describe(res.json_body) if res.ok else None,
                    {"player_id_probed": pid})

    def run(self) -> dict:
        print(f"Phase 1 verification — league {config.LEAGUE_ID}")
        print(f"Base URL: {config.BASE_URL}")
        print("Nothing will be written to a database.\n")

        if not self.probe_bootstrap():
            return self.findings
        self.probe_events()
        self.probe_fixtures()
        self.probe_league()
        self.probe_h2h_matches()
        self.probe_live()
        self.probe_entry_endpoints()
        self.probe_element_summary()

        self.findings["total_requests"] = self.c.request_count
        return self.findings


# --- reporting --------------------------------------------------------------

def render_report(f: dict) -> str:
    L: list[str] = []
    A = L.append

    A("# Phase 1 — FPL API Verification Report")
    A("")
    A(f"- Run at: `{f.get('run_at')}`")
    A(f"- League: `{f.get('league_id')}`")
    A(f"- Requests made: {f.get('total_requests', 'n/a')}")
    A("")

    errs, warns = f.get("errors") or [], f.get("warnings") or []
    if errs:
        A("## Errors")
        A("")
        for e in errs:
            A(f"- **{e}**")
        A("")
    if warns:
        A("## Warnings")
        A("")
        for w in warns:
            A(f"- {w}")
        A("")
    if not errs and not warns:
        A("No errors or warnings.")
        A("")

    A("## Endpoint results")
    A("")
    A("| Endpoint | Status | Time | Result |")
    A("|---|---|---|---|")
    for key, e in (f.get("endpoints") or {}).items():
        mark = "OK" if e.get("ok") else "FAIL"
        ms = f"{e['elapsed_ms']}ms" if e.get("elapsed_ms") else "—"
        A(f"| `{e.get('path')}` | {mark} {e.get('status') or ''} | {ms} | {e.get('summary')} |")
    A("")

    A("## The blocking unknowns")
    A("")
    u = f.get("unknowns") or {}

    A("### 1. Knockout configuration")
    A("")
    ko = u.get("knockout_config")
    if ko and ko.get("field"):
        A(f"Found field `{ko['field']}` = `{ko['value']}`.")
        if ko.get("value"):
            A("")
            A("The league HAS knockout rounds. Projections become playoff odds.")
        else:
            A("")
            A("No knockout rounds. Projections become title-race odds instead.")
    else:
        A("Not determined. See the full league object below.")
    A("")

    A("### 2. Fixture structure (18 managers, 38 gameweeks)")
    A("")
    fs = u.get("fixture_structure") or {}
    if fs.get("gameweeks_covered"):
        A(f"- Gameweeks covered: {fs.get('gameweek_span')}")
        A(f"- Distinct pairings: {fs.get('distinct_pairings')}")
        A(f"- Times each pairing occurs: `{fs.get('times_each_pairing_occurs')}`")
        A(f"- Fixtures per manager: `{fs.get('fixtures_per_manager')}`")
        A(f"- Knockout-flagged gameweeks: {fs.get('knockout_flagged_gameweeks')}")
    else:
        A(fs.get("note", "Not determined."))
    A("")

    A("### 3. Pre-deadline visibility of other managers' picks")
    A("")
    pv = u.get("pre_deadline_visibility") or {}
    if "picks_visible_before_deadline" in pv:
        A(f"- Probed: {pv.get('probed_team')} (entry {pv.get('probed_entry')}), GW{pv.get('upcoming_gameweek')}")
        A(f"- HTTP status: {pv.get('status')}")
        A(f"- Visible: **{pv.get('picks_visible_before_deadline')}**")
        A(f"- {pv.get('interpretation')}")
    else:
        A(pv.get("note", "Not tested."))
    A("")

    A("### 4. Finalization flag")
    A("")
    ff = u.get("finalization_flag") or {}
    if ff:
        A(f"- `data_checked` field present: **{ff.get('has_data_checked_field')}**")
        A(f"- Finished gameweeks: `{ff.get('finished_ids')}`")
        A(f"- Data-checked gameweeks: `{ff.get('data_checked_ids')}`")
        A(f"- Flags disagree on: `{ff.get('flags_disagree_on')}`")
        A(f"- Current GW: {ff.get('current_event')} — Next GW: {ff.get('next_event')}")
        A("")
        A("Available event fields:")
        A("")
        A("```")
        A(", ".join(ff.get("event_keys") or []))
        A("```")
    A("")

    A("### 5. Pagination")
    A("")
    pg = u.get("pagination") or {}
    if pg:
        A(f"- Mechanism: {pg.get('mechanism')}")
        A(f"- Page size: {pg.get('page_size')}")
        A(f"- Pages pulled: {pg.get('pages_pulled')}")
        A(f"- Total matches seen: {pg.get('total_matches')}")
    else:
        A("Not determined.")
    A("")

    A("## Membership cross-check")
    A("")
    mem = u.get("membership") or {}
    if mem:
        A(f"- Matched teams: {len(mem.get('matched') or [])}")
        A(f"- Manager-name mismatches: {len(mem.get('manager_name_mismatches') or [])}")
        A(f"- Expected but missing: {len(mem.get('expected_but_missing') or [])}")
        A(f"- Present but unexpected: {len(mem.get('present_but_unexpected') or [])}")
        for item in mem.get("manager_name_mismatches") or []:
            A(f"  - `{item['team']}`: expected {item['expected_manager']}, live {item['live_manager']}")
        for item in mem.get("expected_but_missing") or []:
            A(f"  - MISSING: `{item['team']}` ({item['expected_manager']})")
        for item in mem.get("present_but_unexpected") or []:
            A(f"  - NEW: `{item['team']}` ({item.get('player_name')}) entry {item.get('entry_id')}")
    A("")

    A("## Observed field names")
    A("")
    for key, e in (f.get("endpoints") or {}).items():
        interesting = {
            k: v for k, v in e.items()
            if k.endswith("_keys") or k.endswith("_field_check")
        }
        if not interesting:
            continue
        A(f"### `{e.get('path')}`")
        A("")
        for k, v in interesting.items():
            A(f"**{k}**")
            A("")
            A("```")
            A(json.dumps(v, indent=2)[:4000])
            A("```")
            A("")

    A("## Full league object")
    A("")
    lo = ((f.get("endpoints") or {}).get("h2h-standings") or {}).get("league_object")
    A("```json")
    A(json.dumps(lo, indent=2) if lo else "not retrieved")
    A("```")
    A("")

    A("---")
    A("")
    A("Paste this report back into Claude. The spec's data-source section gets")
    A("rewritten to match these observations before Phase 2 creates any table.")
    return "\n".join(L)


def write_outputs(findings: dict) -> None:
    config.PHASE1_OUTPUT.mkdir(parents=True, exist_ok=True)
    FINDINGS_PATH.write_text(json.dumps(findings, indent=2, default=str))
    REPORT_PATH.write_text(render_report(findings))
    print(f"\nWrote {REPORT_PATH}")
    print(f"Wrote {FINDINGS_PATH}")


# --- selftest ---------------------------------------------------------------

def selftest() -> int:
    """Exercise the reporting path with synthetic data. Makes no requests."""
    print("Selftest — no network requests will be made.\n")
    fake = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "league_id": config.LEAGUE_ID,
        "total_requests": 0,
        "endpoints": {
            "bootstrap-static": {
                "path": "bootstrap-static/", "ok": True, "status": 200,
                "elapsed_ms": 180, "summary": "HTTP 200 in 180ms",
                "top_level_keys": ["events", "teams", "elements"],
                "element_field_check": {"id": "present in all 200"},
            },
            "h2h-standings": {
                "path": "leagues-h2h/683383/standings/", "ok": True,
                "status": 200, "elapsed_ms": 210, "summary": "HTTP 200 in 210ms",
                "league_object": {"id": 683383, "name": "Almost all Americans",
                                  "ko_rounds": 0},
            },
        },
        "unknowns": {
            "knockout_config": {"field": "ko_rounds", "value": 0},
            "fixture_structure": {
                "gameweeks_covered": [1, 2, 3],
                "gameweek_span": "1-3", "distinct_pairings": 27,
                "times_each_pairing_occurs": {1: 27},
                "fixtures_per_manager": {3: 18},
                "knockout_flagged_gameweeks": [],
            },
            "pre_deadline_visibility": {
                "probed_team": "CMazz", "probed_entry": 111,
                "upcoming_gameweek": 4, "status": 200,
                "picks_visible_before_deadline": False,
                "interpretation": "Not visible, as expected.",
            },
            "finalization_flag": {
                "has_data_checked_field": True,
                "finished_ids": [1, 2, 3], "data_checked_ids": [1, 2, 3],
                "flags_disagree_on": [], "current_event": 3, "next_event": 4,
                "event_keys": ["id", "deadline_time", "finished", "data_checked"],
            },
            "pagination": {"mechanism": "?page=N", "page_size": 50,
                           "pages_pulled": 2, "total_matches": 81},
            "membership": {"matched": [{"team": "CMazz", "entry_id": 111}],
                           "manager_name_mismatches": [],
                           "expected_but_missing": [],
                           "present_but_unexpected": []},
        },
        "warnings": ["example warning"],
        "errors": [],
    }
    report = render_report(fake)
    assert "Phase 1 — FPL API Verification Report" in report
    assert "ko_rounds" in report
    assert "Not visible, as expected." in report
    print(report[:1200])
    print("\n...\n")
    print(f"Report renders correctly ({len(report)} chars). Selftest passed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 1 FPL API verification")
    ap.add_argument("--selftest", action="store_true",
                    help="exercise reporting without network access")
    ap.add_argument("--no-archive", action="store_true",
                    help="do not save raw payloads")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    client = FPLClient(
        archive_dir=None if args.no_archive else config.PHASE1_PAYLOADS
    )
    verifier = Verifier(client)
    findings = verifier.run()
    write_outputs(findings)

    if findings.get("errors"):
        print("\nCompleted WITH ERRORS. Do not proceed to Phase 2.")
        return 1
    print("\nCompleted. Review the report, then paste it back into Claude.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
