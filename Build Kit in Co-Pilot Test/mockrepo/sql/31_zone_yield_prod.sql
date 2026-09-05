-- A second published table on the same chain. It groups by the tracked
-- column, so a change to it changes every number on this table.
CREATE OR REPLACE TABLE marts.zone_yield_prod AS
SELECT
  hrv_zn,
  depot_region,
  COUNT(*) AS consignment_count,
  SUM(crate_count) AS crate_count,
  SUM(gross_weight_kg) AS gross_weight_kg
FROM curated.consignment_enriched
GROUP BY hrv_zn, depot_region;
