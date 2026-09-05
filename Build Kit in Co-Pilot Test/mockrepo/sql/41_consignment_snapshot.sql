-- Whole-table snapshot written with SELECT *, so the column list of the
-- table it builds is written down nowhere. Anything below this file is
-- worked out rather than read, and every row about it has to say so.
CREATE TABLE analytics.consignment_snapshot AS
SELECT *
FROM curated.consignment_enriched;
