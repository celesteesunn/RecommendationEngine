"""Vocabularies: the list of known values for every ID and category column.

The model turns each value into an integer index with a lookup layer built from these lists;
any value not in a list (a new customer, a new product) maps to a shared "unknown" index.
The lists are saved next to the trained model so serving uses exactly the same indexes.

Values are stored as strings, most frequent first.

Index layout (the same as a Keras StringLookup with mask_token="" and one OOV slot, so a
lookup layer built from a saved list gives identical indexes):
    0 = padding (empty history slots), 1 = unknown value, 2... = the vocabulary in order.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc

PADDING_INDEX = 0
UNKNOWN_INDEX = 1
FIRST_INDEX = 2

# Column -> which table its values come from.
USER_COLUMNS = ["age_bucket", "club_member_status", "fashion_news_frequency"]
ITEM_COLUMNS = [
    "product_type_name", "product_group_name", "colour_group_name",
    "garment_group_name", "department_no", "index_group_name", "price_bucket",
]
CONTEXT_COLUMNS = ["day_of_week", "month", "sales_channel_id"]


def _ranked_values(values: pd.Series) -> list[str]:
    """Distinct non-missing values as strings, most frequent first (ties alphabetical)."""
    counts = values.dropna().astype(str).value_counts()
    return sorted(counts.index, key=lambda v: (-counts[v], v))


def build_vocabularies(train: pd.DataFrame, users: pd.DataFrame, items: pd.DataFrame) -> dict[str, list[str]]:
    """Build every vocabulary from the training examples and the feature tables.

    customer_id and article_id only include values seen in training: the model has no
    learned embedding for anything else, so those share the unknown index.
    """
    vocabularies = {
        "customer_id": _ranked_values(train["customer_id"]),
        "article_id": _ranked_values(train["article_id"]),
    }
    for column in USER_COLUMNS:
        vocabularies[column] = _ranked_values(users[column])
    for column in ITEM_COLUMNS:
        vocabularies[column] = _ranked_values(items[column])
    for column in CONTEXT_COLUMNS:
        vocabularies[column] = _ranked_values(train[column])
    return vocabularies


def save_vocabularies(vocabularies: dict[str, list[str]], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for column, values in vocabularies.items():
        (directory / f"{column}.txt").write_text("\n".join(values) + "\n", encoding="utf-8")
    sizes = {column: len(values) for column, values in vocabularies.items()}
    (directory / "sizes.json").write_text(json.dumps(sizes, indent=2), encoding="utf-8")


def load_vocabularies(directory: Path) -> dict[str, list[str]]:
    return {
        path.stem: path.read_text(encoding="utf-8").splitlines()
        for path in sorted(directory.glob("*.txt"))
    }


def vocabulary_size(vocabulary: list[str]) -> int:
    """Number of indexes a lookup over this vocabulary uses (padding + unknown + values)."""
    return len(vocabulary) + FIRST_INDEX


def encode(values: pa.Array | pa.ChunkedArray, vocabulary: list[str]) -> np.ndarray:
    """Map each value to its index. Works on Arrow arrays, so no Python strings are created."""
    positions = pc.index_in(pc.cast(values, pa.string()), value_set=pa.array(vocabulary, pa.string()))
    indexes = pc.fill_null(pc.add(positions, FIRST_INDEX), UNKNOWN_INDEX)
    return np.asarray(indexes.to_numpy(), dtype=np.int32)


def encode_sequences(lists: pa.ListArray | pa.ChunkedArray, vocabulary: list[str], length: int) -> np.ndarray:
    """Encode lists into a (rows, length) matrix, keeping the last `length` items of each.

    Lists are right-aligned: the newest item is always in the last column and shorter lists
    are padded with 0 at the front.
    """
    if isinstance(lists, pa.ChunkedArray):
        lists = lists.combine_chunks()
    flat = encode(lists.flatten(), vocabulary)
    offsets = lists.offsets.to_numpy()
    lengths = np.diff(offsets)
    keep = np.minimum(lengths, length)

    rows = np.repeat(np.arange(len(lists)), keep)
    within = np.arange(keep.sum()) - np.repeat(np.cumsum(keep) - keep, keep)
    source = np.repeat(offsets[:-1] + lengths - keep - offsets[0], keep) + within
    columns = np.repeat(length - keep, keep) + within

    matrix = np.full((len(lists), length), PADDING_INDEX, dtype=np.int32)
    matrix[rows, columns] = flat[source]
    return matrix
