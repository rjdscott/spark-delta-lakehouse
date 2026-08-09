# Bus matrix

Generated from `model/*.yml` by `make docs`. Don't hand-edit: the specs are
the source of truth, and `make docs-check` fails when this file is stale.

Rows are business processes, one per fact table. Columns are the conformed
dimensions. An X means the fact's spec declares the relationship, which is the
same declaration the DDL, the tests and the ERD are generated from.

| Business process | dim_account | dim_date | dim_merchant_category | dim_party |
|---|---|---|---|---|
| fact_account_lifecycle | X | X |  |  |
| fact_daily_balance | X | X |  |  |
| fact_transaction | X | X | X | X |

A dimension with X in more than one row is conformed: built once in silver,
reused by every process that needs it. That reuse is the argument this repo
exists to make; a second `dim_party` appearing here would mean the argument
had failed in its own codebase.

## Grains

- **fact_account_lifecycle**: One row per account, carrying its milestone dates, updated in place as each milestone occurs.
- **fact_daily_balance**: One row per account per calendar day the account was open, whether or not it transacted.
- **fact_transaction**: One row per transaction event, resolved to the dimension versions current at the moment it occurred.
- **dim_account**: One row per account, carrying its latest known state.
- **dim_date**: One row per calendar day across the range the facts require.
- **dim_merchant_category**: One row per merchant category, including a member for transactions that carry none.
- **dim_party**: One row per party per version of its tracked attributes, effective over a timestamp range.
