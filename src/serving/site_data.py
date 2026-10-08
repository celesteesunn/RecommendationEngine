"""Export real model recommendations as static data for the website (web/public/data/).

Usage:
    python -m src.serving.site_data                    # the newest exported model
    python -m src.serving.site_data --version 2026-10-05

The website works from these files until the live API is ready. Everything in them comes from
the trained model and the dataset:

    customers.json      sample customers from the test week: profile, purchase timeline,
                        style DNA and what they really bought in the test week
    moments/<id>.json   each customer's top products for every moment (7 days x 12 months x
                        online / in store), straight from the query tower
    guests/<age>.json   the same for a new visitor of each age group (no history)
    swipe.json          a pool of products with their model vectors, and each shopper's
                        starting vector, so the swipe page can re-rank in the browser
    catalog.json        name, type, colour and other details of every product mentioned
    trending.json       best-sellers of the last training week, overall and by age group
    image_ids.txt       the products whose photos the site can show
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.config import load_config, project_path
from src.models.dataset import encode_queries, load_test_queries
from src.models.train import latest_version, load_model
from src.models.two_tower import tf

SAMPLE_PER_AGE = 3
COLD_SAMPLES = 4
TOP_K = 24
SWIPE_POOL = 360
DAYS = list(range(1, 8))      # Sunday = 1 ... Saturday = 7, as in training
MONTHS = list(range(1, 13))
CHANNELS = [1, 2]             # 1 = in store, 2 = online
AGE_BUCKETS = ["16-24", "25-34", "35-44", "45-54", "55+", "unknown"]
ARTICLE_FIELDS = {
    "prod_name": "name", "product_type_name": "type", "product_group_name": "group",
    "colour_group_name": "colour", "garment_group_name": "garment", "index_group_name": "index",
}


def moment_key(day: int, month: int, channel: int) -> str:
    return f"d{day}-m{month}-c{channel}"


def all_moments(profile: dict) -> pa.Table:
    """One query row per moment for a single shopper."""
    rows = [(d, m, c) for d in DAYS for m in MONTHS for c in CHANNELS]
    n = len(rows)
    return pa.table({
        "customer_id": [profile["customer_id"]] * n,
        "age_bucket": [profile["age_bucket"]] * n,
        "club_member_status": [profile["club_member_status"]] * n,
        "fashion_news_frequency": [profile["fashion_news_frequency"]] * n,
        "history": pa.array([profile["history"]] * n, pa.list_(pa.string())),
        "day_of_week": [r[0] for r in rows],
        "month": [r[1] for r in rows],
        "sales_channel_id": [r[2] for r in rows],
        "days_since_last_purchase": [profile["days_since_last_purchase"]] * n,
    })


def top_products(query_vectors: np.ndarray, item_vectors: np.ndarray, item_ids: np.ndarray, k: int) -> list[list[str]]:
    """The k best products per query, best first. Works in chunks to keep memory small."""
    results = []
    for start in range(0, len(query_vectors), 2048):
        scores = query_vectors[start:start + 2048] @ item_vectors.T
        best = np.argpartition(-scores, k, axis=1)[:, :k]
        order = np.take_along_axis(scores, best, axis=1).argsort(axis=1)[:, ::-1]
        results += item_ids[np.take_along_axis(best, order, axis=1)].tolist()
    return results


def recommendations_by_moment(tower, vocabularies, profile: dict, history_length: int,
                              item_vectors: np.ndarray, item_ids: np.ndarray) -> dict[str, list[str]]:
    table = all_moments(profile)
    vectors = tower(encode_queries(table, vocabularies, history_length)).numpy()
    tops = top_products(vectors, item_vectors, item_ids, TOP_K)
    keys = [moment_key(d, m, c) for d, m, c in zip(table["day_of_week"].to_pylist(),
                                                     table["month"].to_pylist(),
                                                     table["sales_channel_id"].to_pylist())]
    return dict(zip(keys, tops))


def purchases_of(processed: Path, customer_ids: list[str], last_week: int) -> dict[str, list[dict]]:
    """Every purchase of these customers up to the cut-off, oldest first."""
    dataset = ds.dataset(processed / "transactions", format="parquet", partitioning="hive")
    table = dataset.to_table(
        columns=["customer_id", "article_id", "t_dat", "sales_channel_id"],
        filter=(ds.field("customer_id").isin(customer_ids)) & (ds.field("week") <= last_week),
    ).sort_by([("customer_id", "ascending"), ("t_dat", "ascending")])
    purchases: dict[str, list[dict]] = {c: [] for c in customer_ids}
    for row in table.to_pylist():
        purchases[row["customer_id"]].append({
            "article_id": row["article_id"], "date": row["t_dat"].isoformat(),
            "online": row["sales_channel_id"] == 2,
        })
    return purchases


def style_dna(purchases: list[dict], catalog: dict[str, dict]) -> dict[str, list]:
    """Share of colours and product types among a customer's purchases."""
    total = max(len(purchases), 1)
    colours = Counter(catalog[p["article_id"]]["colour"] for p in purchases)
    types = Counter(catalog[p["article_id"]]["type"] for p in purchases)
    return {
        "colours": [[name, round(n / total, 3)] for name, n in colours.most_common(6)],
        "types": [[name, round(n / total, 3)] for name, n in types.most_common(6)],
    }


