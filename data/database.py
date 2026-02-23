from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from config.settings import DATABASE_PATH

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # BUY / SELL
    quantity = Column(Integer)
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    pnl = Column(Float, default=0.0)
    paper = Column(Boolean, default=True)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    quantity = Column(Integer)
    avg_price = Column(Float)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    equity = Column(Float)
    cash = Column(Float)


def init_db():
    from pathlib import Path
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


from contextlib import contextmanager

@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session          # use the session inside a `with` block
        session.commit()       # optional for read-only, but OK
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()        # crucial: returns connection to pool

