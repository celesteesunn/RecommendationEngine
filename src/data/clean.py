"""Clean the raw H&M CSVs with PySpark and write Parquet to data/processed/.

Usage:
    python -m src.data.clean

Outputs (in data/processed/):
    transactions/           cleaned purchases, partitioned by week
    customers/              cleaned customers with cold-start flags
    articles/               cleaned articles with cold-start flags
    cleaning_summary.json   row counts, fixes applied and cold-start counts
"""

import json
import sys
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.storagelevel import StorageLevel

from src.config import load_config, project_path

TRANSACTIONS_SCHEMA = T.StructType([
    T.StructField("t_dat", T.StringType()),
    T.StructField("customer_id", T.StringType()),
    # Read as a string so the leading zero survives.
    T.StructField("article_id", T.StringType()),
    T.StructField("price", T.DoubleType()),
    T.StructField("sales_channel_id", T.IntegerType()),
])

CUSTOMERS_SCHEMA = T.StructType([
    T.StructField("customer_id", T.StringType()),
    T.StructField("FN", T.DoubleType()),
    T.StructField("Active", T.DoubleType()),
    T.StructField("club_member_status", T.StringType()),
    T.StructField("fashion_news_frequency", T.StringType()),
    T.StructField("age", T.DoubleType()),
    T.StructField("postal_code", T.StringType()),
])

# Attribute columns the model and the API use. The numeric codes are kept as stable keys
# (some names, e.g. department_name, are shared by several codes).
ARTICLE_COLUMNS = [
    "article_id", "product_code", "prod_name",
    "product_type_no", "product_type_name", "product_group_name",
    "colour_group_code", "colour_group_name",
    "department_no", "department_name",
    "index_code", "index_name",
    "index_group_no", "index_group_name",
    "section_no", "section_name",
    "garment_group_no", "garment_group_name",
    "detail_desc",
]

ARTICLE_ID_LENGTH = 10
UNKNOWN = "UNKNOWN"


