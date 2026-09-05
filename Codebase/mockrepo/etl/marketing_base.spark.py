"""Marketing base build (PySpark).

Second rename hop: mc -> mkt_cd. The literal 'US' filter is the breaking usage.
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("marketing_base").getOrCreate()

MARKETING_BASE_SQL = """
SELECT
  cp.cust_id,
  cp.mc AS mkt_cd,
  cp.segment,
  am.account_status
FROM customer_profile_odl cp
  JOIN account_master am ON cp.cust_id = am.cust_id
WHERE cp.mc = 'US'
  AND am.account_status = 'ACTIVE'
"""

def build():
    df = spark.sql(MARKETING_BASE_SQL)
    df.write.mode("overwrite").saveAsTable("marketing_base")

if __name__ == "__main__":
    build()
