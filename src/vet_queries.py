"""One-off harness to vet every query in queries/*.sql against the live
database with real parameters, so the library is provably tested before
being called 'vetted' in the README. Not part of the daily pipeline.

Usage:
    python -m src.vet_queries
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import ingest, config

OWNER_ENTRY = 3023365
OPPONENT_ENTRY = 1145577  # CMazz

PARAM_SETS = {
    "roster_by_gw.sql": {"entry_id": OWNER_ENTRY, "gw": 3},
    "captains_by_gw.sql": {"gw": 3},
    "h2h_history.sql": {"entry_a": OWNER_ENTRY, "entry_b": OPPONENT_ENTRY},
    "manager_vs_manager_record.sql": {"entry_a": OWNER_ENTRY, "entry_b": OPPONENT_ENTRY},
    "standings_at_gw.sql": {"gw": 3},
    "ledger_manager_season.sql": {"entry_id": OWNER_ENTRY, "through_gw": 3},
    "manager_skill_summary.sql": {"entry_id": OWNER_ENTRY, "through_gw": 3},
    "gw_extremes.sql": {"gw": 1},
    "open_data_issues.sql": {},
    "gated_metrics_status.sql": {"through_gw": 3},
}


def split_statements(sql_text: str) -> list[str]:
    # Strip full-line comments, then split on ';' — good enough for this
    # hand-written library (no semicolons inside string literals here).
    lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("--")]
    cleaned = "\n".join(lines)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def run() -> int:
    conn = ingest.connect()
    conn.row_factory = None
    failures = 0

    for path in sorted(Path(config.REPO_ROOT / "queries").glob("*.sql")):
        params = PARAM_SETS.get(path.name)
        if params is None:
            print(f"SKIP  {path.name} — no param set defined in this harness")
            continue
        statements = split_statements(path.read_text())
        for i, stmt in enumerate(statements, 1):
            try:
                cur = conn.execute(stmt, params)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                print(f"OK    {path.name} [stmt {i}/{len(statements)}] -> {len(rows)} row(s), cols={cols}")
                if rows[:1]:
                    print(f"        sample: {dict(zip(cols, rows[0]))}")
            except Exception as e:  # noqa: BLE001 — this is a vetting harness
                failures += 1
                print(f"FAIL  {path.name} [stmt {i}/{len(statements)}]: {e}")

    conn.close()
    print(f"\n{failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
