-- Publishes the rollup to production.
INSERT INTO market_rollup_prod
SELECT r.mkt_nm, r.cust_ct, c.mkt_cd
FROM market_rollup_odl r
  LEFT JOIN temp_customer c ON c.mkt_cd = r.mkt_nm;
