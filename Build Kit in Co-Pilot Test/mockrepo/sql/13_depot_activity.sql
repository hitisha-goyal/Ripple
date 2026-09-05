-- The depot side of the pipeline. It runs on the same schedule and ends at a
-- published table, so a scan has to walk it and then report nothing on it.
CREATE OR REPLACE TABLE staging.depot_activity AS
SELECT
  d.depot_ref,
  d.depot_name,
  d.depot_region,
  COUNT(l.consignment_ref) AS late_count
FROM reference.depot_roster AS d
LEFT JOIN staging.consignment_late AS l
  ON d.depot_ref = l.depot_ref
GROUP BY d.depot_ref, d.depot_name, d.depot_region;
