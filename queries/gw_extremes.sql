-- Weekly-recap building blocks for a single gameweek (Tier 1, always shown
-- from GW1 — no confidence gate applies to single-week facts).
-- Params: :gw

-- Gameweek winner (highest net_points) and last place:
SELECT m.display_name, tn.team_name, rmg.net_points, rmg.gross_points, rmg.hit_cost
FROM raw_manager_gw rmg
JOIN managers m ON m.manager_id = rmg.manager_id
JOIN team_names tn ON tn.manager_id = m.manager_id
WHERE rmg.gw_id = :gw
ORDER BY rmg.net_points DESC;

-- Biggest blowout this gameweek (largest H2H margin):
SELECT h.gw_id, ma.display_name AS side_a, h.score_a, mb.display_name AS side_b, h.score_b, h.margin
FROM raw_h2h_matches h
JOIN managers ma ON ma.manager_id = h.manager_a
JOIN managers mb ON mb.manager_id = h.manager_b
WHERE h.gw_id = :gw AND h.status = 'final'
ORDER BY h.margin DESC
LIMIT 1;

-- Unluckiest of the week: highest net_points among that week's LOSERS.
SELECT m.display_name, rmg.net_points
FROM raw_h2h_matches h
JOIN managers m ON m.manager_id = CASE WHEN h.winner = h.manager_a THEN h.manager_b
                                        WHEN h.winner = h.manager_b THEN h.manager_a END
JOIN raw_manager_gw rmg ON rmg.gw_id = h.gw_id AND rmg.manager_id = m.manager_id
WHERE h.gw_id = :gw AND h.status = 'final' AND h.winner IS NOT NULL
ORDER BY rmg.net_points DESC
LIMIT 1;

-- Luckiest of the week: lowest net_points among that week's WINNERS.
SELECT m.display_name, rmg.net_points
FROM raw_h2h_matches h
JOIN managers m ON m.manager_id = h.winner
JOIN raw_manager_gw rmg ON rmg.gw_id = h.gw_id AND rmg.manager_id = m.manager_id
WHERE h.gw_id = :gw AND h.status = 'final' AND h.winner IS NOT NULL
ORDER BY rmg.net_points ASC
LIMIT 1;
