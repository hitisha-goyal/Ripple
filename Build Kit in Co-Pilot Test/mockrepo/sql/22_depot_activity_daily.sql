-- Daily roll-up of the depot side, still with nothing to do with the tracked
-- column. It gives the scan a second chain to walk to the end and drop.
CREATE OR REPLACE TABLE curated.depot_activity_daily AS
SELECT
  depot_ref,
  depot_name,
  depot_region,
  late_count,
  CURRENT_DATE() AS reported_on
FROM staging.depot_activity;
