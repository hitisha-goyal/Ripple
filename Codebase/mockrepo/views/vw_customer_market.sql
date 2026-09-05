CREATE VIEW vw_customer_market AS
SELECT cp.cust_id, cp.mc, cp.region_cd
FROM customer_profile_odl cp;
