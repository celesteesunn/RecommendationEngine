"""Turn the feature tables into the integer and float arrays the two-tower model reads.

Everything stays in Arrow and NumPy, so millions of rows fit in memory without creating
Python objects for each ID.
"""

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.features.vocab import encode, encode_sequences

QUERY_CATEGORIES = [
    "customer_id", "age_bucket", "club_member_status", "fashion_news_frequency",
    "day_of_week", "month", "sales_channel_id",
]
USER_COLUMNS = ["customer_id", "age_bucket", "club_member_status", "fashion_news_frequency"]
CANDIDATE_CATEGORIES = [
    "article_id", "product_type_name", "colour_group_name", "garment_group_name",
    "department_no", "index_group_name", "price_bucket",
]


def popularity_columns(popularity_weeks: list[int]) -> list[str]:
    return [f"popularity_{w}w" for w in popularity_weeks]


def encode_queries(table: pa.Table, vocabularies: dict[str, list[str]], history_length: int) -> dict[str, np.ndarray]:
    """Query-tower inputs: customer profile, purchase history and the context of the visit."""
    inputs = {name: encode(table[name], vocabularies[name]) for name in QUERY_CATEGORIES}
    # The history holds article IDs, so it uses the article vocabulary.
    inputs["history"] = encode_sequences(table["history"], vocabularies["article_id"], history_length)
    inputs["days_since_last_purchase"] = table["days_since_last_purchase"].to_numpy().astype(np.float32)
    return inputs


def encode_candidates(table: pa.Table, vocabularies: dict[str, list[str]], popularity_weeks: list[int]) -> dict[str, np.ndarray]:
    """Candidate-tower inputs: product attributes and popularity over time."""
    inputs = {name: encode(table[name], vocabularies[name]) for name in CANDIDATE_CATEGORIES}
    inputs["popularity"] = np.stack(
        [table[c].to_numpy().astype(np.float32) for c in popularity_columns(popularity_weeks)], axis=1
    )
    return inputs


def rows_matching(keys: pa.ChunkedArray, table: pa.Table, key: str) -> pa.Table:
    """The rows of table whose key matches each value of keys, in the same order."""
    positions = pc.index_in(keys, value_set=table[key].combine_chunks())
    if positions.null_count:
        raise ValueError(f"{positions.null_count} values of {key} are missing from the table")
    return table.take(positions)


def load_training_inputs(
    processed: Path,
    vocabularies: dict[str, list[str]],
    history_length: int,
    popularity_weeks: list[int],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """One (query, candidate) pair per training purchase."""
    train = pq.read_table(processed / "train")
    users = pq.read_table(processed / "user_features", columns=USER_COLUMNS)
    items = pq.read_table(processed / "item_features",
                          columns=CANDIDATE_CATEGORIES + popularity_columns(popularity_weeks))

    profile = rows_matching(train["customer_id"], users, "customer_id")
    for name in USER_COLUMNS[1:]:
        train = train.append_column(name, profile[name])

    queries = encode_queries(train, vocabularies, history_length)
    candidates = encode_candidates(rows_matching(train["article_id"], items, "article_id"),
                                   vocabularies, popularity_weeks)
    return queries, candidates


def load_candidate_items(processed: Path) -> pa.Table:
    """The products the model ranks: those sold at least once in the training window."""
    items = pq.read_table(processed / "item_features")
    return items.filter(pc.equal(items["is_cold_start"], 0))


def load_test_queries(processed: Path, max_days_since: int) -> pa.Table:
    """One query per test customer: their features as of the cut-off, and the visit's context.

    The context is the day of their first test-week purchase (when they "visit the shop"),
    through their usual channel.
    """
    test = pq.read_table(processed / "test")
    users = pq.read_table(processed / "user_features")
    profile = rows_matching(test["customer_id"], users, "customer_id")

    first_date = test["first_date"]
    days_since = pc.days_between(profile["last_purchase_date"], first_date)
    days_since = pc.min_element_wise(pc.fill_null(days_since, max_days_since), max_days_since)
    return pa.table({
        "customer_id": test["customer_id"],
        "age_bucket": profile["age_bucket"],
        "club_member_status": profile["club_member_status"],
        "fashion_news_frequency": profile["fashion_news_frequency"],
        "history": profile["history"],
        # Sunday = 1 ... Saturday = 7, the same as Spark's dayofweek in the training data.
        "day_of_week": pc.day_of_week(first_date, count_from_zero=False, week_start=7),
        "month": pc.month(first_date),
        "sales_channel_id": profile["preferred_channel"],
        "days_since_last_purchase": days_since,
    })
