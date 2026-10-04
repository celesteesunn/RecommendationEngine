import pandas as pd

from src.models.baselines import age_group_popularity, fill_up, global_popularity, repurchase, top_articles


def purchases(rows):
    return pd.DataFrame(rows, columns=["customer_id", "article_id", "t_dat", "quantity"])


LAST_WEEK = purchases([
    ("c1", "a", "2020-01-15", 1),
    ("c2", "b", "2020-01-15", 3),
    ("c3", "a", "2020-01-16", 1),
    ("c3", "c", "2020-01-16", 1),
])


def test_top_articles_counts_units_and_breaks_ties_by_id():
    assert top_articles(LAST_WEEK, 3) == ["b", "a", "c"]


def test_fill_up_skips_duplicates():
    assert fill_up(["c"], ["b", "c", "a"], 3) == ["c", "b", "a"]


def test_global_popularity_is_the_same_for_everyone():
    recs = global_popularity(LAST_WEEK, ["c1", "new"], 2)
    assert recs == {"c1": ["b", "a"], "new": ["b", "a"]}


def test_age_group_popularity_falls_back_to_global():
    users = pd.DataFrame({"customer_id": ["c1", "c3", "c9"], "age_bucket": ["25-34", "25-34", "55+"]})
    recs = age_group_popularity(LAST_WEEK, users, ["c1", "c9"], 3)
    # 25-34 bought a twice and c once; then the global list fills the gap.
    assert recs["c1"] == ["a", "c", "b"]
    # Nobody aged 55+ bought anything, so they get the global best-sellers.
    assert recs["c9"] == ["b", "a", "c"]


def test_repurchase_puts_own_items_first():
    window = purchases([
        ("c1", "x", "2020-01-01", 1),
        ("c1", "y", "2020-01-02", 1),
        ("c1", "x", "2020-01-08", 1),
    ])
    recs = repurchase(window, LAST_WEEK, ["c1", "new"], 4)
    assert recs["c1"] == ["x", "y", "b", "a"]  # x bought twice, then y, then best-sellers
    assert recs["new"] == ["b", "a", "c"]
