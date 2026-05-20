## SQL Schema Documentation

Here are the complete `CREATE TABLE` statements for the three core tables representing the architecture mapped to PostgreSQL:

### A. The historical_data Table (The Archive)

```sql
CREATE TABLE historical_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    interval VARCHAR(20)
);

-- Composite Index for fast time-series queries
CREATE INDEX ix_historical_data_symbol_timestamp ON historical_data (symbol, timestamp);
```

### B. The trade_log Table (The Audit Trail)
*(Mapped as `trades` in SQLAlchemy)*

```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10),
    quantity INTEGER,
    price DOUBLE PRECISION,
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('UTC', now()),
    pnl DOUBLE PRECISION DEFAULT 0.0,
    paper BOOLEAN DEFAULT true,
    segment VARCHAR(50) DEFAULT 'INTRADAY',
    order_type VARCHAR(20),
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION,
    product_type VARCHAR(20),
    is_mtf BOOLEAN DEFAULT false,
    pledge_status VARCHAR(50) DEFAULT 'PENDING'
);

CREATE INDEX ix_trades_symbol ON trades (symbol);
CREATE INDEX ix_trades_segment ON trades (segment);
CREATE INDEX ix_trades_is_mtf ON trades (is_mtf);
```

### C. The portfolio_snapshots Table (The Dashboard Feed)

```sql
CREATE TABLE portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('UTC', now()),
    equity DOUBLE PRECISION,
    cash DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION DEFAULT 0.0,
    realized_pnl_day DOUBLE PRECISION DEFAULT 0.0
);
```
