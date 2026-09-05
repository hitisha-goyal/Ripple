-- Address standardisation staging table.
CREATE TABLE temp_address_std AS
SELECT
  a.cust_id,
  a.country_code AS ctry,
  a.postal_cd
FROM customer_address a;
