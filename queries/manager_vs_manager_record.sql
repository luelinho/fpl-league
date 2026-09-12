-- "What's my record against <manager>?" (aggregate, not match-by-match —
-- see h2h_history.sql for the full list)
-- Params: :entry_a (the "me" side), :entry_b (the opponent)
-- Computed: aggregated from stored H2H matches.
SELECT
    COUNT(*) AS matches_played,
    SUM(CASE
        WHEN h.winner IS NOT NULL
         AND ((ma.entry_id = :entry_a AND h.winner = h.manager_a)
           OR (mb.entry_id = :entry_a AND h.winner = h.manager_b))
        THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN h.winner IS NULL THEN 1 ELSE 0 END) AS draws,
    SUM(CASE
        WHEN h.winner IS NOT NULL
         AND NOT ((ma.entry_id = :entry_a AND h.winner = h.manager_a)
              OR (mb.entry_id = :entry_a AND h.winner = h.manager_b))
        THEN 1 ELSE 0 END) AS losses,
    SUM(CASE WHEN ma.entry_id = :entry_a THEN h.score_a ELSE h.score_b END) AS my_points_for,
    SUM(CASE WHEN ma.entry_id = :entry_a THEN h.score_b ELSE h.score_a END) AS my_points_against
FROM raw_h2h_matches h
JOIN managers ma ON ma.manager_id = h.manager_a
JOIN managers mb ON mb.manager_id = h.manager_b
WHERE (ma.entry_id = :entry_a AND mb.entry_id = :entry_b)
   OR (ma.entry_id = :entry_b AND mb.entry_id = :entry_a);