def pick_customers(queries: pa.Table, test: pa.Table, users: pa.Table, tower, vocabularies,
                   history_length, item_vectors, item_ids, rng) -> list[int]:
    """Rows of `queries` to feature: warm customers per age group whose real next purchase the
    model found, plus a few cold ones. Picked at random among those that qualify."""
    vectors = tower(encode_queries(queries, vocabularies, history_length)).numpy()
    tops = top_products(vectors, item_vectors, item_ids, TOP_K)
    purchased = test["purchased"].to_pylist()
    cold = test["is_cold_start"].to_pylist()
    history_sizes = pc.list_value_length(users["history"]).to_pylist()
    ages = queries["age_bucket"].to_pylist()

    chosen = []
    for age in AGE_BUCKETS[:-1]:
        candidates = [i for i in range(len(queries))
                      if ages[i] == age and cold[i] == 0 and history_sizes[i] >= 12
                      and set(tops[i]) & set(purchased[i])]
        chosen += rng.choice(candidates, min(SAMPLE_PER_AGE, len(candidates)), replace=False).tolist()
    cold_rows = [i for i in range(len(queries)) if cold[i] == 1 and 1 <= history_sizes[i] <= 4]
    chosen += rng.choice(cold_rows, min(COLD_SAMPLES, len(cold_rows)), replace=False).tolist()
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    config = load_config()
    processed = project_path(config["paths"]["processed_dir"])
    models_dir = project_path(config["paths"]["models_dir"])
    version = args.version or latest_version(models_dir)
    model_dir = models_dir / version
    out = project_path("web/public/data")
    (out / "moments").mkdir(parents=True, exist_ok=True)
    (out / "guests").mkdir(parents=True, exist_ok=True)
    history_length = config["model"]["history_length"]
    summary = json.loads((processed / "features_summary.json").read_text(encoding="utf-8"))
    last_week = summary["training_weeks"][1]
    rng = np.random.default_rng(args.seed)

    tf.config.experimental.enable_tensor_float_32_execution(False)
    model, vocabularies = load_model(model_dir, config)
    tower = model.query_tower
    item_vectors = np.load(model_dir / "item_embeddings.npy")
    item_ids = np.load(model_dir / "item_ids.npy")

    print("Choosing sample customers ...")
    queries = load_test_queries(processed, config["features"]["max_days_since"])
    test = pq.read_table(processed / "test")
    users_all = pq.read_table(processed / "user_features")
    users = users_all.take(pc.index_in(queries["customer_id"], value_set=users_all["customer_id"].combine_chunks()))
    rows = pick_customers(queries, test, users, tower, vocabularies, history_length, item_vectors, item_ids, rng)
    sample = queries.take(rows)
    sample_users = users.take(rows)
    sample_test = test.take(rows)
    customer_ids = sample["customer_id"].to_pylist()

    print("Collecting purchases ...")
    purchases = purchases_of(processed, customer_ids, last_week)

    print("Ranking every moment ...")
    moments = {}
    for profile in sample.to_pylist():
        moments[profile["customer_id"]] = recommendations_by_moment(
            tower, vocabularies, profile, history_length, item_vectors, item_ids)
    guests, guest_profiles = {}, {}
    for age in AGE_BUCKETS:
        guest = {"customer_id": "", "age_bucket": age, "club_member_status": "ACTIVE",
                 "fashion_news_frequency": "NONE", "history": [], "days_since_last_purchase": 365}
        guest_profiles[age] = guest
        guests[age] = recommendations_by_moment(tower, vocabularies, guest, history_length, item_vectors, item_ids)

    print("Building the swipe pool and trending lists ...")
    items = pq.read_table(processed / "item_features")
    sold = items.filter(pc.is_in(items["article_id"], value_set=pa.array(item_ids)))
    by_week = sold.sort_by([("popularity_1w", "descending")])["article_id"].to_pylist()
    pool = by_week[:SWIPE_POOL // 2]
    rest = [a for a in by_week[SWIPE_POOL // 2:]]
    pool += rng.choice(rest, SWIPE_POOL - len(pool), replace=False).tolist()
    row_of = {a: i for i, a in enumerate(item_ids.tolist())}
    pool_vectors = item_vectors[[row_of[a] for a in pool]]

    final_week = ds.dataset(processed / "transactions", format="parquet", partitioning="hive").to_table(
        columns=["customer_id", "article_id", "quantity"], filter=ds.field("week") == last_week)
    ages = users_all.select(["customer_id", "age_bucket"])
    final_week = final_week.join(ages, "customer_id")
    trending = {"all": [r["article_id"] for r in final_week.group_by("article_id").aggregate(
        [("quantity", "sum")]).sort_by([("quantity_sum", "descending")]).slice(0, 100).to_pylist()]}
    for age in AGE_BUCKETS:
        group = final_week.filter(pc.equal(final_week["age_bucket"], age))
        trending[age] = [r["article_id"] for r in group.group_by("article_id").aggregate(
            [("quantity", "sum")]).sort_by([("quantity_sum", "descending")]).slice(0, 100).to_pylist()]

    # Catalog of every product the site mentions.
    mentioned = set(pool) | {a for lists in trending.values() for a in lists}
    for table in list(moments.values()) + list(guests.values()):
        mentioned |= {a for top in table.values() for a in top}
    for customer in customer_ids:
        mentioned |= {p["article_id"] for p in purchases[customer]}
    mentioned |= {a for bought in sample_test["purchased"].to_pylist() for a in bought}
    details = items.filter(pc.is_in(items["article_id"], value_set=pa.array(sorted(mentioned))))
    catalog = {}
    for row in details.to_pylist():
        catalog[row["article_id"]] = {
            **{short: row[field] for field, short in ARTICLE_FIELDS.items()},
            "priceBand": row["price_bucket"], "soldLastWeek": row["popularity_1w"],
        }

    customers = []
    for i, profile in enumerate(sample.to_pylist()):
        cid = profile["customer_id"]
        user = sample_users.slice(i, 1).to_pylist()[0]
        customers.append({
            "id": cid[:8],
            "customerId": cid,
            "ageBucket": profile["age_bucket"],
            "club": profile["club_member_status"],
            "newsletter": profile["fashion_news_frequency"],
            "warm": sample_test["is_cold_start"][i].as_py() == 0,
            "purchasesIn12Weeks": user["purchase_count"],
            "onlineShare": round(user["online_share"] or 0, 2),
            "nextVisit": {
                "date": sample_test["first_date"][i].as_py().isoformat(),
                "moment": moment_key(profile["day_of_week"], profile["month"], profile["sales_channel_id"]),
            },
            "purchases": purchases[cid],
            "boughtInTestWeek": sample_test["purchased"][i].as_py(),
            "styleDna": style_dna(purchases[cid], catalog),
        })

    start_vectors = {c["id"]: tower(encode_queries(sample.slice(i, 1), vocabularies, history_length)).numpy()[0]
                     for i, c in enumerate(customers)}
    # A new visitor starts from their age group on a Wednesday in September, online.
    for age, guest in guest_profiles.items():
        moment = all_moments(guest).filter(
            (pc.field("day_of_week") == 4) & (pc.field("month") == 9) & (pc.field("sales_channel_id") == 2))
        start_vectors[f"guest-{age}"] = tower(encode_queries(moment, vocabularies, history_length)).numpy()[0]

    def write(path: Path, data) -> None:
        path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    write(out / "customers.json", {"modelVersion": version, "cutOff": summary["training_weeks"],
                                   "customers": customers})
    for customer in customers:
        write(out / "moments" / f"{customer['id']}.json", moments[customer["customerId"]])
    for age, table in guests.items():
        write(out / "guests" / f"{age.replace('+', 'plus')}.json", table)
    write(out / "swipe.json", {
        "items": pool,
        "vectors": np.round(pool_vectors, 4).tolist(),
        "start": {cid: np.round(v, 4).tolist() for cid, v in start_vectors.items()},
    })
    write(out / "catalog.json", catalog)
    write(out / "trending.json", trending)
    (out / "image_ids.txt").write_text("\n".join(sorted(catalog)) + "\n", encoding="utf-8")

    sizes = {p.name: p.stat().st_size for p in out.iterdir() if p.is_file()}
    print(json.dumps({"customers": len(customers), "products_in_catalog": len(catalog),
                      "swipe_pool": len(pool), "file_sizes_kb": {k: v // 1024 for k, v in sizes.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
