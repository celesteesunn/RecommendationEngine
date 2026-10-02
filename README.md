# Context-Aware Neural Recommendation Engine

A deep learning recommendation system for fashion e-commerce, built on the
[H&M Personalized Fashion Recommendations](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations)
dataset. A two-tower neural network combines user metadata, historical purchase
sequences and item context to generate personalised, real-time recommendations.

## Team

- Samala Sunaina
- Siddhi Kale
- Abhilash Kum
- Tejashvi Khandelwal

## Architecture

```text
OFFLINE                                              ONLINE
Kaggle CSVs                                          GET /recommend/{user_id}
   │                                                    │
   ▼                                                    ▼
PySpark cleaning ──► Feature engineering        FastAPI ──► Redis (user features)
   │                      │                        │
   ▼                      ▼                        ▼
Time-based split ──► Two-Tower model (TFRS)     Query tower ──► user vector
                          │                        │
                          ▼                        ▼
               Item embeddings + query tower ──► FAISS ANN index ──► top-K items

Airflow: weekly retraining, daily embedding refresh
```

## Dataset

| File | Rows | Contents |
|---|---|---|
| `transactions_train.csv` | ~31.8M | Purchases from Sep 2018 to Sep 2020: date, customer, article, price, sales channel |
| `customers.csv` | ~1.37M | Age, club member status, fashion news frequency, postal code |
| `articles.csv` | ~105K | Product type, colour, garment group, department, description |

Only these tabular files are used; the ~29 GB product images are not downloaded.

## Tech Stack

| Area | Tools |
|---|---|
| Language | Python |
| Deep learning | TensorFlow / Keras, TensorFlow Recommenders |
| Data engineering | Apache Spark (PySpark), Apache Airflow |
| Feature store & cache | Redis |
| Retrieval | FAISS (approximate nearest neighbour) |
| Backend | FastAPI |

## Project Structure

```text
├── configs/          # config.yaml: paths, split, model and serving settings
├── dags/             # Airflow DAGs (retraining, embedding refresh)
├── data/
│   ├── raw/          # Kaggle CSVs (not committed)
│   └── processed/    # Parquet outputs from PySpark (not committed)
├── docs/             # Architecture diagrams
├── models/           # Trained models and embeddings (not committed)
├── notebooks/        # Exploration only
├── src/
│   ├── data/         # Download and PySpark cleaning
│   ├── features/     # Feature engineering and vocabularies
│   ├── models/       # Two-tower model, training, evaluation, export
│   ├── serving/      # Redis feature store and ANN index
│   └── api/          # FastAPI service
└── tests/            # Unit tests and load tests
```

## Setup

The project runs on Linux (WSL2 Ubuntu on Windows), because Airflow and Redis do
not run natively on Windows and TensorFlow GPU support requires Linux.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Spark needs Java 17 (`sudo apt install openjdk-17-jdk`).

### Download the data

1. Accept the [competition rules](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/rules) on Kaggle.
2. Create an API token (Kaggle → Settings → API → Create New Token) and save it as `~/.kaggle/kaggle.json`.
3. Run:

```bash
python -m src.data.download
```

### Run tests

```bash
pytest
```

## Roadmap

| Week | Focus | Status |
|---|---|---|
| 1 | PySpark data processing, missing values, cold-start handling | In progress |
| 2 | Contextual features, vocabularies, Two-Tower model, Recall@K / NDCG evaluation | Planned |
| 3 | Model and embedding export, Redis feature store, ANN retrieval | Planned |
| 4 | FastAPI service, Airflow DAGs, load testing, architecture diagrams | Planned |

## Contributing

- Branch from `main` using `feature/<name>`, `fix/<name>` or `docs/<name>`.
- Commit daily with clear messages (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- Open a pull request into `main`; do not push directly to `main`.
