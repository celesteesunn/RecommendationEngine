import numpy as np
import pyarrow as pa
import pytest

pytest.importorskip("tensorflow_recommenders")

from src.models.dataset import CANDIDATE_CATEGORIES, QUERY_CATEGORIES, encode_candidates, encode_queries  # noqa: E402
from src.models.export import (  # noqa: E402
    CandidateModel,
    QueryModel,
    history_matrix,
    raw_candidates,
    raw_queries,
)
from src.models.two_tower import TwoTowerModel, tf  # noqa: E402

HISTORY = 4


@pytest.fixture
def vocabularies():
    vocabularies = {name: [f"{name}_{i}" for i in range(3)] for name in set(QUERY_CATEGORIES) | set(CANDIDATE_CATEGORIES)}
    vocabularies["article_id"] = ["0001", "0002", "0003"]
    vocabularies.update(day_of_week=["3", "4"], month=["9"], sales_channel_id=["2", "1"],
                        department_no=["1676", "1339"], price_bucket=["-1", "0", "9"])
    return vocabularies


@pytest.fixture
def queries():
    return pa.table({
        "customer_id": ["customer_id_0", "someone_new"],
        "age_bucket": ["age_bucket_1", "age_bucket_2"],
        "club_member_status": ["club_member_status_0"] * 2,
        "fashion_news_frequency": ["fashion_news_frequency_2"] * 2,
        "history": [["0001", "0003", "9999"], []],
        "day_of_week": [4, 3],
        "month": [9, 9],
        "sales_channel_id": [2, 1],
        "days_since_last_purchase": [7, 365],
    })


@pytest.fixture
def items():
    return pa.table({
        "article_id": ["0002", "0009"],
        "product_type_name": ["product_type_name_0", "product_type_name_1"],
        "colour_group_name": ["colour_group_name_1"] * 2,
        "garment_group_name": ["garment_group_name_2"] * 2,
        "index_group_name": ["index_group_name_0"] * 2,
        "department_no": [1676, 1339],
        "price_bucket": [9, -1],
        "popularity_1w": [5, 0],
        "popularity_4w": [20, 1],
    })


def test_history_matrix_right_aligns_text():
    assert history_matrix([["a", "b", "c"], [], ["x"]], 2).tolist() == [["b", "c"], ["", ""], ["", "x"]]


def test_exported_towers_match_the_trained_model(vocabularies, queries, items, tmp_path):
    model = TwoTowerModel(vocabularies, output_dim=8, max_days_since=365)
    expected_query = model.query_tower(encode_queries(queries, vocabularies, HISTORY)).numpy()
    expected_item = model.candidate_tower(encode_candidates(items, vocabularies, [1, 4])).numpy()

    query_model = QueryModel(model.query_tower, vocabularies)
    candidate_model = CandidateModel(model.candidate_tower, vocabularies)
    tf.saved_model.save(query_model, str(tmp_path / "query"), signatures={"serving_default": query_model.__call__})
    tf.saved_model.save(candidate_model, str(tmp_path / "candidate"),
                        signatures={"serving_default": candidate_model.__call__})

    query_fn = tf.saved_model.load(str(tmp_path / "query")).signatures["serving_default"]
    candidate_fn = tf.saved_model.load(str(tmp_path / "candidate")).signatures["serving_default"]
    actual_query = query_fn(**raw_queries(queries, HISTORY))["embedding"].numpy()
    actual_item = candidate_fn(**raw_candidates(items, [1, 4]))["embedding"].numpy()

    np.testing.assert_allclose(actual_query, expected_query, atol=1e-5)
    np.testing.assert_allclose(actual_item, expected_item, atol=1e-5)
