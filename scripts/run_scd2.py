"""spark-submit entrypoint for the SCD2 builder. See scripts/run_bronze.py."""

import sys

from lakehouse.scd2 import main

if __name__ == "__main__":
    sys.exit(main())
