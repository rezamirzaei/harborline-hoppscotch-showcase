from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from ..domain import (
    IdempotencyRecord,
    InventoryItem,
    InventoryRequestItem,
    InventoryShortage,
    Order,
    OrderItem,
    OrderStatus,
    PaymentIntent,
    PaymentStatus,
)
from .db import Database
from .models import (
    IdempotencyRecordRecord,
    InventoryItemRecord,
    OrderItemRecord,
    OrderRecord,
    PaymentIntentRecord,
)


def order_from_record(record: OrderRecord) -> Order:
    return Order(
        id=record.id,
        customer_id=record.customer_id,
        status=OrderStatus(record.status),
        currency=record.currency,
        items=[OrderItem(sku=item.sku, qty=item.qty, unit_price=item.unit_price) for item in record.items],
        total=record.total,
        note=record.note,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def payment_from_record(record: PaymentIntentRecord) -> PaymentIntent:
    return PaymentIntent(
        id=record.id,
        order_id=record.order_id,
        amount=record.amount,
        currency=record.currency,
        status=PaymentStatus(record.status),
        created_at=record.created_at,
    )


class SqlAlchemyOrderRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, order: Order) -> Order:
        with self._db.session() as session:
            record = OrderRecord(
                id=order.id,
                customer_id=order.customer_id,
                status=order.status.value,
                currency=order.currency,
                total=order.total,
                note=order.note,
                created_at=order.created_at,
                updated_at=order.updated_at,
                items=[
                    OrderItemRecord(sku=item.sku, qty=item.qty, unit_price=float(item.unit_price))
                    for item in order.items
                ],
            )
            session.add(record)
        return order

    def get(self, order_id: str) -> Optional[Order]:
        with self._db.session() as session:
            stmt = select(OrderRecord).options(joinedload(OrderRecord.items)).where(OrderRecord.id == order_id)
            record = session.execute(stmt).unique().scalars().first()
            if not record:
                return None
            return order_from_record(record)

    def list(self, status: Optional[OrderStatus], limit: int) -> List[Order]:
        with self._db.session() as session:
            stmt = select(OrderRecord).options(joinedload(OrderRecord.items)).order_by(OrderRecord.created_at.desc())
            if status:
                stmt = stmt.where(OrderRecord.status == status.value)
            stmt = stmt.limit(limit)
            records = session.execute(stmt).unique().scalars().all()
            return [order_from_record(record) for record in records]

    def update(self, order: Order) -> Order:
        with self._db.session() as session:
            stmt = select(OrderRecord).where(OrderRecord.id == order.id)
            record = session.execute(stmt).unique().scalars().first()
            if not record:
                return order
            record.status = order.status.value
            record.updated_at = order.updated_at
        return order

    def count(self) -> int:
        with self._db.session() as session:
            return int(session.execute(select(func.count()).select_from(OrderRecord)).scalar_one())

    def total_revenue(self) -> float:
        with self._db.session() as session:
            total = session.execute(select(func.coalesce(func.sum(OrderRecord.total), 0.0))).scalar_one()
            return round(float(total), 2)

    def paid_count(self) -> int:
        with self._db.session() as session:
            stmt = select(func.count()).select_from(OrderRecord).where(OrderRecord.status == OrderStatus.PAID.value)
            return int(session.execute(stmt).scalar_one())


class SqlAlchemyPaymentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, payment: PaymentIntent) -> PaymentIntent:
        with self._db.session() as session:
            record = PaymentIntentRecord(
                id=payment.id,
                order_id=payment.order_id,
                amount=payment.amount,
                currency=payment.currency,
                status=payment.status.value,
                created_at=payment.created_at,
            )
            session.add(record)
        return payment

    def get(self, payment_id: str) -> Optional[PaymentIntent]:
        with self._db.session() as session:
            stmt = select(PaymentIntentRecord).where(PaymentIntentRecord.id == payment_id)
            record = session.execute(stmt).scalars().first()
            return payment_from_record(record) if record else None

    def list_by_order(self, order_id: str) -> List[PaymentIntent]:
        with self._db.session() as session:
            stmt = (
                select(PaymentIntentRecord)
                .where(PaymentIntentRecord.order_id == order_id)
                .order_by(PaymentIntentRecord.created_at.desc())
            )
            records = session.execute(stmt).scalars().all()
            return [payment_from_record(record) for record in records]

    def list_all(self) -> List[PaymentIntent]:
        with self._db.session() as session:
            stmt = select(PaymentIntentRecord).order_by(PaymentIntentRecord.created_at.desc())
            records = session.execute(stmt).scalars().all()
            return [payment_from_record(record) for record in records]

    def update(self, payment: PaymentIntent) -> PaymentIntent:
        with self._db.session() as session:
            stmt = select(PaymentIntentRecord).where(PaymentIntentRecord.id == payment.id)
            record = session.execute(stmt).scalars().first()
            if not record:
                return payment
            record.status = payment.status.value
        return payment


class SqlAlchemyInventoryRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, sku: str) -> Optional[InventoryItem]:
        with self._db.session() as session:
            record = session.execute(select(InventoryItemRecord).where(InventoryItemRecord.sku == sku)).scalars().first()
            if not record:
                return None
            return InventoryItem(sku=record.sku, available=record.available)

    def list_all(self) -> List[InventoryItem]:
        with self._db.session() as session:
            records = session.execute(select(InventoryItemRecord).order_by(InventoryItemRecord.sku.asc())).scalars().all()
            return [InventoryItem(sku=record.sku, available=record.available) for record in records]

    def shortages(self, items: Iterable[InventoryRequestItem]) -> List[InventoryShortage]:
        requested = list(items)
        if not requested:
            return []

        skus = [item.sku for item in requested]
        with self._db.session() as session:
            records = session.execute(select(InventoryItemRecord).where(InventoryItemRecord.sku.in_(skus))).scalars().all()
            current = {record.sku: record.available for record in records}

        shortages: List[InventoryShortage] = []
        for item in requested:
            available = int(current.get(item.sku, 0))
            if available < item.qty:
                shortages.append(InventoryShortage(sku=item.sku, available=available, requested=item.qty))
        return shortages

    def reserve(self, items: Iterable[InventoryRequestItem]) -> None:
        requested = list(items)
        if not requested:
            return

        with self._db.session() as session:
            for item in requested:
                record = (
                    session.execute(select(InventoryItemRecord).where(InventoryItemRecord.sku == item.sku))
                    .scalars()
                    .first()
                )
                if not record:
                    record = InventoryItemRecord(sku=item.sku, available=0)
                    session.add(record)
                    session.flush()
                record.available = max(int(record.available) - int(item.qty), 0)


class SqlAlchemyIdempotencyRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        with self._db.session() as session:
            stmt = (
                select(IdempotencyRecordRecord, OrderRecord)
                .join(OrderRecord, OrderRecord.id == IdempotencyRecordRecord.order_id)
                .options(joinedload(OrderRecord.items))
                .where(IdempotencyRecordRecord.key == key)
            )
            row = session.execute(stmt).unique().first()
            if not row:
                return None
            idempo, order = row
            return IdempotencyRecord(key=idempo.key, order=order_from_record(order))

    def set(self, record: IdempotencyRecord) -> None:
        with self._db.session() as session:
            session.merge(IdempotencyRecordRecord(key=record.key, order_id=record.order.id))
