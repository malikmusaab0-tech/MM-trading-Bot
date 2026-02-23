"""
Enhanced Dashboard - Professional trading dashboard with charts, kill switch, stock search
"""
import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, render_template, jsonify, request
from sqlalchemy import func
from data.database import get_session, Trade, Position, PortfolioSnapshot
from config import settings
from utils.market_scanner import MarketScanner
from utils.pattern_recognizer import PatternRecognizer
from utils.risk_manager import RiskManager
from utils.auth import get_kite_client, load_access_token
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")

# Global instances
scanner = None
pattern_recognizer = PatternRecognizer()
risk_manager = RiskManager()

# Bot control
bot_running = True  # Global flag for kill switch


@app.route("/")
def dashboard():
    """Main dashboard page"""
    return render_template("enhanced_dashboard.html")


@app.route("/api/portfolio")
def get_portfolio():
    """Get portfolio summary"""
    with get_session() as session:
        latest_snap = session.query(PortfolioSnapshot).order_by(
            PortfolioSnapshot.timestamp.desc()
        ).first()
        
        equity = latest_snap.equity if latest_snap else settings.INITIAL_CAPITAL
        cash = latest_snap.cash if latest_snap else settings.INITIAL_CAPITAL
        
        positions = session.query(Position).filter(Position.quantity > 0).all()
        
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        total_realized = sum(p.realized_pnl for p in positions)
        total_pnl = total_unrealized + total_realized
        
        # Calculate returns
        returns_pct = ((equity - settings.INITIAL_CAPITAL) / settings.INITIAL_CAPITAL) * 100
        
        return jsonify({
            'equity': round(equity, 2),
            'cash': round(cash, 2),
            'unrealized_pnl': round(total_unrealized, 2),
            'realized_pnl': round(total_realized, 2),
            'total_pnl': round(total_pnl, 2),
            'returns_pct': round(returns_pct, 2),
            'num_positions': len(positions),
            'bot_running': bot_running
        })


@app.route("/api/positions")
def get_positions():
    """Get all current positions"""
    with get_session() as session:
        positions = session.query(Position).filter(Position.quantity > 0).all()
        
        result = []
        for pos in positions:
            pnl_pct = ((pos.unrealized_pnl / (pos.avg_price * pos.quantity)) * 100) if pos.quantity > 0 else 0
            
            # Get risk info
            stop_loss = risk_manager.stop_losses.get(pos.symbol)
            trailing_stop = risk_manager.trailing_stops.get(pos.symbol)
            take_profit = risk_manager.take_profits.get(pos.symbol)
            
            result.append({
                'symbol': pos.symbol,
                'quantity': pos.quantity,
                'avg_price': round(pos.avg_price, 2),
                'current_price': round(pos.avg_price + (pos.unrealized_pnl / pos.quantity), 2) if pos.quantity > 0 else 0,
                'unrealized_pnl': round(pos.unrealized_pnl, 2),
                'realized_pnl': round(pos.realized_pnl, 2),
                'pnl_pct': round(pnl_pct, 2),
                'stop_loss': round(stop_loss, 2) if stop_loss else None,
                'trailing_stop': round(trailing_stop, 2) if trailing_stop else None,
                'take_profit': round(take_profit, 2) if take_profit else None
            })
        
        return jsonify(result)


