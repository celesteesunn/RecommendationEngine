import datetime as dt

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

pytest.importorskip("tensorflow_recommenders")
pytest.importorskip("faiss")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import create_app  # noqa: E402
from src.api.recommender import AmbiguousId, Moment, Query, Recommender, history_row  # noqa: E402
from src.models.dataset import CANDIDATE_CATEGORIES, QUERY_CATEGORIES, encode_candidates, encode_queries  # noqa: E402
from src.models.export import QueryModel  # noqa: E402
from src.models.two_tower import TwoTowerModel, tf  # noqa: E402

HISTORY = 4
ANNA = "abcdef01" + "0" * 56
BEN = "abcdef02" + "0" * 56
CARA = "fedcba99" + "0" * 56
ARTICLES = ["0001", "0002", "0003", "0004", "0005"]


def vocabularies():
    vocabularies = {name: [f"{name}_{i}" for i in range(3)] for name in set(QUERY_CATEGORIES) | set(CANDIDATE_CATEGORIES)}
    vocabularies.update(customer_id=[ANNA, BEN], article_id=ARTICLES, age_bucket=["25-34", "16-24"],
                        club_member_status=["ACTIVE"], fashion_news_frequency=["NONE", "REGULARLY"],
                        day_of_week=[str(d) for d in range(1, 8)], month=[str(m) for m in range(1, 13)],
                        sales_channel_id=["2", "1"], department_no=["1676"], price_bucket=["0", "9"])
    return vocabularies


def items():
    n = len(ARTICLES)
    return pa.table({
        "article_id": ARTICLES,
        "prod_name": [f"Product {a}" for a in ARTICLES],
        "product_type_name": ["product_type_name_0", "product_type_name_1"] * 2 + ["product_type_name_2"],
        "product_group_name": ["Garment Upper body"] * n,
        "colour_group_name": ["colour_group_name_0", "colour_group_name_1", "colour_group_name_2", "colour_group_name_0", "x"],
        "garment_group_name": ["garment_group_name_1"] * n,
        "department_no": [1676] * n,
        "index_group_name": ["index_group_name_0"] * n,
        "popularity_1w": [5, 0, 2, 9, 1],
        "popularity_4w": [20, 1, 4, 30, 2],
        "price_bucket": [0, 9, 0, 9, 0],
    })


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """A tiny trained-shape model, exported, plus tiny feature tables in the project's layout."""
    root = tmp_path_factory.mktemp("serving")
    vocab = vocabularies()
    model = TwoTowerModel(vocab, output_dim=8, max_days_since=365)
    model_dir = root / "models" / "2026-01-01"
    query_model = QueryModel(model.query_tower, vocab)
    tf.saved_model.save(query_model, str(model_dir / "query_tower"), signatures={"serving_default": query_model.__call__})
    item_table = items()
    # Only four products are on sale; 0005 has no vector, like a product that stopped selling.
    on_sale = item_table.slice(0, 4)
    item_vectors = model.candidate_tower(encode_candidates(on_sale, vocab, [1, 4])).numpy()
    np.save(model_dir / "item_embeddings.npy", item_vectors.astype(np.float32))
    np.save(model_dir / "item_ids.npy", np.asarray(on_sale["article_id"].to_pylist(), dtype="U10"))

    processed = root / "processed"
    for name in ["item_features", "user_features", "test"]:
        (processed / name).mkdir(parents=True)
    pq.write_table(item_table, processed / "item_features" / "part-0.parquet")
    pq.write_table(pa.table({
        "customer_id": [CARA, BEN, ANNA],
        "age_bucket": ["16-24", "25-34", "25-34"],
        "club_member_status": ["ACTIVE"] * 3,
        "fashion_news_frequency": ["NONE", "REGULARLY", "NONE"],
        "purchase_count": [1, 0, 3],
        "online_share": [1.0, None, 0.5],
        "last_purchase_date": [dt.date(2020, 9, 15), None, dt.date(2020, 9, 6)],
        "history": [["0005"], [], ["0001", "0003", "0002"]],
        "preferred_channel": [2, 2, 1],
        "is_cold_start": [1, 1, 0],
    }), processed / "user_features" / "part-0.parquet")
    pq.write_to_dataset(pa.table({
        "article_id": ["0001", "0003", "0002", "0005", "0004"],
        "customer_id": [ANNA, ANNA, ANNA, CARA, ANNA],
        "t_dat": [dt.date(2020, 8, 1), dt.date(2020, 9, 1), dt.date(2020, 9, 6), dt.date(2020, 9, 15), dt.date(2019, 1, 1)],
        "sales_channel_id": [1, 2, 1, 2, 2],
        "quantity": [2, 1, 1, 1, 1],
        "week": [98, 102, 103, 103, 20],
    }), processed / "transactions", partition_cols=["week"])
    pq.write_table(pa.table({
        "customer_id": [ANNA],
        "purchased": [["0004", "0001"]],
        "first_date": [dt.date(2020, 9, 18)],   # a Friday
        "is_cold_start": [0],
    }), processed / "test" / "part-0.parquet")

    recommender = Recommender(model_dir, processed, training_weeks=[92, 103], history_length=HISTORY,
                              max_days_since=365, max_k=3)
    return model, vocab, item_vectors, recommender


