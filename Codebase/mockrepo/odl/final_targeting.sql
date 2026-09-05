-- Builds the production targeting table.
-- SUBSTR on country_code assumes a two character ISO code.
INSERT INTO final_targeting_prod
SELECT
  t.cust_id,
  t.mkt_cd,
  SUBSTR(a.country_code, 1, 2) AS ctry,
  t.segment
FROM marketing_base t
  JOIN customer_address a ON t.cust_id = a.cust_id;
