# Kairos: the website

A fashion shop with no aisles and no search box. It picks clothes for **the moment you're
in** (the day, the season, online or in store), using real recommendations from our
two-tower model.

| Page | What it does |
|---|---|
| **Moments** | Finish the sentence "It's a *Wednesday* in *September*, and I'm shopping *online*". The feed rearranges itself for that moment, every product says why it was picked, and "Reveal what they really bought" shows whether the model found the sample shopper's real purchases |
| **Style story** | A shopper's style DNA (their colours and product types), their purchase timeline month by month, and "the next chapter": what the model expected for their real next visit |
| **Swipe** | Like or pass products. With the live API, every like joins your shopping history and the model re-ranks all 29,009 products on sale; without it, your customer vector is nudged in the browser |

## Run it

Needs Node.js 18 or newer. From this folder:

```bash
npm install
npm run dev
```

Then open http://localhost:5173.

For **live** recommendations, also start the API, in Ubuntu from the repository root (it
takes about 30 seconds to load):

```bash
uvicorn src.api.main:app --port 8000
```

The dev server forwards `/api` to it (see `vite.config.js`). A green **Live** bar appears
under the menu, and you can shop as any of the 1,371,980 customers by ID, or press
**Surprise me** for a random real customer from the test week.

## Where the data comes from

| API running? | Where picks come from |
|---|---|
| Yes (**Live**) | Every change of moment, shopper or swipe asks the model through the API (`src/api/`). About 10 ms per answer |
| No | Static files in `public/data/`, made from the same model by `python -m src.serving.site_data`: 19 real customers from the test week (16–22 Sep 2020), their top products for every moment, a swipe pool with model vectors, and product details |

So the site always works. Both come from the same model: for a sample shopper at the moment
they really shopped, and for a new visitor, the API's top 24 is the same as the saved top 24.

## Product photos (optional)

Without photos, every product shows as a designed card in its real colour. To add H&M's real
product photos for the 3,052 products the site shows, put a Kaggle API token in
`~/.kaggle/kaggle.json` and run, in Ubuntu from the repository root:

```bash
python -m scripts.download_images
```

It downloads a public Kaggle dataset of H&M's photos resized to 224 × 224 (about 285 MB),
keeps only the photos the site needs (about 13 MB) and deletes the rest. The photos land in
`public/images/` and are never committed: they belong to H&M.
