"""
Market Scanner - Scans entire NSE market for trading opportunities
Filters stocks based on volume, liquidity, price action, and technical indicators
"""
import logging
from typing import List, Dict
import pandas as pd
from kiteconnect import KiteConnect
from config import settings

logger = logging.getLogger(__name__)


class MarketScanner:
    """Scans NSE market for trading opportunities"""
    
    def __init__(self, kite: KiteConnect):
        self.kite = kite
        self.instruments = []
        self.eligible_stocks = []
        self._load_instruments()
    
    def _load_instruments(self):
        """Load all NSE equity instruments"""
        try:
            all_instruments = self.kite.instruments("NSE")
            
            # Filter for equity stocks only
            self.instruments = [
                inst for inst in all_instruments
                if inst['instrument_type'] == 'EQ' and inst['segment'] == 'NSE'
            ]
            
            logger.info(f"Loaded {len(self.instruments)} NSE equity instruments")
            
        except Exception as e:
            logger.error(f"Failed to load instruments: {e}")
            self.instruments = []
    
    def get_liquid_stocks(self) -> List[str]:
        """
        Get list of liquid stocks based on volume and price criteria
        
        Returns:
            List of stock symbols meeting liquidity criteria
        """
        try:
            # Get quotes for all stocks (in batches to avoid rate limits)
            symbols = [f"NSE:{inst['tradingsymbol']}" for inst in self.instruments]
            
            liquid_stocks = []
            batch_size = 500  # Kite API limit
            
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                
                try:
                    quotes = self.kite.quote(batch)
                    
                    for symbol, data in quotes.items():
                        tradingsymbol = symbol.replace("NSE:", "")
                        
                        ltp = data.get('last_price', 0)
                        volume = data.get('volume', 0)
                        
                        # Apply filters
                        if (settings.MIN_STOCK_PRICE <= ltp <= settings.MAX_STOCK_PRICE and
                            volume >= settings.MIN_VOLUME):
                            
                            # Calculate turnover (price * volume)
                            turnover_cr = (ltp * volume) / 10000000  # Convert to crores
                            
                            if turnover_cr >= settings.MIN_LIQUIDITY_CRORE:
                                liquid_stocks.append(tradingsymbol)
                    
                except Exception as e:
                    logger.warning(f"Error fetching quotes for batch {i}: {e}")
                    continue
            
            logger.info(f"Found {len(liquid_stocks)} liquid stocks")
            return liquid_stocks
            
        except Exception as e:
            logger.error(f"Error in get_liquid_stocks: {e}")
            return settings.DEFAULT_WATCHLIST
    
    def scan_for_opportunities(self, stocks: List[str] = None) -> List[Dict]:
        """
        Scan stocks for trading opportunities using multiple technical indicators
        
        Args:
            stocks: List of symbols to scan. If None, uses entire market
        
        Returns:
            List of opportunities with stock symbol, signal strength, and indicators
        """
        if stocks is None:
            if settings.SCAN_ENTIRE_MARKET:
                stocks = self.get_liquid_stocks()
            else:
                stocks = settings.DEFAULT_WATCHLIST
        
        opportunities = []
        
        for symbol in stocks:
            try:
                # Get quick indicators from quote
                quote = self.kite.quote(f"NSE:{symbol}")
                data = quote[f"NSE:{symbol}"]
                
                ohlc = data.get('ohlc', {})
                ltp = data.get('last_price', 0)
                volume = data.get('volume', 0)
                avg_volume = data.get('average_price', 0) * volume if volume > 0 else 0
                
                # Quick filters
                signals = []
                signal_strength = 0
                
                # Volume surge
                if volume > avg_volume * 1.5:
                    signals.append("VOLUME_SURGE")
                    signal_strength += 1
                
                # Price action near day low (potential bounce)
                day_low = ohlc.get('low', ltp)
                if ltp <= day_low * 1.02:  # Within 2% of day low
                    signals.append("NEAR_DAY_LOW")
                    signal_strength += 1
                
                # Price action near day high (potential breakout)
                day_high = ohlc.get('high', ltp)
                if ltp >= day_high * 0.98:  # Within 2% of day high
                    signals.append("NEAR_DAY_HIGH")
                    signal_strength += 1
                
                # Strong intraday move
                day_open = ohlc.get('open', ltp)
                if day_open > 0:
                    change_pct = ((ltp - day_open) / day_open) * 100
                    if abs(change_pct) > 2:  # 2%+ move
                        signals.append(f"STRONG_MOVE_{'+' if change_pct > 0 else '-'}{abs(change_pct):.1f}%")
                        signal_strength += 2
                
                # If we have signals, add to opportunities
                if signal_strength >= 2:  # At least 2 signals
                    opportunities.append({
                        'symbol': symbol,
                        'ltp': ltp,
                        'volume': volume,
                        'signals': signals,
                        'signal_strength': signal_strength,
                        'change_pct': ((ltp - day_open) / day_open * 100) if day_open > 0 else 0
                    })
            
            except Exception as e:
                logger.debug(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by signal strength
        opportunities.sort(key=lambda x: x['signal_strength'], reverse=True)
        
        logger.info(f"Found {len(opportunities)} trading opportunities")
        return opportunities[:50]  # Return top 50
    
    def get_detailed_scan(self, symbol: str, df: pd.DataFrame) -> Dict:
        """
        Perform detailed technical analysis on a stock
        
        Args:
            symbol: Stock symbol
            df: OHLCV dataframe
        
        Returns:
            Dict with detailed technical indicators
        """
        if df.empty or len(df) < 30:
            return {}
        
        try:
            # Calculate all indicators
            close = df['close']
            
            # RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=settings.RSI_PERIOD).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=settings.RSI_PERIOD).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # MACD
            ema_fast = close.ewm(span=settings.MACD_FAST).mean()
            ema_slow = close.ewm(span=settings.MACD_SLOW).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=settings.MACD_SIGNAL).mean()
            macd_hist = macd_line - signal_line
            
            # ADX (simplified)
            high = df['high']
            low = df['low']
            tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(settings.ADX_PERIOD).mean()
            
            # Stochastic
            low_min = low.rolling(settings.STOCH_K).min()
            high_max = high.rolling(settings.STOCH_K).max()
            stoch_k = 100 * (close - low_min) / (high_max - low_min)
            stoch_d = stoch_k.rolling(settings.STOCH_D).mean()
            
            # Support/Resistance levels
            recent_high = high.tail(20).max()
            recent_low = low.tail(20).min()
            
            current_price = close.iloc[-1]
            
            return {
                'symbol': symbol,
                'price': current_price,
                'rsi': current_rsi,
                'rsi_signal': 'OVERSOLD' if current_rsi < settings.RSI_OVERSOLD else 'OVERBOUGHT' if current_rsi > settings.RSI_OVERBOUGHT else 'NEUTRAL',
                'macd': macd_line.iloc[-1],
                'macd_signal': signal_line.iloc[-1],
                'macd_histogram': macd_hist.iloc[-1],
                'macd_crossover': 'BULLISH' if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0 else 'BEARISH' if macd_hist.iloc[-1] < 0 and macd_hist.iloc[-2] >= 0 else 'NONE',
                'stoch_k': stoch_k.iloc[-1],
                'stoch_d': stoch_d.iloc[-1],
                'stoch_signal': 'OVERSOLD' if stoch_k.iloc[-1] < settings.STOCH_OVERSOLD else 'OVERBOUGHT' if stoch_k.iloc[-1] > settings.STOCH_OVERBOUGHT else 'NEUTRAL',
                'atr': atr.iloc[-1],
                'support': recent_low,
                'resistance': recent_high,
                'trend': 'BULLISH' if current_price > close.rolling(20).mean().iloc[-1] else 'BEARISH'
            }
            
        except Exception as e:
            logger.error(f"Error in detailed scan for {symbol}: {e}")
            return {}
