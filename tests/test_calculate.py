"""Regression tests for src.calculate's pure logic — no I/O, no fixtures.

best_xi_points() is the trickiest piece of hand-written logic in the
codebase (a brute-force search over legal FPL formations). These cases were
independently hand-verified against real GW1-3 data during Phase 5 (see
SPEC.md); encoding them here means a future change that breaks the formation
search fails a test immediately instead of silently producing a wrong
efficiency number.
"""

from src.calculate import best_xi_points


def test_owner_gw3_matches_hand_verified_value():
    # Luel Waktola's real GW3 squad (raw points by player), hand-verified in
    # Phase 5 against the live FPL site: optimal XI = 68 (formation 5-4-1).
    squad = [
        ("GKP", 2), ("GKP", 0),
        ("DEF", 4), ("DEF", 6), ("DEF", 4), ("DEF", 15), ("DEF", 8),
        ("MID", 8), ("MID", 6), ("MID", 3), ("MID", 3), ("MID", 3),
        ("FWD", 9), ("FWD", 1), ("FWD", 1),
    ]
    assert best_xi_points(squad) == 68


def test_cmazz_gw1_matches_hand_verified_value():
    # Chris Mazzatta's real GW1 squad, also hand-verified in Phase 5: 58.
    squad = [
        ("GKP", 1), ("GKP", 0),
        ("DEF", 5), ("DEF", 9), ("DEF", 10), ("DEF", 1), ("DEF", 2),
        ("MID", 6), ("MID", 2), ("MID", 2), ("MID", 8), ("MID", 2),
        ("FWD", 0), ("FWD", 11), ("FWD", 0),
    ]
    assert best_xi_points(squad) == 58


def test_respects_formation_minimums_not_just_top_scorers():
    # 5 GKPs would be illegal even if they outscored everyone - the search
    # must respect "exactly 1 GKP, 3-5 DEF, 2-5 MID, 1-3 FWD" rather than
    # just picking the 11 highest raw scores regardless of position.
    squad = [
        ("GKP", 100), ("GKP", 99),
        ("DEF", 1), ("DEF", 1), ("DEF", 1), ("DEF", 1), ("DEF", 1),
        ("MID", 1), ("MID", 1), ("MID", 1), ("MID", 1), ("MID", 1),
        ("FWD", 1), ("FWD", 1), ("FWD", 1),
    ]
    # Best legal XI: 1 GKP (100) + 5 DEF (5) + 4 MID (4) + 1 FWD (1) = 110,
    # or any other (d,m,f) with d+m+f=10 - all non-GKP players score 1, so
    # every legal formation totals 100 + 10 = 110. The second GKP (99) can
    # never enter the XI no matter how high it scores.
    assert best_xi_points(squad) == 110


def test_empty_squad_returns_zero():
    assert best_xi_points([]) == 0
