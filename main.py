"""
PRIMA PRO - Professional Trading Bot
Integrates: Market Scanner, Strategy Selector, Risk Manager, Pattern Recognition
"""
import time
from datetime import datetime, timedelta
import logging
import pandas as pd
from kiteconnect import KiteConnect

from config import settings
from data.database import init_db, get_session, Position, Trade
from utils.auth import get_kite_client, load_access_token
from utils.paper_trading import PaperTradingEngine
from utils.market_scanner import MarketScanner
from utils.strategy_selector import StrategySelector
from utils.risk_manager import RiskManager
from utils.pattern_recognizer import PatternRecognizer
from strategies.vwap_momentum import VwapMomentumStrategy

# Setup logging
logging.basicConfig(
    filename=settings.LOG_FILE,
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger("").addHandler(console)

logger = logging.getLogger(__name__)


def fetch_candles(kite: KiteConnect, symbol: str, interval: str = None) -> pd.DataFrame:
    """Fetch historical candle data"""
    if interval is None:
        interval = settings.CANDLE_INTERVAL
    
    to_dt = datetime.now()
    from_dt = to_dt - timedelta(minutes=settings.CANDLE_LOOKBACK_MINUTES)
    
    try:
        # Get instrument token
        q = kite.quote(f"NSE:{symbol}")
        token = q[f"NSE:{symbol}"]["instrument_token"]
        
        data = kite.historical_data(
            instrument_token=token,
            from_date=from_dt,
            to_date=to_dt,
            interval=interval,
            continuous=False,
            oi=False,
        )
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        return df
    
    except Exception as e:
        logger.error(f"Error fetching candles for {symbol}: {e}")
        return pd.DataFrame()


def main():
    logger.info("="*60)
    logger.info("PRIMA PRO TRADING BOT - PROFESSIONAL EDITION")
    logger.info("="*60)
    
    # Initialize database
    init_db()
    
    # Load access token
    access_token = load_access_token()
    if not access_token:
        logger.error("No access_token found. Run scripts/auto_authenticate.py first.")
        return
    
    # Initialize Kite client
    kite = get_kite_client(access_token)
    
    # Initialize components
    engine = PaperTradingEngine()
    scanner = MarketScanner(kite)
    selector = StrategySelector()
    risk_manager = RiskManager()
    pattern_recognizer = PatternRecognizer()
    
    # Strategy instances (we'll dynamically select which to use)
    vwap_strategy = VwapMomentumStrategy(capital=settings.INITIAL_CAPITAL)
    
    logger.info(f"Paper Trading Mode: {settings.PAPER_TRADING_MODE}")
    logger.info(f"Initial Capital: ₹{settings.INITIAL_CAPITAL:,.2f}")
    logger.info(f"Scan Mode: {'ENTIRE MARKET' if settings.SCAN_ENTIRE_MARKET else 'WATCHLIST'}")
    logger.info(f"Max Positions: {settings.MAX_CONCURRENT_POSITIONS}")
    logger.info("="*60)
    
    bot_running = True  # Control flag (can be toggled from dashboard)
    
    while bot_running:
        try:
            # Check if it's market hours (optional)
            current_time = datetime.now().time()
            market_open = datetime.strptime("09:15", "%H:%M").time()
            market_close = datetime.strptime("15:30", "%H:%M").time()
            
            if not (market_open <= current_time <= market_close):
                logger.info("Outside market hours. Waiting...")
                time.sleep(60)  # Check every minute
                continue
            
            # STEP 1: Scan market for opportunities
            logger.info("\n--- Scanning Market ---")
            opportunities = scanner.scan_for_opportunities()
            
            if not opportunities:
                logger.info("No opportunities found. Waiting...")
                time.sleep(settings.REFRESH_SECONDS)
                continue
            
            logger.info(f"Found {len(opportunities)} opportunities")
            
            # STEP 2: Check if we can open new positions
            can_open, reason = risk_manager.can_open_new_position()
            if not can_open:
                logger.warning(f"Cannot open new position: {reason}")
                
                # Still update existing positions
                with get_session() as session:
                    positions = session.query(Position).filter(Position.quantity > 0).all()
                    for pos in positions:
                        # Get current price
                        ltp_data = kite.ltp(f"NSE:{pos.symbol}")
                        current_price = ltp_data[f"NSE:{pos.symbol}"]['last_price']
                        
                        # Update trailing stop
                        risk_manager.update_trailing_stop(pos.symbol, current_price, pos.avg_price)
                        
                        # Check if should close
                        should_close, close_reason = risk_manager.should_close_position(
                            pos.symbol, current_price, pos.avg_price
                        )
                        
                        if should_close:
                            logger.info(f"Closing {pos.symbol}: {close_reason}")
                            engine.sell(pos.symbol, pos.quantity, current_price)
                            risk_manager.cleanup_closed_position(pos.symbol)
                
                time.sleep(settings.REFRESH_SECONDS)
                continue
            
            # STEP 3: Process each opportunity
            with get_session() as session:
                for opp in opportunities[:5]:  # Process top 5 opportunities
                    symbol = opp['symbol']
                    
                    logger.info(f"\n--- Analyzing {symbol} ---")
                    logger.info(f"Signals: {', '.join(opp['signals'])}")
                    logger.info(f"Signal Strength: {opp['signal_strength']}")
                    
                    # Fetch candle data
                    df = fetch_candles(kite, symbol)
                    if df.empty:
                        logger.warning(f"No candle data for {symbol}")
                        continue
                    
                    # Auto-select strategy
                    strategy_name = selector.select_strategy(symbol, df)
                    logger.info(f"Selected Strategy: {strategy_name}")
                    
                    # Get detailed technical scan
                    detailed_scan = scanner.get_detailed_scan(symbol, df)
                    if detailed_scan:
                        logger.info(f"RSI: {detailed_scan.get('rsi', 0):.1f} ({detailed_scan.get('rsi_signal', 'N/A')})")
                        logger.info(f"MACD: {detailed_scan.get('macd_crossover', 'N/A')}")
                        logger.info(f"Trend: {detailed_scan.get('trend', 'N/A')}")
                    
                    # Pattern analysis
                    patterns = pattern_recognizer.analyze_all_patterns(symbol, df)
                    if patterns.get('candlestick_patterns'):
                        logger.info(f"Patterns: {[p['pattern'] for p in patterns['candlestick_patterns']]}")
                    
                    # Check if already have position
                    pos = session.query(Position).filter(Position.symbol == symbol).one_or_none()
                    current_qty = pos.quantity if pos else 0
                    entry_price = pos.avg_price if pos and pos.quantity > 0 else None
                    
                    # Generate signal using VWAP strategy (can switch to other strategies)
                    signal = vwap_strategy.generate_signal(
                        symbol=symbol,
                        df=df,
                        current_position_qty=current_qty,
                        entry_price=entry_price
                    )
                    
                    # Get current price
                    ltp_data = kite.ltp(f"NSE:{symbol}")
                    current_price = ltp_data[f"NSE:{symbol}"]['last_price']
                    
                    # Calculate ATR for risk management
                    if len(df) >= 14:
                        high = df['high']
                        low = df['low']
                        close = df['close']
                        tr = pd.concat([
                            high - low,
                            (high - close.shift()).abs(),
                            (low - close.shift()).abs()
                        ], axis=1).max(axis=1)
                        atr = tr.rolling(14).mean().iloc[-1]
                    else:
                        atr = current_price * 0.02  # 2% fallback
                    
                    # Execute BUY signal
                    if signal.action == "BUY" and current_qty == 0:
                        # Calculate position size using risk manager
                        quantity = risk_manager.calculate_position_size(
                            symbol, current_price, atr, engine.cash
                        )
                        
                        if quantity > 0:
                            logger.info(f"📈 BUY {symbol} x {quantity} @ ₹{current_price:.2f}")
                            logger.info(f"Reason: {signal.reason}")
                            
                            trade = engine.buy(symbol, quantity, current_price)
                            if trade:
                                # Set risk management levels
                                risk_manager.set_stop_loss(symbol, current_price, atr)
                                risk_manager.set_take_profit(symbol, current_price, atr)
                                
                                logger.info(f"✓ Position opened")
                                logger.info(f"  Stop Loss: ₹{risk_manager.stop_losses[symbol]:.2f}")
                                logger.info(f"  Take Profit: ₹{risk_manager.take_profits[symbol]:.2f}")
                    
                    # Execute SELL signal
                    elif signal.action == "SELL" and current_qty > 0:
                        logger.info(f"📉 SELL {symbol} x {signal.quantity} @ ₹{current_price:.2f}")
                        logger.info(f"Reason: {signal.reason}")
                        
                        trade = engine.sell(symbol, signal.quantity, current_price)
                        if trade:
                            logger.info(f"✓ Position closed. P&L: ₹{trade.pnl:.2f}")
                            risk_manager.cleanup_closed_position(symbol)
                    
                    # Update trailing stops for existing positions
                    elif current_qty > 0:
                        risk_manager.update_trailing_stop(symbol, current_price, entry_price)
                        
                        # Check if should close based on risk rules
                        should_close, close_reason = risk_manager.should_close_position(
                            symbol, current_price, entry_price
                        )
                        
                        if should_close:
                            logger.info(f"🛑 Closing {symbol}: {close_reason}")
                            trade = engine.sell(symbol, current_qty, current_price)
                            if trade:
                                logger.info(f"✓ Position closed. P&L: ₹{trade.pnl:.2f}")
                                risk_manager.cleanup_closed_position(symbol)
            
            # Update unrealized P&L for all positions
            with get_session() as session:
                positions = session.query(Position).filter(Position.quantity > 0).all()
                symbols = [f"NSE:{pos.symbol}" for pos in positions]
                
                if symbols:
                    ltp_data = kite.ltp(symbols)
                    ltp_map = {
                        pos.symbol: ltp_data[f"NSE:{pos.symbol}"]['last_price']
                        for pos in positions
                    }
                    engine.update_unrealized_pnls(ltp_map)
            
            # Display portfolio summary
            risk_metrics = risk_manager.get_portfolio_risk()
            logger.info(f"\n--- Portfolio Summary ---")
            logger.info(f"Positions: {risk_metrics['total_positions']}")
            logger.info(f"Exposure: ₹{risk_metrics['total_exposure']:,.2f}")
            logger.info(f"Margin Used: {risk_metrics['margin_used_pct']:.1f}%")
            logger.info(f"Unrealized P&L: ₹{risk_metrics['unrealized_pnl']:,.2f}")
            logger.info(f"Realized P&L: ₹{risk_metrics['realized_pnl']:,.2f}")
            
            # Sleep before next iteration
            logger.info(f"\nWaiting {settings.REFRESH_SECONDS} seconds...")
            time.sleep(settings.REFRESH_SECONDS)
        
        except KeyboardInterrupt:
            logger.info("\n⏹ Stopping bot...")
            bot_running = False
            break
        
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
            time.sleep(5)
    
    logger.info("="*60)
    logger.info("PRIMA PRO TRADING BOT STOPPED")
    logger.info("="*60)


if __name__ == "__main__":
    main()
