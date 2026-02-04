from __future__ import annotations

from typing import Protocol
from uuid import uuid4


class IdProvider(Protocol):
    def new_id(self) -> str: ...


class UUIDProvider:
    def new_id(self) -> str:
        return uuid4().hex
