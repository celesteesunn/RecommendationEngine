import datetime as dt

import pytest

pytest.importorskip("pyspark")

from pyspark.sql import functions as F  # noqa: E402

from src.features.build_features import (  # noqa: E402
    ITEM_CATEGORY_COLUMNS,
    build_item_features,
    build_test_targets,
    build_training_examples,
    build_user_features,
)

MAX_DAYS = 365


@pytest.fixture
def transactions(spark):
    # Weeks 1-2 are training, week 3 is the test week.
    rows = [
        ("2020-01-01", "c1", "a1", 0.010, 1, 1, 0),
        ("2020-01-08", "c1", "a2", 0.020, 2, 1, 1),
        ("2020-01-08", "c1", "a3", 0.030, 2, 1, 1),
        ("2020-01-15", "c1", "a2", 0.020, 1, 1, 2),
        ("2020-01-16", "c2", "a3", 0.030, 2, 2, 2),
        ("2020-01-22", "c1", "a4", 0.040, 1, 1, 3),
        ("2020-01-22", "c3", "a1", 0.010, 1, 1, 3),
    ]
    return spark.createDataFrame(
        rows,
        "t_dat string, customer_id string, article_id string, price double, "
        "sales_channel_id int, quantity int, week int",
    ).withColumn("t_dat", F.to_date("t_dat"))


@pytest.fixture
def customers(spark):
    rows = [
        ("c1", 30, 0, "ACTIVE", "NONE"),
        ("c2", 32, 1, "ACTIVE", "NONE"),
        ("c3", 60, 0, "PRE-CREATE", "REGULARLY"),
    ]
    return spark.createDataFrame(
        rows,
        "customer_id string, age int, age_missing int, club_member_status string, "
        "fashion_news_frequency string",
    )


@pytest.fixture
def articles(spark):
    columns = ["article_id", "prod_name"] + ITEM_CATEGORY_COLUMNS
    rows = [{**{c: "x" for c in columns}, "article_id": a} for a in ("a1", "a2", "a3", "a4")]
    return spark.createDataFrame(rows)


def examples(transactions, history_length=20):
    rows = build_training_examples(transactions, 1, 2, history_length, MAX_DAYS).collect()
    return {(r.customer_id, r.t_dat, r.article_id): r for r in rows}


def test_training_examples_cover_only_the_training_weeks(transactions):
    assert set(examples(transactions)) == {
        ("c1", dt.date(2020, 1, 8), "a2"),
        ("c1", dt.date(2020, 1, 8), "a3"),
        ("c1", dt.date(2020, 1, 15), "a2"),
        ("c2", dt.date(2020, 1, 16), "a3"),
    }


def test_history_excludes_same_day_purchases(transactions):
    rows = examples(transactions)
    # On 8 Jan c1 also bought a3, but only the earlier a1 may be in the history.
    assert rows[("c1", dt.date(2020, 1, 8), "a2")].history == ["a1"]
    assert rows[("c1", dt.date(2020, 1, 15), "a2")].history == ["a1", "a2", "a3"]
    assert rows[("c2", dt.date(2020, 1, 16), "a3")].history == []


def test_history_keeps_the_most_recent_items(transactions):
    rows = examples(transactions, history_length=2)
    assert rows[("c1", dt.date(2020, 1, 15), "a2")].history == ["a2", "a3"]


def test_context_features(transactions):
    rows = examples(transactions)
    row = rows[("c1", dt.date(2020, 1, 8), "a2")]
    assert (row.day_of_week, row.month, row.days_since_last_purchase) == (4, 1, 7)  # Wednesday
    # A first-ever purchase gets the cap.
    assert rows[("c2", dt.date(2020, 1, 16), "a3")].days_since_last_purchase == MAX_DAYS


def test_user_features_as_of_the_last_training_week(transactions, customers):
    users = {
        r.customer_id: r
        for r in build_user_features(transactions, customers, as_of_week=2, window_weeks=2,
                                     history_length=20, min_purchases=2).collect()
    }
    c1 = users["c1"]
    assert c1.age_bucket == "25-34"
    assert c1.purchase_count == 3  # weeks 1-2 only
    assert c1.history == ["a1", "a3", "a2", "a2"]  # oldest first; week 3 is not visible
    assert c1.is_cold_start == 0

    assert users["c2"].age_bucket == "unknown"
    assert users["c2"].preferred_channel == 2
    assert users["c3"].age_bucket == "55+"
    assert (users["c3"].purchase_count, users["c3"].history, users["c3"].is_cold_start) == (0, [], 1)


def test_item_features_popularity_over_time(transactions, articles):
    items = {
        r.article_id: r
        for r in build_item_features(transactions, articles, as_of_week=2,
                                     popularity_weeks=[1, 2], price_buckets=2).collect()
    }
    assert (items["a2"].popularity_1w, items["a2"].popularity_2w) == (1, 2)
    assert (items["a3"].popularity_1w, items["a3"].popularity_2w) == (2, 3)
    # a1 last sold in week 0 and a4 only in the test week: both cold for the model.
    assert items["a1"].is_cold_start == 1
    assert items["a4"].is_cold_start == 1
    assert items["a4"].price_bucket == -1  # never sold before the cut-off, so no price
    assert items["a1"].price_bucket < items["a3"].price_bucket


def test_test_targets(transactions, customers):
    users = build_user_features(transactions, customers, 2, 2, 20, min_purchases=2)
    targets = {r.customer_id: r for r in build_test_targets(transactions, users, 3).collect()}
    assert set(targets) == {"c1", "c3"}
    assert targets["c1"].purchased == ["a4"] and targets["c1"].is_cold_start == 0
    assert targets["c3"].purchased == ["a1"] and targets["c3"].is_cold_start == 1
