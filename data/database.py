from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from config.settings import DATABASE_PATH, SEGMENT_INTRADAY

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
    side = Column(String)  # BUY / SELL / SHORT / COVER
    quantity = Column(Integer)
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    pnl = Column(Float, default=0.0)
    paper = Column(Boolean, default=True)
    # New: which segment created this trade (INTRADAY / SWING / LONGTERM)
    segment = Column(String, default=SEGMENT_INTRADAY, index=True)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    quantity = Column(Integer)
    avg_price = Column(Float)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    # New: segment owning this position (INTRADAY / SWING / LONGTERM)
    segment = Column(String, default=SEGMENT_INTRADAY, index=True)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    equity = Column(Float)
    cash = Column(Float)

class Fundamentals(Base):
    __tablename__ = "fundamentals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)   # e.g. RELIANCE
    yf_ticker = Column(String, index=True)             # e.g. RELIANCE.NS
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Pricing / size
    current_price = Column(Float)
    market_cap = Column(Float)

    # Valuation snapshot
    pe = Column(Float)          # trailing PE
    pb = Column(Float)          # price-to-book
    ps = Column(Float)          # price-to-sales
    ev_ebitda = Column(Float)   # if we compute it

    # Profitability / growth
    roe = Column(Float)
    profit_margin = Column(Float)
    revenue_cagr_5y = Column(Float)
    eps_cagr_5y = Column(Float)

    # Leverage
    debt_to_equity = Column(Float)
    interest_coverage = Column(Float)

    # Cash & dividends
    fcfe_ttm = Column(Float)
    dividend_yield = Column(Float)

    # Valuation outputs
    fv_dcf = Column(Float)          # fair value from FCFE DCF
    fv_multiples = Column(Float)    # fair value from relative multiples
    fv_composite = Column(Float)    # conservative combined fair value

class LongTermIdea(Base):
    __tablename__ = "longterm_ideas"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    symbol = Column(String, index=True)
    action = Column(String)      # "BUY" or "SELL"
    qty = Column(Integer)
    entry_price = Column(Float)  # suggested price (current price when idea generated)
    target_price = Column(Float) # explicit sell target
    fair_value = Column(Float)   # fv_composite at generation time

    margin_of_safety_pct = Column(Float)  # (fv - price)/fv * 100
    upside_pct = Column(Float)            # (target - price)/price * 100
    multibagger_score = Column(Float)     # simple = upside_pct, for now

    # Lifecycle
    approved = Column(Boolean, default=False)  # you toggled yes/no
    executed = Column(Boolean, default=False)  # bot has placed the order
    reason = Column(String)                    # txt summary from strategy

def init_db():
    from pathlib import Path
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


from contextlib import contextmanager


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session  # use the session inside a `with` block
        session.commit()  # optional for read-only, but OK
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()  # crucial: returns connection to pool