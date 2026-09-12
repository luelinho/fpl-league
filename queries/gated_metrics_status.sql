-- "What's my luck/power-ranking/projection look like?"
-- CLAUDE.md rule 4: below the gate, say "insufficient sample — N gameweeks,
-- need M." Do not show a number with a caveat attached — withhold it fully.
-- This query tells you the sample size so the query layer can decide.
-- Params: :through_gw
SELECT
    :through_gw AS gws_played,
    CASE WHEN :through_gw >= 10 THEN 'unlocked' ELSE 'insufficient sample — ' || :through_gw || ' gameweeks, need 10' END AS luck_and_power_rankings,
    CASE WHEN :through_gw >= 15 THEN 'unlocked' ELSE 'insufficient sample — ' || :through_gw || ' gameweeks, need 15' END AS projections;
