# mockrepo

A synthetic data-pipeline repository used to exercise Ripple. Nothing here is real,
and no real company code or data is present.

It deliberately contains:

* a column renamed twice across hops (`market_code` -> `mc` -> `mkt_cd`)
* breaking usages: a literal filter, a join key, a ranking order, a 2-char SUBSTR
* an upstream table nothing consumes (`prospect_master`) so "no impact" can be shown
* files the SQL reader cannot parse: dynamic SQL, a stored procedure, malformed SQL
* a `SELECT *` view, which hides which columns flow onward
