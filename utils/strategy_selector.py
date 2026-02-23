"""
Strategy Selector - Intelligently selects best trading strategy for each stock
Based on market conditions, volatility, trend strength, and technical setup
"""
import logging
from typing import Dict, List
import pandas as pd
import numpy as np
from config import settings

logger = logging.getLogger(__name__)


class StrategySelector:
    """Selects optimal trading strategy based on market conditions"""
    
    # Strategy categories
    TREND_STRATEGIES = [
        'VWAP_MOMENTUM', 'EMA_CROSSOVER', 'SUPERTREND', 'DONCHIAN_BREAKOUT',
        'ADX_TREND', 'PARABOLIC_SAR'
    ]
    
    MEAN_REVERSION_STRATEGIES = [
        'BOLLINGER_REVERSAL', 'RSI_REVERSAL', 'STOCHASTIC_REVERSAL',
        'WILLIAMS_R', 'CCI_REVERSAL'
    ]
    
    MOMENTUM_STRATEGIES = [
        'MACD_MOMENTUM', 'ROC_MOMENTUM', 'MOMENTUM_BREAKOUT',
        'VOLUME_BREAKOUT', 'PRICE_CHANNEL'
    ]
    
    VOLATILITY_STRATEGIES = [
        'ATR_BREAKOUT', 'KELTNER_CHANNEL', 'VOLATILITY_BREAKOUT',
        'SQUEEZE_MOMENTUM'
    ]
    
    PATTERN_STRATEGIES = [
        'CANDLESTICK_PATTERNS', 'CHART_PATTERNS', 'HARMONIC_PATTERNS',
        'ELLIOTT_WAVE'
    ]
    
    ALL_STRATEGIES = (
        TREND_STRATEGIES + MEAN_REVERSION_STRATEGIES + 
        MOMENTUM_STRATEGIES + VOLATILITY_STRATEGIES + PATTERN_STRATEGIES
    )
    
    def __init__(self):
        self.strategy_cache = {}  # Cache strategy selections
    
    def analyze_market_condition(self, df: pd.DataFrame) -> Dict:
        """
        Analyze current market condition for the stock
        
        Args:
            df: OHLCV dataframe
        
        Returns:
            Dict with market characteristics
        """
        if df.empty or len(df) < 50:
            return {'condition': 'UNKNOWN'}
        
        try:
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # Trend strength (ADX-like)
            price_change = close.diff().abs()
            volatility = price_change.rolling(14).std()
            trend_strength = price_change.rolling(14).mean() / (volatility + 1e-9)
            current_trend_strength = trend_strength.iloc[-1]
            
            # Trend direction
            sma_20 = close.rolling(20).mean()
            sma_50 = close.rolling(50).mean() if len(df) >= 50 else sma_20
            
            is_uptrend = close.iloc[-1] > sma_20.iloc[-1] and sma_20.iloc[-1] > sma_50.iloc[-1]
            is_downtrend = close.iloc[-1] < sma_20.iloc[-1] and sma_20.iloc[-1] < sma_50.iloc[-1]
            
            # Volatility (ATR)
            tr = pd.concat([
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            volatility_pct = (atr.iloc[-1] / close.iloc[-1]) * 100
            
            # Volume analysis
            avg_volume = volume.rolling(20).mean()
            volume_ratio = volume.iloc[-1] / avg_volume.iloc[-1] if avg_volume.iloc[-1] > 0 else 1
            
            # RSI
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # Determine market condition
            if current_trend_strength > 1.5:
                if is_uptrend:
                    condition = 'STRONG_UPTREND'
                elif is_downtrend:
                    condition = 'STRONG_DOWNTREND'
                else:
                    condition = 'TRENDING'
            elif volatility_pct > 3:
                condition = 'HIGH_VOLATILITY'
            elif current_rsi < 30 or current_rsi > 70:
                condition = 'OVERSOLD' if current_rsi < 30 else 'OVERBOUGHT'
            elif abs(close.iloc[-1] - sma_20.iloc[-1]) / sma_20.iloc[-1] < 0.01:
                condition = 'RANGING'
            else:
                condition = 'NEUTRAL'
            
            return {
                'condition': condition,
                'trend_strength': current_trend_strength,
                'is_uptrend': is_uptrend,
                'is_downtrend': is_downtrend,
                'volatility_pct': volatility_pct,
                'rsi': current_rsi,
                'volume_ratio': volume_ratio,
                'price': close.iloc[-1]
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market condition: {e}")
            return {'condition': 'UNKNOWN'}
    
    def select_strategy(self, symbol: str, df: pd.DataFrame) -> str:
        """
        Select best trading strategy for the given stock
        
        Args:
            symbol: Stock symbol
            df: OHLCV dataframe
        
        Returns:
            Strategy name to use
        """
        if not settings.AUTO_STRATEGY_SELECTION:
            return settings.DEFAULT_STRATEGY
        
        # Analyze market condition
        market_info = self.analyze_market_condition(df)
        condition = market_info.get('condition', 'UNKNOWN')
        
        logger.info(f"{symbol}: Market condition = {condition}")
        
        # Select strategy based on condition
        if condition == 'STRONG_UPTREND':
            # Use trend-following strategies
            strategies = self.TREND_STRATEGIES
            selected = np.random.choice(['VWAP_MOMENTUM', 'EMA_CROSSOVER', 'SUPERTREND'])
            
        elif condition == 'STRONG_DOWNTREND':
            # Avoid or use short strategies (for now, hold)
            selected = 'HOLD'
            
        elif condition in ['OVERSOLD', 'OVERBOUGHT']:
            # Use mean reversion strategies
            strategies = self.MEAN_REVERSION_STRATEGIES
            selected = np.random.choice(['BOLLINGER_REVERSAL', 'RSI_REVERSAL', 'STOCHASTIC_REVERSAL'])
            
        elif condition == 'HIGH_VOLATILITY':
            # Use volatility strategies
            strategies = self.VOLATILITY_STRATEGIES
            selected = np.random.choice(['ATR_BREAKOUT', 'KELTNER_CHANNEL', 'VOLATILITY_BREAKOUT'])
            
        elif condition == 'RANGING':
            # Use range-bound strategies
            selected = np.random.choice(['BOLLINGER_REVERSAL', 'RSI_REVERSAL'])
            
        elif condition == 'TRENDING':
            # Use momentum strategies
            strategies = self.MOMENTUM_STRATEGIES
            selected = np.random.choice(['MACD_MOMENTUM', 'MOMENTUM_BREAKOUT', 'VOLUME_BREAKOUT'])
            
        else:
            # Default to VWAP momentum
            selected = 'VWAP_MOMENTUM'
        
        logger.info(f"{symbol}: Selected strategy = {selected}")
        return selected
    
    def get_all_strategies(self) -> List[str]:
        """Get list of all available strategies"""
        return self.ALL_STRATEGIES
    
    def get_strategy_description(self, strategy_name: str) -> str:
        """Get description of a strategy"""
        descriptions = {
            # Trend Strategies
            'VWAP_MOMENTUM': 'Volume-weighted average price momentum with Bollinger Bands',
            'EMA_CROSSOVER': 'Exponential moving average crossover (fast/slow)',
            'SUPERTREND': 'Supertrend indicator based on ATR',
            'DONCHIAN_BREAKOUT': 'Breakout of Donchian channel (highest high/lowest low)',
            'ADX_TREND': 'Average Directional Index for trend strength',
            'PARABOLIC_SAR': 'Parabolic Stop and Reverse indicator',
            
            # Mean Reversion
            'BOLLINGER_REVERSAL': 'Mean reversion at Bollinger Band extremes',
            'RSI_REVERSAL': 'Reversal trading based on RSI oversold/overbought',
            'STOCHASTIC_REVERSAL': 'Stochastic oscillator reversal signals',
            'WILLIAMS_R': 'Williams %R reversal at extremes',
            'CCI_REVERSAL': 'Commodity Channel Index reversal',
            
            # Momentum
            'MACD_MOMENTUM': 'MACD histogram momentum trading',
            'ROC_MOMENTUM': 'Rate of Change momentum indicator',
            'MOMENTUM_BREAKOUT': 'Price momentum breakout strategy',
            'VOLUME_BREAKOUT': 'Volume surge with price breakout',
            'PRICE_CHANNEL': 'Price channel breakout',
            
            # Volatility
            'ATR_BREAKOUT': 'Average True Range based breakout',
            'KELTNER_CHANNEL': 'Keltner Channel breakout/reversal',
            'VOLATILITY_BREAKOUT': 'Volatility expansion breakout',
            'SQUEEZE_MOMENTUM': 'Squeeze momentum (Bollinger + Keltner)',
            
            # Patterns
            'CANDLESTICK_PATTERNS': 'Japanese candlestick pattern recognition',
            'CHART_PATTERNS': 'Chart pattern detection (head & shoulders, triangles)',
            'HARMONIC_PATTERNS': 'Harmonic pattern trading (Gartley, Butterfly)',
            'ELLIOTT_WAVE': 'Elliott Wave pattern recognition'
        }
        
        return descriptions.get(strategy_name, 'Custom strategy')