def expected_vector(model, vocab, query: Query, moment: Moment) -> np.ndarray:
    """The customer vector through the training code path, for comparison."""
    table = pa.table({
        "customer_id": [query.customer_id], "age_bucket": [query.age_bucket],
        "club_member_status": [query.club_member_status], "fashion_news_frequency": [query.fashion_news_frequency],
        "history": pa.array([query.history], pa.list_(pa.string())),
        "day_of_week": [moment.day], "month": [moment.month], "sales_channel_id": [moment.channel],
        "days_since_last_purchase": [query.days_since_last_purchase],
    })
    return model.query_tower(encode_queries(table, vocab, HISTORY)).numpy()


def test_history_row_right_aligns_and_keeps_the_newest():
    assert history_row(["a", "b", "c"], 2).tolist() == ["b", "c"]
    assert history_row(["a"], 3).tolist() == ["", "", "a"]
    assert history_row([], 2).tolist() == ["", ""]


def test_customers_are_found_by_id_or_prefix(built):
    recommender = built[3]
    anna = recommender.find_customer(ANNA)
    assert recommender.find_customer("ABCDEF01") == anna
    assert recommender.find_customer("fedcba") is not None
    assert recommender.find_customer("999999") is None
    with pytest.raises(AmbiguousId):
        recommender.find_customer("abcdef")
    with pytest.raises(AmbiguousId):
        recommender.find_customer("abc")


def test_customer_query_uses_profile_history_and_days_since(built):
    recommender = built[3]
    query = recommender.query_for(recommender.find_customer(ANNA), ["0004"])
    assert query.history == ["0001", "0003", "0002", "0004"]
    # The last training day is 15 Sep 2020, so "today" is the 16th: 10 days after the 6th.
    assert query.days_since_last_purchase == 10
    assert recommender.query_for(recommender.find_customer(BEN)).days_since_last_purchase == 365


def test_live_vectors_match_the_training_code(built):
    model, vocab, _, recommender = built
    moment = Moment(6, 9, 2)
    anna = recommender.query_for(recommender.find_customer(ANNA))
    np.testing.assert_allclose(recommender.customer_vector(anna, moment),
                               expected_vector(model, vocab, anna, moment), atol=1e-5)
    # A new visitor must get the "unknown customer" vector, as in training.
    guest = Query(age_bucket="16-24", history=["0002"])
    np.testing.assert_allclose(recommender.customer_vector(guest, moment),
                               expected_vector(model, vocab, guest, moment), atol=1e-5)


def test_recommend_ranks_by_dot_product_and_skips_excluded(built):
    model, vocab, item_vectors, recommender = built
    moment = Moment(1, 12, 1)
    query = recommender.query_for(recommender.find_customer(ANNA))
    scores = item_vectors @ expected_vector(model, vocab, query, moment)[0]
    ranked = [ARTICLES[i] for i in np.argsort(-scores)]

    picks = recommender.recommend(query, moment, k=3)
    assert [p["articleId"] for p in picks] == ranked[:3]
    assert picks[0]["name"] == f"Product {ranked[0]}"
    assert recommender.recommend(query, moment, k=99, exclude=[ranked[0]])[0]["articleId"] == ranked[1]
    # k is capped at max_k, and never more than the products on sale.
    assert len(recommender.recommend(query, moment, k=99)) == 3


