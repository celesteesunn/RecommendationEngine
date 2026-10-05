# Team Tasks

Who does what across the 4 weeks. Each task says what to do, how to do it, and what "done"
looks like. No deep machine learning knowledge is needed for the supporting tasks.

For the full project plan, see the [Project Blueprint](PROJECT_BLUEPRINT.md).

## Roles

| Person | Role | Focus |
|---|---|---|
| **Tejashvi Khandelwal** | Technical lead | Core pipeline (PySpark, model, Redis, API, Airflow); reviews and merges all pull requests |
| **Siddhi Kale** | Data analysis and testing | Data exploration, baseline, load testing |
| **Samala Sunaina** | Documentation and data quality | Data dictionary, data-quality report, diagrams, final presentation |

---

## Rules for everyone

1. **Work on your own branch**, never directly on `main`:
   `Tejashvi`, `Siddhi`, `Sunaina`.
2. **Commit and push every working day.** The brief says commit history is used for
   evaluation. One or two real commits a day is the goal.
3. **Write clear commit messages** that start with a type:
   `docs: add data dictionary for customers table`,
   `feat: add EDA charts for sales over time`,
   `fix: remove broken recommender test`.
4. **Never commit data files or secrets.** No CSVs, no Parquet, no `kaggle.json`, no `.env`.
   `.gitignore` blocks most of these, but check `git status` before committing.
5. **When a task is done, open a pull request into `main`.** Tejashvi reviews it and merges it.
6. **Ask early if stuck.** A question in the group chat is better than a day lost.

### Git steps (copy and paste)

First time only:

```bash
git clone https://github.com/celesteesunn/RecommendationEngine.git
cd RecommendationEngine
git switch -c <your-name>
```

Every day:

```bash
git switch <your-name>
git pull origin main              # get the latest team work
# ... do your work ...
git status                        # check what changed (no data files!)
git add <the files you changed>
git commit -m "docs: describe what you did"
git push origin <your-name>
```

When a task is finished, go to the repo on GitHub, click **"Compare & pull request"**, choose
`base: main`, describe the change, and click **Create pull request**.

### Working with the data without downloading it

The easiest way to explore the data is a **Kaggle Notebook**. It runs in the browser, and the
data is already attached:

1. Log in to Kaggle and accept the
   [competition rules](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/rules).
