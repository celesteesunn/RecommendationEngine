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
| TensorFlow sees the GPU | ✅ After installing NVIDIA's CUDA libraries (`tensorflow[and-cuda]`, about 3 GB). The setup script now does this automatically when an NVIDIA card is present. |

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

## Step 9: Vocabularies (`src/features/vocab.py`)

**What we did.** Wrote the code that gives every ID and category value its own number.

**Why.** A neural network only does maths on numbers. It cannot read "Trousers" or a
64-character customer ID, so each value gets an index: `Trousers → 7`, `Dress → 3`, and so on.

**Purpose of the rules.**

| Index | Meaning | Why |
|---|---|---|
| 0 | Padding | Customers with fewer than 20 past purchases get empty slots in their history |
| 1 | Unknown | A new customer or product the model never saw maps here instead of crashing it |
| 2, 3, … | Known values, most common first | The actual vocabulary |

These lists are saved **with every trained model**, so the API in Week 3 uses exactly the same
numbers as training did. A mismatch would silently give wrong recommendations.

**A memory fix.** The 3.36 million training rows hold about 67 million product IDs in their
histories. Loaded the normal Python way, that is over 4 GB, more than WSL has. The encoder
works directly on the Parquet data (with Arrow) and needs about 300 MB instead.

**Output.** `models/<version>/vocab/`: one text file per column, written when the model is
trained. 5 tests check the rules.

---

## Step 10: Metrics and baselines (`src/models/metrics.py`, `src/models/baselines.py`)

**What we did.** Wrote the scoring rules, built three simple recommenders, and scored them on
the test week.

**Why.** A deep learning model takes weeks to build. If a one-line rule works just as well,
the model is not worth it. These simple methods set the bar the model has to clear.

**The metrics** (each compares our list with what the customer really bought in the test week):

| Metric | Question | Example |
|---|---|---|
| Recall@12 | What share of the products they bought were in our top 12? | Bought 4, 1 was in our 12 → 0.25 |
| Recall@50, @100 | The same for the top 50 and 100 | The vector search hands 100 candidates to the next step, so the right product must be in them |
| NDCG@12 | Were the hits near the **top** of the list? | A hit at position 1 counts more than at position 12 |
| MAP@12 | The Kaggle competition's own metric | Lets us compare with public results |

**The baselines:**

| Baseline | Rule |
|---|---|
| Global popularity | Everyone gets the 100 best-sellers of the last training week |
| Age-group popularity | The best-sellers among customers in the same age band |
| Repurchase | The customer's own most-bought products from the 12 weeks, then the best-sellers |

**How long it takes.** About 1.5 minutes.

**Output.** `reports/baselines.md` and `reports/baselines.json`. Results for all 68,984 test
customers:

| Baseline | Recall@12 | Recall@100 | MAP@12 |
|---|---|---|---|
| Global popularity | 0.0255 | 0.1181 | 0.0088 |
| Age-group popularity | 0.0280 | 0.1269 | 0.0095 |
| **Repurchase** | **0.0518** | **0.1442** | **0.0227** |

**What this means.**

- Fashion is hard to predict: even the best simple rule finds only 5% of what people buy in
  its top 12. These numbers match public results for this Kaggle competition, which gives
  confidence that the pipeline is correct.
- **People rebuy what they bought before.** Repurchase is twice as good as best-sellers. It is
  the bar the two-tower model has to beat, and a known tough one.
- Age groups help a little over plain best-sellers (0.0280 vs 0.0255), which supports using the
  age-group fallback for cold customers.

---

## Step 11: The two-tower model (`src/models/two_tower.py`, `train.py`, `dataset.py`)

**What we did.** Built the deep learning model from the blueprint with TensorFlow Recommenders
and trained it on the 3.36 million training purchases.

**Why two towers.** One tower turns a **customer** (profile, last 20 purchases, the day and
channel of the visit) into a list of 64 numbers, a "customer vector". The other tower turns a
**product** (type, colour, department, price band, popularity) into a "product vector" of the
same size. The score for a customer and a product is how well their vectors line up (the dot
product). Product vectors can be calculated once in advance, so finding a customer's best
products among 100,000 takes milliseconds. This is how large shops do recommendations.

**How it learns.** Training shows the model batches of 4,096 real purchases. For each customer
in the batch, the product they really bought should score higher than the 4,095 products the
*other* customers bought ("in-batch negatives"). Every batch nudges the numbers to make that
more true.

**Guarding against overfitting.** 2% of the examples are held out. If the model gets better
on the training data but worse on the held-out data, it is memorising instead of learning, so
training stops and the best version is kept ("early stopping").

**Output.** `models/2026-10-04/` (not committed: too large, and it can be rebuilt):
weights, vocabularies, and `training.json`. Training took 10.4 minutes on the CPU.

| Epoch | Training loss | Held-out loss | |
|---|---|---|---|
| 1 | 20,218 | 9,790 | Learning (random guessing would be about 34,000) |
| 2 | 18,060 | **9,611** | Best: kept |
| 3 | 16,502 | 9,802 | Held-out loss went up: memorising, so training stopped |

