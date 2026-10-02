# Context-Aware Neural Recommendation Engine

A deep learning-based recommendation system for personalised fashion recommendations using the **H&M Personalized Fashion Recommendations** dataset.

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

-- Samala Sunaina
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

The system follows a Two-Tower recommendation architecture:

**User Information + Purchase History + Context**

↓

**User / Query Tower**

↓

**User Embedding**

↓

**Similarity Search**

↓

**Top-K Recommended Products**

↑

**Item Embedding**

↑

**Item / Candidate Tower**

↑

**Article Metadata**

## Evaluation

The recommendation system is evaluated using:

- Recall@K
- NDCG@K (Normalized Discounted Cumulative Gain)

These metrics measure how effectively the system retrieves relevant products for a user.

## Tech Stack

- **Language:** Python
- **Data Processing:** Apache Spark / PySpark
- **Deep Learning:** TensorFlow, Keras, TensorFlow Recommenders (TFRS)
- **Feature Store / Cache:** Redis
- **Backend:** FastAPI
- **Workflow Orchestration:** Apache Airflow
- **Dataset:** H&M Personalized Fashion Recommendations
