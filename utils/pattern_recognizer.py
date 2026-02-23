"""
Pattern Recognizer - Detects chart patterns, support/resistance, and price levels
"""
import logging
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from config import settings

logger = logging.getLogger(__name__)


class PatternRecognizer:
    """Recognizes chart patterns and calculates price levels"""
    
    def __init__(self):
        self.patterns_cache = {}
    
    def find_support_resistance(self, df: pd.DataFrame, lookback: int = 50) -> Dict:
        """
        Find support and resistance levels using pivot points
        
        Returns:
            Dict with support and resistance levels
        """
        if len(df) < lookback:
            return {}
        
        recent_df = df.tail(lookback)
        high = recent_df['high']
        low = recent_df['low']
        close = recent_df['close']
        
        # Find local maxima (resistance) and minima (support)
        resistance_levels = []
        support_levels = []
        
        for i in range(2, len(recent_df) - 2):
            # Resistance: high is higher than 2 candles before and after
            if (high.iloc[i] > high.iloc[i-1] and high.iloc[i] > high.iloc[i-2] and
                high.iloc[i] > high.iloc[i+1] and high.iloc[i] > high.iloc[i+2]):
                resistance_levels.append(high.iloc[i])
            
            # Support: low is lower than 2 candles before and after
            if (low.iloc[i] < low.iloc[i-1] and low.iloc[i] < low.iloc[i-2] and
                low.iloc[i] < low.iloc[i+1] and low.iloc[i] < low.iloc[i+2]):
                support_levels.append(low.iloc[i])
        
        # Cluster nearby levels
        def cluster_levels(levels, threshold=0.02):
            if not levels:
                return []
            levels_sorted = sorted(levels)
            clustered = []
            current_cluster = [levels_sorted[0]]
            
            for level in levels_sorted[1:]:
                if (level - current_cluster[-1]) / current_cluster[-1] < threshold:
                    current_cluster.append(level)
                else:
                    clustered.append(np.mean(current_cluster))
                    current_cluster = [level]
            
            clustered.append(np.mean(current_cluster))
            return clustered
        
        support_clustered = cluster_levels(support_levels)
        resistance_clustered = cluster_levels(resistance_levels)
        
        current_price = close.iloc[-1]
        
        # Find nearest support and resistance
        supports_below = [s for s in support_clustered if s < current_price]
        resistances_above = [r for r in resistance_clustered if r > current_price]
        
        nearest_support = max(supports_below) if supports_below else low.min()
        nearest_resistance = min(resistances_above) if resistances_above else high.max()
        
        return {
            'all_supports': support_clustered,
            'all_resistances': resistance_clustered,
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'current_price': current_price,
            'support_distance_pct': ((current_price - nearest_support) / current_price) * 100,
            'resistance_distance_pct': ((nearest_resistance - current_price) / current_price) * 100
        }
    
    def detect_candlestick_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect candlestick patterns in recent data
        
        Returns:
            List of detected patterns
        """
        if len(df) < 3:
            return []
        
        patterns = []
        
        # Get last 3 candles
        c0 = df.iloc[-3]  # 2 candles ago
        c1 = df.iloc[-2]  # 1 candle ago
        c2 = df.iloc[-1]  # Current candle
        
        # Doji
        if abs(c2['close'] - c2['open']) / (c2['high'] - c2['low'] + 1e-9) < 0.1:
            patterns.append({
                'pattern': 'DOJI',
                'signal': 'NEUTRAL',
                'strength': 'MEDIUM',
                'description': 'Indecision - potential reversal'
            })
        
        # Hammer (bullish)
        body = abs(c2['close'] - c2['open'])
        lower_shadow = min(c2['open'], c2['close']) - c2['low']
        upper_shadow = c2['high'] - max(c2['open'], c2['close'])
        
        if lower_shadow > 2 * body and upper_shadow < body and c2['close'] > c2['open']:
            patterns.append({
                'pattern': 'HAMMER',
                'signal': 'BULLISH',
                'strength': 'STRONG',
                'description': 'Bullish reversal pattern'
            })
        
        # Shooting Star (bearish)
        if upper_shadow > 2 * body and lower_shadow < body and c2['close'] < c2['open']:
            patterns.append({
                'pattern': 'SHOOTING_STAR',
                'signal': 'BEARISH',
                'strength': 'STRONG',
                'description': 'Bearish reversal pattern'
            })
        
        # Engulfing patterns
        if c2['close'] > c2['open'] and c1['close'] < c1['open']:
            # Bullish engulfing
            if c2['open'] < c1['close'] and c2['close'] > c1['open']:
                patterns.append({
                    'pattern': 'BULLISH_ENGULFING',
                    'signal': 'BULLISH',
                    'strength': 'VERY_STRONG',
                    'description': 'Strong bullish reversal'
                })
        
        if c2['close'] < c2['open'] and c1['close'] > c1['open']:
            # Bearish engulfing
            if c2['open'] > c1['close'] and c2['close'] < c1['open']:
                patterns.append({
                    'pattern': 'BEARISH_ENGULFING',
                    'signal': 'BEARISH',
                    'strength': 'VERY_STRONG',
                    'description': 'Strong bearish reversal'
                })
        
        # Morning Star (bullish)
        if (c0['close'] < c0['open'] and  # First candle red
            abs(c1['close'] - c1['open']) < (c0['high'] - c0['low']) * 0.3 and  # Second candle small
            c2['close'] > c2['open'] and c2['close'] > (c0['open'] + c0['close']) / 2):  # Third candle green
            patterns.append({
                'pattern': 'MORNING_STAR',
                'signal': 'BULLISH',
                'strength': 'VERY_STRONG',
                'description': 'Major bullish reversal'
            })
        
        # Evening Star (bearish)
        if (c0['close'] > c0['open'] and  # First candle green
            abs(c1['close'] - c1['open']) < (c0['high'] - c0['low']) * 0.3 and  # Second candle small
            c2['close'] < c2['open'] and c2['close'] < (c0['open'] + c0['close']) / 2):  # Third candle red
            patterns.append({
                'pattern': 'EVENING_STAR',
                'signal': 'BEARISH',
                'strength': 'VERY_STRONG',
                'description': 'Major bearish reversal'
            })
        
        return patterns
    
    def detect_chart_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect chart patterns (triangles, head & shoulders, etc.)
        
        Returns:
            List of detected chart patterns
        """
        if len(df) < 20:
            return []
        
        patterns = []
        recent_df = df.tail(20)
        high = recent_df['high']
        low = recent_df['low']
        close = recent_df['close']
        
        # Double Top/Bottom
        highs = high.rolling(3).max()
        lows = low.rolling(3).min()
        
        # Simple double top detection
        local_highs = []
        for i in range(2, len(highs)):
            if highs.iloc[i] == highs.iloc[i-2] and abs(highs.iloc[i] - highs.iloc[i-1]) / highs.iloc[i] > 0.02:
                local_highs.append(i)
        
        if len(local_highs) >= 2:
            patterns.append({
                'pattern': 'DOUBLE_TOP',
                'signal': 'BEARISH',
                'strength': 'STRONG',
                'description': 'Resistance level tested twice'
            })
        
        # Breakout detection
        ma_20 = close.rolling(20).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        if current_price > ma_20 * 1.02:  # 2% above MA
            patterns.append({
                'pattern': 'BREAKOUT_ABOVE_MA',
                'signal': 'BULLISH',
                'strength': 'MEDIUM',
                'description': f'Price broke above 20-MA (₹{ma_20:.2f})'
            })
        elif current_price < ma_20 * 0.98:  # 2% below MA
            patterns.append({
                'pattern': 'BREAKDOWN_BELOW_MA',
                'signal': 'BEARISH',
                'strength': 'MEDIUM',
                'description': f'Price broke below 20-MA (₹{ma_20:.2f})'
            })
        
        return patterns
    
    def calculate_price_targets(self, df: pd.DataFrame, entry_price: float) -> Dict:
        """
        Calculate price targets based on ATR and support/resistance
        
        Returns:
            Dict with target prices and stop loss
        """
        if len(df) < 20:
            return {}
        
        # Calculate ATR
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        # Get support/resistance
        sr_levels = self.find_support_resistance(df)
        
        # Calculate targets
        target_1 = entry_price + (atr * 1.0)  # 1 ATR
        target_2 = entry_price + (atr * 2.0)  # 2 ATR
        target_3 = sr_levels.get('nearest_resistance', entry_price + (atr * 3.0))
        
        stop_loss = max(
            entry_price - (atr * 1.0),  # 1 ATR below
            sr_levels.get('nearest_support', entry_price - (atr * 1.5))
        )
        
        return {
            'entry_price': entry_price,
            'target_1': target_1,
            'target_2': target_2,
            'target_3': target_3,
            'stop_loss': stop_loss,
            'atr': atr,
            'risk_reward_1': (target_1 - entry_price) / (entry_price - stop_loss) if entry_price > stop_loss else 0,
            'risk_reward_2': (target_2 - entry_price) / (entry_price - stop_loss) if entry_price > stop_loss else 0,
            'risk_reward_3': (target_3 - entry_price) / (entry_price - stop_loss) if entry_price > stop_loss else 0
        }
    
    def analyze_all_patterns(self, symbol: str, df: pd.DataFrame) -> Dict:
        """
        Comprehensive pattern analysis
        
        Returns:
            Dict with all pattern analysis
        """
        if len(df) < 20:
            return {'symbol': symbol, 'error': 'Insufficient data'}
        
        candlestick_patterns = self.detect_candlestick_patterns(df)
        chart_patterns = self.detect_chart_patterns(df)
        sr_levels = self.find_support_resistance(df)
        
        current_price = df['close'].iloc[-1]
        targets = self.calculate_price_targets(df, current_price)
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'candlestick_patterns': candlestick_patterns,
            'chart_patterns': chart_patterns,
            'support_resistance': sr_levels,
            'price_targets': targets,
            'analysis_timestamp': pd.Timestamp.now()
        }
