-- "Who was first after GW<N>?" / "What were the standings after GW<N>?"
-- Params: :gw
-- Fact for W/D/L/points/streak. `rank` is only Fact when source='fpl_h2h_endpoint'
-- (fetched live from FPL). For source='reconstructed' rows (currently GW1-2),
-- rank is NULL on purpose: FPL's H2H tiebreak rule for ties was never
-- empirically verified, so a rank number there would be invented rather than
-- computed. W/D/L/points/streak are still exact either way, aggregated from
-- immutable raw match data. See data_issues, category='historical_gap', for
-- the full explanation, and SPEC.md §13.
SELECT
    s.rank,
    m.display_name,
    tn.team_name,
    s.wins, s.draws, s.losses,
    s.league_points,
    s.points_for,
    s.points_against,
    s.streak,
    s.source
FROM standings_snapshots s
JOIN managers m ON m.manager_id = s.manager_id
JOIN team_names tn ON tn.manager_id = m.manager_id
WHERE s.gw_id = :gw
ORDER BY (s.rank IS NULL), s.rank, s.league_points DESC, s.points_for DESC;
