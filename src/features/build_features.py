"""Build user, item and context features and the train/test split with PySpark.

Usage:
    python -m src.features.build_features

Reads the cleaned Parquet from data/processed/ (run src.data.clean first) and writes:
    item_features/     one row per article: categories, price band, popularity over time
    user_features/     one row per customer: profile, 12-week activity, last 20 purchases
    train/             one row per purchase in the 12 training weeks, with its context
                       and the customer's history before that day (the model's examples)
    test/              one row per customer who bought in the test week, with what they bought
    features_summary.json

All features are calculated "as of" the last training week, so nothing from the test week
leaks into training.
"""

import json
import sys

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from src.config import load_config, project_path
from src.data.clean import training_weeks
from src.spark import create_spark

# Product attributes the candidate tower uses. department_no is the key because some
# department names are shared by several departments.
ITEM_CATEGORY_COLUMNS = [
    "product_type_name", "product_group_name", "colour_group_name",
    "garment_group_name", "department_no", "index_group_name",
]
UNKNOWN_AGE = "unknown"


def age_bucket(age: str = "age", age_missing: str = "age_missing") -> F.Column:
    return (
        F.when(F.col(age_missing) == 1, F.lit(UNKNOWN_AGE))
        .when(F.col(age) < 25, "16-24")
        .when(F.col(age) < 35, "25-34")
        .when(F.col(age) < 45, "35-44")
        .when(F.col(age) < 55, "45-54")
        .otherwise("55+")
    )


def last_n(array_column: str, n: int) -> F.Column:
    """The last n elements of an array (all of it when shorter)."""
    return F.expr(f"slice({array_column}, greatest(size({array_column}) - {n - 1}, 1), {n})")


def build_item_features(
    transactions: DataFrame,
    articles: DataFrame,
    as_of_week: int,
    popularity_weeks: list[int],
    price_buckets: int,
) -> DataFrame:
    """Categories, a price band, and purchase counts over the weeks ending at as_of_week."""
    past = transactions.where(F.col("week") <= as_of_week)

    popularity = past.groupBy("article_id").agg(*[
        F.sum(F.when(F.col("week") > as_of_week - w, F.col("quantity")).otherwise(0))
        .cast("int").alias(f"popularity_{w}w")
        for w in popularity_weeks
    ])

    # The typical price is the median over the longest popularity window, falling back to
    # all history for products that did not sell recently.
    recent = as_of_week - max(popularity_weeks)
    prices = past.groupBy("article_id").agg(
        F.percentile_approx(F.when(F.col("week") > recent, F.col("price")), 0.5).alias("recent_price"),
        F.percentile_approx("price", 0.5).alias("any_price"),
    ).select("article_id", F.coalesce("recent_price", "any_price").alias("price"))

    items = (
        articles.select("article_id", "prod_name", *ITEM_CATEGORY_COLUMNS)
        .join(popularity, "article_id", "left")
        .join(prices, "article_id", "left")
        .fillna(0, subset=[f"popularity_{w}w" for w in popularity_weeks])
    )

    # Equal-sized price bands: band k means the price is above k of the cut points.
    probabilities = [i / price_buckets for i in range(1, price_buckets)]
    cut_points = items.approxQuantile("price", probabilities, 0.001)
    band = sum((F.col("price") > cut).cast("int") for cut in cut_points)
    return (
        items.withColumn("price_bucket", F.when(F.col("price").isNull(), -1).otherwise(band))
        .withColumn("is_cold_start", (F.col(f"popularity_{max(popularity_weeks)}w") == 0).cast("int"))
    )


def build_user_features(
    transactions: DataFrame,
    customers: DataFrame,
    as_of_week: int,
    window_weeks: int,
    history_length: int,
    min_purchases: int,
) -> DataFrame:
    """Profile, recent activity and the last purchases of every customer, as of as_of_week."""
    past = transactions.where(F.col("week") <= as_of_week)
    in_window = F.col("week") > as_of_week - window_weeks

    activity = past.groupBy("customer_id").agg(
        F.sum(F.when(in_window, F.col("quantity")).otherwise(0)).cast("int").alias("purchase_count"),
        (F.sum(F.when(in_window, F.col("price") * F.col("quantity")))
         / F.sum(F.when(in_window, F.col("quantity")))).alias("avg_price"),
        # Online share over all history, so customers quiet in the window still get a value.
        (F.sum(F.when(F.col("sales_channel_id") == 2, F.col("quantity")).otherwise(0))
         / F.sum("quantity")).alias("online_share"),
        F.max("t_dat").alias("last_purchase_date"),
    )

    latest_first = Window.partitionBy("customer_id").orderBy(F.col("t_dat").desc(), F.col("article_id"))
    history = (
        past.withColumn("rank", F.row_number().over(latest_first))
        .where(F.col("rank") <= history_length)
        .groupBy("customer_id")
        # Sorting by descending rank puts the oldest first and the newest last.
        .agg(F.sort_array(F.collect_list(F.struct((-F.col("rank")).alias("order"), "article_id")))
             .alias("ranked"))
        .select("customer_id", F.col("ranked.article_id").alias("history"))
    )

    return (
        customers.select(
            "customer_id", "age", "age_missing", "club_member_status", "fashion_news_frequency",
        )
        .withColumn("age_bucket", age_bucket())
        .join(activity, "customer_id", "left")
        .join(history, "customer_id", "left")
        .withColumn("purchase_count", F.coalesce("purchase_count", F.lit(0)))
        .withColumn("preferred_channel", F.when(F.col("online_share") >= 0.5, 2).otherwise(1))
        .withColumn("history", F.coalesce("history", F.array().cast("array<string>")))
        .withColumn("is_cold_start", (F.col("purchase_count") < min_purchases).cast("int"))
        .drop("age_missing")
    )