def test_own_products_most_units_then_most_recent(built):
    recommender = built[3]
    # 0001 was bought twice; 0002 (6 Sep) is more recent than 0003 (1 Sep); 0004 is too old.
    assert recommender.own_products(recommender.find_customer(ANNA)) == ["0001", "0002", "0003"]
    assert recommender.own_products(recommender.find_customer(BEN)) == []


def test_recommend_puts_first_items_first_without_repeats(built):
    recommender = built[3]
    query = recommender.query_for(recommender.find_customer(ANNA))
    picks = recommender.recommend(query, Moment(1, 12, 1), k=3, exclude=["0002"], first=["0002", "0005"])
    assert picks[0]["articleId"] == "0005" and picks[0]["source"] == "bought before" and picks[0]["score"] is None
    assert [p["source"] for p in picks[1:]] == ["model", "model"]
    assert len({p["articleId"] for p in picks}) == 3 and "0002" not in {p["articleId"] for p in picks}


def test_profile_has_timeline_style_and_real_next_visit(built):
    recommender = built[3]
    profile = recommender.profile(recommender.find_customer(ANNA))
    # Only purchases inside the training window (weeks 92-103), oldest first.
    assert [p["article_id"] for p in profile["purchases"]] == ["0001", "0003", "0002"]
    assert profile["nextVisit"] == {"date": "2020-09-18", "moment": "d6-m9-c1"}
    assert profile["boughtInTestWeek"] == ["0004", "0001"]
    assert profile["warm"] and profile["inTestWeek"]
    assert set(profile["products"]) == {"0001", "0002", "0003", "0004"}
    assert profile["styleDna"]["types"][0] == ["product_type_name_0", 0.667]

    stranger = recommender.profile(recommender.find_customer(BEN))
    assert stranger["nextVisit"] is None and stranger["purchases"] == []


@pytest.fixture(scope="module")
def client(built):
    with TestClient(create_app(lambda: built[3])) as test_client:
        yield test_client


def test_api_health_and_customer(client):
    health = client.get("/health").json()
    assert health["status"] == "ok" and health["products"] == 4 and health["cutOff"] == "2020-09-15"
    assert client.get("/customers/abcdef01").json()["customerId"] == ANNA
    assert client.get("/customers/random").json()["customerId"] == ANNA
    assert client.get("/customers/999999").status_code == 404
    assert client.get("/customers/abcdef").status_code == 400


def test_api_recommendations(client):
    picks = client.get("/customers/abcdef01/recommendations", params={"day": 6, "month": 9, "channel": 1, "k": 2}).json()
    assert picks["moment"] == "d6-m9-c1" and picks["customerId"] == ANNA and len(picks["items"]) == 2
    assert client.get("/customers/abcdef01/recommendations", params={"day": 8}).status_code == 422

    guest = client.post("/recommendations", json={"ageBucket": "16-24", "history": ["0002"], "exclude": ["0001"]}).json()
    assert guest["customerId"] is None
    assert "0001" not in [p["articleId"] for p in guest["items"]]
    liked = client.post("/recommendations", json={"customerId": "abcdef01", "history": ["0004"], "k": 1}).json()
    assert liked["customerId"] == ANNA and len(liked["items"]) == 1
    assert client.post("/recommendations", json={"ageBucket": "99+"}).status_code == 422


def test_api_blends_own_products_first_by_default(client):
    best = client.get("/customers/abcdef01/recommendations", params={"k": 3}).json()
    assert best["blend"] == "best"
    assert [p["articleId"] for p in best["items"]] == ["0001", "0002", "0003"]
    model_only = client.get("/customers/abcdef01/recommendations", params={"k": 3, "blend": "model"}).json()
    assert model_only["blend"] == "model" and {p["source"] for p in model_only["items"]} == {"model"}
    # A new visitor has nothing of their own, so the list is the model's.
    assert client.post("/recommendations", json={"k": 2}).json()["blend"] == "model"
