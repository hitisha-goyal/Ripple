CREATE TABLE merchant_rollup AS
SELECT m.merchant_id, SUM(t.amount) AS total_amt
FROM transactions t
  JOIN merchant_master m ON t.merchant_id = m.merchant_id
GROUP BY m.merchant_id;
