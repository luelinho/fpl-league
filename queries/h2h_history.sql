-- "Show every matchup between <manager A> and <manager B>" /
-- "How have I done against <manager>?"
-- Params: :entry_a (the "me" side), :entry_b (the opponent)
-- Fact: every stored H2H match between the two, in order, from :entry_a's
-- perspective. Tally W/D/L yourself over the returned rows.
SELECT
    h.gw_id,
    CASE WHEN ma.entry_id = :entry_a THEN h.score_a ELSE h.score_b END AS my_score,
    CASE WHEN ma.entry_id = :entry_a THEN h.score_b ELSE h.score_a END AS opponent_score,
    CASE
        WHEN h.winner IS NULL THEN 'Draw'
        WHEN (ma.entry_id = :entry_a AND h.winner = h.manager_a)
          OR (mb.entry_id = :entry_a AND h.winner = h.manager_b) THEN 'Won'
        ELSE 'Lost'
    END AS result,
    h.margin
FROM raw_h2h_matches h
JOIN managers ma ON ma.manager_id = h.manager_a
JOIN managers mb ON mb.manager_id = h.manager_b
WHERE h.status = 'final'
  AND ((ma.entry_id = :entry_a AND mb.entry_id = :entry_b)
   OR  (ma.entry_id = :entry_b AND mb.entry_id = :entry_a))
ORDER BY h.gw_id;
