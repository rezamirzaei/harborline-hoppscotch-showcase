from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


@dataclass(frozen=True)
class Database:
    url: str
    echo: bool = False
    engine: Engine = field(init=False)
    session_factory: sessionmaker[Session] = field(init=False)

    def __post_init__(self) -> None:
        engine = create_engine(self.url, echo=self.echo, future=True, pool_pre_ping=True)
        session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
        object.__setattr__(self, "engine", engine)
        object.__setattr__(self, "session_factory", session_factory)

    def create_tables(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

