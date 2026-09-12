-- "How good are <manager>'s in-season decisions?" — Tier 2 manager skill.
-- Params: :entry_id, :through_gw
-- Computed: efficiencies are ratios of stored facts to a brute-force optimal
-- (see src/calculate.py: best_xi_points / captain comparison), not estimates.
SELECT
    ds.through_gw,
    ROUND(ds.season_captain_efficiency * 100, 1) AS captain_efficiency_pct,
    ROUND(ds.season_xi_efficiency * 100, 1) AS xi_efficiency_pct,
    ds.total_bench_points,
    ds.total_hit_cost
FROM derived_manager_season ds
JOIN managers m ON m.manager_id = ds.manager_id
WHERE m.entry_id = :entry_id AND ds.through_gw = :through_gw;

-- Per-gameweek breakdown (same manager, every finalized gameweek):
SELECT
    dg.gw_id,
    dg.score_rank,
    ROUND(dg.score_percentile, 1) AS score_percentile,
    dg.captain_points,
    dg.optimal_captain_points,
    ROUND(dg.captain_efficiency * 100, 1) AS captain_efficiency_pct,
    dg.bench_points,
    dg.xi_points,
    dg.optimal_xi_points,
    ROUND(dg.xi_efficiency * 100, 1) AS xi_efficiency_pct
FROM derived_manager_gw dg
JOIN managers m ON m.manager_id = dg.manager_id
WHERE m.entry_id = :entry_id
ORDER BY dg.gw_id;
