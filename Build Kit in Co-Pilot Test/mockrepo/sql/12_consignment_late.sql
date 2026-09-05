-- Late consignments. Built from the same source table but never reading the
-- tracked column, so it is the control case: an impact reported here is wrong.
CREATE OR REPLACE TABLE staging.consignment_late AS
SELECT
  consignment_ref,
  depot_ref,
  picked_on,
  DATE_DIFF(CURRENT_DATE(), picked_on, DAY) AS days_late
FROM raw_orchard.consignment_source
WHERE picked_on < DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY);
