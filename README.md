# Context-Aware Neural Recommendation Engine

A context-aware fashion recommendation system based on the H&M Personalized Fashion Recommendations dataset.

## Project Pipeline

1. Data preparation
2. Feature engineering
3. Two-Tower neural recommendation model
4. User and item embeddings
5. Approximate Nearest Neighbor retrieval
6. FastAPI recommendation service

## Team

Samala Sunaina
- Tejashvi Khandelwal
- Siddhi Kale
- Abhilash Kum

---

## About

This project is about building a personalised recommendation system.

The idea is to use user interactions and item information to understand what a user may be interested in and recommend relevant items.

As a team, we are working with different datasets to see how the recommendation approach works with different types of data.

Currently, we are testing with:

- MovieLens
- H&M
- Blinkit

Each dataset has different types of users, items and interactions, so we will compare the results and understand which type of data works better for our recommendation system.

---

## Datasets

### MovieLens
MovieLens contains user ratings and movie information. We are using it to work with movie recommendations and understand user-movie interactions.

Main files:

```text
users.csv
movies.csv
ratings.csv