"""SQLite-backed paper-trade store (SQLAlchemy). Real ledger lives at
data/app.db (gitignored, app state per the plan's DB decision). Tests never
touch it — see tests/conftest.py's `paper_db` fixture, which rebinds the
session factory to an isolated in-memory database per test.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "app.db"

Base = declarative_base()


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    kind = Column(String, nullable=False)               # index | future | equity
    horizon = Column(String, nullable=False, default="swing")
    strategy = Column(String, nullable=True)
    bias = Column(String, nullable=False)                # Long | Short
    opened_at = Column(String, nullable=False)            # IST ISO string
    entry = Column(Float, nullable=False)
    stop = Column(Float, nullable=False)
    target1 = Column(Float, nullable=False)
    target2 = Column(Float, nullable=True)
    size = Column(Integer, nullable=False, default=0)
    predicted_score = Column(Integer, nullable=True)
    predicted_confidence = Column(String, nullable=True)
    status = Column(String, nullable=False, default="open")   # open | closed
    closed_at = Column(String, nullable=True)
    close_price = Column(Float, nullable=True)
    close_reason = Column(String, nullable=True)          # target | stop | time_exit
    r_multiple = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)


_engine = None
_SessionLocal = None


def configure(url: str | None = None) -> None:
    """(Re)bind the engine/session factory. Called once lazily for the real
    DB; tests call this explicitly with an in-memory URL for isolation."""
    global _engine, _SessionLocal
    url = url or os.environ.get("MARKETDAWN_DB_URL") or f"sqlite:///{DB_PATH}"
    if url == "sqlite:///:memory:":
        # StaticPool keeps the SAME in-memory DB across the many short-lived
        # sessions ledger.py opens/closes — without it, each session would
        # see a fresh, empty in-memory database.
        _engine = create_engine(url, echo=False, future=True,
                                 connect_args={"check_same_thread": False},
                                 poolclass=StaticPool)
    else:
        if url.startswith("sqlite:///"):
            Path(url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, echo=False, future=True)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def get_session():
    if _SessionLocal is None:
        configure()
    return _SessionLocal()