@app.route("/api/trades")
def get_trades():
    """Get recent trades"""
    limit = request.args.get('limit', 50, type=int)
    
    with get_session() as session:
        trades = session.query(Trade).order_by(
            Trade.timestamp.desc()
        ).limit(limit).all()
        
        result = []
        for trade in trades:
            result.append({
                'id': trade.id,
                'symbol': trade.symbol,
                'side': trade.side,
                'quantity': trade.quantity,
                'price': round(trade.price, 2),
                'pnl': round(trade.pnl, 2) if trade.pnl else 0,
                'timestamp': trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify(result)


@app.route("/api/stats")
def get_stats():
    """Get trading statistics"""
    with get_session() as session:
        total_trades = session.query(func.count(Trade.id)).scalar()
        
        winning_trades = session.query(func.count(Trade.id)).filter(
            Trade.pnl > 0
        ).scalar()
        
        losing_trades = session.query(func.count(Trade.id)).filter(
            Trade.pnl < 0
        ).scalar()
        
        win_rate = (winning_trades / total_trades * 100) if total_trades else 0
        
        # Best and worst trades
        best_trade = session.query(func.max(Trade.pnl)).scalar() or 0
        worst_trade = session.query(func.min(Trade.pnl)).scalar() or 0
        
        # Average win/loss
        avg_win = session.query(func.avg(Trade.pnl)).filter(Trade.pnl > 0).scalar() or 0
        avg_loss = session.query(func.avg(Trade.pnl)).filter(Trade.pnl < 0).scalar() or 0
        
        return jsonify({
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'best_trade': round(best_trade, 2),
            'worst_trade': round(worst_trade, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0
        })


@app.route("/api/stock/<symbol>")
def get_stock_details(symbol):
    """Get detailed stock information with chart data"""
    try:
        access_token = load_access_token()
        if not access_token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        kite = get_kite_client(access_token)
        
        # Get quote
        quote = kite.quote(f"NSE:{symbol}")
        data = quote[f"NSE:{symbol}"]
        
        # Get historical data
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=30)
        
        instrument_token = data['instrument_token']
        candles = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_dt,
            to_date=to_dt,
            interval='day',
            continuous=False,
            oi=False
        )
        
        # Convert to format for charting
        chart_data = []
        for candle in candles:
            chart_data.append({
                'date': candle['date'].strftime('%Y-%m-%d'),
                'open': candle['open'],
                'high': candle['high'],
                'low': candle['low'],
                'close': candle['close'],
                'volume': candle['volume']
            })
        
        # Pattern analysis
        df = pd.DataFrame(candles)
        patterns = pattern_recognizer.analyze_all_patterns(symbol, df)
        
        return jsonify({
            'symbol': symbol,
            'ltp': data['last_price'],
            'ohlc': data['ohlc'],
            'volume': data['volume'],
            'chart_data': chart_data,
            'patterns': patterns
        })
    
    except Exception as e:
        logger.error(f"Error getting stock details for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/search")
def search_stocks():
    """Search for stocks"""
    query = request.args.get('q', '').upper()
    
    if len(query) < 2:
        return jsonify([])
    
    try:
        access_token = load_access_token()
        if not access_token:
            return jsonify([])
        
        kite = get_kite_client(access_token)
        instruments = kite.instruments("NSE")
        
        # Filter equity stocks matching query
        matches = []
        for inst in instruments:
            if (inst['instrument_type'] == 'EQ' and 
                query in inst['tradingsymbol']):
                matches.append({
                    'symbol': inst['tradingsymbol'],
                    'name': inst['name']
                })
                
                if len(matches) >= 10:  # Limit results
                    break
        
        return jsonify(matches)
    
    except Exception as e:
        logger.error(f"Error searching stocks: {e}")
        return jsonify([])


@app.route("/api/kill_switch", methods=['POST'])
def kill_switch():
    """Emergency kill switch - close all positions"""
    global bot_running
    
    try:
        bot_running = False  # Stop bot from opening new positions
        
        access_token = load_access_token()
        if not access_token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        kite = get_kite_client(access_token)
        
        # Get all open positions
        with get_session() as session:
            positions = session.query(Position).filter(Position.quantity > 0).all()
            
            closed = []
            for pos in positions:
                try:
                    if settings.PAPER_TRADING_MODE:
                        # Paper trading - just update database
                        ltp_data = kite.ltp(f"NSE:{pos.symbol}")
                        ltp = ltp_data[f"NSE:{pos.symbol}"]['last_price']
                        
                        # Create sell trade
                        pnl = (ltp - pos.avg_price) * pos.quantity
                        trade = Trade(
                            symbol=pos.symbol,
                            side='SELL',
                            quantity=pos.quantity,
                            price=ltp,
                            pnl=pnl,
                            paper=True
                        )
                        session.add(trade)
                        
                        # Update position
                        pos.quantity = 0
                        pos.realized_pnl += pnl
                        
                        closed.append({
                            'symbol': pos.symbol,
                            'quantity': pos.quantity,
                            'pnl': round(pnl, 2)
                        })
                    else:
                        # Real trading - place actual orders
                        order_id = kite.place_order(
                            variety=kite.VARIETY_REGULAR,
                            exchange=kite.EXCHANGE_NSE,
                            tradingsymbol=pos.symbol,
                            transaction_type=kite.TRANSACTION_TYPE_SELL,
                            quantity=pos.quantity,
                            product=kite.PRODUCT_MIS,
                            order_type=kite.ORDER_TYPE_MARKET
                        )
                        closed.append({
                            'symbol': pos.symbol,
                            'order_id': order_id
                        })
                
                except Exception as e:
                    logger.error(f"Error closing position {pos.symbol}: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Closed {len(closed)} positions',
            'closed_positions': closed
        })
    
    except Exception as e:
        logger.error(f"Kill switch error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/toggle_bot", methods=['POST'])
def toggle_bot():
    """Toggle bot on/off"""
    global bot_running
    bot_running = not bot_running
    
    return jsonify({
        'success': True,
        'bot_running': bot_running,
        'message': 'Bot started' if bot_running else 'Bot stopped'
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.DASHBOARD_PORT, debug=True)
