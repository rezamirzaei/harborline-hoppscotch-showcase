from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel


class UiDefaults(BaseModel):
    graphql_query: str
    graphql_variables: Dict[str, Any]
    order_items_sample: list[Dict[str, Any]]


@lru_cache(maxsize=4)
def load_ui_defaults(path: str) -> UiDefaults:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return UiDefaults(**data)
