-- Deliberately broken. The FROM clause names no table, so no parser can read
-- this file, and Ripple has to hand it to a human with the line and the line
-- number rather than counting it as read.
CREATE OR REPLACE TABLE curated.zone_summary AS
SELECT
  hrv_zn,
  COUNT(*) AS row_count
FROM
GROUP BY hrv_zn;
