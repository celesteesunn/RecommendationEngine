# Work Log: What We Did, Why, and What It Produced

A step-by-step record of the work, in plain language. For every step it answers four
questions: **What** did we do, **Why** was it needed, **What is the purpose**, and
**What is the output**. Use it to understand the project and to explain it to the team.

| Document | Purpose |
|---|---|
| [Project Blueprint](PROJECT_BLUEPRINT.md) | The target: what the finished system does, and the 4-week plan |
| [Project Guide](PROJECT_GUIDE.md) | The current state: files, branches, decisions, glossary |
| **Work Log** (this file) | The story so far: each step explained, newest at the bottom |

---

## The big picture in one paragraph

We are building a recommendation engine for an online fashion store (H&M). It looks at what
each customer bought before, plus context such as the day of the week, and picks the 12
products they are most likely to buy next. To get there, the data has to pass through a
pipeline: **raw data → cleaning → features → model training → fast serving through an API**.
Week 1 is about the first two boxes: getting the data and cleaning it.

```text
 [1] Get data  ──►  [2] Clean  ──►  [3] Features  ──►  [4] Train model  ──►  [5] Serve via API
   Week 1            Week 1           Week 2              Week 2               Weeks 3–4
   ✅ done           ✅ done          ✅                  ⬜                    ⬜
```

---

## Step 1: Get the dataset

**What we did.** Downloaded the H&M dataset from Kaggle by hand (as zip files in `Dataset/`),
checked it, and extracted the three files we need into `data/raw/`.

**Why.** A recommendation model learns from past purchases. Without real data there is nothing
to learn from. The download script (`src/data/download.py`) needs a Kaggle API token; a manual
download gives the same files without one.

**Purpose of the checks.** A download can be cut off halfway and still look fine. We opened
every zip and counted the rows to be sure nothing was missing.

**Output.**

| File | Rows | What one row means |
|---|---|---|
| `data/raw/articles.csv` | 105,542 | One product (name, type, colour, department, description) |
| `data/raw/customers.csv` | 1,371,980 | One customer (age, club membership, newsletter setting) |
| `data/raw/transactions_train.csv` | 31,788,324 | One purchase (date, customer, product, price, online or in store) |

The counts match the official Kaggle numbers exactly. `sample_submission.csv` was not needed:
it is only the answer template for the Kaggle competition.

**Safety.** These files are large (3.7 GB) and must never go to GitHub. `.gitignore` excludes
`data/raw/`, `*.zip` and the `Dataset/` folder, so git cannot pick them up by accident.

---

## Step 2: Write the cleaning job (`src/data/clean.py`)

**What we did.** Wrote a PySpark program that reads the three raw files, fixes problems in them,
and saves clean copies. Also wrote tests for it (`tests/test_clean.py`).

**Why.** Raw data is messy. We profiled it and found real problems:

| Problem found | Count | What the cleaning job does |
|---|---|---|
| Customers with no age | 15,861 | Fill with the median age of their club-status group, and add an `age_missing` flag so the model knows it was filled in |
| Missing newsletter flags (`FN`, `Active`) | ~900,000 | Empty means "no", so fill with 0 |
| Same label written two ways (`NONE` and `None`) | many | Merge into one label |
| Missing club status or newsletter frequency | 6,062 / 16,011 | Label as `UNKNOWN` |
| Products with no description | 416 | Use an empty description |
| Product IDs losing their leading zero (`0108775015` → `108775015`) | risk in every file | Always store the ID as a 10-character text |
| Exact duplicate purchase rows | ~9% of rows | These are the same item bought twice on the same day, so merge them into one row with a `quantity` column instead of deleting them |
| Purchases of unknown customers or products | checked | Removed, so every purchase links to a real customer and product |

**Why PySpark and not pandas.** The purchase file has 31.8 million rows (3.5 GB). pandas loads
everything into memory at once and would crash a 16 GB laptop. Spark works through the data in
chunks and spreads the work over all CPU cores. The project brief also asks for distributed
data processing.

**Cold-start flags.** The job also marks **new customers** (fewer than 5 purchases in the
12 weeks used for training) and **new products** (no purchases in that window). The model
cannot personalise for someone it knows almost nothing about, so these customers will be shown
trending products instead. The flag decides which strategy is used.

**Week numbers.** Every purchase gets a `week` number (0 = first week, the last week = the
final 7 days). The last week is held back as the **test week**: we train on the 12 weeks before
it and check whether the model predicts what people actually bought in it.

