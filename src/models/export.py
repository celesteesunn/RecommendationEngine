"""Export a trained model for serving.

Usage:
    python -m src.models.export                  # the newest model in models/
    python -m src.models.export --version 2026-10-05

Writes into models/<version>/:
    query_tower/          SavedModel: raw customer and visit values -> customer vector
    candidate_tower/      SavedModel: raw product values -> product vector
    item_embeddings.npy   the vectors of the products the API can recommend
    item_ids.npy          their article IDs, in the same order
    export.json           sizes and settings

The exported towers take plain values (IDs as text, day of week as a number) and do the
vocabulary lookups themselves, so the API needs no project code to call them. Before
finishing, the export reloads both towers and checks they give the same vectors as the
trained model.
"""

import argparse
import json
import sys

import numpy as np
import pyarrow as pa

from src.config import load_config, project_path
from src.models.dataset import encode_candidates, encode_queries, load_candidate_items, load_test_queries
from src.models.evaluate import in_batches
from src.models.train import latest_version, load_model
from src.models.two_tower import tf

QUERY_TEXT = ["customer_id", "age_bucket", "club_member_status", "fashion_news_frequency"]
QUERY_NUMBERS = ["day_of_week", "month", "sales_channel_id"]
CANDIDATE_TEXT = ["article_id", "product_type_name", "colour_group_name", "garment_group_name", "index_group_name"]
CANDIDATE_NUMBERS = ["department_no", "price_bucket"]
# Exported vectors must match the trained model to this tolerance.
TOLERANCE = 1e-4


def lookup(vocabulary: list[str]) -> tf.keras.layers.StringLookup:
    # mask_token="" and one OOV slot give 0 = padding, 1 = unknown, 2... = vocabulary:
    # the same indexes as src.features.vocab.encode.
    return tf.keras.layers.StringLookup(vocabulary=vocabulary, mask_token="", num_oov_indices=1)


def as_text(values: tf.Tensor) -> tf.Tensor:
    return values if values.dtype == tf.string else tf.strings.as_string(values)


class QueryModel(tf.Module):
    """Customer and visit values -> customer vector."""

    def __init__(self, tower: tf.keras.Model, vocabularies: dict[str, list[str]]):
        super().__init__()
        self.tower = tower
        self.lookups = {name: lookup(vocabularies[name]) for name in QUERY_TEXT + QUERY_NUMBERS}
        self.history_lookup = lookup(vocabularies["article_id"])

    @tf.function(input_signature=[
        *[tf.TensorSpec([None], tf.string, name=name) for name in QUERY_TEXT],
        tf.TensorSpec([None, None], tf.string, name="history"),
        *[tf.TensorSpec([None], tf.int64, name=name) for name in QUERY_NUMBERS],
        tf.TensorSpec([None], tf.float32, name="days_since_last_purchase"),
    ])
    def __call__(self, customer_id, age_bucket, club_member_status, fashion_news_frequency, history,
                 day_of_week, month, sales_channel_id, days_since_last_purchase):
        raw = {
            "customer_id": customer_id, "age_bucket": age_bucket,
            "club_member_status": club_member_status, "fashion_news_frequency": fashion_news_frequency,
            "day_of_week": day_of_week, "month": month, "sales_channel_id": sales_channel_id,
        }
        features = {name: self.lookups[name](as_text(values)) for name, values in raw.items()}
        features["history"] = self.history_lookup(history)
        features["days_since_last_purchase"] = days_since_last_purchase
        return {"embedding": self.tower(features)}


class CandidateModel(tf.Module):
    """Product values -> product vector."""

    def __init__(self, tower: tf.keras.Model, vocabularies: dict[str, list[str]]):
        super().__init__()
        self.tower = tower
        self.lookups = {name: lookup(vocabularies[name]) for name in CANDIDATE_TEXT + CANDIDATE_NUMBERS}

    @tf.function(input_signature=[
        *[tf.TensorSpec([None], tf.string, name=name) for name in CANDIDATE_TEXT],
        *[tf.TensorSpec([None], tf.int64, name=name) for name in CANDIDATE_NUMBERS],
        tf.TensorSpec([None, None], tf.float32, name="popularity"),
    ])
    def __call__(self, article_id, product_type_name, colour_group_name, garment_group_name,
                 index_group_name, department_no, price_bucket, popularity):
        raw = {
            "article_id": article_id, "product_type_name": product_type_name,
            "colour_group_name": colour_group_name, "garment_group_name": garment_group_name,
            "index_group_name": index_group_name, "department_no": department_no,
            "price_bucket": price_bucket,
        }
        features = {name: self.lookups[name](as_text(values)) for name, values in raw.items()}
        features["popularity"] = popularity
        return {"embedding": self.tower(features)}


