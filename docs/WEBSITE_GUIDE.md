# Kairos: The Website, End to End

A complete guide to the website and everything behind it: what has been done, how it looks
to a shopper, how it works for a developer, what is not good yet, and what to improve next.

| Document | Purpose |
|---|---|
| [Work Log](WORK_LOG.md) | Every step in order, with why, purpose and output |
| [Team Tasks](TEAM_TASKS.md) | Who does what |
| **Website Guide** (this file) | The finished product explained, plus an honest review |

---

## 1. Kairos in one minute

Kairos is a fashion shop with **no aisles, no categories and no search box**. It picks clothes
for **the moment you are in**: the day of the week, the month (season) and whether you shop
online or in a store. Every pick comes from our own deep learning model (a **two-tower
model**) trained on 31.8 million real H&M purchases.

It has three pages:

| Page | The idea in one line |
|---|---|
| **Moments** | Tell it the moment, and the shop rearranges itself |
| **Style story** | A customer's wardrobe as a story, and what the model thinks comes next |
| **Swipe** | Like or pass products, and watch the model learn your taste |

It runs in two modes:

| Mode | When | Where picks come from |
|---|---|---|
| **Live** | The API (`src/api/`) is running | The model is asked on every click, in about 10 ms, for any of 1,371,980 customers |
| **Saved** | The API is not running | Files exported in advance for 19 sample customers and 6 kinds of new visitors |

---

## 2. What has been done

| # | Step | Output |
|---|---|---|
| 1–3 | Downloaded the H&M dataset, wrote the PySpark cleaning job, pushed to GitHub | `src/data/` |
| 4–7 | Set up Ubuntu (WSL2), Java and Python; cleaned all 31.8M transactions | `data/processed/` (28.8M rows) |
| 8 | Built customer, product and context features; split train (12 weeks) and test (1 week) | `src/features/build_features.py` |
| 9 | Vocabularies: every ID and category turned into a number | `src/features/vocab.py` |
| 10 | Ranking metrics and 3 simple baselines to beat | `reports/baselines.md` |
| 11–12 | Two-tower model v1, trained and evaluated | `src/models/` |
| 13 | Model v2: fixed popularity bias; **beats both best-seller baselines** | `models/2026-10-05/` |
| 14 | Exported the model for serving, checked it gives the same numbers | `query_tower/`, `item_embeddings.npy` |
| 15 | Built the website, Kairos, on saved model results | `web/`, `src/serving/site_data.py` |
| 16 | Real H&M product photos for the 3,047 products shown | `scripts/download_images.py` |
| 17 | Cross-checked Siddhi's Weeks 1–2 notebook: counts match ours exactly | Work Log step 17 |
| 18 | **Live recommendation API** (FastAPI + FAISS), 8 tests | `src/api/` |
| 19 | **Website connected to the live API**, saved data as fallback | `web/src/api.js`, `LiveBar.jsx` |
| 20 | First review fixes: best blend served live, all photos, honest labels, API fallback | Work Log step 20 |

Test status: all tests pass, including 11 for the API. (The old, broken
`tests/test_recommender.py` was removed in step 20.)

---

## 3. The shopper's view (user perspective)

### Opening the site

You land on **Moments**. At the top:

- **Menu**: Moments · Style story · Swipe.
- **"Shopping as"**: whose eyes you shop through. Choices:
  - 19 **real customers** from the test week (16–22 Sep 2020), such as
    "Shopper e85178e6 · 16-24 · 132 past buys". 4 of them are "almost new" (few purchases).
  - Customers you **looked up live** (see below).
  - A **new visitor** of each age group (16-24, 25-34, 35-44, 45-54, 55+, age not given),
    with no history at all.
- **The live bar** (a strip under the menu):
  - Green dot, **"Live: model 2026-10-05 is answering for 1,371,980 customers and 29,009
    products."**
  - A box to type **any customer ID** (8 or more characters are enough), and a
    **Surprise me** button that opens a random real customer from the test week.
  - If the API is off, the bar instead says the site shows saved picks for 19 shoppers.