**Purpose of the tests.** The tests run the cleaning rules on a few hand-made rows where we
know the right answer (for example: two identical rows must become one row with
`quantity = 2`). If someone later breaks a rule, a test fails straight away. All 10 tests pass.

**Output (once run on the full data).** Clean Parquet files in `data/processed/`:

| Folder / file | Contents |
|---|---|
| `transactions/` | Clean purchases, split into one folder per week |
| `customers/` | Clean customers with `age_missing`, `train_purchases`, `is_cold_start` |
| `articles/` | Clean products with `train_purchases`, `is_cold_start` |
| `cleaning_summary.json` | Row counts before and after, how many values were filled, cold-start counts |

**Why Parquet instead of CSV.** Parquet is compressed (much smaller), stores the data types
(dates stay dates, IDs stay text), and lets later steps read only the columns they need. Reading
it is many times faster than reading CSV.

---

## Step 3: Commit and push to GitHub

**What we did.** Saved the cleaning job as a commit on the `Tejashvi` branch and pushed it.

**Why.** A **commit** is a saved snapshot of the project on your laptop. A **push** sends your
commits to GitHub, so teammates can see them and they are backed up. Until you push, the work
exists only on your laptop. Daily commits are also how Zaalima tracks progress.

**How to check what is not pushed yet.**

```bash
git status -sb
```

| First line says | Meaning |
|---|---|
| `## Tejashvi...origin/Tejashvi` | Everything is pushed |
| `[ahead 2]` | 2 commits are only on your laptop: push them |
| `[behind 1]` | GitHub has a commit you don't have: pull first |

---

## Step 4: Install WSL2 and Ubuntu

**What we did.** Installed WSL2 (Windows Subsystem for Linux), which runs a real Ubuntu Linux
inside Windows.

**Why.** The project's tools are built for Linux:

| Tool | Used for | Problem on plain Windows |
|---|---|---|
| PySpark | Data cleaning and features (Week 1–2) | Cannot save Parquet without extra Hadoop programs. We saw this error: `HADOOP_HOME and hadoop.home.dir are unset` |
| TensorFlow | Training the model (Week 2) | No GPU support on Windows after version 2.10, so training would be much slower |
| Airflow | Automatic weekly retraining (Week 4) | Does not run on Windows |
| Redis | Fast storage for live recommendations (Week 3) | No official Windows version |

**Output.** Ubuntu 26.04 with user `tejashvikh`. It can see the project folder at
`/mnt/c/Users/TEJASHVI/Desktop/ZALIMA ML/RecommendationEngine`, so nothing had to be copied.
Resources: 16 CPU cores, about 7 GB of memory, and the NVIDIA RTX 2050 graphics card (4 GB).

---

## Step 5: Install Java 17

**What we did.** Ran `sudo apt install openjdk-17-jdk-headless python3-venv` in Ubuntu.

**Why.** Spark is written in Scala, which runs on Java. PySpark is only a Python remote control
for a Java program, so without Java, Spark cannot start. Version 17 is the newest Java that
Spark 3.5 officially supports. `python3-venv` lets Python create separate environments.

**Output.** Java 17 installed at `/usr/lib/jvm/java-17-openjdk-amd64`.

---

## Step 6: Set up the Python environment (`scripts/setup_wsl.sh`)

**What we did.** Wrote a setup script and ran it. It installs Python 3.11 and every library the
project needs into a separate environment at `~/venvs/reco`.

**Why a separate environment.** Every project needs specific versions of its libraries (for
example, TensorFlow 2.18 exactly). Installing them into their own folder keeps them from
clashing with other projects or with Ubuntu's own Python.

**Why Python 3.11.** Ubuntu 26.04 comes with Python 3.14, which is too new: TensorFlow 2.18 and
PySpark 3.5 support Python up to 3.12. 3.11 is also what the project uses on Windows.

**Why the environment is outside the project folder.** The project sits on the Windows drive.
Linux reads files on the Windows drive slowly, and TensorFlow alone is about 2 GB of files, so
every `import` would be slow. The Linux home folder is fast.

**Why a script.** So anyone in the team can create exactly the same setup with one command
instead of following a list of manual steps:

```bash
bash scripts/setup_wsl.sh
source ~/venvs/reco/bin/activate
```

