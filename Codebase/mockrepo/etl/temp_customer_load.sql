-- Staging hop used by the rollup.
INSERT INTO temp_customer
SELECT cust_id, mc AS mkt_cd, segment
FROM customer_profile_odl;
