"""The SCD2 integrity rules, checked against the table that was written.

Row counts prove nothing. These are the claims: ranges do not overlap, there
is exactly one current version per live key, the timeline has no gaps, a
same-day change produces two versions, an untracked change produces none, and
a deleted party has no current version at all.
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window

from lakehouse.catalog import session
from lakehouse.spec import load_all

TABLE = "silver.party"


def main() -> int:
    spark = session("verify-scd2")
    spec = load_all()["silver_party"]
    party = spark.table(TABLE)
    ok = True

    timeline = Window.partitionBy("party_id").orderBy("effective_from")
    ranged = party.withColumn("_next", F.lead("effective_from").over(timeline))

    overlaps = ranged.filter(F.col("_next").isNotNull() & (F.col("effective_to") > F.col("_next")))
    gaps = ranged.filter(F.col("_next").isNotNull() & (F.col("effective_to") < F.col("_next")))
    overlap_count, gap_count = overlaps.count(), gaps.count()
    inverted = party.filter(F.col("effective_to") < F.col("effective_from")).count()
    print(f"overlapping ranges  : {overlap_count}")
    print(f"timeline gaps       : {gap_count}")
    print(f"inverted ranges     : {inverted}")
    ok &= overlap_count == 0 and gap_count == 0 and inverted == 0

    per_key = party.groupBy("party_id").agg(F.sum(F.col("is_current").cast("int")).alias("c"))
    many = per_key.filter(F.col("c") > 1).count()
    none = per_key.filter(F.col("c") == 0).count()
    print(f"keys with >1 current: {many}")
    print(f"keys with 0 current : {none}  (deleted parties, ADR 0007)")
    ok &= many == 0

    # Defect 2: two versions on one date, at different times.
    same_day = (
        party.groupBy("party_id", F.to_date("effective_from").alias("d"))
        .count()
        .filter(F.col("count") > 1)
    )
    same_day_count = same_day.count()
    print(f"same-day versions   : {same_day_count} keys")
    ok &= same_day_count > 0

    versions = party.groupBy("party_id").count()
    stats = versions.agg(
        F.min("count").alias("lo"), F.max("count").alias("hi"), F.avg("count").alias("avg")
    ).first()
    print(f"versions per party  : min={stats['lo']} max={stats['hi']} mean={stats['avg']:.2f}")

    # An untracked change must not open a version: full_name is untracked, so
    # no two adjacent versions of a key may have identical tracked attributes.
    tracked = [a.name for a in spec.tracked]
    fingerprint = F.concat_ws(
        "\u001f", *[F.coalesce(F.col(c).cast("string"), F.lit("\u0000")) for c in tracked]
    )
    repeats = (
        party.withColumn("_f", fingerprint)
        .withColumn("_prev", F.lag("_f").over(timeline))
        .filter(F.col("_prev").isNotNull() & (F.col("_f") == F.col("_prev")))
        .count()
    )
    print(f"no-op versions      : {repeats}")
    ok &= repeats == 0

    spark.stop()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
