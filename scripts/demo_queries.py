"""Business questions, answered by name against the star schema.

The point is not the SQL. It is that these are answerable without knowing
where anything is stored, what a surrogate key is, or that party has history.
"""

from lakehouse.catalog import session

QUERIES = {
    "Spend by merchant category": """
        SELECT c.merchant_category_name AS category,
               count(*) AS txns,
               round(sum(abs(f.amount)), 0) AS total_spend
        FROM gold.fact_transaction f
        JOIN gold.dim_merchant_category c USING (merchant_category_sk)
        WHERE f.txn_type = 'DEBIT'
        GROUP BY 1 ORDER BY total_spend DESC LIMIT 5
    """,
    "Closing balance by product, latest day": """
        SELECT a.product_type,
               count(*) AS accounts,
               round(avg(b.closing_balance), 0) AS avg_balance
        FROM gold.fact_daily_balance b
        JOIN gold.dim_account a USING (account_sk)
        WHERE b.date_key = (SELECT max(date_key) FROM gold.fact_daily_balance)
        GROUP BY 1 ORDER BY avg_balance DESC
    """,
    "Spend by customer segment, as they were at the time": """
        SELECT p.segment,
               count(*) AS txns,
               round(sum(abs(f.amount)), 0) AS total_spend
        FROM gold.fact_transaction f
        JOIN gold.dim_party p USING (party_sk)
        WHERE f.txn_type = 'DEBIT'
        GROUP BY 1 ORDER BY total_spend DESC
    """,
    "Accounts that closed, and how long they lasted": """
        SELECT a.product_type,
               count(*) AS closed_accounts,
               round(avg(l.days_open)) AS avg_days_open,
               round(avg(l.txn_count)) AS avg_txns
        FROM gold.fact_account_lifecycle l
        JOIN gold.dim_account a USING (account_sk)
        WHERE l.closed_date_key IS NOT NULL
        GROUP BY 1 ORDER BY closed_accounts DESC
    """,
}


def main() -> int:
    spark = session("demo-queries")
    for title, sql in QUERIES.items():
        print(f"\n=== {title} ===")
        spark.sql(sql).show(truncate=False)
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
