from recommendation_engine.data import create_sample_data
from recommendation_engine.model import recommend_top_products


def test_create_sample_data_returns_valid_rows():
    df = create_sample_data()
    required_columns = {"user_id", "item_id", "rating"}
    assert required_columns.issubset(df.columns)
    assert len(df) > 0


def test_recommend_top_products_returns_top_n_items():
    df = create_sample_data()
    recommendations = recommend_top_products(df, user_id=1, top_n=3)
    assert len(recommendations) == 3
    assert all("item_id" in item for item in recommendations)
