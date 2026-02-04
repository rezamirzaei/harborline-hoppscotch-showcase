from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, conint


class RecommendationSource(str, Enum):
    GRAPH = "graph"
    FALLBACK = "fallback"


class ProjectionSource(str, Enum):
    GRAPH = "graph"
    DISABLED = "disabled"
    ERROR = "error"


class ProductRecommendation(BaseModel):
    sku: str
    score: conint(ge=0) = 0
    evidence: List[str] = Field(default_factory=list)


class CustomerRecommendationsQuery(BaseModel):
    customer_id: str
    limit: conint(gt=0, le=50) = 10


class CustomerRecommendations(BaseModel):
    customer_id: str
    source: RecommendationSource
    generated_at: datetime
    items: List[ProductRecommendation]


class AlsoBoughtQuery(BaseModel):
    sku: str
    limit: conint(gt=0, le=50) = 10


class AlsoBoughtRecommendations(BaseModel):
    sku: str
    source: RecommendationSource
    generated_at: datetime
    items: List[ProductRecommendation]


class GraphWriteResult(BaseModel):
    ok: bool
    error: Optional[str] = None


class OrderProjectionResult(BaseModel):
    order_id: str
    source: ProjectionSource
    projected_at: datetime
    write: GraphWriteResult

