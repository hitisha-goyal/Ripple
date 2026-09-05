-- Production customer master.
INSERT INTO final_odl_prod
SELECT g.cust_id, g.tag_cd, g.lut_ts
FROM global_tagging_main g;