def create_spark(config: dict) -> SparkSession:
    spark_config = config["spark"]
    local_dir = Path(spark_config["local_dir"]).expanduser()
    local_dir.mkdir(parents=True, exist_ok=True)
    return (
        SparkSession.builder
        .appName("hm-clean")
        .master("local[*]")
        .config("spark.driver.memory", spark_config["driver_memory"])
        .config("spark.sql.shuffle.partitions", spark_config["shuffle_partitions"])
        .config("spark.local.dir", str(local_dir))
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def normalize_article_id(column: str = "article_id") -> F.Column:
    return F.lpad(F.trim(F.col(column)), ARTICLE_ID_LENGTH, "0")


def clean_transactions(raw: DataFrame) -> DataFrame:
    """Fix types, collapse exact duplicate rows into a quantity, and add a week index.

    Exact duplicates in this dataset are multiple units of the same article bought by the
    same customer on the same day, so they are counted rather than thrown away.

    week 0 is the earliest week. Weeks are counted back from the last date, so the final
    week is always a complete 7 days (the held-out test week).
    """
    typed = raw.select(
        F.to_date("t_dat", "yyyy-MM-dd").alias("t_dat"),
        F.trim("customer_id").alias("customer_id"),
        normalize_article_id().alias("article_id"),
        F.col("price").cast("double"),
        F.col("sales_channel_id").cast("int"),
    ).dropna(subset=["t_dat", "customer_id", "article_id"])

    # Date range from the typed rows: a plain scan, no shuffle.
    bounds = typed.agg(F.min("t_dat").alias("first"), F.max("t_dat").alias("last")).first()
    deduped = typed.groupBy(typed.columns).agg(F.count(F.lit(1)).cast("int").alias("quantity"))

    last_week = (bounds["last"] - bounds["first"]).days // 7
    weeks_ago = F.floor(F.datediff(F.lit(bounds["last"]), F.col("t_dat")) / 7)
    return deduped.withColumn("week", (F.lit(last_week) - weeks_ago).cast("int"))


def clean_customers(raw: DataFrame) -> DataFrame:
    """Fill missing flags, normalise labels, and impute age by club status median."""
    customers = raw.select(
        F.trim("customer_id").alias("customer_id"),
        F.coalesce(F.col("FN"), F.lit(0.0)).cast("int").alias("FN"),
        F.coalesce(F.col("Active"), F.lit(0.0)).cast("int").alias("Active"),
        F.coalesce(F.upper(F.trim("club_member_status")), F.lit(UNKNOWN)).alias("club_member_status"),
        # "NONE" and "None" both mean no newsletter; upper-casing merges them.
        F.coalesce(F.upper(F.trim("fashion_news_frequency")), F.lit(UNKNOWN)).alias("fashion_news_frequency"),
        F.col("age").cast("double"),
        F.col("postal_code"),
    ).dropDuplicates(["customer_id"])

    medians = customers.groupBy("club_member_status").agg(
        F.percentile_approx("age", 0.5).alias("group_median_age")
    )
    overall_median = customers.agg(F.percentile_approx("age", 0.5)).first()[0]

    return (
        customers.join(F.broadcast(medians), "club_member_status", "left")
        .withColumn("age_missing", F.col("age").isNull().cast("int"))
        .withColumn(
            "age",
            F.coalesce("age", "group_median_age", F.lit(overall_median)).cast("int"),
        )
        .drop("group_median_age")
        .select("customer_id", "FN", "Active", "club_member_status", "fashion_news_frequency",
                "age", "age_missing", "postal_code")
    )


def clean_articles(raw: DataFrame) -> DataFrame:
    return (
        raw.withColumn("article_id", normalize_article_id())
        .withColumn("detail_desc", F.coalesce(F.col("detail_desc"), F.lit("")))
        .select(*ARTICLE_COLUMNS)
        .dropDuplicates(["article_id"])
    )


def keep_known_ids(transactions: DataFrame, customers: DataFrame, articles: DataFrame) -> DataFrame:
    """Drop purchases whose customer or article is missing from the other tables."""
    return (
        transactions
        .join(customers.select("customer_id"), "customer_id", "left_semi")
        .join(F.broadcast(articles.select("article_id")), "article_id", "left_semi")
    )


def training_weeks(transactions: DataFrame, train_weeks: int, test_weeks: int) -> tuple[int, int]:
    """Return the first and last week (inclusive) of the training window."""
    last_week = transactions.agg(F.max("week")).first()[0]
    last_train_week = last_week - test_weeks
    return last_train_week - train_weeks + 1, last_train_week


def add_cold_start_flags(
    transactions: DataFrame,
    customers: DataFrame,
    articles: DataFrame,
    first_week: int,
    last_week: int,
    min_purchases: int,
) -> tuple[DataFrame, DataFrame]:
    """Count purchases in the training window and flag customers and articles with too few.

    Customers with fewer than min_purchases are cold-start; articles with none are.
    """
    window = transactions.where(F.col("week").between(first_week, last_week))

    customer_counts = window.groupBy("customer_id").agg(F.sum("quantity").alias("train_purchases"))
    customers = (
        customers.join(customer_counts, "customer_id", "left")
        .withColumn("train_purchases", F.coalesce("train_purchases", F.lit(0)).cast("int"))
        .withColumn("is_cold_start", (F.col("train_purchases") < min_purchases).cast("int"))
    )

    article_counts = window.groupBy("article_id").agg(F.sum("quantity").alias("train_purchases"))
    articles = (
        articles.join(article_counts, "article_id", "left")
        .withColumn("train_purchases", F.coalesce("train_purchases", F.lit(0)).cast("int"))
        .withColumn("is_cold_start", (F.col("train_purchases") == 0).cast("int"))
    )
    return customers, articles


def main() -> int:
    config = load_config()
    raw_dir = project_path(config["paths"]["raw_dir"])
    out_dir = project_path(config["paths"]["processed_dir"])

    missing = [f for f in config["dataset"]["files"] if not (raw_dir / f).is_file()]
    if missing:
        print(f"Missing raw files in {raw_dir}: {', '.join(missing)}", file=sys.stderr)
        return 1

    spark = create_spark(config)
    read_csv = lambda name, schema=None: spark.read.csv(  # noqa: E731
        str(raw_dir / name), header=True, schema=schema, inferSchema=schema is None
    )

    raw_transactions = read_csv("transactions_train.csv", TRANSACTIONS_SCHEMA)
    raw_customers = read_csv("customers.csv", CUSTOMERS_SCHEMA)
    raw_articles = read_csv("articles.csv").withColumn("article_id", F.col("article_id").cast("string"))

    # Customers and articles are small enough to keep; the 31.8M transactions are not.
    customers = clean_customers(raw_customers).persist(StorageLevel.MEMORY_AND_DISK)
    articles = clean_articles(raw_articles).persist(StorageLevel.MEMORY_AND_DISK)

    # Transactions go straight to Parquet, and later steps read them back from disk.
    print(f"Writing Parquet to {out_dir} ...")
    transactions = keep_known_ids(clean_transactions(raw_transactions), customers, articles)
    transactions.repartition("week").write.mode("overwrite").partitionBy("week").parquet(
        str(out_dir / "transactions")
    )
    transactions = spark.read.parquet(str(out_dir / "transactions"))

    first_train_week, last_train_week = training_weeks(
        transactions, config["split"]["train_weeks"], config["split"]["test_weeks"]
    )
    customers, articles = add_cold_start_flags(
        transactions, customers, articles, first_train_week, last_train_week,
        config["cleaning"]["cold_start_min_purchases"],
    )
    customers.write.mode("overwrite").parquet(str(out_dir / "customers"))
    articles.write.mode("overwrite").parquet(str(out_dir / "articles"))

    # Counts come from the written files, so the summary describes exactly what was saved.
    saved_customers = spark.read.parquet(str(out_dir / "customers"))
    saved_articles = spark.read.parquet(str(out_dir / "articles"))
    raw_rows = raw_transactions.count()
    totals = transactions.agg(F.count(F.lit(1)).alias("rows"), F.sum("quantity").alias("units")).first()
    summary = {
        "transactions": {
            "raw_rows": raw_rows,
            # Each written row is one distinct purchase; quantity counts its duplicate raw rows.
            "rows_written": totals["rows"],
            "duplicate_rows_collapsed": totals["units"] - totals["rows"],
            "raw_rows_dropped": raw_rows - totals["units"],
            "weeks": last_train_week + config["split"]["test_weeks"] + 1,
        },
        "customers": {
            "raw_rows": raw_customers.count(),
            "rows_written": saved_customers.count(),
            "age_imputed": saved_customers.where("age_missing = 1").count(),
            "cold_start": saved_customers.where("is_cold_start = 1").count(),
        },
        "articles": {
            "raw_rows": raw_articles.count(),
            "rows_written": saved_articles.count(),
            "cold_start": saved_articles.where("is_cold_start = 1").count(),
        },
        "training_window_weeks": [first_train_week, last_train_week],
        "cold_start_min_purchases": config["cleaning"]["cold_start_min_purchases"],
    }
    (out_dir / "cleaning_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
