-- Customer Profile ODL
-- Renames market_code -> mc and last_update_timestamp -> last_upd.
CREATE TABLE customer_profile_odl AS
SELECT
  d.cust_id,
  d.market_code           AS mc,
  d.segment_cd            AS segment,
  d.last_update_timestamp AS last_upd,
  m.region_cd
FROM customer_demographics d
  JOIN market_ref m ON d.market_code = m.market_code
WHERE d.record_status = 1;
