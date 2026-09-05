-- Upstream table owned by C360. We only read it.
CREATE TABLE customer_demographics (
  cust_id                BIGINT,
  market_code            VARCHAR(2),
  market_name            VARCHAR(80),
  segment_cd             VARCHAR(10),
  record_status          INT,
  last_update_timestamp  TIMESTAMP
);
