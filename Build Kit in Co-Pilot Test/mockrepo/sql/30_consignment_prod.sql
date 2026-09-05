-- Third hop, and the end of the chain the upstream team needs to hear about.
-- The name ends in _prod, so the default published rule matches it.
CREATE OR REPLACE TABLE marts.consignment_prod AS
SELECT
  consignment_ref,
  hrv_zn,
  zone_label,
  depot_name,
  picked_on,
  crate_count,
  gross_weight_kg
FROM curated.consignment_enriched
WHERE picked_on >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY);
