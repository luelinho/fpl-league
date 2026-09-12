-- "Are there any data problems I should know about?"
-- Fact: every logged issue, unresolved first. Severity 'info' includes
-- documented permanent gaps (e.g. GW1-2 standings), not just errors.
SELECT detected_at, severity, category, season_id, gw_id, manager_id, description, resolved
FROM data_issues
ORDER BY resolved ASC, severity = 'error' DESC, severity = 'warning' DESC, detected_at DESC;
