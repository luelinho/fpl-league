-- "How has <manager> done this season?" — Tier 0 ledger, exact from GW1.
-- Params: :entry_id, :through_gw
-- Fact/Computed: derived_manager_season is a documented aggregate of raw
-- facts (see src/calculate.py), not an estimate. gws_played tells you the
-- sample size behind every number here.
SELECT
    ds.through_gw,
    ds.gws_played,
    ds.points_for,
    ds.points_against,
    ROUND(ds.avg_pf, 1) AS avg_points_for,
    ROUND(ds.avg_pa, 1) AS avg_points_against,
    ds.actual_w, ds.actual_d, ds.actual_l,
    ds.actual_league_pts,
    ds.close_w, ds.close_l, ds.blowout_w, ds.blowout_l,
    ds.total_bench_points,
    ds.total_hit_cost
FROM derived_manager_season ds
JOIN managers m ON m.manager_id = ds.manager_id
WHERE m.entry_id = :entry_id AND ds.through_gw = :through_gw;
