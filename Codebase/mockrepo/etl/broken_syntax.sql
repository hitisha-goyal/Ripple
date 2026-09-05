-- Intentionally malformed: exercises the "could not read" list.
SELECT cust_id, market_code AS
FROM customer_demographics
WHERE ;
