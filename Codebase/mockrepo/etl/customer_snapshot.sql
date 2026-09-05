-- Daily snapshot picks the latest row per customer.
CREATE TABLE temp_customer_latest AS
SELECT
  cust_id,
  MAX(last_update_timestamp) AS upd_ts
FROM customer_demographics
GROUP BY cust_id;

INSERT INTO customer_snapshot_prod
SELECT l.cust_id, l.upd_ts, d.segment_cd
FROM temp_customer_latest l
  JOIN customer_demographics d ON d.cust_id = l.cust_id;
