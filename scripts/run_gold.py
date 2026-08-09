"""spark-submit entrypoint for the gold builder. See scripts/run_bronze.py."""

import sys

from lakehouse.gold import main

if __name__ == "__main__":
    sys.exit(main())
