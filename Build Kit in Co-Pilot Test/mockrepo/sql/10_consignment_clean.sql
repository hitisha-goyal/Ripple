-- First hop of the chain.
-- HARVEST_ZONE is carried forward as hz, so from this file down the original
-- word never appears again. The join is on a column of the same name in two
-- different tables, which is the case a word search reports twice and a
-- parser reports once.
CREATE OR REPLACE TABLE staging.consignment_clean AS
SELECT
  s.consignment_ref,
  s.HARVEST_ZONE AS hz,
  z.zone_label,
  z.zone_region,
  s.depot_ref,
  s.grade_code,
  s.picked_on,
  s.crate_count,
  s.gross_weight_kg
FROM raw_orchard.consignment_source AS s
LEFT JOIN reference.zone_lookup AS z
  ON s.HARVEST_ZONE = z.HARVEST_ZONE
WHERE s.crate_count > 0;
