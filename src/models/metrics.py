"""Ranking metrics for recommendations: Recall@K, NDCG@K and MAP@K.

Each metric compares one customer's ranked recommendations with the set of products they
really bought in the test week. evaluate() averages them over all customers, and separately
over warm and cold customers.
"""

import math
from collections.abc import Iterable, Mapping, Sequence

import pandas as pd


def recall_at_k(recommended: Sequence[str], actual: set[str], k: int) -> float:
    """Share of the bought products that appear in the top k."""
    if not actual:
        return 0.0
    return len(set(recommended[:k]) & actual) / len(actual)


def ndcg_at_k(recommended: Sequence[str], actual: set[str], k: int) -> float:
    """Like recall, but a hit counts more the nearer it is to the top of the list."""
    if not actual:
        return 0.0
    dcg = sum(1 / math.log2(rank + 2) for rank, item in enumerate(recommended[:k]) if item in actual)
    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(len(actual), k)))
    return dcg / ideal


def average_precision_at_k(recommended: Sequence[str], actual: set[str], k: int) -> float:
    """The Kaggle competition's metric (MAP@12 when averaged over customers)."""
    if not actual:
        return 0.0
    hits, total = 0, 0.0
    for rank, item in enumerate(recommended[:k]):
        if item in actual:
            hits += 1
            total += hits / (rank + 1)
    return total / min(len(actual), k)


def _average(rows: Iterable[tuple[Sequence[str], set[str]]], k_values: Sequence[int]) -> dict[str, float]:
    sums: dict[str, float] = {}
    count = 0
    for recommended, actual in rows:
        count += 1
        for k in k_values:
            sums[f"recall@{k}"] = sums.get(f"recall@{k}", 0.0) + recall_at_k(recommended, actual, k)
        sums["ndcg@12"] = sums.get("ndcg@12", 0.0) + ndcg_at_k(recommended, actual, 12)
        sums["map@12"] = sums.get("map@12", 0.0) + average_precision_at_k(recommended, actual, 12)
    return {name: round(total / count, 5) for name, total in sums.items()} if count else {}


def evaluate(
    recommendations: Mapping[str, Sequence[str]],
    test: pd.DataFrame,
    k_values: Sequence[int],
) -> dict[str, dict]:
    """Average every metric over all test customers, and over warm and cold ones.

    test needs the columns customer_id, purchased (list of article IDs) and is_cold_start.
    A customer missing from recommendations counts as getting an empty list.
    """
    results = {}
    groups = {"all": test, "warm": test[test["is_cold_start"] == 0], "cold": test[test["is_cold_start"] == 1]}
    for name, group in groups.items():
        rows = (
            (recommendations.get(customer, []), set(purchased))
            for customer, purchased in zip(group["customer_id"], group["purchased"])
        )
        results[name] = {"customers": len(group), **_average(rows, k_values)}
    return results