**How long it takes.** Mainly download time: about 1.8 GB of libraries. It took several
minutes here; on a slow connection it can take up to an hour. Running it again is safe and
quick, because finished downloads are cached.

**What gets installed, and why:**

| Library | Used in | Purpose |
|---|---|---|
| `pyspark` | Weeks 1–2 | Clean data and build features over 31.8M rows |
| `pandas`, `numpy`, `pyarrow` | All weeks | Work with smaller tables; read and write Parquet |
| `tensorflow`, `tf-keras`, `tensorflow-recommenders` | Week 2 | Build and train the two-tower recommendation model |
| `scikit-learn` | Week 2 | Helper tools for evaluation |
| `faiss-cpu` | Week 3 | Find the most similar products among 105K in milliseconds |
| `redis` | Week 3 | Talk to the Redis feature store |
| `fastapi`, `uvicorn`, `pydantic` | Week 4 | The web API that returns recommendations |
| `pytest` | All weeks | Run the tests |
| `locust` | Week 4 | Load testing: simulate many users at once |
| `kaggle`, `pyyaml` | Setup | Download data; read `configs/config.yaml` |

**Output.** A ready environment at `~/venvs/reco`, plus a `.env` settings file in the project.

**Result of the checks.**

| Check | Result |
|---|---|
| Python, TensorFlow 2.18.1, TF Recommenders 0.7.7 | ✅ Import and run |
| Tests (`pytest`) | ✅ 10 passed, including the Spark cleaning tests that could not save files on Windows |
| `tests/test_recommender.py` | ❌ Imports a module (`recommendation_engine`) that does not exist in the repository. It came from an earlier teammate commit; fixing it is task S1 in the team tasks. Run the other tests with `pytest --ignore=tests/test_recommender.py` until then. |
| TensorFlow sees the GPU | ⏳ Not yet: TensorFlow needs NVIDIA's CUDA libraries, a separate ~3 GB download. Needed for Week 2 training. |

---

## Step 7: Run the cleaning job on the full data

**What we did.** Ran `python -m src.data.clean` inside Ubuntu on all 31.8 million purchases.

**Why.** Step 2 only wrote and tested the cleaning rules on small examples. Week 2 (features
and the model) needs the real cleaned dataset.

**Three problems on the way, and how each was fixed.** None of them were mistakes in the
cleaning rules; all three came from how the laptop and Ubuntu are set up. They are worth knowing
because anyone running Spark on WSL2 can hit them.

| # | What happened | Cause | Fix |
|---|---|---|---|
| 1 | Linux killed Spark after 3 minutes (`Out of memory: Killed process ... (java)`) | WSL2 gets only half of the laptop's 16 GB (about 7.5 GB). Spark was allowed 5 GB and also kept four big tables in memory at once | Spark now writes the cleaned purchases to disk straight away and reads them back for the later steps, instead of holding them in memory |
| 2 | `No space left on device` | Ubuntu 26.04 keeps the `/tmp` folder **in memory** (3.9 GB). Spark puts its temporary working files in `/tmp`, so they used up the same memory Spark needed | Spark's temporary files now go to `~/.cache/spark-tmp` on the real disk (setting `spark.local_dir` in `configs/config.yaml`) |
| 3 | `chmod: Operation not permitted` when saving Parquet | Ubuntu connected the Windows `C:` drive as owned by the admin user (`root`), so Spark could not set file permissions in the project folder | A one-time setting in `/etc/wsl.conf` (`metadata,uid=1000,gid=1000`) plus `wsl --shutdown`. The setup script now checks for this and prints the fix |

**How long it takes.** About 5 minutes (296 seconds) on the laptop, using all 16 CPU cores.

**Output.** 875 MB of Parquet in `data/processed/` (the 3.7 GB of CSVs shrank to under a quarter):

| Folder | Size | Contents |
|---|---|---|
| `transactions/` | 698 MB | 28,813,419 purchases in 105 week folders (`week=0` … `week=104`) |
| `customers/` | 166 MB | 1,371,980 customers |
| `articles/` | 11 MB | 105,542 products |

**The numbers from `cleaning_summary.json`, and what they mean:**

