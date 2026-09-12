-- "Who was first after GW<N>?" / "What were the standings after GW<N>?"
-- Params: :gw
-- Fact, but with a real gap: only gameweeks where a snapshot was actually
-- captured have rows here. GW1-2 of this season have none — the live FPL
-- standings endpoint has no history parameter, so those snapshots are
-- permanently unavailable (see data_issues, category='historical_gap').
-- An empty result for a given :gw means exactly that, not a query error.
SELECT
    s.rank,
    m.display_name,
    tn.team_name,
    s.wins, s.draws, s.losses,
    s.league_points,
    s.points_for,
    s.points_against,
    s.streak
FROM standings_snapshots s
JOIN managers m ON m.manager_id = s.manager_id
JOIN team_names tn ON tn.manager_id = m.manager_id
WHERE s.gw_id = :gw
ORDER BY s.rank;
