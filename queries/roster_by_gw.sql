-- "What was <manager>'s roster in GW<N>?"
-- Params: :entry_id (FPL entry id), :gw
-- Fact: stored picks, joined to that gameweek's finalized player stats.
SELECT
    pl.web_name,
    pl.position,
    p.slot,
    CASE WHEN p.is_starter THEN 'XI' ELSE 'Bench' END AS status,
    CASE WHEN p.is_captain THEN 'C' WHEN p.is_vice THEN 'VC' ELSE '' END AS armband,
    p.multiplier,
    s.total_points AS raw_points,
    p.points_scored AS points_with_multiplier
FROM raw_manager_gw_picks p
JOIN managers m ON m.manager_id = p.manager_id
JOIN players pl ON pl.season_id = p.season_id AND pl.player_id = p.player_id
JOIN raw_player_gw_stats s ON s.season_id = p.season_id AND s.gw_id = p.gw_id AND s.player_id = p.player_id
WHERE m.entry_id = :entry_id AND p.gw_id = :gw
ORDER BY p.slot;
