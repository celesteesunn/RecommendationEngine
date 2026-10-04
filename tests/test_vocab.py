import pandas as pd
import pyarrow as pa

from src.features.vocab import (
    ITEM_COLUMNS,
    build_vocabularies,
    encode,
    encode_sequences,
    load_vocabularies,
    save_vocabularies,
    vocabulary_size,
)


def tables():
    train = pd.DataFrame({
        "customer_id": ["c1", "c1", "c2"],
        "article_id": ["0002", "0001", "0002"],
        "day_of_week": [4, 4, 5],
        "month": [1, 1, 1],
        "sales_channel_id": [2, 1, 2],
    })
    users = pd.DataFrame({
        "age_bucket": ["25-34", "unknown", "25-34", "55+"],
        "club_member_status": ["ACTIVE"] * 4,
        "fashion_news_frequency": ["NONE", "NONE", None, "REGULARLY"],
    })
    items = pd.DataFrame({column: ["x", "y", "x"] for column in ITEM_COLUMNS})
    items["department_no"] = [1676, 1339, 1676]
    items["price_bucket"] = [3, -1, 3]
    return train, users, items


def test_ids_come_from_training_most_frequent_first():
    vocabularies = build_vocabularies(*tables())
    assert vocabularies["customer_id"] == ["c1", "c2"]
    # Leading zeros survive because IDs stay strings.
    assert vocabularies["article_id"] == ["0002", "0001"]


def test_categories_are_strings_without_missing_values():
    vocabularies = build_vocabularies(*tables())
    assert vocabularies["age_bucket"] == ["25-34", "55+", "unknown"]
    assert vocabularies["fashion_news_frequency"] == ["NONE", "REGULARLY"]
    assert vocabularies["department_no"] == ["1676", "1339"]
    assert vocabularies["price_bucket"] == ["3", "-1"]
    assert vocabularies["day_of_week"] == ["4", "5"]


def test_save_and_load_round_trip(tmp_path):
    vocabularies = build_vocabularies(*tables())
    save_vocabularies(vocabularies, tmp_path)
    assert load_vocabularies(tmp_path) == vocabularies
    assert (tmp_path / "sizes.json").exists()


def test_encode_reserves_padding_and_unknown():
    vocabulary = ["0002", "0001"]
    assert encode(pa.array(["0001", "0002", "9999", None]), vocabulary).tolist() == [3, 2, 1, 1]
    assert encode(pa.array([4, 5]), ["5", "4"]).tolist() == [3, 2]  # numbers match as strings
    assert vocabulary_size(vocabulary) == 4


def test_encode_sequences_right_aligns_and_truncates():
    lists = pa.chunked_array([pa.array([["a", "b", "c"], [], ["b"]]), pa.array([["z", "a"]])])
    matrix = encode_sequences(lists, ["a", "b", "c"], length=2)
    assert matrix.tolist() == [
        [3, 4],  # last two of a, b, c
        [0, 0],  # no history
        [0, 3],  # padded at the front
        [1, 2],  # z is unknown
    ]
