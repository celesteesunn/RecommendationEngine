# Kairos: the website

A fashion shop with no aisles and no search box. It picks clothes for **the moment you're
in** (the day, the season, online or in store), using real recommendations from our
two-tower model.

| Page | What it does |
|---|---|
| **Moments** | Finish the sentence "It's a *Wednesday* in *September*, and I'm shopping *online*". The feed rearranges itself for that moment, every product says why it was picked, and "Reveal what they really bought" shows whether the model found the sample shopper's real purchases |
| **Style story** | A shopper's style DNA (their colours and product types), their purchase timeline month by month, and "the next chapter": what the model expected for their real next visit |
| **Swipe** | Like or pass products. Each swipe moves your customer vector towards or away from that product's vector, and the whole feed is re-ranked live in the browser |

## Run it

Needs Node.js 18 or newer. From this folder:

```bash
npm install
npm run dev
```

Then open http://localhost:5173.

## Where the data comes from

The site reads static files in `public/data/`, made from the trained model by
`python -m src.serving.site_data` (run in Ubuntu from the repository root). They hold 19 real
customers from the test week (16–22 Sep 2020), their top products for every moment, a swipe
pool with model vectors, and product details. When the FastAPI backend is ready, the same
pages can call it instead.

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
