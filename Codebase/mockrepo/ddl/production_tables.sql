-- Tables this team publishes. Anything downstream of these is customer facing.
CREATE TABLE final_targeting_prod (
  cust_id  BIGINT,
  mkt_cd   VARCHAR(40),
  ctry     VARCHAR(2),
  segment  VARCHAR(10)
);

CREATE TABLE market_rollup_prod (
  mkt_nm   VARCHAR(80),
  cust_ct  BIGINT,
  mkt_cd   VARCHAR(40)
);

CREATE TABLE final_odl_prod (
  cust_id  BIGINT,
  tag_cd   VARCHAR(20),
  lut_ts   TIMESTAMP
);

CREATE TABLE customer_snapshot_prod (
  cust_id     BIGINT,
  upd_ts      TIMESTAMP,
  segment_cd  VARCHAR(10)
);
