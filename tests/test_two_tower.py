import numpy as np
import pytest

pytest.importorskip("tensorflow_recommenders")

from src.models.dataset import CANDIDATE_CATEGORIES, QUERY_CATEGORIES  # noqa: E402
from src.models.two_tower import TwoTowerModel, tf  # noqa: E402

HISTORY = 5
ROWS = 16


@pytest.fixture
def vocabularies():
    names = set(QUERY_CATEGORIES) | set(CANDIDATE_CATEGORIES)
    return {name: [f"{name}_{i}" for i in range(6)] for name in names}


@pytest.fixture
def batch():
    rng = np.random.default_rng(0)
    # Indexes 0..7: padding, unknown and the six known values.
    queries = {name: rng.integers(1, 8, ROWS).astype(np.int32) for name in QUERY_CATEGORIES}
    queries["history"] = rng.integers(0, 8, (ROWS, HISTORY)).astype(np.int32)
    queries["days_since_last_purchase"] = rng.integers(0, 366, ROWS).astype(np.float32)
    candidates = {name: rng.integers(1, 8, ROWS).astype(np.int32) for name in CANDIDATE_CATEGORIES}
    candidates["popularity"] = rng.integers(0, 500, (ROWS, 3)).astype(np.float32)
    return {"query": queries, "candidate": candidates}


def test_towers_output_vectors_of_the_same_size(vocabularies, batch):
    model = TwoTowerModel(vocabularies, output_dim=64, max_days_since=365)
    assert model.query_tower(batch["query"]).shape == (ROWS, 64)
    assert model.candidate_tower(batch["candidate"]).shape == (ROWS, 64)


def test_empty_history_does_not_break_the_average(vocabularies, batch):
    model = TwoTowerModel(vocabularies, output_dim=8, max_days_since=365)
    batch["query"]["history"][:] = 0
    assert np.isfinite(model.query_tower(batch["query"]).numpy()).all()


def test_training_lowers_the_loss(vocabularies, batch):
    tf.keras.utils.set_random_seed(0)
    model = TwoTowerModel(vocabularies, output_dim=8, max_days_since=365)
    model.compile(optimizer=tf.keras.optimizers.Adagrad(learning_rate=0.05))
    data = tf.data.Dataset.from_tensor_slices(batch).batch(ROWS)
    history = model.fit(data, epochs=20, verbose=0)
    losses = history.history["loss"]
    assert np.isfinite(losses).all()
    assert losses[-1] < losses[0]
