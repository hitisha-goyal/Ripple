-- Upstream table owned by DNA. Nothing in this repo consumes it.
CREATE TABLE prospect_master (
  prospect_id          BIGINT,
  legacy_segment_code  VARCHAR(10),
  segment_code_v2      VARCHAR(20),
  created_dt           DATE
);
