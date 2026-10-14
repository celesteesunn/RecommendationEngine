"""The live recommender behind the API.

Everything is loaded once, when the API starts, and kept in memory:

    models/<version>/query_tower/          customer + visit -> customer vector (SavedModel)
    models/<version>/item_embeddings.npy   the vectors of the products on sale, in a FAISS index
    data/processed/user_features           each customer's profile and last 20 purchases
    data/processed/item_features           product names, types and colours for the responses
    data/processed/transactions            purchases in the training window, for the timelines
    data/processed/test                    what test-week customers really bought next

A request turns a customer and a moment (day, month, online or in store) into a customer
vector with the query tower, and FAISS finds the products with the highest dot product with
it: the same score the model was trained and evaluated with. By default a real customer's
list starts with up to 6 of their own recent products ("bought before"), then the model's
picks: the blend that scored best in the evaluation (reports/evaluation_2026-10-05.md). Only the exported model is used,
not the training code, so the API needs no TensorFlow Recommenders.
"""

import datetime as dt
import json
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import tensorflow as tf

from src.config import load_config, project_path

AGE_BUCKETS = ["16-24", "25-34", "35-44", "45-54", "55+", "unknown"]
# Shorter ID prefixes than this match too many customers to be useful.
MIN_ID_PREFIX = 6
ARTICLE_FIELDS = {
    "prod_name": "name", "product_type_name": "type", "product_group_name": "group",
    "colour_group_name": "colour", "garment_group_name": "garment", "index_group_name": "index",
}
# Any ID outside the vocabulary works for a new visitor. Not "": the exported lookup reads ""
# as padding, while training gave unknown customers the "unknown" index.
GUEST_ID = "new-visitor"
USER_COLUMNS = ["customer_id", "age_bucket", "club_member_status", "fashion_news_frequency", "purchase_count",
                "online_share", "last_purchase_date", "history", "preferred_channel", "is_cold_start"]


class AmbiguousId(ValueError):
    """An ID prefix that matches more than one customer."""


@dataclass
class Moment:
    day: int       # Sunday = 1 ... Saturday = 7, as in training
    month: int     # 1 ... 12
    channel: int   # 1 = in store, 2 = online

    @property
    def key(self) -> str:
        return f"d{self.day}-m{self.month}-c{self.channel}"


@dataclass
class Query:
    """Everything the query tower reads about a shopper, apart from the moment."""
    customer_id: str = GUEST_ID
    age_bucket: str = "unknown"
    club_member_status: str = "ACTIVE"
    fashion_news_frequency: str = "NONE"
    history: list[str] = field(default_factory=list)   # article IDs, oldest first
    days_since_last_purchase: float = 365.0


def latest_exported_version(models_dir: Path) -> str:
    """The newest model that has been exported for serving (versions are dates)."""
    versions = sorted(p.name for p in models_dir.iterdir() if (p / "export.json").exists())
    if not versions:
        raise FileNotFoundError(f"No exported model in {models_dir}. Run: python -m src.models.export")
    return versions[-1]


def history_row(history: list[str], length: int) -> np.ndarray:
    """The last `length` article IDs, right-aligned with "" as padding (as in training)."""
    row = np.full(length, "", dtype=object)
    recent = history[-length:]
    if recent:
        row[length - len(recent):] = recent
    return row.astype(str)


def catalog_entry(row: dict) -> dict:
    return {**{short: row[name] for name, short in ARTICLE_FIELDS.items()},
            "priceBand": row["price_bucket"], "soldLastWeek": row["popularity_1w"]}


def style_dna(article_ids: list[str], catalog: dict[str, dict]) -> dict[str, list]:
    """Share of colours and product types among a customer's purchases."""
    known = [catalog[a] for a in article_ids if a in catalog]
    total = max(len(known), 1)
    colours = Counter(item["colour"] for item in known)
    types = Counter(item["type"] for item in known)
    return {
        "colours": [[name, round(n / total, 3)] for name, n in colours.most_common(6)],
        "types": [[name, round(n / total, 3)] for name, n in types.most_common(6)],
    }


