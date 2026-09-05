-- The chain also ends here, at a table whose name matches no published rule.
-- The depot team opens it every morning, so dropping it because it is not
-- called _prod would hide a real breaking impact behind a clean result.
CREATE OR REPLACE TABLE sandbox.consignment_review AS
SELECT
  hrv_zn,
  depot_name,
  COUNT(*) AS row_count,
  MAX(picked_on) AS last_picked_on
FROM curated.consignment_enriched
GROUP BY hrv_zn, depot_name;
