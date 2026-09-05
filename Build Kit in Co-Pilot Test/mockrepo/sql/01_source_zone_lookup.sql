-- Zone descriptions. The key is spelled exactly as the feed spells it, which
-- is why the join in 10_consignment_clean.sql reads the same word twice and a
-- word search cannot tell the two sides of it apart.
CREATE TABLE IF NOT EXISTS reference.zone_lookup (
  HARVEST_ZONE STRING,
  zone_label STRING,
  zone_region STRING
);