def history_matrix(histories: list[list[str]], length: int) -> np.ndarray:
    """Right-aligned (rows, length) text matrix: newest item last, "" as padding."""
    matrix = np.full((len(histories), length), "", dtype=object)
    for row, items in enumerate(histories):
        recent = items[-length:]
        if recent:
            matrix[row, length - len(recent):] = recent
    return matrix


def raw_queries(table: pa.Table, history_length: int) -> dict[str, tf.Tensor]:
    """Plain values for the exported query tower, the way the API will send them."""
    inputs = {name: tf.constant(table[name].to_pylist()) for name in QUERY_TEXT}
    inputs["history"] = tf.constant(history_matrix(table["history"].to_pylist(), history_length).astype(str))
    for name in QUERY_NUMBERS:
        inputs[name] = tf.constant(table[name].to_numpy().astype(np.int64))
    inputs["days_since_last_purchase"] = tf.constant(table["days_since_last_purchase"].to_numpy().astype(np.float32))
    return inputs


def raw_candidates(table: pa.Table, popularity_weeks: list[int]) -> dict[str, tf.Tensor]:
    inputs = {name: tf.constant(table[name].to_pylist()) for name in CANDIDATE_TEXT}
    for name in CANDIDATE_NUMBERS:
        inputs[name] = tf.constant(table[name].to_numpy().astype(np.int64))
    inputs["popularity"] = tf.constant(
        np.stack([table[f"popularity_{w}w"].to_numpy() for w in popularity_weeks], axis=1).astype(np.float32)
    )
    return inputs


def max_difference(exported, raw_inputs: dict[str, tf.Tensor], expected: np.ndarray) -> float:
    actual = exported.signatures["serving_default"](**raw_inputs)["embedding"].numpy()
    return float(np.abs(actual - expected).max())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version")
    args = parser.parse_args()

    config = load_config()
    processed = project_path(config["paths"]["processed_dir"])
    models_dir = project_path(config["paths"]["models_dir"])
    version = args.version or latest_version(models_dir)
    model_dir = models_dir / version
    history_length = config["model"]["history_length"]
    popularity_weeks = config["features"]["popularity_weeks"]
    candidate_weeks = config["evaluation"]["candidate_weeks"]

    # Newer NVIDIA GPUs multiply in reduced precision (TF32) by default, which makes results
    # depend slightly on the batch size. The stored vectors should be exact float32.
    tf.config.experimental.enable_tensor_float_32_execution(False)
    model, vocabularies = load_model(model_dir, config)

    print("Saving the towers ...")
    query_model = QueryModel(model.query_tower, vocabularies)
    candidate_model = CandidateModel(model.candidate_tower, vocabularies)
    tf.saved_model.save(query_model, str(model_dir / "query_tower"),
                        signatures={"serving_default": query_model.__call__})
    tf.saved_model.save(candidate_model, str(model_dir / "candidate_tower"),
                        signatures={"serving_default": candidate_model.__call__})

    print("Computing product vectors ...")
    items = load_candidate_items(processed, candidate_weeks)
    item_vectors = in_batches(model.candidate_tower,
                              encode_candidates(items, vocabularies, popularity_weeks), 8192)
    np.save(model_dir / "item_embeddings.npy", item_vectors.astype(np.float32))
    np.save(model_dir / "item_ids.npy", np.asarray(items["article_id"].to_pylist(), dtype="U10"))

    print("Checking the exported towers against the trained model ...")
    sample = load_test_queries(processed, config["features"]["max_days_since"]).slice(0, 512)
    expected_queries = in_batches(model.query_tower, encode_queries(sample, vocabularies, history_length), 512)
    query_difference = max_difference(tf.saved_model.load(str(model_dir / "query_tower")),
                                       raw_queries(sample, history_length), expected_queries)
    item_sample = items.slice(0, 512)
    candidate_difference = max_difference(tf.saved_model.load(str(model_dir / "candidate_tower")),
                                           raw_candidates(item_sample, popularity_weeks), item_vectors[:512])

    record = {
        "version": version,
        "products": len(items),
        "product_selection": f"sold in the last {candidate_weeks} week(s) before the cut-off",
        "embedding_dim": int(item_vectors.shape[1]),
        "check": {
            "query_tower_max_difference": query_difference,
            "candidate_tower_max_difference": candidate_difference,
            "tolerance": TOLERANCE,
        },
    }
    (model_dir / "export.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))

    if max(query_difference, candidate_difference) > TOLERANCE:
        print("The exported towers do not match the trained model.", file=sys.stderr)
        return 1
    print(f"Exported model {version} to {model_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
