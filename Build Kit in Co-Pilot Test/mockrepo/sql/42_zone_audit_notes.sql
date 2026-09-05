-- Sits below the snapshot, so the only reason this file can name hrv_zn at
-- all is the SELECT * above it. One inferred hop, and the chain ends off the
-- published list a second time.
CREATE OR REPLACE TABLE sandbox.zone_audit_notes AS
SELECT
  consignment_ref,
  hrv_zn,
  'checked' AS note_state
FROM analytics.consignment_snapshot
WHERE hrv_zn IS NOT NULL;
