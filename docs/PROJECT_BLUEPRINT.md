# Project Blueprint: Context-Aware Neural Recommendation Engine

The complete plan for the project: what we are building, what the finished system delivers
(to a shopper and as a system), how every part fits together, and what gets done each week.

| Document | Purpose |
|---|---|
| [README](../README.md) | Short public summary and setup instructions |
| **Project Blueprint** (this file) | The target: final outputs, full architecture, the work plan |
| [Project Guide](PROJECT_GUIDE.md) | The current state: files, branches, decisions, status, glossary |

---

## Contents

1. [The project on one page](#1-the-project-on-one-page)
2. [Final output: the end user's view](#2-final-output-the-end-users-view)
3. [Final output: the system's view](#3-final-output-the-systems-view)
4. [System architecture](#4-system-architecture)
5. [Offline pipeline in detail](#5-offline-pipeline-in-detail)
6. [The model in detail](#6-the-model-in-detail)
7. [Online serving in detail](#7-online-serving-in-detail)
8. [Automation with Airflow](#8-automation-with-airflow)
9. [Data and storage layout](#9-data-and-storage-layout)
10. [Evaluation plan](#10-evaluation-plan)
11. [Work plan: what gets done, week by week](#11-work-plan-what-gets-done-week-by-week)
12. [Final repository layout](#12-final-repository-layout)
13. [Risks and how we handle them](#13-risks-and-how-we-handle-them)
14. [Out of scope](#14-out-of-scope)

---

## 1. The project on one page

| | |
|---|---|
| **Project** | Project 3: Context-Aware Neural Recommendation Engine (Deep Learning), Zaalima |
| **Team** | Samala Sunaina, Siddhi Kale, Tejashvi Khandelwal |
| **Duration** | 4 weeks, with daily commits to GitHub |
| **Problem** | An online fashion store has 105,000 products. Each customer will only look at a handful. Which ones should we show them? |
| **Solution** | A deep learning model (a two-tower neural network) learns each customer's taste from their profile, purchase history and shopping context. It then finds the best-matching products in milliseconds. |
| **Dataset** | H&M Personalized Fashion Recommendations (Kaggle): 31.8M purchases, 1.37M customers, 105K products, Sep 2018 to Sep 2020 |
| **Tech stack** | Python, PySpark, TensorFlow / Keras, TensorFlow Recommenders, FAISS, Redis, FastAPI, Apache Airflow, Locust |
| **Business goal** | Higher engagement, click-through rate (CTR) and average order value (AOV), by showing products that match both long-term taste and recent shopping |

### What "context-aware" means here

A basic recommender only knows who bought what. Ours also uses three kinds of context:

| Context | Examples | Why it helps |
|---|---|---|
| **Who the customer is** | Age, club membership, newsletter preference | A 22-year-old and a 55-year-old shop differently |
| **What they did recently** | Last 20 purchases, days since their last purchase | Captures short-term intent (for example, building a summer wardrobe) |
| **When and how they shop** | Day of week, month (season), online or in-store | Coats in November, swimwear in June |

### How we know it worked (success criteria)

| Area | Criterion |
|---|---|
| Model quality | Beats a "most popular items" baseline on Recall@12 and NDCG@12, measured on a held-out final week |
| Speed | API returns recommendations in under 100 ms (95th percentile), measured on the laptop under a load test (this target is our own; the brief only asks for "real-time") |
| Completeness | Every component in the brief works end to end: PySpark → TFRS → Redis → ANN → FastAPI → Airflow |
| Process | Daily commits for all 4 weeks, as the brief requires |

---

## 2. Final output: the end user's view

The system has three kinds of users, and each sees a different result.

### 2.1 The shopper

The shopper never sees the model. They see **a row of products picked for them**.

```text
┌──────────────────────────────────────────────────────────────────────┐
│  H&M                                                   👤 Customer   │
├──────────────────────────────────────────────────────────────────────┤
│  Recommended for you                                                 │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │ Linen  │ │ Wide   │ │ Basic  │ │ Denim  │ │ Strap  │ │ Canvas │ … │
│  │ shirt  │ │ trouser│ │ tee    │ │ shorts │ │ top    │ │ tote   │   │
│  │ White  │ │ Beige  │ │ Black  │ │ Blue   │ │ Green  │ │ Natural│   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │
│                                         (12 products in total)       │
└──────────────────────────────────────────────────────────────────────┘
```

(Illustrative layout. Building a shop front-end is not part of this project.)

What the shopper experiences:

| Situation | What they see |
|---|---|
| Returning customer | 12 products that match their style, their recent purchases and the season |
| Customer who just bought something | Recommendations shift with their recent purchases after the daily refresh |
| Brand-new visitor (no history) | Trending products, adjusted for age group where known (cold-start fallback) |
| Products that can't be sold | Never shown (discontinued items are filtered out) |

### 2.2 The developer integrating the system (API consumer)

A developer building the shop's website or app calls **one HTTP endpoint**. They don't need to
know anything about the model.

**Request**

```http
GET /recommend/{customer_id}?k=12
```

**Response** (illustrative values)

```json
{
  "customer_id": "00000dbacae5abe5e23885899a1fa44253a17956c6d1c3d25f88aa139fdfc657",
  "recommendations": [
    {
      "rank": 1,
      "article_id": "0706016001",
      "product_name": "Jade HW Skinny Denim TRS",
      "product_type": "Trousers",
      "colour": "Black",
      "score": 0.87
    },
    {
      "rank": 2,
      "article_id": "0372860002",
      "product_name": "7p Basic Shaftless",
      "product_type": "Socks",
      "colour": "Black",
      "score": 0.84
    }
  ],
  "strategy": "personalized",
  "model_version": "2026-10-26",
  "latency_ms": 18
}
```

`strategy` is `"personalized"` for known customers and `"cold_start_trending"` for new ones.

**All planned endpoints**

| Endpoint | Purpose | Required by brief |
|---|---|---|
| `GET /recommend/{customer_id}?k=12` | Top-K recommendations for a customer | Yes |
| `GET /health` | Is the API up, and are Redis and the model loaded? | Standard practice |
| `GET /trending?k=12` | Trending products (also used as the cold-start fallback) | Supporting |
| `GET /docs` | Interactive API documentation (Swagger UI, built into FastAPI) | Comes with FastAPI |

The `/docs` page is also how the system is **demonstrated**: open it in a browser, type a
customer ID, click "Execute" and see their recommendations.

### 2.3 The team running the system (ML engineers and operations)

| What they get | Where |
|---|---|
| Automatic weekly retraining and daily refresh, with no manual steps | Airflow web UI (http://localhost:8080) |
| An evaluation report for each trained model: Recall@K, NDCG@K, compared with the baseline | `reports/evaluation_<date>.md` |
| A load-test report: latency and requests per second under concurrent users | `reports/load_test.md` + Locust HTML report |
| Architecture diagrams | `docs/architecture/` |
| A health endpoint to check the system | `GET /health` |

---

## 3. Final output: the system's view

What exists at the end of Week 4:

| # | Deliverable | Format | Produced by |
|---|---|---|---|
| 1 | Cleaned dataset | Parquet files in `data/processed/` | PySpark cleaning job |
| 2 | Feature tables (user, item, context) | Parquet files | PySpark feature job |
| 3 | Vocabularies (ID → number lookup tables) | Text/JSON files in `models/` | Feature job |
| 4 | Trained two-tower model | TensorFlow SavedModel (query tower + candidate tower) | Training job |
| 5 | Product embeddings (105K × 64 numbers) | `.npy` file | Export job |
| 6 | ANN search index | FAISS index file | Index builder |
| 7 | Feature store, loaded with customer profiles and product data | Redis database | Redis loader |
| 8 | Recommendation API | FastAPI service (port 8000) | `src/api/` |
| 9 | Scheduled pipelines | 2 Airflow DAGs | `dags/` |
| 10 | Evaluation report | Markdown | Evaluation job |
| 11 | Load-test report | Markdown + Locust HTML | Locust |
| 12 | Architecture diagrams | Images or diagrams in `docs/` | Week 4 |
| 13 | Tests | pytest suite | `tests/` |
| 14 | Commit history | Daily commits on GitHub | The whole team |

---

## 4. System architecture

### 4.1 The big picture

The system is split into an **offline** half, which learns from history on a schedule, and an
**online** half, which answers live requests in milliseconds. The **artifacts** (trained model,
embeddings, index) and the **feature store** connect them.

```text
╔═══════════════════════════════ OFFLINE (batch, scheduled by Airflow) ═══════════════════════════════╗
║                                                                                                     ║
║   Kaggle          ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      ║
║   CSVs  ────────► │ 1. INGEST    │──► │ 2. CLEAN     │──► │ 3. FEATURES  │──► │ 4. TRAIN +   │      ║
║   (raw)           │  download.py │    │   PySpark    │    │   PySpark    │    │   EVALUATE   │      ║
║                   └──────────────┘    └──────────────┘    └──────────────┘    │   TF + TFRS  │      ║
║                                              │                   │            └──────┬───────┘      ║
║                                              ▼                   ▼                   │              ║
║                                       data/processed/*.parquet                       ▼              ║
║                                                                               ┌──────────────┐      ║
║                                                                               │ 5. EXPORT    │      ║
║                                                                               └──────┬───────┘      ║
╚══════════════════════════════════════════════════════════════════════════════════════╪══════════════╝
                                                                                       │
                ┌──────────────────────────────── ARTIFACTS ───────────────────────────┼──────────┐
                │  models/query_tower/ (SavedModel)   models/item_embeddings.npy      ▼          │
                │  models/vocab/                      models/faiss.index  ◄── 6. BUILD INDEX     │
                └──────────────────────────────────────────────────────────────────────┬──────────┘
                                                                                       │ load
                ┌──────────────────── FEATURE STORE (Redis) ─────────────────┐         │
                │  user:{id}   profile + last 20 purchases                   │◄── 7. LOAD FEATURES
                │  item:{id}   name, type, colour, availability              │         │
                │  trending    top products of the last week                 │         │
                └────────────────────────────┬───────────────────────────────┘         │
                                             │ ~1 ms lookup                            │
╔════════════════════════════════════ ONLINE (real time) ══════════════════════════════╪══════════════╗
║                                            ▼                                         ▼              ║
║   Client ──► GET /recommend/{id} ──► ┌────────────────────────────────────────────────────────┐     ║
║  (web/app)                           │  FastAPI service                                        │     ║
║   ◄── JSON top-K ─────────────────── │  features ─► query tower ─► FAISS search ─► filter/rank │     ║
║                                      └────────────────────────────────────────────────────────┘     ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════════╝

  Airflow:  weekly_retrain (steps 2→3→4→5→6→7)    daily_refresh (update features, embeddings, index)
  Locust:   load test against the API
```

### 4.2 Components

| # | Component | Technology | Responsibility | Input → Output | Code |
|---|---|---|---|---|---|
| 1 | Ingestion | Kaggle API | Download the 3 CSV files | Kaggle → `data/raw/*.csv` | `src/data/download.py` ✅ |
| 2 | Cleaning | PySpark | Types, missing values, duplicates, cold-start flags | CSV → Parquet | `src/data/clean.py` |
| 3 | Feature engineering | PySpark | User, item and context features; train/test split; vocabularies | Parquet → feature Parquet + vocab files | `src/features/` |
| 4 | Model | TensorFlow + TFRS | Two-tower network definition | — | `src/models/two_tower.py` |
| 5 | Training + evaluation | TensorFlow + TFRS | Train with in-batch negatives; compute Recall@K, NDCG@K | Features → trained model + report | `src/models/train.py`, `evaluate.py` |
| 6 | Export | TensorFlow | Save the query tower; calculate every product's embedding | Model → SavedModel + `.npy` | `src/models/export.py` |
| 7 | ANN index | FAISS | Fast nearest-neighbour search over product embeddings | `.npy` → `faiss.index` | `src/serving/ann_index.py` |
| 8 | Feature store | Redis | Hold customer profiles, recent history, product data, trending list | Feature Parquet → Redis keys | `src/serving/feature_store.py` |
| 9 | API | FastAPI + Uvicorn | Serve top-K recommendations | Customer ID → JSON | `src/api/main.py` |
| 10 | Orchestration | Apache Airflow | Schedule retraining and refreshes | — | `dags/` |
| 11 | Load testing | Locust | Simulate many concurrent users | — | `tests/load/locustfile.py` |

### 4.3 Runtime layout (on the laptop, inside WSL2 Ubuntu)

```text
┌──────────────────────────── WSL2 Ubuntu ────────────────────────────┐
│                                                                     │
│   uvicorn (FastAPI)     :8000   ◄── browser /docs, curl, Locust     │
│   redis-server          :6379                                       │
│   airflow scheduler                                                 │
│   airflow webserver     :8080   ◄── browser                         │
│                                                                     │
│   PySpark + TensorFlow run as batch jobs (started by Airflow)       │
│   TensorFlow uses the RTX 2050 GPU through WSL2                     │
│                                                                     │
│   ~/RecommendationEngine/  ◄── git repo, data/, models/             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Offline pipeline in detail

### Step 1: Ingest

`python -m src.data.download` fetches `transactions_train.csv`, `customers.csv` and
`articles.csv` (about 3.8 GB unzipped). It skips the 29 GB images folder.

### Step 2: Clean (PySpark), Week 1

| Table | Cleaning |
|---|---|
| transactions | Parse `t_dat` as a date; keep `article_id` as a 10-character string (with its leading zero); remove exact duplicate rows; check every customer and article exists in the other tables |
| customers | Missing `age` → median by club status, plus an `age_missing` flag; missing `FN` / `Active` → 0; normalise `club_member_status` and `fashion_news_frequency` labels (`NONE`, `None` → `NONE`); missing values → `UNKNOWN` |
| articles | Fill missing `detail_desc` with an empty string; keep only the attribute columns the model uses |
| all | Write Parquet to `data/processed/`, partitioned by week for transactions |

**Cold-start flags:** customers with fewer than N purchases in the training window, and
products with no purchases in it. These decide which recommendation strategy is used.

### Step 3: Features (PySpark), Week 2

| Group | Feature | How it's calculated |
|---|---|---|
| **User** | `age_bucket` | Age in bands: 16–24, 25–34, 35–44, 45–54, 55+, unknown |
| | `club_member_status`, `fashion_news_frequency` | Categorical, from customers |
| | `purchase_count`, `avg_price` | Over the training window |
| | `history` | Last 20 article IDs bought before the purchase being predicted |
| | `preferred_channel` | Share of purchases made online |
| **Item** | `product_type`, `colour_group`, `garment_group`, `department`, `index_group` | Categorical, from articles |
| | `popularity_1w`, `popularity_4w`, `popularity_12w` | Purchase counts over recent windows (popularity over time) |
| | `price_bucket` | Price in bands |
| **Context** | `day_of_week`, `month` | From the purchase date (time of purchase) |
| | `days_since_last_purchase` | Recency |
| | `sales_channel` | 1 = in-store, 2 = online |

**Train/test split by time:** test = the final week; train = the 12 weeks before it. No future
data leaks into training.

**Vocabularies:** for each ID and category column, a lookup table from value to integer index,
with an "unknown" slot for values never seen in training.

### Step 4: Train + evaluate (TFRS), Week 2

See [section 6](#6-the-model-in-detail) for the model and [section 10](#10-evaluation-plan)
for evaluation.

### Step 5: Export, Week 3

- Save the **query tower** as a TensorFlow SavedModel. The API runs it on every request.
- Run the **candidate tower** once over all 105K products and save the result:
  `item_embeddings.npy` (105K × 64) and `item_ids.npy` (row → article_id).

### Step 6: Build the ANN index, Week 3

Load the embeddings into a FAISS index. An exact inner-product index (`IndexFlatIP`) is fast
enough for 105K items. An approximate index (`IndexHNSWFlat` or `IndexIVFFlat`) is benchmarked
against it to meet the brief's ANN requirement and to show how it scales.

### Step 7: Load the feature store, Week 3

Write customer profiles, recent purchase histories, product data and the trending list to Redis
(key design in [section 9](#9-data-and-storage-layout)).

---

## 6. The model in detail

### 6.1 Two-tower architecture

```text
            QUERY TOWER (customer)                         CANDIDATE TOWER (product)

  customer_id ──► Embedding(32) ─┐                 article_id ────► Embedding(32) ─┐
  age_bucket ───► Embedding(8)  ─┤                 product_type ──► Embedding(8)  ─┤
  club_status ──► Embedding(4)  ─┤                 colour_group ──► Embedding(8)  ─┤
  news_freq ────► Embedding(4)  ─┤                 garment_group ─► Embedding(8)  ─┤
  history[20] ──► Embedding(32)  │                 department ────► Embedding(8)  ─┤
                  → average ────┤                 index_group ───► Embedding(4)  ─┤
  day_of_week ──► Embedding(4)  ─┤                 popularity ────► normalised    ─┤
  month ────────► Embedding(4)  ─┤                 price_bucket ──► Embedding(4)  ─┘
  channel ──────► Embedding(2)  ─┤                                      │
  days_since ───► normalised    ─┘                                 concatenate
                    │                                                   │
               concatenate                                    Dense(128, ReLU)
                    │                                                   │
            Dense(128, ReLU)                                     Dense(64)
                    │                                                   │
              Dense(64)                                       product vector (64)
                    │                                                   │
          customer vector (64) ─────────────── dot product ─────────────┘
                                                    │
                                              match score
```

The embedding sizes shown are starting points. They will be tuned in Week 2.

### 6.2 Training

| Setting | Choice | Reason |
|---|---|---|
| Training examples | Each (customer + context, purchased product) pair in the 12-week window | Positive examples |
| Negatives | **In-batch negatives**: the other products in the same batch count as "not bought" | Built into the TFRS `Retrieval` task; no separate sampling step needed |
| Loss | Softmax cross-entropy over the batch | TFRS default for retrieval |
| Batch size | 4096 | Large batches mean more negatives per example |
| Optimiser | Adagrad, learning rate 0.05 (to tune) | Common TFRS choice for embeddings |
| Epochs | ~5, with early stopping on validation recall | Avoid overfitting |
| Hardware | RTX 2050 GPU through WSL2 | |

Settings live in [configs/config.yaml](../configs/config.yaml).

### 6.3 Why two towers?

The customer side and the product side are calculated **separately**. That means:

- All 105K product vectors can be calculated **once**, in advance.
- At request time, only **one** customer vector is calculated, followed by a fast vector search.
- So the system stays fast even with millions of products, which is the core reason this
  architecture is used for large-scale recommendation.

---

## 7. Online serving in detail

### 7.1 What happens on one request

```text
 Client                FastAPI                 Redis            Query tower        FAISS
   │  GET /recommend/abc?k=12  │                    │                  │               │
   │──────────────────────────►│                    │                  │               │
   │                           │ HGETALL user:abc   │                  │               │
   │                           │───────────────────►│                  │               │
   │                           │◄── profile + last 20 purchases        │               │
   │                           │                                       │               │
   │                           │ build input (profile + history + current time context)│
   │                           │──────────────────────────────────────►│               │
   │                           │◄─────────────── customer vector (64) ─│               │
   │                           │                                                       │
   │                           │ search(vector, 100) ─────────────────────────────────►│
   │                           │◄──────────────────────────── 100 nearest products ────│
   │                           │                                                       │
   │                           │ filter: unavailable products, (optionally) already bought
   │                           │ keep top 12, add names/colours from Redis item:{id}   │
   │◄── JSON (12 products) ────│                                                       │
```

| Step | Target time |
|---|---|
| Redis lookup | ~1 ms |
| Query tower | ~5–15 ms (CPU) |
| FAISS search over 105K products | ~1–5 ms |
| Filter, rank, build response | ~1–2 ms |
| **Total** | **well under 100 ms** |

### 7.2 Cold-start and edge cases

| Case | Strategy |
|---|---|
| Customer not in Redis (brand new) | Return the trending list, by age group if known → `strategy: "cold_start_trending"` |
| Customer with very little history | Use the model; profile and context features still carry signal |
| New product with no purchases | Its attributes (type, colour, …) still give it a vector, so it can be recommended |
| Redis down | `/health` reports it; the API returns 503 with a clear error |
| `k` out of range | Validation error (allowed range 1–100) |

### 7.3 Updating the model without downtime

The daily and weekly jobs write new artifacts to a versioned folder, then update
`meta:model_version` in Redis. The API checks this key and reloads the model and index in the
background, so requests keep being served during the switch.

---

## 8. Automation with Airflow

### `weekly_retrain` (every Monday, 02:00)

```text
download_new_data ─► clean ─► build_features ─► train ─► evaluate ─┬─► export ─► build_index ─► load_redis ─► publish_version
                                                                  │
                                                                  └─► (if worse than the current model) stop and alert
```

### `daily_refresh` (every day, 03:00)

```text
update_user_features (new purchases → history, recency) ─► load_redis
recompute_item_embeddings (current model, updated popularity) ─► rebuild_index ─► publish_version
update_trending
```

Since the H&M dataset is a fixed historical snapshot, we **simulate** time passing: each run
moves the "current date" forward one week (or day) through the data. This shows the pipeline
working as it would in production.

---

## 9. Data and storage layout

### Files

```text
data/
├── raw/                                  (from Kaggle, never committed)
│   ├── transactions_train.csv
│   ├── customers.csv
│   └── articles.csv
└── processed/                            (PySpark output, never committed)
    ├── transactions/  (partitioned by week)
    ├── customers/
    ├── articles/
    ├── user_features/
    ├── item_features/
    ├── train/
    └── test/

models/                                   (never committed)
└── <version, e.g. 2026-10-26>/
    ├── query_tower/                      TensorFlow SavedModel
    ├── candidate_tower/                  TensorFlow SavedModel
    ├── vocab/                            lookup tables
    ├── item_embeddings.npy               105K × 64
    ├── item_ids.npy
    ├── faiss.index
    └── metrics.json                      Recall@K, NDCG@K for this version
```

### Redis keys

| Key | Type | Contents |
|---|---|---|
| `user:{customer_id}` | Hash | `age_bucket`, `club_member_status`, `fashion_news_frequency`, `purchase_count`, `last_purchase_date`, `history` (JSON list of the last 20 article IDs) |
| `item:{article_id}` | Hash | `product_name`, `product_type`, `colour`, `garment_group`, `available` |
| `trending:global` | List | Top 100 article IDs of the last week |
| `trending:age:{bucket}` | List | Top 100 per age group (cold start) |
| `meta:model_version` | String | Currently active model version |

---

## 10. Evaluation plan

### Metrics

| Metric | Question it answers |
|---|---|
| **Recall@K** (K = 12, 50, 100) | Of the products the customer really bought in the test week, what fraction were in our top K? |
| **NDCG@12** | Were the right products near the **top** of the list? |
| MAP@12 (extra) | The Kaggle competition's metric, for comparison with public results |

Recall@50 and @100 matter because the ANN step retrieves 100 candidates. If the right product
isn't among them, nothing later can fix it.

### Baselines (the model must beat these)

| Baseline | Description |
|---|---|
| Global popularity | The same 12 best-selling products of the last week for everyone |
| Popularity by age group | Best-sellers among customers of the same age band |
| Repurchase | The customer's own most-bought products |

### Protocol

1. Train on 12 weeks and test on the following week (no overlap).
2. Score only customers who bought something in the test week.
3. Report the metrics separately for **warm** customers (with history) and **cold** customers.
4. Save the results to `models/<version>/metrics.json` and `reports/evaluation_<date>.md`.

---

## 11. Work plan: what gets done, week by week

Status: ✅ done, ⏳ next, ⬜ planned.

### Week 1: distributed data processing and feature engineering

| Task | Output | Done when | Status |
|---|---|---|---|
| Repo setup, dependencies, config, download script | Repo structure, `download.py` | Merged into `main` | ✅ |
| Environment: WSL2, Python, Java, GPU check | Working environment, `scripts/setup_wsl.sh` | `pytest` passes in WSL; TF sees the GPU | ✅ (RTX 2050 via `tensorflow[and-cuda]`) |
| Download data | `data/raw/*.csv` | 3 files present | ✅ (row counts match Kaggle) |
| PySpark cleaning | `src/data/clean.py`, Parquet | Row counts and missing-value checks pass | ✅ (31.8M rows in about 5 minutes; see Work Log step 7) |
| Cold-start flags | Flags in Parquet | Cold-start counts reported | ✅ (81% of customers, 61% of products) |
| Data-quality report | `reports/data_quality.md` | Committed | ⬜ |

### Week 2: deep learning model

| Task | Output | Done when | Status |
|---|---|---|---|
| Contextual features (time, recency, popularity over time) | `src/features/build_features.py` | Feature tables written | ✅ (3.36M training examples; see Work Log step 8) |
| Vocabularies | `src/features/vocab.py` | Lookup tables saved | ✅ (saved with each model) |
| Baselines | `src/models/baselines.py` | Baseline metrics recorded | ✅ (`reports/baselines.md`; repurchase MAP@12 0.0227) |
| Two-tower model | `src/models/two_tower.py` | Model builds; a training step runs | ✅ |
| Training with negative sampling | `src/models/train.py` | Model trained and saved | ✅ (in-batch negatives, early stopping) |
| Evaluation: Recall@K, NDCG | `src/models/evaluate.py`, report | Beats the popularity baseline | ⏳ (v1 does not yet; see Work Log step 12) |

### Week 3: model serving and feature store

| Task | Output | Done when | Status |
|---|---|---|---|
| Export towers and product embeddings | `src/models/export.py` | SavedModel + `.npy` files | ⬜ |
| Redis feature store | `src/serving/feature_store.py` | Profiles and products loaded | ⬜ |
| ANN index (FAISS) | `src/serving/ann_index.py` | Approximate results match exact search ≥ 95% | ⬜ |

### Week 4: pipeline scheduling and API

| Task | Output | Done when | Status |
|---|---|---|---|
| FastAPI service | `src/api/main.py` | `/recommend` returns top-K; tests pass | ⬜ |
| Airflow DAGs | `dags/weekly_retrain.py`, `dags/daily_refresh.py` | Both DAGs run successfully in the Airflow UI | ⬜ |
| Load test | `tests/load/locustfile.py`, report | p95 latency and requests per second recorded | ⬜ |
| Architecture diagrams + final docs | `docs/architecture/`, README | Committed | ⬜ |
| Final demo | Swagger UI walkthrough | Shown end to end | ⬜ |

---

## 12. Final repository layout

```text
RecommendationEngine/
├── README.md
├── requirements*.txt, .env.example, .gitignore
├── configs/config.yaml
├── src/
│   ├── config.py
│   ├── data/
│   │   ├── download.py          ✅ Kaggle download
│   │   └── clean.py             PySpark cleaning
│   ├── features/
│   │   ├── build_features.py    user / item / context features, split
│   │   └── vocab.py             vocabularies
│   ├── models/
│   │   ├── baselines.py         popularity baselines
│   │   ├── two_tower.py         TFRS model
│   │   ├── train.py             training
│   │   ├── evaluate.py          Recall@K, NDCG@K
│   │   └── export.py            SavedModel + embeddings
│   ├── serving/
│   │   ├── feature_store.py     Redis read/write
│   │   └── ann_index.py         FAISS build/search
│   └── api/
│       ├── main.py              FastAPI app
│       └── schemas.py           request/response models
├── dags/
│   ├── weekly_retrain.py
│   └── daily_refresh.py
├── tests/
│   ├── test_*.py                unit tests
│   └── load/locustfile.py       load test
├── reports/                     data quality, evaluation, load test
└── docs/
    ├── PROJECT_BLUEPRINT.md     this file
    ├── PROJECT_GUIDE.md
    └── architecture/            diagrams
```

---

## 13. Risks and how we handle them

| Risk | Impact | Mitigation |
|---|---|---|
| 16 GB RAM is not enough for 31.8M rows in memory | Crashes | Spark processes the data in partitions; train only on the 12-week window; use Parquet |
| ~30 GB free disk | Download or processing fails | Skip images (−29 GB); the download script checks free space; the Instacart folder (~4.2 GB) can be removed if needed |
| Airflow, Redis and TF GPU don't run natively on Windows | Blocked | Develop in WSL2 Ubuntu |
| TFRS incompatible with Keras 3 | Code crashes | Pinned `tf-keras` + `TF_USE_LEGACY_KERAS=1` |
| Data leakage (training on test-week data) | Misleadingly good scores | Strict time-based split; tests check there's no overlap |
| Many customers bought only once | Weak personalisation | Cold-start strategy; profile and context features; report warm and cold results separately |
| Model doesn't beat the baselines | Weak result | Tune features and embedding sizes; add popularity as a feature; try hard negatives |
| Team members' changes conflict | Lost work, confusion | Pull `main` before working; short-lived branches; one PR per task |
| Missed daily commits | Evaluation not processed (per the brief) | Commit every working day, even small progress |

---

## 14. Out of scope

- A real shop front-end (the API plus the Swagger UI demo stands in for it)
- Product images and image models (the brief doesn't require them; they'd add 29 GB)
- Cloud deployment (everything runs locally on the laptop; the design would carry over to cloud)
- Real-time event streaming (for example Kafka); updates come in daily batches
- A re-ranking second-stage model (possible future work after retrieval)
- A/B testing against live traffic (the data is a historical snapshot)
