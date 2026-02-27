from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class UiDefaults(BaseModel):
    graphql_query: str
    graphql_variables: dict[str, Any]
    order_items_sample: list[dict[str, Any]]
    graph_customer_recommendations_query: str = ""
    graph_customer_recommendations_variables: dict[str, Any] = {}
    graph_also_bought_query: str = ""
    graph_also_bought_variables: dict[str, Any] = {}


@lru_cache(maxsize=4)
def load_ui_defaults(path: str) -> UiDefaults:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return UiDefaults(**data)
