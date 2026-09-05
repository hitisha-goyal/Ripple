-- Landing copy of the orchard consignment feed.
-- The upstream team owns these names, so a rename they make arrives here
-- first and every table below inherits it under a different name.
CREATE TABLE IF NOT EXISTS raw_orchard.consignment_source (
  consignment_ref STRING,
  HARVEST_ZONE STRING,
  depot_ref STRING,
  grade_code STRING,
  picked_on DATE,
  crate_count INT64,
  gross_weight_kg NUMERIC
);