class Recommender:
    def __init__(self, model_dir: Path, processed: Path, training_weeks: list[int], history_length: int,
                 max_days_since: int, max_k: int, repurchase_slots: int = 6):
        self.version = model_dir.name
        self.repurchase_slots = repurchase_slots
        self.history_length = history_length
        self.max_days_since = max_days_since
        self.max_k = max_k

        # Keep the loaded model alive: its signature only works while the object exists.
        self._query_model = tf.saved_model.load(str(model_dir / "query_tower"))
        self._query_tower = self._query_model.signatures["serving_default"]

        self.item_ids = np.load(model_dir / "item_ids.npy").astype(str)
        vectors = np.ascontiguousarray(np.load(model_dir / "item_embeddings.npy"), dtype=np.float32)
        # Exact search on inner product: the model's own score. 29,009 products x 64 numbers
        # take about a millisecond, so an approximate index is not needed yet.
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

        items = pq.read_table(processed / "item_features")
        self.catalog = {row["article_id"]: catalog_entry(row) for row in items.to_pylist()}

        # Customers sorted by ID, so an ID or ID prefix is found by binary search.
        users = pq.read_table(processed / "user_features", columns=USER_COLUMNS).sort_by("customer_id")
        self.users = users
        self.user_keys = np.array(users["customer_id"].to_pylist(), dtype="S64")

        # Purchases in the training window, grouped by customer row, for the timelines.
        window = (ds.field("week") >= training_weeks[0]) & (ds.field("week") <= training_weeks[1])
        purchases = ds.dataset(processed / "transactions", format="parquet", partitioning="hive").to_table(
            columns=["customer_id", "article_id", "t_dat", "sales_channel_id", "quantity"], filter=window)
        user_row = pc.index_in(purchases["customer_id"], value_set=users["customer_id"].combine_chunks())
        purchases = purchases.append_column("user_row", user_row).drop_columns(["customer_id"])
        self.purchases = purchases.sort_by([("user_row", "ascending"), ("t_dat", "ascending")])
        self.purchase_rows = self.purchases["user_row"].to_numpy()
        # "Today" for the live model is the day after the last day it learned from.
        self.cut_off = pc.max(self.purchases["t_dat"]).as_py()
        self.today = self.cut_off + dt.timedelta(days=1)

        test = pq.read_table(processed / "test")
        self.test = {row["customer_id"]: row for row in test.to_pylist()}
        self.test_ids = sorted(self.test)
        self.warm_test_ids = [c for c in self.test_ids if self.test[c]["is_cold_start"] == 0]

        # The first call builds TensorFlow's graph (about 2 seconds); do it now, not on a request.
        self.customer_vector(Query(), Moment(4, 9, 2))

    @classmethod
    def from_config(cls, version: str | None = None) -> "Recommender":
        config = load_config()
        processed = project_path(config["paths"]["processed_dir"])
        models_dir = project_path(config["paths"]["models_dir"])
        summary = json.loads((processed / "features_summary.json").read_text(encoding="utf-8"))
        return cls(
            model_dir=models_dir / (version or latest_exported_version(models_dir)),
            processed=processed,
            training_weeks=summary["training_weeks"],
            history_length=config["model"]["history_length"],
            max_days_since=config["features"]["max_days_since"],
            max_k=config["serving"]["ann_candidates"],
            repurchase_slots=config["serving"]["repurchase_slots"],
        )

    # ---- customers ----

    def find_customer(self, customer_id: str) -> int | None:
        """The row of the customer with this ID, or with an ID starting with it."""
        key = customer_id.strip().lower().encode()
        if len(key) < MIN_ID_PREFIX:
            raise AmbiguousId(f"Give at least {MIN_ID_PREFIX} characters of the customer ID")
        row = int(np.searchsorted(self.user_keys, key))
        if row >= len(self.user_keys) or not self.user_keys[row].startswith(key):
            return None
        if self.user_keys[row] != key and row + 1 < len(self.user_keys) and self.user_keys[row + 1].startswith(key):
            raise AmbiguousId(f"More than one customer ID starts with {customer_id}")
        return row

    def random_customer(self, warm_only: bool = False) -> int:
        """A random customer from the test week, so the real next purchases can be checked."""
        return self.find_customer(random.choice(self.warm_test_ids if warm_only else self.test_ids))

    def query_for(self, row: int, extra_history: list[str] = ()) -> Query:
        user = self.users.slice(row, 1).to_pylist()[0]
        last = user["last_purchase_date"]
        days = self.max_days_since if last is None else min((self.today - last).days, self.max_days_since)
        return Query(
            customer_id=user["customer_id"], age_bucket=user["age_bucket"],
            club_member_status=user["club_member_status"],
            fashion_news_frequency=user["fashion_news_frequency"],
            history=list(user["history"]) + list(extra_history), days_since_last_purchase=float(days),
        )

    def purchases_of(self, row: int) -> list[dict]:
        """A customer's purchases in the training window, oldest first."""
        start, end = np.searchsorted(self.purchase_rows, [row, row + 1])
        return self.purchases.slice(start, end - start).to_pylist()

    def own_products(self, row: int) -> list[str]:
        """Their own products, most units first, then most recent (as the repurchase baseline)."""
        units, last = Counter(), {}
        for p in self.purchases_of(row):
            units[p["article_id"]] += p["quantity"]
            last[p["article_id"]] = max(last.get(p["article_id"], p["t_dat"]), p["t_dat"])
        return sorted(units, key=lambda a: (-units[a], -last[a].toordinal(), a))

    def profile(self, row: int) -> dict:
        """A customer as the website shows them: profile, timeline, style DNA, real next visit."""
        user = self.users.slice(row, 1).to_pylist()[0]
        cid = user["customer_id"]
        purchases = [{"article_id": p["article_id"], "date": p["t_dat"].isoformat(), "online": p["sales_channel_id"] == 2}
                     for p in self.purchases_of(row)]
        bought_ids = [p["article_id"] for p in purchases] or list(user["history"])

        next_visit, bought_next = None, []
        if cid in self.test:
            first = self.test[cid]["first_date"]
            moment = Moment(first.isoweekday() % 7 + 1, first.month, user["preferred_channel"])
            next_visit = {"date": first.isoformat(), "moment": moment.key}
            bought_next = self.test[cid]["purchased"]

        mentioned = set(bought_ids) | set(bought_next) | set(user["history"])
        return {
            "id": cid[:8],
            "customerId": cid,
            "ageBucket": user["age_bucket"],
            "club": user["club_member_status"],
            "newsletter": user["fashion_news_frequency"],
            "warm": user["is_cold_start"] == 0,
            "purchasesIn12Weeks": user["purchase_count"],
            "onlineShare": round(user["online_share"] or 0, 2),
            "purchases": purchases,
            "history": list(user["history"]),
            "inTestWeek": cid in self.test,
            "nextVisit": next_visit,
            "boughtInTestWeek": bought_next,
            "styleDna": style_dna(bought_ids, self.catalog),
            "products": self.products(mentioned),
        }

    def products(self, article_ids) -> dict[str, dict]:
        return {a: self.catalog[a] for a in article_ids if a in self.catalog}

    # ---- the model ----

    def customer_vector(self, query: Query, moment: Moment) -> np.ndarray:
        outputs = self._query_tower(
            customer_id=tf.constant([query.customer_id]),
            age_bucket=tf.constant([query.age_bucket]),
            club_member_status=tf.constant([query.club_member_status]),
            fashion_news_frequency=tf.constant([query.fashion_news_frequency]),
            history=tf.constant(history_row(query.history, self.history_length)[np.newaxis, :]),
            day_of_week=tf.constant([moment.day], tf.int64),
            month=tf.constant([moment.month], tf.int64),
            sales_channel_id=tf.constant([moment.channel], tf.int64),
            days_since_last_purchase=tf.constant([query.days_since_last_purchase], tf.float32),
        )
        return outputs["embedding"].numpy().astype(np.float32)

    def recommend(self, query: Query, moment: Moment, k: int, exclude=(), first=()) -> list[dict]:
        """`first` (e.g. the customer's own products), then the products with the highest score
        for this shopper at this moment, best first: k in all, none of them in `exclude`."""
        k = max(1, min(k, self.max_k))
        exclude = set(exclude)
        picks = [{"articleId": a, "source": "bought before", "score": None, **self.catalog.get(a, {})}
                 for a in dict.fromkeys(first) if a not in exclude][:k]
        exclude |= {p["articleId"] for p in picks}
        wanted = min(k + len(exclude), self.index.ntotal)
        scores, rows = self.index.search(self.customer_vector(query, moment), wanted)
        for score, row in zip(scores[0], rows[0]):
            if len(picks) == k:
                break
            if row < 0 or self.item_ids[row] in exclude:
                continue
            article_id = self.item_ids[row]
            picks.append({"articleId": article_id, "source": "model", "score": round(float(score), 4),
                          **self.catalog.get(article_id, {})})
        return picks

    def summary(self) -> dict:
        return {
            "modelVersion": self.version,
            "products": int(self.index.ntotal),
            "customers": len(self.user_keys),
            "testWeekCustomers": len(self.test_ids),
            "cutOff": self.cut_off.isoformat(),
        }
