# Project Guide: Context-Aware Neural Recommendation Engine

A plain-language guide to everything in this repository: what the project is, what has been
built, what is on GitHub, how the finished system will work, and what comes next.

The [README](../README.md) is the short public summary. This guide is the long version, for
understanding the project.

**Status as of 2 Oct 2026:** Week 1, Day 1. The project setup is done and waiting for review
in PR #1. No data has been downloaded or processed yet.

---

## Contents

1. [What we are building](#1-what-we-are-building)
2. [Where things stand](#2-where-things-stand)
3. [GitHub: branches, pull requests and history](#3-github-branches-pull-requests-and-history)
4. [Walkthrough of every file](#4-walkthrough-of-every-file)
5. [How the finished system will work](#5-how-the-finished-system-will-work)
6. [The dataset](#6-the-dataset)
7. [Decisions made and why](#7-decisions-made-and-why)
8. [Key concepts](#8-key-concepts)
9. [The 4-week plan](#9-the-4-week-plan)
10. [Development environment](#10-development-environment)
11. [Team workflow rules](#11-team-workflow-rules)
12. [Next steps](#12-next-steps)
13. [Command reference](#13-command-reference)

---

## 1. What we are building

This is **Project 3: Context-Aware Neural Recommendation Engine (Deep Learning)** for Zaalima.

The goal is a system that answers one question: **"Given a customer, which products should we
show them?"** It answers in real time, through an API.

It goes beyond simple "people who bought X also bought Y" recommendations by combining three
kinds of information:

| Information | Example | Brief's term |
|---|---|---|
| Who the customer is | age, club membership status | user metadata |
| What they bought before | their last 20 purchases | historical interaction sequences |
| What the product is | colour, garment type, department | item context |

The model is a **two-tower neural network** (explained in [section 8](#8-key-concepts)). It is
built with TensorFlow Recommenders and served through FastAPI, with Redis as a fast cache and
Airflow to schedule retraining.

**Business goal in the brief:** more engagement, a higher click-through rate (CTR) and a higher
average order value (AOV), by showing products that match both the customer's long-term taste
and their recent shopping.

---

## 2. Where things stand

### Done

| Item | Details |
|---|---|
| Dataset chosen | H&M Personalized Fashion Recommendations (see [section 7](#7-decisions-made-and-why)) |
| System designed | Full pipeline from raw data to API (see [section 5](#5-how-the-finished-system-will-work)) |
| Repo structured | Folders for every stage of the pipeline |
| Dependencies pinned | Exact package versions, checked to install together |
| Config file | One settings file for the whole project |
| Download script | Fetches the 3 H&M CSV files from Kaggle |
| README rewritten | Matches the project brief |
| Tests | 3 tests, all passing |
| PR opened | PR #1, `feature/project-setup` into `main` |

### Not started

- Downloading the data (needs your Kaggle token)
- PySpark cleaning, feature engineering, the model, serving, API, Airflow, load testing

### Blocked on you

| Task | Why it's needed |
|---|---|
| Install WSL2 (Ubuntu) | Airflow and Redis don't run natively on Windows, and TensorFlow can only use your GPU on Linux |
| Kaggle API token in `C:\Users\TEJASHVI\.kaggle\kaggle.json` | Needed to download the data |
| Accept the H&M competition rules on Kaggle | Kaggle refuses downloads until you do |
| `gh auth login` | Lets Claude create and track pull requests from the command line |
| Get PR #1 reviewed and merged | So `main` has the new structure |
| Close PR #2 | It duplicates PR #1 (see [section 3](#3-github-branches-pull-requests-and-history)) |

---

## 3. GitHub: branches, pull requests and history

**Repository:** https://github.com/celesteesunn/RecommendationEngine (owned by celesteesunn)

### Branches

| Branch | Latest commit | What it is |
|---|---|---|
| `main` | `569731c`, Siddhi, 2 Oct: "Update team member list in README" | The official version. It still has the old README and no code. |
| `feature/project-setup` | `7b7ac7c`, 2 Oct: "Merge main into feature/project-setup" | **The active work.** All the setup described in this guide. Up to date with `main`. |
| `Tejashvi` | `ddb9343`, 2 Oct: "chore: set up H&M project structure…" | A copy of the first setup commit, without the later merge. **Duplicate, not needed.** |
| `dataset/movielens-1m` | **Deleted** from GitHub | celesteesunn's MovieLens data-inspection notebook (16–18 Sep). Someone deleted it after the switch to H&M. |

### Pull requests

| PR | From → into | Status | Notes |
|---|---|---|---|
| [#1](https://github.com/celesteesunn/RecommendationEngine/pull/1) | `feature/project-setup` → `main` | Open, can merge cleanly | **The one to keep.** It includes Siddhi's latest team-list change. |
| [#2](https://github.com/celesteesunn/RecommendationEngine/pull/2) | `Tejashvi` → `main` | Open | **Duplicate of #1.** It's missing the merge with `main`, so its README would conflict with Siddhi's change. Recommendation: close it, and delete the `Tejashvi` branch. |

### Commit history

```text
2026-09-15  celesteesunn   Initialise the repo (README, .gitignore)
2026-09-16  Tejashvi       Update project status to "data collection phase"
2026-09-16  siddhi         Set up structure: requirements.txt, .gitignore
2026-09-16  celesteesunn   README: add MovieLens / H&M / Blinkit comparison plan
2026-09-30  Tejashvi       Fix team member order in README
            ── branch: feature/project-setup ──
2026-10-02  Tejashvi       Set up H&M project structure and dependencies   (ddb9343)
2026-10-02  siddhi         Update team member list in README (on main)    (569731c)
2026-10-02  Tejashvi       Merge main into feature/project-setup           (7b7ac7c)
```

### What changed in the project's direction

Until 30 Sep, the plan in the README was to **compare three datasets** (MovieLens, H&M,
Blinkit). On 2 Oct, after reading the brief, we switched to **H&M only**, because the brief
names it as the primary data source. Teammates should know about this change. See
[section 7](#7-decisions-made-and-why).

### Related folder outside this repo

`ZALIMA ML/instacart-market-basket-analysis/` is a separate project. It has Instacart grocery
data (about 4.2 GB), theory notes and an exploration script. It is **not part of this
project** and has no commits. It takes up disk space that you may want back later (see
[section 10](#10-development-environment)).

---

## 4. Walkthrough of every file

```text
RecommendationEngine/
├── README.md                  Public summary of the project
├── .gitignore                 What git must never commit
├── .env.example               Template for local settings
├── requirements.txt           Main Python packages (pinned versions)
├── requirements-dev.txt       Extra packages for testing
├── requirements-airflow.txt   Airflow install instructions
├── configs/
│   └── config.yaml            All project settings in one place
├── src/                       All project code (a Python package)
│   ├── __init__.py
│   ├── config.py              Reads config.yaml
│   ├── data/
│   │   ├── __init__.py
│   │   └── download.py        Downloads the H&M data from Kaggle
│   ├── features/__init__.py   (empty, Week 2: feature engineering)
│   ├── models/__init__.py     (empty, Week 2: Two-Tower model)
│   ├── serving/__init__.py    (empty, Week 3: Redis + ANN)
│   └── api/__init__.py        (empty, Week 4: FastAPI)
├── tests/
│   ├── __init__.py
│   └── test_config.py         3 tests for the config
├── dags/                      (empty, Week 4: Airflow DAGs)
├── docs/
│   └── PROJECT_GUIDE.md       This file
├── notebooks/                 (empty, optional data exploration)
├── data/
│   ├── raw/                   Kaggle CSVs go here (never committed)
│   └── processed/             Cleaned Parquet files go here (never committed)
└── models/                    Trained models go here (never committed)
```

The empty folders contain a `.gitkeep` file. Git doesn't track empty folders, so this
placeholder keeps them in the repo.

### `requirements.txt`: the Python packages

Every version is **pinned** (for example `pandas==2.2.3`), so every teammate installs exactly
the same thing and "works on my machine" problems are avoided.

| Package | Version | Used for |
|---|---|---|
| numpy, pandas, pyarrow | 1.26.4, 2.2.3, 17.0.0 | Working with data tables; pyarrow reads and writes Parquet |
| pyspark | 3.5.6 | Processing the 31.8M purchase rows (Week 1) |
| scikit-learn | 1.5.2 | Helper utilities (encoding, metrics) |
| tensorflow | 2.18.1 | The deep learning framework |
| tf-keras | 2.18.0 | Keras 2, which TensorFlow Recommenders needs (see below) |
| tensorflow-recommenders | 0.7.7 | Ready-made building blocks for two-tower models |
| faiss-cpu | 1.9.0 | Fast nearest-neighbour search over product vectors |
| redis | 5.2.1 | Python client for the Redis feature store |
| fastapi, uvicorn, pydantic | 0.115.6, 0.32.1, 2.10.4 | The web API and the server that runs it |
| kaggle | 1.7.4.5 | Downloading the dataset |
| pyyaml | 6.0.2 | Reading `config.yaml` |

**Why `tf-keras` and `TF_USE_LEGACY_KERAS=1`?** TensorFlow 2.16+ switched to Keras 3, but
TensorFlow Recommenders was written for Keras 2. Installing `tf-keras` and setting this
environment variable makes TensorFlow use Keras 2. Without it, TFRS code crashes.

- `requirements-dev.txt` adds **pytest** (runs the tests) and **Locust** (the Week 4 load test).
- `requirements-airflow.txt` holds Airflow on its own because Airflow has hundreds of
  dependencies. It must be installed with its official "constraints file", or it breaks
  other packages. The file contains the exact install command.

### `configs/config.yaml`: all settings in one place

Instead of hard-coding numbers in the code, every setting lives here. To change something,
edit one file.

| Section | Setting | Value | Meaning |
|---|---|---|---|
| dataset | `files` | 3 CSVs | Which Kaggle files to download (no images) |
| paths | `raw_dir`, `processed_dir`, `models_dir` | `data/raw`, … | Where files go |
| split | `test_weeks` | 1 | The last week of data is held back for testing |
| split | `train_weeks` | 12 | Train on the 12 weeks before that |
| model | `embedding_dim` | 64 | Each customer and product becomes a list of 64 numbers |
| model | `history_length` | 20 | Use each customer's last 20 purchases |
| model | `batch_size` | 4096 | Purchases processed per training step |
| model | `learning_rate`, `epochs` | 0.05, 5 | Training speed and number of passes over the data |
| evaluation | `k_values` | 12, 50, 100 | Measure Recall@12, @50 and @100 |
| serving | `top_k` | 12 | The API returns 12 products |
| serving | `ann_candidates` | 100 | The search finds 100 candidates, then the best 12 are kept |

These model numbers are sensible starting points. They will be tuned in Week 2.

### `src/config.py`

Two small helpers:

- `load_config()` reads `config.yaml` into a Python dictionary.
- `project_path("data/raw")` turns a relative path into a full path, so scripts work from any
  folder.

### `src/data/download.py`

Run it with `python -m src.data.download`. It:

1. Checks that your Kaggle token exists, and stops with a clear message if it doesn't.
2. Checks there are at least 6 GB of free disk space. The purchases file is about 3.5 GB once
   unzipped, and the zip and the CSV exist together briefly while unzipping.
3. Downloads each of the 3 CSVs and unzips them into `data/raw/`.
4. Skips files that are already downloaded, unless you pass `--force`.
5. If Kaggle refuses access (an HTTP 403 error, meaning the competition rules haven't been
   accepted), it prints the link to accept them instead of crashing.

The Kaggle library tries to log in the moment it's imported, which crashes without a token.
That's why the script imports it only after checking the token exists.

### `tests/test_config.py`

These tests check that `config.yaml` has every section, lists exactly the 3 expected data
files, and resolves paths inside the repo. Run them with `pytest`. All 3 pass.

### `.gitignore`

This file stops git from committing:

- **Data** (`data/raw/*`, `data/processed/*`, `*.parquet`, `*.zip`). It's gigabytes in size and
  Kaggle's rules don't allow re-sharing it.
- **Trained models** (`models/*`). These are large, and can be regenerated.
- **Secrets** (`.env`, `kaggle.json`). Never put passwords or API keys on GitHub.
- **Tool output** (Python caches, Spark's `spark-warehouse/` and `derby.log`, Airflow logs).

### `.env.example`

A template for your local `.env` file. Copy it with `cp .env.example .env`. It holds
`TF_USE_LEGACY_KERAS=1` and the Redis host and port. `.env` itself is never committed.

---

## 5. How the finished system will work

The system has two halves. The **offline** half learns from historical data and runs on a
schedule. The **online** half answers live requests in milliseconds.

### Offline: training pipeline

```text
 [1] DOWNLOAD           Kaggle ─► data/raw/*.csv                      src/data/download.py
          │
 [2] CLEAN (PySpark)    fix data types, fill missing values,          src/data/  (Week 1)
          │             remove duplicates, flag cold-start users and items
          │             ─► data/processed/*.parquet
          │
 [3] FEATURES (PySpark) user:    age group, club status, # purchases, src/features/ (Week 2)
          │                      average price, last 20 items
          │             item:    type, colour, garment group, popularity
          │                      over the last 1/4/12 weeks
          │             context: day of week, month, days since last
          │                      purchase, sales channel (online/store)
          │
 [4] SPLIT + VOCABS     train = 12 weeks, test = the final week       src/features/ (Week 2)
          │             build ID ─► number lookup tables
          │
 [5] TWO-TOWER MODEL    query tower (customer) + candidate tower      src/models/ (Week 2)
          │             (product), each outputs 64 numbers
          │
 [6] TRAIN + EVALUATE   in-batch negative sampling;                   src/models/ (Week 2)
          │             Recall@K, NDCG; must beat a "most popular" baseline
          │
 [7] EXPORT             query tower ─► SavedModel                     src/models/ (Week 3)
                        every product's vector ─► .npy file
```

### Online: answering a request

```text
 Client ──► GET /recommend/{customer_id}?k=12                         src/api/ (Week 4)
              │
              ├─ 1. Look up the customer's features in Redis           (about 1 ms)
              ├─ 2. Run the query tower ─► customer vector (64 numbers)
              ├─ 3. FAISS search: the 100 product vectors closest to it
              ├─ 4. Remove products that can't be sold ─► keep the top 12
              └─ 5. Return JSON: [{article_id, score, name, ...}, ...]

 New customer with no history? ─► return trending products instead (cold-start fallback)
```

Only the **customer's** vector is calculated at request time. All 105K product vectors are
calculated in advance and stored in the FAISS index, which is what makes the system fast.

### Automation (Airflow)

| DAG (scheduled workflow) | Schedule | Steps |
|---|---|---|
| Retraining | Weekly | Clean → features → train → evaluate → export (steps 2–7) |
| Embedding refresh | Daily | Recalculate product vectors → update Redis → rebuild the FAISS index |

---

## 6. The dataset

**H&M Personalized Fashion Recommendations** is a 2022 Kaggle competition dataset from H&M
Group.

| File | Rows | Key columns |
|---|---|---|
| `transactions_train.csv` (~3.5 GB) | ~31.8 million | `t_dat` (date), `customer_id`, `article_id`, `price`, `sales_channel_id` (1 = store, 2 = online) |
| `customers.csv` (~200 MB) | ~1.37 million | `customer_id`, `age`, `club_member_status`, `fashion_news_frequency`, `FN`, `Active`, `postal_code` |
| `articles.csv` (~36 MB) | ~105,000 | `article_id`, `product_type_name`, `colour_group_name`, `garment_group_name`, `department_name`, `index_group_name`, `detn_desc` (text description) |

- **Time span:** Sep 2018 to Sep 2020. That's 2 years of purchases.
- **Images:** an extra ~29 GB folder of product photos. **We don't download it.** The brief
  doesn't need it, and your disk has only about 30 GB free.
- **Known quirks** (to handle in Week 1): many customers have missing ages and empty
  `FN`/`Active` fields; prices are scaled (not real currency); and many customers bought
  only once or twice (the cold-start problem).
- **Kaggle's own metric** was MAP@12 (how good the top 12 predictions are). The brief asks for
  Recall@K and NDCG. We report the brief's metrics, and can add MAP@12 for comparison.

---

## 7. Decisions made and why

| Decision | Alternatives considered | Why |
|---|---|---|
| **H&M dataset** | MovieLens-1M, Instacart, Blinkit | The brief names H&M as the primary source. It is the only option with customer details, rich product attributes **and** real purchase dates. MovieLens is movies, not shopping. Instacart has no customer details or real dates. No public Blinkit interaction dataset exists. |
| **Download only the CSVs** | The full download with images | Saves about 29 GB. Images aren't required by the brief. |
| **Train on the last 12 weeks** | All 2 years | Fashion changes fast, so old purchases predict poorly. It's also much faster on a laptop. The data cleaning still processes the full data, as the brief requires. |
| **Time-based train/test split** | A random split | A random split lets the model "see the future" and gives misleadingly good scores. Testing on the final week mimics real use. |
| **TensorFlow 2.18 + tf-keras + TFRS 0.7.7** | TF 2.15 (older), TF 2.21 (newest) | TF 2.18 supports Python 3.11 and 3.12. TFRS 0.7.7 officially supports tf-keras. Checked to install together. |
| **FAISS for ANN search** | ScaNN, Annoy | FAISS is mature, has CPU builds for Linux and Windows, and is fast on 105K items. |
| **Develop in WSL2 (Linux)** | Native Windows | Airflow and Redis don't run on Windows, TensorFlow can't use the GPU on Windows, and Spark is awkward there. |
| **Airflow in a separate requirements file** | Inside requirements.txt | Airflow must be installed with its constraints file, or it breaks other packages. |

---

## 8. Key concepts

**Recommendation as retrieval.** We don't predict a star rating. We pick the best ~12 products
out of 105,000 for each customer.

**Embedding.** A list of numbers (here 64) that represents something: a customer, a product, a
colour. The model learns these numbers so that similar things end up with similar lists.

**Two-tower model.** Two neural networks side by side:
- The **query tower** turns a customer, plus their context, into a 64-number vector.
- The **candidate tower** turns a product into a 64-number vector.
- The **score** is the dot product of the two vectors: multiply the numbers pairwise and add
  them up. A high score means a good match.

Because the towers are separate, all product vectors can be calculated in advance. That is what
makes real-time serving possible.

**Vocabulary (lookup table).** Neural networks need numbers, not text IDs. A vocabulary maps
each `customer_id` or `article_id` (or colour, product type, …) to an integer, which then looks
up its embedding. IDs not in the vocabulary map to a shared "unknown" slot.

**Negative sampling.** The data only tells us what customers *did* buy. To learn, the model also
needs examples of what they *didn't* buy. **In-batch negatives** reuse the other customers'
purchases in the same training batch as "not bought" examples. TFRS does this automatically.

**Recall@K.** Of the products a customer actually bought in the test week, the fraction that
appeared in our top K. Example: they bought 4 items, and 2 were in our top 12, so Recall@12 =
0.5.

**NDCG@K (Normalized Discounted Cumulative Gain).** Like Recall, but it also rewards putting the
right products near the **top** of the list. A hit at position 1 counts more than a hit at
position 12. The score ranges from 0 (worst) to 1 (perfect order).

**Baseline.** A simple method to compare against, here "recommend the most popular items of the
last week". If the neural model can't beat it, something is wrong.

**Cold start.** A new customer, or a new product, with little or no history. The model knows
little about them, so we fall back to their age group, product attributes, or trending
products.

**ANN (approximate nearest neighbour) search.** Finding the product vectors closest to the
customer vector. Checking all 105K exactly is slow at scale. ANN libraries such as FAISS find
almost the best matches much faster.

**Feature store (Redis).** An in-memory database that holds ready-made customer profiles, so the
API doesn't recalculate them on every request. Lookups take about 1 ms.

**Parquet.** A compressed, column-based file format. It's much smaller and faster to read than
CSV, and it's Spark's standard format.

**PySpark.** Python for Apache Spark, which processes large data in parallel, across CPU cores
or machines. The brief requires it for data preparation.

**Airflow DAG.** A scheduled workflow defined in Python ("run step A, then B, then C, every
Monday"). DAG stands for directed acyclic graph.

**Load / stress test (Locust).** Simulates many users calling the API at once, and measures
response time and requests per second.

---

## 9. The 4-week plan

From the brief, with the planned files. (The brief's day numbering restarts partway through
Week 2. The order of the tasks is what matters.)

### Week 1: data processing and feature engineering

| Day | Task | Output | Status |
|---|---|---|---|
| 1 | Repo setup, dependencies, config, download script | PR #1 | ✅ Done, in review |
| 1–3 | PySpark: load CSVs, fix types, handle missing values, flag cold-start users and items, save Parquet | `src/data/clean.py`, `data/processed/` | ⏳ Next (needs WSL2 and Kaggle) |

### Week 2: deep learning model

| Day | Task | Output | Status |
|---|---|---|---|
| 4–6 | Contextual features: time of purchase, recency, popularity over time | `src/features/build_features.py` | Planned |
| 7 | Vocabularies for users, items and categories | `src/features/vocab.py` | Planned |
| 1–4 | Two-tower model in TFRS (query tower + candidate tower) | `src/models/two_tower.py` | Planned |
| 5–7 | Train with negative sampling; evaluate Recall@K and NDCG against the baseline | `src/models/train.py`, `evaluate.py` | Planned |

### Week 3: serving and feature store

| Day | Task | Output | Status |
|---|---|---|---|
| 1–3 | Export the query tower and product vectors | `src/models/export.py`, `models/` | Planned |
| 4–6 | Redis feature store: customer profiles and product vectors | `src/serving/feature_store.py` | Planned |
| 7 | FAISS ANN index | `src/serving/ann_index.py` | Planned |

### Week 4: pipeline scheduling and API

| Day | Task | Output | Status |
|---|---|---|---|
| 1–3 | FastAPI: customer ID → Redis → model → FAISS → top K | `src/api/main.py` | Planned |
| 4–5 | Airflow DAGs: weekly retraining, daily embedding refresh | `dags/*.py` | Planned |
| 6–7 | Locust load test, architecture diagrams, final docs | `tests/load/`, `docs/` | Planned |

---

## 10. Development environment

### Your laptop (checked 2 Oct 2026)

| Component | Value | Notes |
|---|---|---|
| CPU | Intel i5-1240P, 16 threads | Good for Spark |
| RAM | 16 GB | Enough, if training uses the 12-week window |
| GPU | NVIDIA RTX 2050 (4 GB) | Usable for training, but **only inside WSL2** |
| Free disk on C: | ~30 GB | Tight. The H&M CSVs plus Parquet need ~6–8 GB. The Instacart folder uses ~4.2 GB you could free. |
| Python | 3.11.8 (Windows) | |
| Java | 17 (Eclipse Adoptium) | Spark needs Java. Inside WSL, install `openjdk-17-jdk`. |
| Git | Installed | |
| GitHub CLI | Installed, **not logged in** | Run `gh auth login` |
| WSL2 | **Not installed** | Run `wsl --install -d Ubuntu` (Administrator), then restart |
| Docker | Not installed | Not needed if you use WSL2 |
| Kaggle token | **Missing** | `C:\Users\TEJASHVI\.kaggle\kaggle.json` |

### Target setup (inside WSL2 Ubuntu)

```text
Ubuntu (WSL2)
├── Python 3.12 + .venv         ← requirements-dev.txt
├── OpenJDK 17                  ← for PySpark
├── Redis server                ← sudo apt install redis-server
├── Airflow 2.10.4              ← requirements-airflow.txt
└── NVIDIA GPU via WSL          ← TensorFlow can use the RTX 2050
```

---

## 11. Team workflow rules

From the brief's "Required protocol":

- **Commit to GitHub every day.** The commit history is used to track daily productivity. **No
  daily commits means the evaluation isn't processed.**
- Write professional commit messages, manage branches logically, and follow a normal team
  workflow.

How this repo follows that:

| Rule | Practice |
|---|---|
| Branches | Create from `main`: `feature/<name>`, `fix/<name>`, `docs/<name>` |
| Commit messages | Start with a type: `feat:`, `fix:`, `docs:`, `chore:`, `test:` |
| Merging | Always through a pull request into `main`, never a direct push |
| Before a PR | Merge the latest `main` into your branch (as done for PR #1) |
| One PR per piece of work | Avoid duplicates like PR #2 |

---

## 12. Next steps

### For you (in order)

1. **Close PR #2** on GitHub, and delete the `Tejashvi` branch. It duplicates PR #1.
2. **Ask a teammate to review and merge PR #1.**
3. **Tell the team** the project has switched to H&M only. The MovieLens branch has already been
   deleted.
4. **Install WSL2:** `wsl --install -d Ubuntu` in an Administrator PowerShell, then restart.
5. **Set up Kaggle:** accept the competition rules, then create a token and save it as
   `C:\Users\TEJASHVI\.kaggle\kaggle.json`.
6. **Log in to GitHub CLI:** `gh auth login`.

### Then, for Claude (Week 1, Days 1–3, on `feature/spark-etl`)

1. Set up Python, Java and the packages inside WSL. Check that TensorFlow can see the GPU.
2. Download the data with `python -m src.data.download`.
3. Write the PySpark cleaning job: types, missing values, duplicates, cold-start flags, Parquet
   output.
4. Add tests and a short data-quality report, and commit daily.

---

## 13. Command reference

Run these from the repo folder, inside WSL once it's set up.

```bash
# One-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

# Download the H&M data (needs ~/.kaggle/kaggle.json)
python -m src.data.download
python -m src.data.download --force      # re-download

# Run tests
pytest

# Daily git routine
git switch main
git pull
git switch -c feature/<name>             # new piece of work
git add <files>
git commit -m "feat: describe the change"
git push -u origin feature/<name>
gh pr create --base main                  # open a pull request
```
