-- Published, and genuinely untouched by the tracked column. A scan that
-- lists this table has followed a join it should have left alone.
CREATE OR REPLACE TABLE marts.depot_activity_prod AS
SELECT
  depot_ref,
  depot_name,
  depot_region,
  late_count,
  reported_on
FROM curated.depot_activity_daily;
