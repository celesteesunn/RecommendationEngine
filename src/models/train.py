"""Train the two-tower model on the 12 training weeks.

Usage:
    python -m src.models.train                 # version = today's date
    python -m src.models.train --version v1

Writes models/<version>/:
    vocab/           the vocabularies (needed to load the model again)
    weights/         the trained weights
    training.json    settings, data sizes and the loss after every epoch
"""

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from src.config import load_config, project_path
from src.features.vocab import build_vocabularies, load_vocabularies, save_vocabularies
from src.models.dataset import CANDIDATE_CATEGORIES, QUERY_CATEGORIES, load_training_inputs
from src.models.two_tower import TwoTowerModel, tf

WEIGHTS_FILE = "weights/model"


def build_model(vocabularies: dict[str, list[str]], config: dict) -> TwoTowerModel:
    return TwoTowerModel(vocabularies, config["model"]["embedding_dim"], config["features"]["max_days_since"])


def latest_version(models_dir: Path) -> str:
    """The newest trained model in models/ (versions are dates, so they sort in time order)."""
    versions = sorted(p.name for p in models_dir.iterdir() if (p / "training.json").exists())
    if not versions:
        raise FileNotFoundError(f"No trained model in {models_dir}. Run: python -m src.models.train")
    return versions[-1]


def load_model(model_dir: Path, config: dict) -> tuple[TwoTowerModel, dict[str, list[str]]]:
    """Rebuild a trained model from its saved vocabularies and weights."""
    vocabularies = load_vocabularies(model_dir / "vocab")
    model = build_model(vocabularies, config)
    # Keras creates the layers on the first call, so run each tower once on a dummy row.
    one = np.zeros(1, np.int32)
    model.query_tower({
        **{name: one for name in QUERY_CATEGORIES},
        "history": np.zeros((1, config["model"]["history_length"]), np.int32),
        "days_since_last_purchase": np.zeros(1, np.float32),
    })
    model.candidate_tower({
        **{name: one for name in CANDIDATE_CATEGORIES},
        "popularity": np.zeros((1, len(config["features"]["popularity_weeks"])), np.float32),
    })
    model.load_weights(str(model_dir / WEIGHTS_FILE)).expect_partial()
    return model, vocabularies


def take(arrays: dict[str, np.ndarray], rows: np.ndarray) -> dict[str, np.ndarray]:
    return {name: values[rows] for name, values in arrays.items()}


def to_dataset(queries: dict, candidates: dict, batch_size: int, shuffle: bool, seed: int) -> tf.data.Dataset:
    dataset = tf.data.Dataset.from_tensor_slices({"query": queries, "candidate": candidates})
    if shuffle:
        dataset = dataset.shuffle(200_000, seed=seed, reshuffle_each_iteration=True)
    return dataset.batch(batch_size).prefetch(tf.data.AUTOTUNE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default=dt.date.today().isoformat())
    args = parser.parse_args()

    config = load_config()
    model_config = config["model"]
    processed = project_path(config["paths"]["processed_dir"])
    out_dir = project_path(config["paths"]["models_dir"]) / args.version
    if not (processed / "train").is_dir():
        print("Feature tables not found. Run: python -m src.features.build_features", file=sys.stderr)
        return 1

    print("Building vocabularies ...")
    vocabularies = build_vocabularies(
        pq.read_table(processed / "train",
                      columns=["customer_id", "article_id", "day_of_week", "month", "sales_channel_id"]).to_pandas(),
        pq.read_table(processed / "user_features").select(
            ["age_bucket", "club_member_status", "fashion_news_frequency"]).to_pandas(),
        pq.read_table(processed / "item_features").to_pandas(),
    )
    save_vocabularies(vocabularies, out_dir / "vocab")

    print("Encoding training examples ...")
    queries, candidates = load_training_inputs(
        processed, vocabularies, model_config["history_length"], config["features"]["popularity_weeks"]
    )
    rows = len(candidates["article_id"])
    # The chance that a product is the positive example in a random training row.
    counts = np.bincount(candidates["article_id"])
    candidates["sampling_probability"] = (counts[candidates["article_id"]] / rows).astype(np.float32)

    # A random slice is held out to watch for overfitting and to stop training early.
    rng = np.random.default_rng(model_config["seed"])
    order = rng.permutation(rows)
    n_valid = int(rows * model_config["validation_share"])
    valid_rows, train_rows = order[:n_valid], order[n_valid:]
    train_data = to_dataset(take(queries, train_rows), take(candidates, train_rows),
                            model_config["batch_size"], shuffle=True, seed=model_config["seed"])
    valid_data = to_dataset(take(queries, valid_rows), take(candidates, valid_rows),
                            model_config["batch_size"], shuffle=False, seed=model_config["seed"])
    del queries, candidates

    gpus = tf.config.list_physical_devices("GPU")
    print(f"Training on {len(train_rows):,} examples ({n_valid:,} held out) using "
          f"{'GPU: ' + gpus[0].name if gpus else 'CPU'}")

    tf.keras.utils.set_random_seed(model_config["seed"])
    model = build_model(vocabularies, config)
    model.compile(optimizer=tf.keras.optimizers.Adagrad(learning_rate=model_config["learning_rate"]))
    started = time.time()
    history = model.fit(
        train_data,
        validation_data=valid_data,
        epochs=model_config["epochs"],
        callbacks=[tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=model_config["early_stopping_patience"], restore_best_weights=True
        )],
        verbose=2,
    )
    minutes = round((time.time() - started) / 60, 1)

    model.save_weights(str(out_dir / WEIGHTS_FILE))
    record = {
        "version": args.version,
        "device": "GPU" if gpus else "CPU",
        "training_minutes": minutes,
        "examples": {"train": len(train_rows), "validation": n_valid},
        "vocabulary_sizes": {name: len(values) for name, values in vocabularies.items()},
        "settings": {**model_config, "features": config["features"]},
        "epochs_run": len(history.history["loss"]),
        "loss": [round(v, 4) for v in history.history["loss"]],
        "val_loss": [round(v, 4) for v in history.history["val_loss"]],
    }
    (out_dir / "training.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    print(f"Saved model to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
