"""The recommendation API: live picks from the two-tower model for any customer and moment.

Run inside Ubuntu, from the repository root:
    uvicorn src.api.main:app --port 8000

Loading takes about a minute (the model, 1.4 million customers and their purchases). Then
http://localhost:8000/docs lists every endpoint and lets you try them.

    GET  /health                                  model version and what is loaded
    GET  /customers/random                        a random real customer from the test week
    GET  /customers/{id}                          one customer: profile, timeline, style DNA
    GET  /customers/{id}/recommendations          their picks for a moment
    POST /recommendations                         picks for a new visitor, or a customer plus
                                                  the products they just liked (Swipe page)

A customer can be given by their full ID or its first 8 characters, as the website shows it.
For a real customer, blend=best (the default) puts up to 6 of their own recent products first
and fills the rest with the model's picks: the best blend in the evaluation. blend=model gives
the model's picks only. Every item says where it came from ("source").
"""

import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.recommender import AmbiguousId, Moment, Recommender
from src.api.recommender import Query as ShopperQuery

AgeBucket = Literal["16-24", "25-34", "35-44", "45-54", "55+", "unknown"]
Blend = Literal["best", "model"]
BLEND_HELP = "best: up to 6 of their own recent products first, then the model's; model: the model's only"


class RecommendationRequest(BaseModel):
    customerId: str | None = Field(None, description="A real customer, or leave out for a new visitor")
    ageBucket: AgeBucket = "unknown"
    history: list[str] = Field([], description="Article IDs to add to the history, oldest first (e.g. likes)")
    day: int = Field(4, ge=1, le=7, description="1 = Sunday ... 7 = Saturday")
    month: int = Field(9, ge=1, le=12)
    channel: int = Field(2, ge=1, le=2, description="1 = in store, 2 = online")
    k: int = Field(12, ge=1, le=100)
    exclude: list[str] = Field([], description="Article IDs not to recommend (e.g. already seen)")
    blend: Blend = Field("best", description=BLEND_HELP + " (real customers only)")


def create_app(load: Callable[[], Recommender]) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.recommender = load()
        yield

    app = FastAPI(title="Kairos recommendation API", version="1.0", lifespan=lifespan)
    # The website's dev server, when it calls the API directly instead of through its proxy.
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    def model(request: Request) -> Recommender:
        return request.app.state.recommender

    def customer_row(recommender: Recommender, customer_id: str) -> int:
        try:
            row = recommender.find_customer(customer_id)
        except AmbiguousId as error:
            raise HTTPException(400, str(error)) from error
        if row is None:
            raise HTTPException(404, f"No customer with ID {customer_id}")
        return row

    def answer(recommender: Recommender, query: ShopperQuery, moment: Moment, k: int, exclude: list[str],
               started: float, row: int | None = None, blend: str = "model", **extra) -> dict:
        first = []
        if row is not None and blend == "best":
            first = recommender.own_products(row)[:recommender.repurchase_slots]
        items = recommender.recommend(query, moment, k, exclude, first)
        return {"modelVersion": recommender.version, "moment": moment.key, "blend": blend if first else "model",
                **extra, "items": items, "tookMs": round((time.perf_counter() - started) * 1000, 1)}

    @app.get("/health")
    def health(request: Request) -> dict:
        return {"status": "ok", **model(request).summary()}

    @app.get("/customers/random")
    def random_customer(request: Request, warm: bool = Query(False, description="Only customers with 5+ purchases")) -> dict:
        recommender = model(request)
        return recommender.profile(recommender.random_customer(warm))

    @app.get("/customers/{customer_id}")
    def customer(request: Request, customer_id: str) -> dict:
        recommender = model(request)
        return recommender.profile(customer_row(recommender, customer_id))

    @app.get("/customers/{customer_id}/recommendations")
    def customer_recommendations(
        request: Request, customer_id: str,
        day: int = Query(4, ge=1, le=7, description="1 = Sunday ... 7 = Saturday"),
        month: int = Query(9, ge=1, le=12),
        channel: int = Query(2, ge=1, le=2, description="1 = in store, 2 = online"),
        k: int = Query(12, ge=1, le=100),
        exclude: list[str] = Query([]),
        blend: Blend = Query("best", description=BLEND_HELP),
    ) -> dict:
        started = time.perf_counter()
        recommender = model(request)
        row = customer_row(recommender, customer_id)
        query = recommender.query_for(row)
        return answer(recommender, query, Moment(day, month, channel), k, exclude, started,
                      row=row, blend=blend, customerId=query.customer_id)

    @app.post("/recommendations")
    def recommendations(request: Request, body: RecommendationRequest) -> dict:
        started = time.perf_counter()
        recommender = model(request)
        row = None
        if body.customerId:
            row = customer_row(recommender, body.customerId)
            query = recommender.query_for(row, body.history)
        else:
            query = ShopperQuery(age_bucket=body.ageBucket, history=body.history,
                                 days_since_last_purchase=float(recommender.max_days_since))
        return answer(recommender, query, Moment(body.day, body.month, body.channel), body.k, body.exclude,
                      started, row=row, blend=body.blend, customerId=body.customerId and query.customer_id)

    return app


app = create_app(Recommender.from_config)