The site's accent colour changes to the shopper's favourite colour (taken from what they
buy most).

### Page 1: Moments

A sentence you can edit: **"It's a *Wednesday* in *September*, and I'm shopping *online*."**

- Change any word with its drop-down, click a month on the **year ring**, or try a preset
  ("Lazy Sunday, online", "Summer Saturday in town", "Back to work, September",
  "December weekend").
- The 12 picks below change. New ones are highlighted: **"12 new picks for this moment."**
- A green tag shows **"Live from the model · 10 ms"**.
- Each product card shows the photo (or a card in the product's colour), where the pick came
  from (**Model pick** or **↻ Bought before**), name, colour, type, price band (1–5 dots),
  rank, and tags for the shopper's patterns it matches, e.g. "You often buy trousers", "In
  your colour: black", "Popular with 25-34 shoppers". A note says these tags are not the
  model's own reasons.
- For real customers (live), up to 6 of their own recent buys come first, then the model's
  picks: the best blend in the evaluation. The **Their past buys first** switch turns this off
  to see the model alone.
- For real customers, the page opens at **the moment they really shopped**, with a tag like
  "This is when they really shopped: 17 Sept 2020". A chip takes you back to it.
- **"Reveal what they really bought"** shows the top 24 and stamps **"Really bought"** on
  products the customer actually bought that week, with a note saying how many of their real
  purchases are in the model's top 24 (often none: Recall@12 is about 4%). This is the honest
  test of the model, in front of the user.

**Why it is interesting:** changing the month from September to June replaces about 96% of
the picks, so the controls change the model's real output, not just the decoration.

### Page 2: Style story

For a real customer:

- **Headline**: "132 pieces since 20 Sept 2018" (sample shopper e85178e6) or "11 pieces in
  the 12 weeks before 16 Sep 2020" (a live customer), then age, club status, how often they
  shop online, and their last purchase.
- **Style DNA**: a colour bar (Black 19%, White 14%, ...) and the product types they buy
  most (Blouse 37%, Trousers 20%, ...).
- **The story so far**: a sideways-scrolling timeline, month by month, with photos of what
  they bought.
- **The next chapter**: the 12 picks the model makes for their real next visit, with the
  same "Reveal what they really bought" switch.

For a new visitor the page says there is no story yet and offers real shoppers to open.

### Page 3: Swipe

A card deck. Drag the card right (like) or left (pass), click ♥ / ✕, or use the → and ←
keys.

- **Live mode**: every like joins your shopping history, and the model re-ranks all 29,009
  products on sale. A side panel shows **"Your feed right now"** with ▲/▼ arrows for products
  that moved, a **"Taste learned"** meter ("29% of your top 24 has changed since you
  started"), and your liked items.
- **Saved mode**: a pool of 360 products; your vector is nudged in the browser.
- Live, the deck is ranked for the moment chosen on the Moments page, using the model alone.
- The page explains a surprising result honestly: **liking dresses brings cardigans and
  sweaters, not just more dresses**, because the model predicts what people buy *next*.

---

## 4. The developer's view

### 4.1 The whole system

```text
 H&M CSVs (3.5 GB)
     │  PySpark cleaning (src/data/clean.py)                 Ubuntu / WSL2
     ▼
 data/processed/  transactions, customers, articles (Parquet)
     │  features + vocabularies (src/features/)
     ▼
 user_features, item_features, train, test
     │  training (src/models/train.py, two_tower.py)          GPU, ~7 min
     ▼
 models/2026-10-05/  weights + vocab
     │  export (src/models/export.py)
     ▼
 query_tower/ (SavedModel)  +  item_embeddings.npy (29,009 x 64)
     │                                   │
     │ src/serving/site_data.py          │ src/api/ (FastAPI + FAISS)
     ▼                                   ▼
 web/public/data/*.json   ◄─ fallback ─  http://localhost:8000
     │                                   │
     └──────────────►  web/ (React + Vite)  ◄── /api proxy ──┘
                       http://localhost:5173
```

### 4.2 The model in two sentences

- The **query tower** turns a customer (ID, age group, club status, newsletter, the average
  of their last 20 purchases, days since their last purchase) plus the **moment** (day,
  month, channel) into 64 numbers.
- The **candidate tower** turns a product (ID, type, colour, garment group, department,
  index group, price band, popularity in the last 1/4/12 weeks) into 64 numbers. The score
  is the dot product; the highest scores are the picks.

Model v2 adds a **popularity correction (logQ)** in training, which more than doubled
Recall@12 (0.0168 → 0.0358).

### 4.3 How one click flows (changing the month to June, live mode)

```text
1. Moments.jsx         moment = {day: 4, month: 6, channel: 2}
2. api.js fetchPicks   POST /api/recommendations {customerId, day, month, channel, k: 24}
3. Vite proxy          /api/... → http://127.0.0.1:8000/...
4. main.py             validates the body (day 1-7, month 1-12, channel 1-2, k ≤ 100)
5. recommender.py      find the customer (binary search over 1.37M sorted IDs)
                       → their profile + last 20 purchases + days since last purchase
                       → query tower → 64-number vector
                       → FAISS inner-product search over 29,009 product vectors
                       → top 24 with names, types, colours, price bands
6. Moments.jsx         adds the new products to the catalog, highlights what changed,
                       shows "Live from the model · 10 ms"
```

### 4.4 The API (`src/api/`)

| File | Job |
|---|---|
| `recommender.py` | Loads everything once; finds customers; builds queries; runs the tower; searches FAISS; builds profiles |
| `main.py` | The FastAPI app: endpoints, input checks, error codes (400 ambiguous ID, 404 unknown, 422 bad input) |

| Endpoint | Returns |
|---|---|
| `GET /health` | Model version, number of customers, products, test-week customers, cut-off date |
| `GET /customers/random?warm=true` | A random real test-week customer's full profile |
| `GET /customers/{id}` | Profile, 12-week timeline, style DNA, real next visit and purchases (test-week customers) |
| `GET /customers/{id}/recommendations` | Picks for a day/month/channel; `exclude` skips products |
| `POST /recommendations` | Picks for a new visitor (by age), or a customer plus extra history (Swipe likes) |

Interactive docs: http://localhost:8000/docs.

| Fact | Value |
|---|---|
| Start-up | About 25 seconds |
| Memory | 2.7 GB (mostly 1.4M customer profiles and 12 weeks of purchases) |
| One request | About 10 ms (first TensorFlow call is done at start-up, it takes 2 s) |
| Runs on | CPU on purpose (GPU TF32 maths changes scores slightly) |
| Checked | Same top 24 as the saved data for a sample shopper and for a new visitor |

### 4.5 The website (`web/`)

React 18 + Vite 5, no UI library, about 1,400 lines.

| File | Job |
|---|---|
| `src/main.jsx` | Starts React, loads fonts (Fraunces, Inter) and styles |
| `src/App.jsx` | Shell: menu, routing by `#/moments` etc., shopper choice (saved in the browser), live check, loading saved data |
| `src/api.js` | Talks to the API: `checkLive`, `fetchCustomer`, `fetchRandomCustomer`, `fetchPicks`, `addProducts` |
| `src/data.js` | Loads saved JSON files; day/month/channel names; moment keys like `d4-m9-c2` |
| `src/reasons.js` | The "why this was picked" labels |
| `src/colours.js` | H&M colour names → colours for cards and the style DNA bar |
| `src/components/LiveBar.jsx` | The live strip: status, find by ID, Surprise me |
| `src/components/ShopperPicker.jsx` | "Shopping as" drop-down |
| `src/components/ProductCard.jsx` | Product card and photo / colour-card visual |
| `src/pages/Moments.jsx`, `Story.jsx`, `Swipe.jsx` | The three pages, each with a live and a saved path |
| `src/styles.css` | All styling; colours as variables; phone layout under 860 px and 520 px |
| `vite.config.js` | Dev server on 5173, forwards `/api` to the API on 8000 |

Saved data in `web/public/data/` (2.5 MB, from `python -m src.serving.site_data`):

| File | Holds |
|---|---|
| `customers.json` | 19 sample customers: profile, full purchase history, style DNA, real test-week purchases |
| `moments/<id>.json` | Their top 24 for all 168 moments (7 days × 12 months × 2 channels) |
| `guests/<age>.json` | The same for a new visitor of each age group |
| `swipe.json` | 360 products with their model vectors, and each shopper's starting vector |
| `catalog.json` | Details of the 3,052 products mentioned |
| `trending.json` | Best-sellers of the last training week, overall and by age group |

Photos: `web/public/images/`, for every product the site can show, including all 29,009
products on sale (`python -m scripts.download_images --all-on-sale`). Never committed: they
are H&M's.

### 4.6 Running it

In Ubuntu, from the repository root (start the API first, it takes ~25 s):

```bash
uvicorn src.api.main:app --port 8000
```

In `web/`:

```bash
npm run dev
```

Open http://localhost:5173. Without the API, the site runs in saved mode.

Tests, in Ubuntu with the environment activated:

```bash
python -m pytest --ignore=tests/test_recommender.py
```

---

## 5. What is not good yet (honest review)

Ordered from most to least important. Items marked **✅ Fixed** were fixed in Work Log step 20.

### The recommendations

1. **✅ Fixed (now up to 6 past buys, then the model: Recall@12 0.0527).** **The API served the model alone, not the best recommender.** Our own evaluation
   (Work Log step 13) shows *repurchase + two-tower* is best (Recall@12 0.0534), while the
   two-tower alone scores 0.0358, and plain repurchase scores 0.0518. So the live site
   currently shows a weaker list than we know how to make.
2. **✅ Fixed (cards say "Model pick" or "Bought before", and a note explains the tags).** **The "why this was picked" labels are not the model's reasons.** They are simple rules in
   the browser (same type, same colour, on a best-seller list). They are true statements,
   but the model did not use them to decide. A reviewer could call this misleading.
3. **"Popular with 25-34 shoppers" and "Best-seller last week" come from saved lists**, even
   in live mode, and only cover the top 100 per group.
4. **Swipe treats a like as a purchase** and a pass as nothing (passed items are only hidden).
   The model has no way to learn "I don't like this".
5. **✅ Fixed.** **The live Swipe always ranked for a Wednesday in September, online**, even though the
   Moments page lets you pick a moment.
6. **The world is frozen at 15 Sep 2020.** "Days since last purchase" is always counted to
   16 Sep 2020, whatever month you pick on Moments.

### The API

7. **Everything is held in memory**: 2.7 GB and 25 seconds to start, in one process. Two API
   workers would need 5.4 GB. This is what Redis was planned for.
8. **It only runs inside Ubuntu (WSL2)** with our hand-built environment. There is no Docker
   image, so a teammate cannot start it with one command.
9. **No logging or metrics.** Response time is returned to the browser but not recorded, so
   we cannot show how fast the API is under load.
10. **No caching.** The same customer and moment asked twice is computed twice (cheap now,
    but wasted).
11. **The product vectors are frozen at export time**, including their popularity numbers.
    New products cannot be recommended until the model is exported again.

### The website

12. **✅ Fixed.** **Most live picks had no photo.** Only 3,047 photos were downloaded (for the saved
    data); live picks come from 29,009 products, so many show as colour cards.
13. **You cannot click a product.** There is no product page, no "more like this", no cart.
    For a shop, that is the first thing a user tries.
14. **✅ Fixed (falls back, re-checks every 30 s).** **If the API stopped during a visit, pages showed an error** instead of falling back to the
    saved picks. The live check runs only once, when the page opens.
15. **Swiping fast sends one request per swipe**, with no waiting; older answers are ignored,
    but the requests are still made.
16. **Two different Swipe engines** (live: the model; saved: vector nudging in the browser)
    behave differently, so the same page teaches users two different things.
17. **Story pages differ between samples and live customers**: samples show their full history
    since 2018, live customers only 12 weeks.
18. **Product details are added to a shared object** (`shared.catalog`) by changing it in
    place. It works, but it is not the React way and could cause stale screens later.
19. **No front-end tests and no linter.** All website checks were done by hand in the browser.
20. **The production build has no API.** `npm run build` makes a site that always runs in
    saved mode; there is no plan yet for hosting the API with it.

### The project

21. **Duplicated code**: the product-detail and style-DNA helpers exist in both
    `src/serving/site_data.py` and `src/api/recommender.py`.
22. **✅ Fixed (removed).** **`tests/test_recommender.py` was broken** (imports a package that does not exist).
23. **✅ Fixed.** **The Work Log's top diagram was out of date** (it still shows Weeks 2–4 as not done).
24. **Work reached `main` without a pull request**, while `TEAM_TASKS.md` asks everyone to use
    pull requests. Fine for speed, but reviewers may notice.
25. **Siddhi's branch duplicates the pipeline** with a few bugs (article IDs lose their leading
    zero, duplicates dropped). It should not be merged as it is.

---

## 6. Improvements and next steps

### Do first (high impact, small effort): ✅ all done in Work Log step 20

| Improvement | Fixes | Effort |
|---|---|---|
| **Serve repurchase + two-tower in the API**: put the customer's own recent products first, then the model's picks (as in the evaluation), with a switch to compare | 1 | ½ day |
| **Download photos for all 29,009 products on sale** (`scripts/download_images.py` reading `item_ids.npy`; ~130 MB, never committed) | 12 | 1 hour |
| **Honest labels**: show the model's score as a "match" bar, and mark rule-based reasons as "also true:" | 2 | 2 hours |
| **Fall back to saved picks on any API error**, and re-check the API every 30 s | 14 | 2 hours |
| **Delete or fix `tests/test_recommender.py`**, update the Work Log diagram | 22, 23 | 30 min |
| **Use the Moments moment on the Swipe page** (share the moment between pages) | 5 | 1 hour |

### Do next (the planned Weeks 3–4 work)

| Improvement | Fixes | Effort |
|---|---|---|
| **Redis feature store**: customer profiles and histories in Redis; the API keeps only the model and FAISS | 7 | 1–2 days |
| **Docker Compose**: API + Redis + website with `docker compose up` | 8, 20 | 1 day |
| **Request logging and a `/metrics` endpoint** (count, average and slowest response times) | 9 | ½ day |
| **Load test (Siddhi, S4)** with Locust: requests per second and the slowest 5% | 9 | 1 day |
| **Airflow DAG**: weekly clean → features → train → evaluate → export → reload the API | 11 | 2 days |
| **Product page with "more like this"**: product vector → nearest products in FAISS | 13 | 1 day |

### Nice to have (makes the demo stand out)

| Improvement | Why |
|---|---|
| **"Not for me" that counts**: subtract passed products' vectors from the query (live) | Makes passes teach the model (4) |
| **Compare mode on Moments**: two moments side by side (e.g. June vs December) | Shows context-awareness at a glance |
| **Model vs baselines toggle**: the same shopper ranked by best-sellers, repurchase, model | Shows *why* the model is worth it, live |
| **Cache answers** (customer + moment → picks) for a few minutes | Faster repeated clicks (10) |
| **Front-end tests** (Vitest + React Testing Library) and ESLint | Fewer silent breaks (19) |
| **A small React data store** for the product catalog instead of changing it in place | Cleaner code (18) |
| **One shared module** for product details and style DNA | Removes duplication (21) |
| **Debounce swipes** (wait 150 ms before asking) | Fewer wasted requests (15) |
| **Deploy**: website on a static host, API on a small cloud machine | A link reviewers can open |

### Suggested order for the remaining time

```text
Week 3: ✅ repurchase blend → ✅ all photos → ✅ honest labels → ✅ API fallback
        → Redis feature store → logging/metrics → load test (Siddhi)
Week 4: Docker Compose → Airflow DAG → product page / more like this
        → compare mode → final demo guide and slides (Sunaina)
```