def build_training_examples(
    transactions: DataFrame,
    first_week: int,
    last_week: int,
    history_length: int,
    max_days_since: int,
) -> DataFrame:
    """One row per purchase in the training weeks, with its context and prior history.

    The history only contains purchases from earlier days, never from the same day, so the
    model cannot see the answer in its input.
    """
    target_customers = transactions.where(F.col("week").between(first_week, last_week)) \
        .select("customer_id").distinct()

    days = (
        transactions.where(F.col("week") <= last_week)
        .join(target_customers, "customer_id", "left_semi")
        .groupBy("customer_id", "t_dat")
        .agg(F.sort_array(F.collect_list("article_id")).alias("basket"))
    )

    # history_length earlier days always hold at least history_length articles.
    by_day = Window.partitionBy("customer_id").orderBy("t_dat")
    earlier_days = by_day.rowsBetween(-history_length, -1)
    days = (
        days.withColumn("all_before", F.flatten(F.collect_list("basket").over(earlier_days)))
        .withColumn("history", last_n("all_before", history_length))
        .withColumn("previous_date", F.lag("t_dat").over(by_day))
        .select(
            "customer_id", "t_dat", "history",
            F.least(
                F.coalesce(F.datediff("t_dat", "previous_date"), F.lit(max_days_since)),
                F.lit(max_days_since),
            ).alias("days_since_last_purchase"),
        )
    )

    return (
        transactions.where(F.col("week").between(first_week, last_week))
        .join(days, ["customer_id", "t_dat"])
        .select(
            "customer_id", "article_id", "t_dat", "week", "sales_channel_id",
            # Spark's dayofweek is 1 = Sunday ... 7 = Saturday.
            F.dayofweek("t_dat").alias("day_of_week"),
            F.month("t_dat").alias("month"),
            "days_since_last_purchase", "history",
        )
    )


def build_test_targets(transactions: DataFrame, user_features: DataFrame, first_test_week: int) -> DataFrame:
    """What each customer bought in the test weeks, plus whether they are warm or cold."""
    return (
        transactions.where(F.col("week") >= first_test_week)
        .groupBy("customer_id")
        .agg(
            F.sort_array(F.collect_set("article_id")).alias("purchased"),
            F.min("t_dat").alias("first_date"),
        )
        .join(user_features.select("customer_id", "is_cold_start"), "customer_id", "left")
        .fillna(1, subset=["is_cold_start"])
    )


def main() -> int:
    config = load_config()
    processed = project_path(config["paths"]["processed_dir"])
    if not (processed / "transactions").is_dir():
        print("Cleaned data not found. Run: python -m src.data.clean", file=sys.stderr)
        return 1

    features = config["features"]
    history_length = config["model"]["history_length"]
    min_purchases = config["cleaning"]["cold_start_min_purchases"]

    spark = create_spark(config, "hm-features")
    transactions = spark.read.parquet(str(processed / "transactions"))
    customers = spark.read.parquet(str(processed / "customers"))
    articles = spark.read.parquet(str(processed / "articles"))

    first_week, last_week = training_weeks(
        transactions, config["split"]["train_weeks"], config["split"]["test_weeks"]
    )
    print(f"Training weeks {first_week}-{last_week}; features as of week {last_week}")

    items = build_item_features(
        transactions, articles, last_week, features["popularity_weeks"], features["price_buckets"]
    )
    items.write.mode("overwrite").parquet(str(processed / "item_features"))

    users = build_user_features(
        transactions, customers, last_week, config["split"]["train_weeks"], history_length, min_purchases
    )
    users.write.mode("overwrite").parquet(str(processed / "user_features"))
    users = spark.read.parquet(str(processed / "user_features"))

    train = build_training_examples(
        transactions, first_week, last_week, history_length, features["max_days_since"]
    )
    train.write.mode("overwrite").parquet(str(processed / "train"))

    test = build_test_targets(transactions, users, last_week + 1)
    test.write.mode("overwrite").parquet(str(processed / "test"))

    # Counts come from the written files.
    items = spark.read.parquet(str(processed / "item_features"))
    train = spark.read.parquet(str(processed / "train"))
    test = spark.read.parquet(str(processed / "test"))
    summary = {
        "features_as_of_week": last_week,
        "training_weeks": [first_week, last_week],
        "item_features": {
            "rows": items.count(),
            "sold_in_last_12_weeks": items.where("is_cold_start = 0").count(),
            "price_buckets": features["price_buckets"],
        },
        "user_features": {
            "rows": users.count(),
            "with_history": users.where(F.size("history") > 0).count(),
            "cold_start": users.where("is_cold_start = 1").count(),
        },
        "train": {
            "rows": train.count(),
            "customers": train.select("customer_id").distinct().count(),
            "articles": train.select("article_id").distinct().count(),
            "rows_without_history": train.where(F.size("history") == 0).count(),
        },
        "test": {
            "customers": test.count(),
            "warm_customers": test.where("is_cold_start = 0").count(),
            "cold_customers": test.where("is_cold_start = 1").count(),
            "avg_articles_per_customer": round(test.agg(F.avg(F.size("purchased"))).first()[0], 2),
        },
    }
    (processed / "features_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
