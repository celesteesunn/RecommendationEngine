# Context-Aware Neural Recommendation Engine

A deep learning-based recommendation system for personalised fashion recommendations using the
**[H&M Personalized Fashion Recommendations](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations)**
dataset. A two-tower neural network combines user metadata, historical purchase sequences and
item context to generate personalised, real-time recommendations.

New to the project? Two documents explain it in depth:

- [Project Blueprint](docs/PROJECT_BLUEPRINT.md): the full architecture, the final outputs for
  end users and the system, and the week-by-week work plan.
- [Project Guide](docs/PROJECT_GUIDE.md): the current state of the repo, design decisions,
  status and next steps.

## Project Pipeline

1. Distributed data processing and data preparation
2. Contextual feature engineering
3. User and item feature representation
4. Two-Tower neural recommendation model
5. User and item embedding generation
6. Approximate Nearest Neighbor (ANN) candidate retrieval
7. Recommendation serving through FastAPI
8. Feature storage and caching using Redis
9. Model retraining and embedding updates using Apache Airflow

## Team

- Samala Sunaina
- Siddhi Kale
- Tejashvi Khandelwal

## Dataset

### H&M Personalized Fashion Recommendations

This project uses the **H&M Personalized Fashion Recommendations** dataset from Kaggle.

The dataset is based on real-world fashion retail interactions and contains information about customers, fashion articles, and customer purchase transactions.

The main data components include:

- **Customers** – Contains customer-level information such as customer identifiers and available demographic or profile attributes.
- **Articles** – Contains detailed information about H&M fashion products, including product categories, garment types, colours, departments, and other article attributes.
- **Transactions** – Contains historical customer purchases, including customer IDs, article IDs, transaction dates, and purchase prices.

| File | Rows | Contents |
|---|---|---|
| `transactions_train.csv` | ~31.8M | Purchases from Sep 2018 to Sep 2020: date, customer, article, price, sales channel |
| `customers.csv` | ~1.37M | Age, club member status, fashion news frequency, postal code |
| `articles.csv` | ~105K | Product type, colour, garment group, department, description |

Only these tabular files are used; the ~29 GB product images are not downloaded.

These three components allow us to connect:

**Customer → Purchase History → Fashion Articles**

The transaction history provides the interaction data required to learn customer preferences, while customer and article attributes provide additional contextual information for the recommendation model.

### How We Use the Dataset

The dataset is processed using **PySpark** to prepare the large-scale transaction and product data.

From the available data, we engineer features such as:

- Customer purchase history
- Product interaction frequency
- Recency of purchases
- Purchase time information
- Product popularity
- Product category and garment information
- Product colour and other article attributes
- User and item identifiers

These features are then used by the **Two-Tower neural network**.

The **Query/User Tower** learns a representation of the customer based on their profile, historical interactions, and contextual information.

The **Candidate/Item Tower** learns a representation of each fashion article using its available product attributes.

The resulting user and item embeddings are compared to retrieve relevant fashion products.

## Recommendation Architecture

### Two-Tower Model

```text
User Information + Purchase History + Context        Article Metadata
                    │                                        │
                    ▼                                        ▼
          User / Query Tower                     Item / Candidate Tower
                    │                                        │
                    ▼                                        ▼
             User Embedding ───► Similarity Search ◄─── Item Embedding
                                        │
                                        ▼
                           Top-K Recommended Products
```

### System Architecture

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

## Evaluation

The recommendation system is evaluated using:

- Recall@K
- NDCG@K (Normalized Discounted Cumulative Gain)

These metrics measure how effectively the system retrieves relevant products for a user.

## Tech Stack

| Area | Tools |
|---|---|
| Language | Python |
| Data processing | Apache Spark / PySpark |
| Deep learning | TensorFlow, Keras, TensorFlow Recommenders (TFRS) |
| Feature store / cache | Redis |
| Retrieval | FAISS (approximate nearest neighbour) |
| Backend | FastAPI |
| Workflow orchestration | Apache Airflow |
| Dataset | H&M Personalized Fashion Recommendations |

## Project Structure

```text
├── configs/          # config.yaml: paths, split, model and serving settings
├── dags/             # Airflow DAGs (retraining, embedding refresh)
├── data/
│   ├── raw/          # Kaggle CSVs (not committed)
│   └── processed/    # Parquet outputs from PySpark (not committed)
├── docs/             # Project guide and architecture diagrams
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

- `main` is the only long-lived branch.
- For a piece of work, branch from `main` using `feature/<name>`, `fix/<name>` or `docs/<name>`,
  open a pull request into `main`, and delete the branch once it is merged.
- Commit daily with clear messages (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- Pull the latest `main` before starting new work.
