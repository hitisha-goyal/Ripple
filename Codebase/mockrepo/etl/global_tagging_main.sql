-- Deduplicates to one row per customer.
-- The ordering column is the renamed last_update_timestamp.
CREATE TABLE global_tagging_main AS
SELECT cust_id, tag_cd, lut_ts
FROM (
  SELECT
    c.cust_id,
    t.tag_cd,
    c.last_upd AS lut_ts,
    ROW_NUMBER() OVER (
      PARTITION BY c.cust_id
      ORDER BY c.last_upd DESC
    ) AS rn
  FROM customer_profile_odl c
    JOIN customer_tags t ON t.cust_id = c.cust_id
) ranked
WHERE rn = 1;
