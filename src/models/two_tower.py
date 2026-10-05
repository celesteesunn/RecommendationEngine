"""The two-tower retrieval model, built with TensorFlow Recommenders.

The query tower turns a customer and the context of their visit into a 64-number vector.
The candidate tower turns a product into a vector of the same size. The match score is the
dot product of the two, so all product vectors can be computed once in advance and a
customer's best products found with a fast vector search.

Inputs are integer indexes from src.features.vocab (0 = padding, 1 = unknown) plus a few
numbers; see src.models.dataset.
"""

import math
import os

# TFRS 0.7 needs Keras 2, which TensorFlow 2.16+ only provides through tf-keras.
os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")

import tensorflow as tf  # noqa: E402
import tensorflow_recommenders as tfrs  # noqa: E402

from src.features.vocab import vocabulary_size  # noqa: E402

# Embedding size per input, from the blueprint (section 6.1). These are starting points.
QUERY_EMBEDDINGS = {
    "customer_id": 32, "age_bucket": 8, "club_member_status": 4, "fashion_news_frequency": 4,
    "day_of_week": 4, "month": 4, "sales_channel_id": 2,
}
HISTORY_EMBEDDING = 32
CANDIDATE_EMBEDDINGS = {
    "article_id": 32, "product_type_name": 8, "colour_group_name": 8, "garment_group_name": 8,
    "department_no": 8, "index_group_name": 4, "price_bucket": 4,
}
HIDDEN_UNITS = 128
# log(1 + sales) is at most about 10 for this dataset, so dividing by 10 keeps it near 0-1.
POPULARITY_SCALE = 10.0


def _embeddings(sizes: dict[str, int], vocabularies: dict[str, list[str]]) -> dict[str, tf.keras.layers.Layer]:
    return {
        name: tf.keras.layers.Embedding(vocabulary_size(vocabularies[name]), dim, name=f"{name}_embedding")
        for name, dim in sizes.items()
    }


class QueryTower(tf.keras.Model):
    """Customer profile + purchase history + visit context -> customer vector."""

    def __init__(self, vocabularies: dict[str, list[str]], output_dim: int, max_days_since: int):
        super().__init__(name="query_tower")
        self.embeddings = _embeddings(QUERY_EMBEDDINGS, vocabularies)
        self.history_embedding = tf.keras.layers.Embedding(
            vocabulary_size(vocabularies["article_id"]), HISTORY_EMBEDDING, name="history_embedding"
        )
        self.days_scale = math.log1p(max_days_since)
        self.hidden = tf.keras.layers.Dense(HIDDEN_UNITS, activation="relu")
        self.output_layer = tf.keras.layers.Dense(output_dim)

    def call(self, features: dict[str, tf.Tensor]) -> tf.Tensor:
        parts = [layer(features[name]) for name, layer in self.embeddings.items()]

        # Average of the history embeddings, ignoring padding (index 0).
        history = self.history_embedding(features["history"])
        mask = tf.cast(features["history"] > 0, tf.float32)[..., tf.newaxis]
        count = tf.maximum(tf.reduce_sum(mask, axis=1), 1.0)
        parts.append(tf.reduce_sum(history * mask, axis=1) / count)

        days = tf.math.log1p(tf.cast(features["days_since_last_purchase"], tf.float32)) / self.days_scale
        parts.append(days[:, tf.newaxis])

        return self.output_layer(self.hidden(tf.concat(parts, axis=1)))


class CandidateTower(tf.keras.Model):
    """Product attributes + popularity over time -> product vector."""

    def __init__(self, vocabularies: dict[str, list[str]], output_dim: int):
        super().__init__(name="candidate_tower")
        self.embeddings = _embeddings(CANDIDATE_EMBEDDINGS, vocabularies)
        self.hidden = tf.keras.layers.Dense(HIDDEN_UNITS, activation="relu")
        self.output_layer = tf.keras.layers.Dense(output_dim)

    def call(self, features: dict[str, tf.Tensor]) -> tf.Tensor:
        parts = [layer(features[name]) for name, layer in self.embeddings.items()]
        parts.append(tf.math.log1p(tf.cast(features["popularity"], tf.float32)) / POPULARITY_SCALE)
        return self.output_layer(self.hidden(tf.concat(parts, axis=1)))


class TwoTowerModel(tfrs.Model):
    """Trained with in-batch negatives: in each batch, every other purchased product counts
    as a product this customer did not buy."""

    def __init__(self, vocabularies: dict[str, list[str]], output_dim: int, max_days_since: int):
        super().__init__()
        self.query_tower = QueryTower(vocabularies, output_dim, max_days_since)
        self.candidate_tower = CandidateTower(vocabularies, output_dim)
        # A batch can hold the same product twice; don't count the copy as a wrong answer.
        self.task = tfrs.tasks.Retrieval(remove_accidental_hits=True)

    def compute_loss(self, features: dict[str, dict[str, tf.Tensor]], training: bool = False) -> tf.Tensor:
        query = self.query_tower(features["query"])
        candidate = self.candidate_tower(features["candidate"])
        return self.task(query, candidate, candidate_ids=features["candidate"]["article_id"],
                         compute_metrics=False)
