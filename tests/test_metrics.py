import math

import pandas as pd
import pytest

from src.models.metrics import average_precision_at_k, evaluate, ndcg_at_k, recall_at_k


def test_recall_counts_hits_in_the_top_k():
    assert recall_at_k(["a", "b", "c"], {"a", "c", "z"}, k=2) == pytest.approx(1 / 3)
    assert recall_at_k(["a", "b", "c"], {"a", "c", "z"}, k=3) == pytest.approx(2 / 3)
    assert recall_at_k(["a"], set(), k=12) == 0.0


def test_ndcg_rewards_hits_near_the_top():
    assert ndcg_at_k(["a", "b"], {"a"}, k=12) == pytest.approx(1.0)
    assert ndcg_at_k(["b", "a"], {"a"}, k=12) == pytest.approx(1 / math.log2(3))


def test_average_precision_matches_the_kaggle_definition():
    # Hits at ranks 1 and 3: (1/1 + 2/3) / min(2, 12)
    assert average_precision_at_k(["a", "x", "b"], {"a", "b"}, k=12) == pytest.approx((1 + 2 / 3) / 2)


def test_evaluate_splits_warm_and_cold_customers():
    test = pd.DataFrame({
        "customer_id": ["warm1", "cold1", "cold2"],
        "purchased": [["a"], ["b"], ["c"]],
        "is_cold_start": [0, 1, 1],
    })
    results = evaluate({"warm1": ["a"], "cold1": ["x", "b"]}, test, k_values=[1, 2])

    assert results["warm"] == {"customers": 1, "recall@1": 1.0, "recall@2": 1.0,
                               "ndcg@12": 1.0, "map@12": 1.0}
    # cold2 has no recommendations at all, which counts as zero.
    assert results["cold"]["recall@2"] == 0.5
    assert results["all"]["customers"] == 3
