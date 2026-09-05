-- Upstream table owned by C360.
CREATE TABLE customer_address (
  cust_id       BIGINT,
  country_code  VARCHAR(2),
  postal_cd     VARCHAR(12),
  addr_line_1   VARCHAR(120)
);
