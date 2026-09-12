-- "Who did everyone captain in GW<N>?"
-- Params: :gw
-- Fact: stored captain picks and the raw points that player scored, joined
-- to the applied multiplier (2 normal, 3 on Triple Captain).
SELECT
    m.display_name,
    tn.team_name,
    pl.web_name AS captain,
    p.multiplier,
    s.total_points AS raw_points,
    p.points_scored AS captain_contribution
FROM raw_manager_gw_picks p
JOIN managers m ON m.manager_id = p.manager_id
JOIN team_names tn ON tn.manager_id = m.manager_id
JOIN players pl ON pl.season_id = p.season_id AND pl.player_id = p.player_id
JOIN raw_player_gw_stats s ON s.season_id = p.season_id AND s.gw_id = p.gw_id AND s.player_id = p.player_id
WHERE p.gw_id = :gw AND p.is_captain = 1
ORDER BY p.points_scored DESC;
