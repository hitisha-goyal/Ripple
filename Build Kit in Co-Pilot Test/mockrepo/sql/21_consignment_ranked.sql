-- The window is ordered by the tracked column, so which row wins depends on
-- the values in it. Nothing in this file can be edited to keep the old
-- answer once those values change: it is a ranking with no local fix.
CREATE OR REPLACE TABLE curated.consignment_ranked AS
SELECT
  consignment_ref,
  hz,
  depot_ref,
  picked_on,
  ROW_NUMBER() OVER (
    PARTITION BY depot_ref
    ORDER BY hz DESC, picked_on DESC
  ) AS zone_rank
FROM staging.consignment_clean;
