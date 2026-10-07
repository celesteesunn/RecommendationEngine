
  # Context Aware Neural Recommendation Engine

This project is about building a personalised fashion recommendation system using the H&M Personalized Fashion Recommendations dataset.

The main goal is to understand what a customer is likely to buy and recommend relevant fashion products based on their previous purchases, customer information and product details.

Instead of using only basic purchase history, we are building a Two Tower Neural Network that learns separate representations for users and products. These representations can then be used to find products that are more relevant to a particular customer.

## Project Idea

The system connects three main types of information:

Customer
→ Purchase History
→ Fashion Products

For example, if a customer frequently buys a particular type of clothing, the system should be able to learn this behaviour and recommend similar or relevant products.

The final system is planned to include:

- Data processing using PySpark
- Feature engineering
- Two Tower Neural Network
- User and item embeddings
- Fast product retrieval using ANN
- FastAPI for serving recommendations
- Redis for storing frequently used features
- Airflow for scheduled pipelines and model updates

## Dataset

We are using the H&M Personalized Fashion Recommendations dataset from Kaggle.

The dataset contains information about customers, products and customer purchase transactions.

### Main files

| File | Approx. Size | Description |
|---|---:|---|
| `transactions_train.csv` | 31.8M rows | Customer purchase transactions |
| `customers.csv` | 1.37M rows | Customer information |
| `articles.csv` | 105K rows | Product information |

The project uses the tabular data only. The large product image dataset is not being used.

### What the data contains

**Customers**

Contains information such as:

- Customer ID
- Age
- Club member status
- Fashion news frequency
- Other available customer attributes

**Articles**

Contains product information such as:

- Article ID
- Product type
- Product group
- Colour
- Department
- Section
- Garment group

**Transactions**

Contains customer purchase history such as:

- Transaction date
- Customer ID
- Article ID
- Price
- Sales channel

## Week 1: Data Processing and Feature Engineering

Week 1 focused mainly on understanding, cleaning and preparing the H&M data for the recommendation model.

### Completed work

- Loaded the H&M datasets using PySpark
- Checked the structure and schema of the datasets
- Checked missing values
- Checked duplicate transactions
- Checked invalid or zero transaction prices
- Checked transaction date ranges
- Cleaned transaction data
- Removed duplicate records
- Cleaned customer and article data
- Checked cold start users
- Checked cold start products
- Calculated customer purchase frequency
- Calculated user purchase recency
- Calculated product popularity
- Created time based features
- Added customer information to transaction data
- Added product information to transaction data
- Created user vocabulary
- Created item vocabulary
- Created product type and department vocabularies
- Prepared the combined training dataset for the next stage

### Features created

Some of the features prepared during Week 1 include:

- Purchase frequency
- Recency of purchase
- Product popularity
- Purchase year
- Purchase month
- Purchase day
- Day of week
- Week of year
- Customer age
- Club member status
- Fashion news frequency
- Product type
- Product group
- Product colour
- Department
- Section
- Garment group

PySpark was used because the transaction dataset contains more than 30 million records and requires distributed processing.

## Recommendation Model

The main recommendation model planned for the project is a Two Tower Neural Network.

The two towers are:

### User Tower

The user tower learns a representation of the customer using information such as:

- Customer ID
- Customer profile information
- Previous purchases
- Purchase frequency
- Recency
- Contextual information

The output of this tower is a user embedding.

### Item Tower

The item tower learns a representation of each fashion product using information such as:

- Article ID
- Product type
- Product group
- Colour
- Department
- Section
- Garment group
- Product popularity

The output is an item embedding.

The user and item embeddings are then compared to find products that are most relevant to the customer.

```text
Customer Data + Purchase History
                |
                v
          User Tower
                |
                v
        User Embedding
                |
                | Similarity
                |
                v
        Recommended Items
                ^
                |
          Item Embedding
                ^
                |
          Item Tower
                ^
                |
         Product Metadata
###projecr structure
RecommendationEngine/
│
├── configs/
│   └── Project configuration files
│
├── dags/
│   └── Airflow pipelines
│
├── data/
│   ├── raw/
│   └── processed/
│
├── docs/
│   └── Project documentation
│
├── models/
│   └── Trained models and embeddings
│
├── notebooks/
│   └── Week 1 analysis and experiments
│
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── serving/
│   └── api/
│
├── tests/
│   └── Testing files
│
├── .env.example
├── .gitignore
├── README.md
└── requirements-airflow.txt
