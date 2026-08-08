"""spark-submit entrypoint for the bronze loader.

spark-submit runs a file, not a module, and running `src/lakehouse/bronze.py`
directly fails with "attempted relative import with no known parent package".
This is the thin shim that lets the package stay a package.
"""

import sys

from lakehouse.bronze import main

if __name__ == "__main__":
    sys.exit(main())
