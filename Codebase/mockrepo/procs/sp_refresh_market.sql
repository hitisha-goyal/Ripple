-- Stored procedure. Body is not parsed by the SQL reader.
CREATE OR REPLACE PROCEDURE sp_refresh_market()
LANGUAGE plpgsql
AS $$
DECLARE
  v_cnt INT;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM customer_demographics WHERE market_code IS NOT NULL;
  IF v_cnt > 0 THEN
    INSERT INTO market_audit_log(run_dt, row_ct) VALUES (CURRENT_DATE, v_cnt);
  END IF;
END;
$$;
