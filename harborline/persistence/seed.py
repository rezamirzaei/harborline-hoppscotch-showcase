from __future__ import annotations

from sqlalchemy import select

from ..seed import load_inventory_seed
from .db import Database
from .models import InventoryItemRecord


def seed_inventory_if_empty(db: Database, seed_path: str) -> None:
    items = load_inventory_seed(seed_path)
    if not items:
        return

    with db.session() as session:
        existing = session.execute(select(InventoryItemRecord.sku).limit(1)).first()
        if existing:
            return
        session.add_all([InventoryItemRecord(sku=item.sku, available=item.available) for item in items])

