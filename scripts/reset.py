"""Drop every table so the demo can run from cold. Data in MinIO is removed
separately, because dropping an external table leaves its files behind."""

from lakehouse.catalog import session
from lakehouse.spec import load_all


def main() -> int:
    spark = session("reset")
    for spec in load_all().values():
        spark.sql(f"DROP TABLE IF EXISTS {spec.table}")
    print(f"dropped {len(load_all())} tables")
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