| Number | Value | Meaning |
|---|---|---|
| Raw purchase rows | 31,788,324 | Same as Kaggle |
| Duplicate rows merged | 2,974,905 | Same item, same customer, same day: now one row with `quantity` 2, 3, … |
| Rows dropped | 0 | Every purchase links to a real customer and product |
| Rows written | 28,813,419 | 28,813,419 + 2,974,905 = 31,788,324, so nothing was lost |
| Weeks | 105 | 20 Sep 2018 to 22 Sep 2020 |
| Training window | weeks 92–103 | The 12 weeks the model will learn from |
| Test week | week 104 (16–22 Sep 2020) | 217,916 purchases by 68,984 customers, held back to check the model |
| Ages filled in | 15,861 | Flagged with `age_missing = 1` |

**Cold start: the most important finding.**

| Customers by purchases in the 12 training weeks | Count | Share |
|---|---|---|
| None at all | 866,670 | 63% |
| 1 to 4 | 250,866 | 18% |
| 5 or more (warm: enough history to personalise) | 254,444 | 19% |

So **81% of customers are cold-start**, and 64,166 of the 105,542 products (61%) were not
bought at all in the training window (mostly older products no longer on sale). This is why the
project needs a good fallback: trending products by age group for cold customers, and the model
only ranks products that are actually selling. It is also why the evaluation reports warm and
cold customers separately.

**Checks on the written files.** No missing values left in customers; `None` and `NONE` merged
into one label; every product ID is 10 characters; all tests still pass.

---

## Step 8: Build the features (`src/features/build_features.py`)

**What we did.** Wrote and ran a second PySpark job that turns the clean purchases into the
inputs the model learns from, and splits the data into training and test sets.

**Why.** A model cannot learn from a raw list of purchases. It needs *facts* about the
customer, the product and the moment of the purchase, called **features**. For example: this
customer is 25–34, usually shops online, last bought 7 days ago, and it is a Wednesday in
September; this product is a dark blue pair of trousers that sold 800 times last week.

**Purpose of each feature group (from the blueprint):**

| Group | Features | Why the model needs it |
|---|---|---|
| Customer | Age group, club status, newsletter setting | People of different ages and habits buy different things |
| Customer | Last 20 products bought | The strongest signal: what you bought says what you like |
| Customer | Purchases and average price (12 weeks), online share | How active and how price-sensitive the customer is |
| Product | Type, colour, garment group, department, index group, price band | Lets the model link similar products, even new ones |
| Product | Sales in the last 1, 4 and 12 weeks | **Popularity over time**: what is trending right now |
| Context | Day of week, month, online or in store, days since last purchase | **Time of purchase**: the same person shops differently on a Saturday in summer |

**The most important rule: no peeking into the future.** If the model could see test-week
purchases while training, it would look brilliant in testing and fail in real life. So:

- All features are calculated **as of week 103**, the last training week. The test week (104)
  is invisible to them.
- For each training example, the history contains only purchases from **earlier days**, never
  from the same day, otherwise the answer would be in the question.

Tests check both rules on a tiny made-up shop where every right answer is known in advance.

**How long it takes.** About 4.5 minutes (267 seconds).

**Output.** Four new tables in `data/processed/`, plus `features_summary.json`:

| Table | Rows | One row is | Used for |
|---|---|---|---|
| `train/` | 3,359,320 | One purchase in weeks 92–103, with its context and the customer's history before that day | Training examples for the model |
| `user_features/` | 1,371,980 | One customer, as of week 103 | The customer side of the model; later loaded into Redis for serving |
| `item_features/` | 105,542 | One product, as of week 103 | The product side of the model |
| `test/` | 68,984 | One customer who bought in the test week, and what they bought (3.1 products on average) | Checking the model's predictions |

**What the numbers say.**

- 505,310 customers and 41,376 products appear in the training examples. Only those 41,376
  products sold in the 12 weeks, so they are the ones the model will rank.
- 215,691 training purchases (6%) have no history at all: the customer's first-ever purchase.
- Of the 68,984 test customers, **33,168 are warm** (5 or more purchases in the training
  window) and **35,816 are cold**. Cold customers are more than half of the people we have to
  recommend for, which confirms the cold-start fallback matters.

---

## What comes next

| Next step | Why | Output |
|---|---|---|
| Vocabularies (`src/features/vocab.py`) | The model works with numbers, so every ID and category needs one | Lookup lists saved with the model |
| Baselines and metrics (`src/models/baselines.py`) | Simple methods the model has to beat | `reports/baselines.md` |
| Two-tower model and training | The deep learning model itself | A trained model in `models/` |
| Evaluation | Prove whether the model beats the baselines | `reports/evaluation_<version>.md` |
