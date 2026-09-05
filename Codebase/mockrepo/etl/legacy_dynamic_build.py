"""Legacy job that assembles SQL by string concatenation.

Ripple cannot follow this reliably - it is reported under "could not read".
"""
COLS = ["cust_id", "market_code", "segment_cd"]
TARGET = "legacy_market_extract"

def build_sql(where_col, where_val):
    select_list = ", ".join(COLS)
    sql = "INSERT INTO " + TARGET + " SELECT " + select_list
    sql += " FROM customer_demographics"
    sql += " WHERE " + where_col + " = '" + where_val + "'"
    return sql

if __name__ == "__main__":
    print(build_sql("market_code", "US"))