**Tests.** 3 tests check the towers produce 64-number vectors, cope with an empty history, and
that training lowers the loss. A first version of that test used too high a learning rate
(0.5) and the loss exploded, which shows this model needs a small learning rate (0.05).

---

## Step 12: Evaluation, version 1 (`src/models/evaluate.py`)

**What we did.** For each of the 68,984 test customers, made a customer vector, found the 100
best-scoring products, and compared them with what the customer really bought.

**Why.** This is the moment of truth: is the model better than the simple baselines?

**Output.** `reports/evaluation_2026-10-04.md`. Took 35 seconds.

| Recommender (all customers) | Recall@12 | Recall@100 | MAP@12 |
|---|---|---|---|
| **Repurchase** (baseline) | **0.0518** | **0.1442** | **0.0227** |
| Age-group best-sellers (baseline) | 0.0280 | 0.1269 | 0.0095 |
| Global best-sellers (baseline) | 0.0255 | 0.1181 | 0.0088 |
| Two-tower v1 + best-sellers for cold customers | 0.0241 | 0.1073 | 0.0079 |
| Two-tower v1 alone | 0.0168 | 0.0727 | 0.0056 |

**Honest result: version 1 loses to all three baselines.** This is common for a first deep
learning model on this dataset, and it is exactly why we built the baselines first. The three
likely causes, and the fix for each:

| Cause | Why it hurts | Fix for version 2 |
|---|---|---|
| **Popularity bias.** Best-sellers appear in almost every batch as a "wrong answer" | The model learns to push best-sellers down, but in fashion best-sellers are exactly what people buy | Correct for how often each product appears in batches ("logQ correction", built into TFRS) |
| **Old products in the list.** The model ranks all 41,376 products sold in 12 weeks | Many of them no longer sell, and they crowd out current ones | Rank only products that sold recently |
| **No repurchase.** The model sees only an *average* of past purchases | The baselines prove people rebuy what they bought before | Blend: the customer's own repurchase items first, then the model's suggestions |

---

## Step 13: Model version 2: fixing popularity bias

**What we did.** Tested the three suspected causes from step 12, one at a time, and retrained
the model with the fix that mattered. Version 2 trained on the **GPU** (RTX 2050) in
6.6 minutes, against 10.4 on the CPU.

**Testing the causes first (on version 1, no retraining needed):**

| Suspected cause | Test | Result |
|---|---|---|
| Old products crowd the list | Rank only products sold in the last 1, 4 or 12 weeks | Almost no change (Recall@12 0.0170 / 0.0169 / 0.0168): not the problem |
| No repurchase | Put the customer's own products first, then the model's | Worse than repurchase + best-sellers (0.0419 vs 0.0518): the model's suggestions were worse than plain best-sellers |
| Popularity bias | The previous result points here; fixing it needs retraining | See below |

**The fix: logQ correction.** In training, every other product in the batch counts as a
"wrong answer". Best-sellers appear in almost every batch, so the model was punished for
liking them, and learned to push them down. In fashion, best-sellers are exactly what people
buy. The correction tells the model how often each product is sampled and subtracts that
from its score during training, so popular products are no longer unfairly punished.

**Output.** `models/2026-10-05/` and `reports/evaluation_2026-10-05.md`:

| Recommender (all 68,984 customers) | Recall@12 | Recall@100 | MAP@12 |
|---|---|---|---|
| Two-tower v1 | 0.0168 | 0.0727 | 0.0056 |
| **Two-tower v2** | **0.0358** | **0.1361** | **0.0130** |
| Global best-sellers (baseline) | 0.0255 | 0.1181 | 0.0088 |
| Age-group best-sellers (baseline) | 0.0280 | 0.1269 | 0.0095 |
| Repurchase (baseline) | 0.0518 | 0.1442 | 0.0227 |
| **Repurchase + two-tower v2** | **0.0534** | **0.1507** | **0.0235** |

**What this means.**

- One fix **more than doubled** the model's score (Recall@12 0.0168 → 0.0358).
- The model on its own now **beats both popularity baselines** on every metric. This is the
  Week 2 "done when" condition in the blueprint.
- **Repurchase + two-tower is the best recommender so far**, ahead of repurchase on every
  metric. People's own past products come first; the model fills the rest of the list better
  than best-sellers do. The gain is small at the top (0.0534 vs 0.0518) and larger deeper in
  the list (Recall@100 0.1507 vs 0.1442), which is what matters for the 100 candidates.
- **A finding that changes the plan:** for cold customers, the model (Recall@12 0.0345) beats
  the age-group best-seller fallback (0.0287). The model still uses their age, club status and
  any purchases they do have. So the fallback should be kept only for **brand-new** customers
  with no record at all, not for every customer with fewer than 5 purchases.

**Still to improve (optional tuning).** The held-out loss rose again in epoch 3, so the model
starts memorising after two passes. The likely reason is the 505,310 customer-ID embeddings:
one learned vector per customer is easy to memorise. Trying the model without the customer ID
(relying on profile and history) is the next experiment.

---

## Step 14: Export the model for serving (`src/models/export.py`)

