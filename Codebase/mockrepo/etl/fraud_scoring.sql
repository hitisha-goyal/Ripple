CREATE TABLE fraud_score_daily AS
SELECT t.txn_id, t.cust_id, t.amount, r.risk_band
FROM transactions t
  JOIN risk_reference r ON t.risk_cd = r.risk_cd
WHERE t.txn_dt >= CURRENT_DATE - 30;
