-- Depot reference data. Nothing here touches the tracked column, so a scan
-- that reports an impact on this table has followed something wrongly.
CREATE TABLE IF NOT EXISTS reference.depot_roster (
  depot_ref STRING,
  depot_name STRING,
  depot_region STRING,
  opened_on DATE
);
