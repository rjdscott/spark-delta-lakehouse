"""spark-submit entrypoint for the silver builder. See scripts/run_bronze.py."""

import sys

from lakehouse.silver import main

if __name__ == "__main__":
    sys.exit(main())
