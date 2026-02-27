from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .domain import InventoryItem


class InventorySeed(BaseModel):
    items: list[InventoryItem]


def load_inventory_seed(path: str) -> list[InventoryItem]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    seed = InventorySeed(**data)
    return seed.items
