from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

NonNegativeInt = Annotated[int, Field(ge=0)]
RecommendationLimit = Annotated[int, Field(gt=0, le=50)]


class RecommendationSource(StrEnum):
    GRAPH = "graph"
    FALLBACK = "fallback"


class ProjectionSource(StrEnum):
    GRAPH = "graph"
    DISABLED = "disabled"
    ERROR = "error"


class ProductRecommendation(BaseModel):
    sku: str
    score: NonNegativeInt = 0
    evidence: list[str] = Field(default_factory=list)


class CustomerRecommendationsQuery(BaseModel):
    customer_id: str
    limit: RecommendationLimit = 10


class CustomerRecommendations(BaseModel):
    customer_id: str
    source: RecommendationSource
    generated_at: datetime
    items: list[ProductRecommendation]


class AlsoBoughtQuery(BaseModel):
    sku: str
    limit: RecommendationLimit = 10


class AlsoBoughtRecommendations(BaseModel):
    sku: str
    source: RecommendationSource
    generated_at: datetime
    items: list[ProductRecommendation]


class GraphWriteResult(BaseModel):
    ok: bool
    error: str | None = None


class OrderProjectionResult(BaseModel):
    order_id: str
    source: ProjectionSource
    projected_at: datetime
    write: GraphWriteResult
