"""
Engine + session setup.

Why `expire_on_commit=False`: after we commit a bid inside a request,
we often want to return the committed object in the HTTP response
without triggering a fresh SELECT. Default SQLAlchemy behavior expires
all attributes on commit (forcing a reload on next access); turning
that off avoids a wasted extra query on the common path.

Why a generator-based `get_db` dependency: FastAPI's `Depends(get_db)`
calls this, runs the route with the yielded session, and guarantees
the `finally` block closes it even if the route raises. This is what
ties a database session's lifetime to exactly one HTTP request — no
session is ever shared across requests or leaked.
"""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/british_auction_rfq",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