2. Open the [competition's Code tab](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/code)
   and click **New Notebook**.
3. The files are at `/kaggle/input/h-and-m-personalized-fashion-recommendations/`.
4. When finished: **File → Download notebook** (`.ipynb`), put it in `notebooks/` in the repo,
   then commit and push it.

`transactions_train.csv` is 3.5 GB. In a notebook, read it with
`usecols=[...]` and `dtype={"article_id": str}`, or work on recent weeks only, to stay within
memory.

---

## Siddhi Kale

### S1. Fix the notebook and test on `main` (Week 1, start here)

The commit "Add recommendation notebook and tests" broke the test suite:
`tests/test_recommender.py` imports a package called `recommendation_engine`, which doesn't
exist in this repo, so `pytest` fails.

- [ ] Delete `tests/test_recommender.py` (or rewrite it to test real code in `src/`).
- [ ] Move `nb.ipynb` to `notebooks/` with a clear name, for example `notebooks/00_setup_check.ipynb`.
- [ ] Run `pytest` and check that it passes.
- [ ] Commit: `fix: remove broken recommender test and move notebook to notebooks/`

**Done when:** `pytest` passes on `main` after your pull request is merged.

### S2. Exploratory data analysis notebook (Week 1)

Build `notebooks/01_eda.ipynb` in a Kaggle Notebook. Answer each question with a chart or a
table, plus one or two sentences explaining what you see:

- [ ] How many customers, products and purchases are there? Over what dates?
- [ ] Purchases per week over the 2 years. Are there seasonal peaks?
- [ ] Customer age distribution. How many ages are missing?
- [ ] How many purchases does a typical customer make? (Histogram; many will have 1–2.)
- [ ] Top 20 best-selling products, with their names and product types.
- [ ] Top product types, colours and garment groups.
- [ ] Online vs in-store purchases (`sales_channel_id`: 1 = store, 2 = online).
- [ ] Price distribution.
- [ ] A short "Key findings" section at the end: five bullet points.

**Done when:** the notebook runs top to bottom, includes the outputs, and is merged into `main`.

### S3. Popularity baseline (Week 2)

The neural model must beat a simple baseline. This is the baseline.

- [ ] In a notebook, take the **last week** of transactions as the "test week".
- [ ] Find the 12 best-selling products in the **week before** it.
- [ ] Recommend those same 12 products to every customer who bought something in the test week.
- [ ] Calculate **Recall@12**: for each customer, the number of their test-week purchases that
      are in the 12, divided by the number of distinct products they bought. Average over all
      customers.
- [ ] Write the final number in a markdown cell.

Tejashvi will turn this into `src/models/baselines.py`.

**Done when:** the notebook shows one Recall@12 number and how it was calculated.

### S4. Load test (Week 4)

Once the API is running, write a Locust script that simulates many shoppers.

- [ ] Write `tests/load/locustfile.py`. Tejashvi will give you a starting template.
- [ ] Run it with 10, 50 and 100 simultaneous users.
- [ ] Record the median and 95th-percentile response times and requests per second in
      `reports/load_test.md`, with a screenshot of the Locust charts.

**Done when:** the report is merged into `main`.

---

## Samala Sunaina

### N1. Data dictionary (Week 1)

Write `docs/DATA_DICTIONARY.md`: one table per file (`transactions_train.csv`,
`customers.csv`, `articles.csv`), with these columns:

| Column | Type | Meaning | Example | Missing values? | Used in model? |
|---|---|---|---|---|---|

- [ ] Fill it in from the
      [Kaggle data page](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data)
      and a quick look in a Kaggle Notebook (`df.head()`, `df.info()`, `df.isna().sum()`).
- [ ] For "Used in model?", use the feature list in the
      [Blueprint, section 5](PROJECT_BLUEPRINT.md#5-offline-pipeline-in-detail).

**Done when:** every column of all 3 files is described and the file is merged into `main`.

### N2. Data-quality report (Week 1)

Write `reports/data_quality.md` from a Kaggle Notebook (save the notebook as
`notebooks/02_data_quality.ipynb`):

- [ ] Row count of each file.
- [ ] Missing values per column (count and %).
- [ ] Number of duplicate rows in transactions.
- [ ] Do all `customer_id`s in transactions exist in customers? All `article_id`s in articles?
- [ ] Odd values: for example, different spellings in `fashion_news_frequency`
      (`NONE`, `None`), ages below 16 or above 90, prices of 0.
- [ ] A "Recommendations for cleaning" section: one bullet per problem found.

Tejashvi's PySpark cleaning job will use this report.

**Done when:** the report and notebook are merged into `main`.

### N3. Architecture diagrams (Week 3–4)

- [ ] Using [draw.io](https://app.diagrams.net) (free), redraw these diagrams from the
      [Blueprint](PROJECT_BLUEPRINT.md) as clean images:
  - [ ] System architecture (section 4.1)
  - [ ] Two-tower model (section 6.1)
  - [ ] Request flow (section 7.1)
  - [ ] Airflow DAGs (section 8)
- [ ] Save each as `.png`, plus the `.drawio` source, in `docs/architecture/`.

**Done when:** all 4 diagrams are merged into `main`.

### N4. Demo guide and final presentation (Week 4)

- [ ] `docs/DEMO.md`: step-by-step instructions to start the system and show recommendations
      through the `/docs` page, with screenshots.
- [ ] Final presentation slides: the problem, the dataset, the architecture (use the N3
      diagrams), the results (model vs baseline), the load-test numbers and a demo.
- [ ] Final README polish with Tejashvi.

**Done when:** the demo guide is merged and the slides are ready.

---

## Tejashvi Khandelwal (technical lead)

| Week | Task | Status |
|---|---|---|
| 1 | Repo setup, dependencies, config, download script | ✅ |
| 1 | WSL2 environment, data download | ⏳ |
| 1 | PySpark cleaning job + cold-start flags (uses N2) | ⬜ |
| 2 | Feature engineering, vocabularies | ⬜ |
| 2 | Two-tower model, training, evaluation (must beat S3) | ⬜ |
| 3 | Export, Redis feature store, FAISS index | ⬜ |
| 4 | FastAPI service, Airflow DAGs | ⬜ |
| All | Review and merge teammates' pull requests; give Siddhi the Locust template | ongoing |

---

## Summary by week

| Week | Tejashvi | Siddhi | Sunaina |
|---|---|---|---|
| 1 | Environment, data download, PySpark cleaning | S1 fix test, S2 EDA notebook | N1 data dictionary, N2 data-quality report |
| 2 | Features, two-tower model, training, evaluation | S3 popularity baseline | (buffer: help with S2/S3 review, README) |
| 3 | Export, Redis, FAISS | (buffer: learn FastAPI basics for S4) | N3 architecture diagrams |
| 4 | FastAPI, Airflow | S4 load test | N3 finish, N4 demo guide and presentation |
