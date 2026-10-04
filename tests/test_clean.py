import datetime as dt

import pytest

pytest.importorskip("pyspark")

from src.data.clean import (  # noqa: E402
    ARTICLE_COLUMNS,
    add_cold_start_flags,
    clean_articles,
    clean_customers,
    clean_transactions,
    keep_known_ids,
    training_weeks,
)


@pytest.fixture
def raw_transactions(spark):
    rows = [
        # Two identical rows: one purchase of quantity 2.
        ("2020-09-22", "c1", "0108775015", 0.01, 2),
        ("2020-09-22", "c1", "0108775015", 0.01, 2),
        ("2020-09-16", "c2", "108775044", 0.02, 1),  # leading zero lost upstream
        ("2020-09-15", "c1", "0108775015", 0.01, 2),
        ("2020-09-01", "c3", "0108775015", 0.01, 1),
    ]
    return spark.createDataFrame(
        rows, "t_dat string, customer_id string, article_id string, price double, sales_channel_id int"
    )


def test_transactions_collapse_duplicates_into_quantity(raw_transactions):
    rows = clean_transactions(raw_transactions).where("customer_id = 'c1'").collect()
    by_date = {r.t_dat: r.quantity for r in rows}
    assert by_date == {dt.date(2020, 9, 22): 2, dt.date(2020, 9, 15): 1}


def test_transactions_keep_ten_character_article_ids(raw_transactions):
    ids = {r.article_id for r in clean_transactions(raw_transactions).collect()}
    assert ids == {"0108775015", "0108775044"}


def test_transactions_last_week_is_the_final_seven_days(raw_transactions):
    weeks = {r.t_dat: r.week for r in clean_transactions(raw_transactions).collect()}
    # 2020-09-22 is the last date: 09-16..09-22 share the final week, 09-15 is one before.
    assert weeks[dt.date(2020, 9, 22)] == weeks[dt.date(2020, 9, 16)] == 3
    assert weeks[dt.date(2020, 9, 15)] == 2
    assert weeks[dt.date(2020, 9, 1)] == 0


def test_customers_fill_missing_values(spark):
    rows = [
        ("c1", 1.0, 1.0, "ACTIVE", "Regularly", 20.0, "p1"),
        ("c2", None, None, "ACTIVE", "None", 40.0, "p2"),
        ("c3", None, None, "ACTIVE", "NONE", None, "p3"),
        ("c4", None, None, None, None, None, "p4"),
    ]
    raw = spark.createDataFrame(
        rows,
        "customer_id string, FN double, Active double, club_member_status string, "
        "fashion_news_frequency string, age double, postal_code string",
    )
    customers = {r.customer_id: r for r in clean_customers(raw).collect()}

    assert customers["c2"].FN == 0 and customers["c2"].Active == 0
    assert customers["c2"].fashion_news_frequency == customers["c3"].fashion_news_frequency == "NONE"
    assert customers["c4"].club_member_status == "UNKNOWN"
    assert customers["c4"].fashion_news_frequency == "UNKNOWN"

    # c3 takes the ACTIVE median; c4's group has no ages, so it takes the overall median.
    assert customers["c3"].age_missing == 1 and customers["c3"].age in (20, 40)
    assert customers["c4"].age_missing == 1 and customers["c4"].age in (20, 40)
    assert customers["c1"].age_missing == 0 and customers["c1"].age == 20


def test_articles_fill_description_and_keep_model_columns(spark):
    columns = ARTICLE_COLUMNS + ["graphical_appearance_name"]
    values = {c: "x" for c in columns}
    raw = spark.createDataFrame(
        [
            {**values, "article_id": "108775015", "detail_desc": None},
            {**values, "article_id": "0108775044"},
        ],
    )
    articles = {r.article_id: r for r in clean_articles(raw).collect()}

    assert set(articles) == {"0108775015", "0108775044"}
    assert articles["0108775015"].detail_desc == ""
    assert "graphical_appearance_name" not in clean_articles(raw).columns


def test_keep_known_ids_drops_orphans(spark, raw_transactions):
    transactions = clean_transactions(raw_transactions)
    customers = spark.createDataFrame([("c1",), ("c2",)], "customer_id string")
    articles = spark.createDataFrame([("0108775015",)], "article_id string")

    kept = keep_known_ids(transactions, customers, articles).collect()
    assert {(r.customer_id, r.article_id) for r in kept} == {("c1", "0108775015")}


def test_cold_start_flags_use_the_training_window_only(spark, raw_transactions):
    transactions = clean_transactions(raw_transactions)
    first, last = training_weeks(transactions, train_weeks=3, test_weeks=1)
    assert (first, last) == (0, 2)

    customers = spark.createDataFrame([("c1",), ("c2",), ("c3",), ("c9",)], "customer_id string")
    articles = spark.createDataFrame([("0108775015",), ("0108775044",)], "article_id string")
    customers, articles = add_cold_start_flags(
        transactions, customers, articles, first, last, min_purchases=1
    )

    customer_flags = {r.customer_id: (r.train_purchases, r.is_cold_start) for r in customers.collect()}
    # c2 only bought in the test week, so it has no training purchases.
    assert customer_flags == {"c1": (1, 0), "c2": (0, 1), "c3": (1, 0), "c9": (0, 1)}

    article_flags = {r.article_id: r.is_cold_start for r in articles.collect()}
    assert article_flags == {"0108775015": 0, "0108775044": 1}