**What we did.** Saved the two towers of model version 2 as standalone TensorFlow models,
calculated the vector of every product in advance, and checked the exported towers give the
same numbers as the trained model.

**Why.** Until now the model only worked inside our training code, which first turns every
value into a number with our own encoders. The web API (Week 4) has to call the model with
plain values, such as a customer ID and "Wednesday", and get a vector back, without
depending on the training code.

**Purpose of each output.**

| Output | Size | Purpose |
|---|---|---|
| `query_tower/` (SavedModel) | 104 MB | Runs on every API request: customer + visit → customer vector. The vocabulary lookups are inside it, so it accepts plain text and numbers |
| `candidate_tower/` (SavedModel) | 6 MB | Makes the vector for a product, for example a new product added to the shop |
| `item_embeddings.npy` | 7 MB | The vectors of the 29,009 products sold in the last 4 weeks, computed once. Product vectors don't change between requests, so there is no need to recompute them |
| `item_ids.npy` | 1 MB | Which product each row of `item_embeddings.npy` is |
| `export.json` | small | Sizes and the result of the check |

The query tower is the largest because it holds a vector for each of the 505,310 customers
seen in training.

**The check, and a GPU surprise.** After saving, the export reloads both towers, gives them
plain values for 512 real customers and 512 real products, and compares the vectors with the
trained model. The first run **failed**: the query tower matched exactly, but product vectors
differed by 0.0013.

The cause was the graphics card, not the code. Newer NVIDIA cards, including the RTX 2050,
multiply in a faster, slightly less precise format called **TF32**, and TensorFlow switches it
on by default. With TF32 the result depends a little on the batch size. The product vectors
were computed in batches of 8,192 and checked in batches of 512, so they rounded differently.
With TF32 switched off for the export, the largest difference is 0.00000095: normal float32
rounding. The check now passes, and the stored vectors are full precision.

**How long it takes.** About 70 seconds.

**Tests.** 2 new tests check that a tiny exported model gives exactly the trained model's
vectors from plain values, including for an unknown customer, an unknown product and an
empty history.

---

## Step 15: The website, Kairos (`web/`, `src/serving/site_data.py`)

**What we did.** Built the project's shop front: a website called **Kairos** (Greek for "the
right moment") with three pages, all showing real recommendations from model version 2.

**Why.** Project reviews look at the commits and the working project. A website makes the
model visible: anyone can open it and see what it recommends and why.

**Why it is different from Blinkit, Instacart or Myntra.** Those shops are built around
aisles, categories and a search box. Kairos has none of them. It is built around what makes
our model special, **context**:

| Page | The idea | What the shopper sees |
|---|---|---|
| **Moments** | Shop by the moment, not by aisle | A sentence to complete: "It's a *Wednesday* in *September*, and I'm shopping *online*." Changing a word reshapes the feed, new picks are highlighted, and every product says why it was picked ("You often buy dresses", "Popular with 25-34 shoppers") |
| **Style story** | Your wardrobe as a story | Style DNA (your colours and product types), a month-by-month timeline of purchases, and "the next chapter": what the model expected for your real next visit |
| **Swipe** | Teach it your taste, live | Like or pass products; the feed re-ranks after every swipe, with arrows showing what moved up or down and a "taste learned" meter |

**Honesty built in.** The sample shoppers are 19 real customers from the test week. A
"Reveal what they really bought" switch marks the products they really bought that week, so
anyone can check the model's predictions. For one shopper, 1 of their 13 real purchases is in
the model's top 24 for the moment they really shopped; in June, none are.

**How the parts fit.**

| Part | Purpose |
|---|---|
| `src/serving/site_data.py` | Runs the trained model for the 19 shoppers and for new visitors of each age group, for all 168 moments (7 days × 12 months × online / in store), and saves the results as small data files in `web/public/data/` (2.5 MB) |
| `web/` (React + Vite) | The website itself. It reads those data files, so it works without a backend for now |
| Swipe learning | Each product in the swipe pool carries its real 64-number vector from the model. A like moves the shopper's vector towards the product, a pass away from it, and the browser re-ranks all 360 products by the dot product, the same score the model uses |
| `scripts/download_images.py` | Optional: downloads and shrinks H&M's photos for only the 3,052 products the site shows (needs a Kaggle token). Without photos, each product is a designed card in its real colour. Photos are never committed |

**Checking the model really reacts to the moment.** Before building the Moments page, we
tested 200 test customers. Changing only the month from September to June keeps just **4%**
of the top 24 picks; online versus in store keeps about half; the day of the week keeps 92%.
So the controls on the page change the model's real output, not just the decoration.

**Output.** The website runs with `npm run dev` in `web/` and opens at
http://localhost:5173. Checked in the browser: all three pages, the moment controls, the
reveal switch, swiping with the keyboard, and a phone-sized screen. The production build is
53 KB of compressed code.

---

## What comes next

| Next step | Why | Output |
|---|---|---|
| Product photos | Real H&M photos on the cards | `web/public/images/` (needs a Kaggle token) |
| FastAPI backend | Live recommendations for any customer, not just the 19 samples | `src/api/` |
| Connect the website to the API | Swap the data files for live calls | The same pages, live |
