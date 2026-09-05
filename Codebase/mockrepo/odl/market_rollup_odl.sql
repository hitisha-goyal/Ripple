-- Market rollup, grouped on the market label.
CREATE TABLE market_rollup_odl AS
SELECT
  d.market_name AS mkt_nm,
  COUNT(*)      AS cust_ct
FROM customer_demographics d
GROUP BY d.market_name;
