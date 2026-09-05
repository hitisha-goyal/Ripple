-- Second hop. hz becomes hrv_zn here, which is the name every published
-- table below uses. Two renames between the upstream word and the mart is
-- the whole reason a word search over this folder answers "no impact".
CREATE OR REPLACE TABLE curated.consignment_enriched AS
SELECT
  c.consignment_ref,
  c.hz AS hrv_zn,
  c.zone_label,
  c.zone_region,
  d.depot_name,
  d.depot_region,
  c.picked_on,
  c.crate_count,
  c.gross_weight_kg
FROM staging.consignment_clean AS c
LEFT JOIN reference.depot_roster AS d
  ON c.depot_ref = d.depot_ref;
