# MM-trading-Bot
Algo Trading Platform

## Setup

1. Make sure you have a local PostgreSQL database running on port 5432 with a database `trading_db`.
2. Make sure you have a local Redis server running on port 6379.
3. Install the requirements with `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill in your details.

**Important:** Never commit your `.env`, `token.json`, or `scan_state.json` as they contain your actual API credentials. Rotate them if accidentally committed.

## Live Trading vs Paper Trading

By default, the bot runs in **Paper Trading** mode (`LIVE_TRADING_MODE=False`).
Set `LIVE_TRADING_MODE=True` in your `.env` to execute real trades via DhanHQ.

## Training Regimes

Train the Regime Classifier using NIFTY historical data before running live inference:

```bash
python -m ml.train_regimes --symbol NIFTY --days 365
```

## Running the Bot

Run the main bot script:
```bash
python main.py
```

## Manual Rebalance

To trigger the Long Term Investing Engine manually:
```bash
python main.py --rebalance
```
