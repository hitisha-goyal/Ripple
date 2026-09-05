-- BigQuery script shape: the statement that matters is wrapped in a block
-- with its own error handler, and a parser handed the file whole will refuse
-- it unless the wrapper is dealt with on the way in.
BEGIN
  CREATE OR REPLACE TABLE curated.zone_refresh_log AS
  SELECT
    hrv_zn,
    COUNT(*) AS row_count,
    CURRENT_TIMESTAMP() AS refreshed_at
  FROM curated.consignment_enriched
  GROUP BY hrv_zn;

EXCEPTION WHEN ERROR THEN
  INSERT INTO ops.refresh_failures (job_name, message, failed_at)
  VALUES ('zone_refresh', @@error.message, CURRENT_TIMESTAMP());
  RAISE USING MESSAGE = 'zone_refresh failed, see ops.refresh_failures';
END;
