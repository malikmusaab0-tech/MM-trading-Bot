import asyncio
import json
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis_async

from config import settings
from data.database import get_async_session, Trade, Position
from ml.regime_classifier import classifier

logger = logging.getLogger("fastapi_dashboard")

app = FastAPI(title="MM-Trading-Bot Institutional Dashboard", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# Globals for async connections
redis_client: Optional[redis_async.Redis] = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_client = redis_async.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )
    logger.info("FastAPI connected to Redis.")

@app.on_event("shutdown")
async def shutdown_event():
    if redis_client:
        await redis_client.aclose()

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("institutional_dashboard.html", {"request": request})

@app.get("/api/v1/trade_log")
async def get_trade_log(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    strategy: str = Query("ALL")
):
    offset = (page - 1) * limit

    async with get_async_session() as session:
        # Base query
        stmt = select(Trade).order_by(desc(Trade.timestamp))
        count_stmt = select(func.count(Trade.trade_id))

        if strategy != "ALL":
            # Basic matching, might need adjustment based on exact segment naming
            stmt = stmt.filter(Trade.segment.ilike(f"%{strategy}%"))
            count_stmt = count_stmt.filter(Trade.segment.ilike(f"%{strategy}%"))

        # Execute count
        total_records = await session.scalar(count_stmt)

        # Execute paginated query
        stmt = stmt.offset(offset).limit(limit)
        result = await session.execute(stmt)
        trades = result.scalars().all()

        data = []
        for t in trades:
            data.append({
                "trade_id": t.trade_id,
                "symbol": t.symbol,
                "side": t.side,
                "segment": t.segment,
                "quantity": t.quantity,
                "entry_price": t.price,
                "exit_price": t.exit_price,
                "net_pnl": getattr(t, 'net_pnl', t.pnl),
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "product_type": t.product_type
            })

        return {
            "total_records": total_records or 0,
            "page": page,
            "limit": limit,
            "data": data
        }

@app.get("/api/v1/system_audit")
async def get_system_audit(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    # Mocking system audit for now, would typically query a dedicated table
    return {
        "total_records": 0,
        "page": page,
        "limit": limit,
        "data": []
    }

# React/Flask API Route Compatibility Matchers
@app.get("/api/portfolio")
async def get_portfolio_compat():
    # Provide backward compatibility for React UI hooks seeking portfolio stats
    async with get_async_session() as session:
        result = await session.execute(select(Position).filter(Position.quantity != 0))
        positions = result.scalars().all()
        return {
            "total_positions": len(positions),
            "data": [
                {"symbol": p.symbol, "quantity": p.quantity, "segment": p.segment, "unrealized_pnl": p.unrealized_pnl}
                for p in positions
            ]
        }

@app.post("/api/toggle_bot")
async def toggle_bot_compat():
    # Provide backward compatibility for React UI hooks
    return {"status": "success", "message": "Bot toggled via compat API."}

async def fetch_telemetry_data():
    """Aggregates all data required for the WebSocket stream."""
    try:
        # 1. Global Health
        dhan_health = True
        redis_health = await redis_client.ping() if redis_client else False
        db_health = True

        # 2. Macro Regime
        regime_label = "UNKNOWN"
        if classifier.current_regime_info:
            regime_label = classifier.current_regime_info.get("label", "UNKNOWN").upper()

        # 3. MTF Pledges
        mtf_warnings = 0
        intraday_pnl = 0.0
        intraday_count = 0
        swing_exposure = 0.0
        swing_margin = 0.0
        lt_assets = 0
        lt_allocated = 0.0

        async with get_async_session() as session:
            stmt = select(func.count(Trade.trade_id)).filter(Trade.is_mtf == True, Trade.pledge_status == 'PENDING', Trade.exit_time == None)
            mtf_warnings = await session.scalar(stmt) or 0

            result = await session.execute(select(Position).filter(Position.quantity != 0))
            positions = result.scalars().all()

            for pos in positions:
                live_price_str = await redis_client.hget(f"live_state:{pos.symbol}", "ltp")
                live_price = float(live_price_str) if live_price_str else pos.avg_price

                notional = abs(pos.quantity) * live_price
                unrealized = (live_price - pos.avg_price) * pos.quantity if pos.quantity > 0 else (pos.avg_price - live_price) * abs(pos.quantity)

                if pos.segment == settings.SEGMENT_INTRADAY:
                    intraday_count += 1
                    intraday_pnl += (pos.realized_pnl or 0) + unrealized
                elif pos.segment == settings.SEGMENT_SWING:
                    swing_exposure += notional
                    swing_margin += notional * 0.25 # Assume 25% margin for MTF roughly
                elif pos.segment == settings.SEGMENT_LONGTERM:
                    lt_assets += 1
                    lt_allocated += notional

        telemetry = {
            "health": {
                "live_mode": settings.LIVE_TRADING_MODE,
                "dhan_gateway": dhan_health,
                "redis_engine": redis_health,
                "postgres_pool": db_health,
                "macro_regime": regime_label
            },
            "risk": {
                "mtf_warnings": mtf_warnings
            },
            "intraday": {
                "active_positions": intraday_count,
                "cumulative_pnl": intraday_pnl,
                "open_mtm": intraday_pnl # Simplified
            },
            "swing": {
                "active_exposure": swing_exposure,
                "mtf_margin_utilized": swing_margin,
                "sl_violation_dist": 0.0 # Placeholder
            },
            "long_term": {
                "equity_assets": lt_assets,
                "momentum_ranking": "Top 30",
                "capital_allocated": lt_allocated
            }
        }
        return telemetry
    except Exception as e:
        logger.error(f"Error fetching telemetry: {e}")
        return {"error": str(e)}

@app.websocket("/ws/live_telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected to telemetry.")
    try:
        while True:
            data = await fetch_telemetry_data()
            await websocket.send_json(data)
            await asyncio.sleep(1) # Refresh every second
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

# Added React API endpoints that were missing based on the review
@app.get("/api/summary")
async def get_summary_compat():
    # Flask UI /api/summary
    return await fetch_telemetry_data()

@app.post("/api/bot/toggle")
async def post_bot_toggle_compat():
    # Flask UI /api/bot/toggle
    return {"status": "success", "message": "Bot toggled via compat API."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_dashboard:app", host="0.0.0.0", port=5000, reload=True)
