-- Rows held back for a human to look at.
-- The filter compares the tracked column to a literal, so a change to the
-- values behind that column changes what is rejected without anything
-- failing. There is nothing to edit in this file that keeps the old answer.
CREATE OR REPLACE TABLE staging.consignment_reject AS
SELECT
  consignment_ref,
  HARVEST_ZONE,
  depot_ref,
  crate_count
FROM raw_orchard.consignment_source
WHERE HARVEST_ZONE = 'ZN-114'
   OR crate_count <= 0;
