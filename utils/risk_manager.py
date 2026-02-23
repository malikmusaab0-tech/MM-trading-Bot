"""
Risk Manager - Advanced risk management with trailing stops, dynamic stop losses
Manages intraday margin, position sizing, and portfolio risk
"""
import logging
from typing import Dict, Optional
from datetime import datetime, time
from data.database import get_session, Position, Trade
from config import settings

logger = logging.getLogger(__name__)


class RiskManager:
    """Advanced risk management system"""
    
    def __init__(self):
        self.trailing_stops = {}  # {symbol: trailing_stop_price}
        self.position_high_prices = {}  # {symbol: highest_price_since_entry}
        self.stop_losses = {}  # {symbol: stop_loss_price}
        self.take_profits = {}  # {symbol: take_profit_price}
    
    def calculate_position_size(self, 
                                symbol: str, 
                                entry_price: float,
                                atr: float,
                                available_capital: float,
                                margin_multiplier: float = None) -> int:
        """
        Calculate optimal position size based on risk parameters
        
        Args:
            symbol: Stock symbol
            entry_price: Proposed entry price
            atr: Average True Range
            available_capital: Available trading capital
            margin_multiplier: Intraday margin multiplier (default from settings)
        
        Returns:
            Number of shares to buy
        """
        if margin_multiplier is None:
            margin_multiplier = settings.INTRADAY_MARGIN_MULTIPLIER
        
        # Calculate risk per share (ATR-based or percentage-based)
        risk_per_share = max(
            atr * settings.STOP_LOSS_ATR_MULTIPLIER,
            entry_price * (settings.STOP_LOSS_PCT / 100)
        )
        
        # Calculate position size based on risk
        risk_capital = available_capital * settings.POSITION_SIZE_PCT  # 2% risk per trade
        position_size_by_risk = int(risk_capital / risk_per_share)
        
        # Calculate max position based on capital limits
        max_position_value = min(
            settings.MAX_POSITION_VALUE,
            available_capital * 0.2  # Max 20% of capital per position
        )
        
        # Apply intraday margin
        position_value_with_margin = max_position_value * margin_multiplier
        position_size_by_capital = int(position_value_with_margin / entry_price)
        
        # Take minimum to respect both risk and capital limits
        final_position_size = min(position_size_by_risk, position_size_by_capital)
        
        # Ensure minimum position size
        if final_position_size * entry_price < settings.MIN_POSITION_SIZE:
            return 0
        
        logger.info(f"{symbol}: Position size = {final_position_size} shares "
                   f"(Entry: ₹{entry_price:.2f}, Risk/share: ₹{risk_per_share:.2f})")
        
        return max(1, final_position_size)
    
    def set_stop_loss(self, symbol: str, entry_price: float, atr: float):
        """Set initial stop loss for a position"""
        stop_loss_distance = atr * settings.STOP_LOSS_ATR_MULTIPLIER
        stop_loss_price = entry_price - stop_loss_distance
        
        self.stop_losses[symbol] = stop_loss_price
        self.position_high_prices[symbol] = entry_price
        
        logger.info(f"{symbol}: Stop loss set at ₹{stop_loss_price:.2f}")
    
    def set_take_profit(self, symbol: str, entry_price: float, atr: float):
        """Set take profit target for a position"""
        take_profit_distance = atr * settings.TAKE_PROFIT_ATR_MULTIPLIER
        take_profit_price = entry_price + take_profit_distance
        
        self.take_profits[symbol] = take_profit_price
        
        logger.info(f"{symbol}: Take profit set at ₹{take_profit_price:.2f}")
    
    def update_trailing_stop(self, symbol: str, current_price: float, entry_price: float):
        """
        Update trailing stop loss
        
        Args:
            symbol: Stock symbol
            current_price: Current market price
            entry_price: Original entry price
        
        Returns:
            True if trailing stop was updated
        """
        # Check if trailing stop is activated
        profit_pct = ((current_price - entry_price) / entry_price) * 100
        
        if profit_pct < settings.TRAILING_STOP_ACTIVATION_PCT:
            return False  # Not enough profit to activate trailing stop
        
        # Update highest price seen
        if symbol not in self.position_high_prices:
            self.position_high_prices[symbol] = current_price
        else:
            self.position_high_prices[symbol] = max(self.position_high_prices[symbol], current_price)
        
        # Calculate trailing stop
        trailing_distance_pct = settings.TRAILING_STOP_DISTANCE_PCT / 100
        new_trailing_stop = self.position_high_prices[symbol] * (1 - trailing_distance_pct)
        
        # Update if new trailing stop is higher than existing stop loss
        if symbol not in self.trailing_stops or new_trailing_stop > self.trailing_stops[symbol]:
            old_stop = self.trailing_stops.get(symbol, 0)
            self.trailing_stops[symbol] = new_trailing_stop
            
            # Also update regular stop loss
            if symbol in self.stop_losses:
                self.stop_losses[symbol] = max(self.stop_losses[symbol], new_trailing_stop)
            
            logger.info(f"{symbol}: Trailing stop updated from ₹{old_stop:.2f} to ₹{new_trailing_stop:.2f}")
            return True
        
        return False
    
    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """Check if stop loss is hit"""
        if symbol in self.stop_losses:
            if current_price <= self.stop_losses[symbol]:
                logger.warning(f"{symbol}: Stop loss hit! Price ₹{current_price:.2f} <= SL ₹{self.stop_losses[symbol]:.2f}")
                return True
        return False
    
    def check_trailing_stop(self, symbol: str, current_price: float) -> bool:
        """Check if trailing stop is hit"""
        if symbol in self.trailing_stops:
            if current_price <= self.trailing_stops[symbol]:
                logger.warning(f"{symbol}: Trailing stop hit! Price ₹{current_price:.2f} <= TSL ₹{self.trailing_stops[symbol]:.2f}")
                return True
        return False
    
    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        """Check if take profit is hit"""
        if symbol in self.take_profits:
            if current_price >= self.take_profits[symbol]:
                logger.info(f"{symbol}: Take profit hit! Price ₹{current_price:.2f} >= TP ₹{self.take_profits[symbol]:.2f}")
                return True
        return False
    
    def should_close_position(self, symbol: str, current_price: float, entry_price: float) -> tuple[bool, str]:
        """
        Determine if position should be closed based on risk rules
        
        Returns:
            (should_close, reason)
        """
        # Check stop loss
        if self.check_stop_loss(symbol, current_price):
            return True, "STOP_LOSS"
        
        # Check trailing stop
        if self.check_trailing_stop(symbol, current_price):
            return True, "TRAILING_STOP"
        
        # Check take profit
        if self.check_take_profit(symbol, current_price):
            return True, "TAKE_PROFIT"
        
        # Check if it's near square-off time
        if self.is_square_off_time():
            return True, "SQUARE_OFF_TIME"
        
        return False, ""
    
    def is_square_off_time(self) -> bool:
        """Check if it's time to square off intraday positions"""
        current_time = datetime.now().time()
        square_off_time = time.fromisoformat(settings.SQUARE_OFF_TIME)
        return current_time >= square_off_time
    
    def get_portfolio_risk(self) -> Dict:
        """Calculate current portfolio risk metrics"""
        with get_session() as session:
            positions = session.query(Position).filter(Position.quantity > 0).all()
            
            total_exposure = sum(pos.quantity * pos.avg_price for pos in positions)
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
            total_realized_pnl = sum(pos.realized_pnl for pos in positions)
            
            # Calculate max margin usage
            margin_used_pct = (total_exposure / settings.MAX_INTRADAY_EXPOSURE) * 100
            
            # Calculate risk per position
            position_risks = []
            for pos in positions:
                if pos.symbol in self.stop_losses:
                    potential_loss = (pos.avg_price - self.stop_losses[pos.symbol]) * pos.quantity
                    risk_pct = (potential_loss / settings.INITIAL_CAPITAL) * 100
                    position_risks.append({
                        'symbol': pos.symbol,
                        'potential_loss': potential_loss,
                        'risk_pct': risk_pct
                    })
            
            return {
                'total_positions': len(positions),
                'total_exposure': total_exposure,
                'margin_used_pct': margin_used_pct,
                'unrealized_pnl': total_unrealized_pnl,
                'realized_pnl': total_realized_pnl,
                'position_risks': position_risks,
                'at_max_positions': len(positions) >= settings.MAX_CONCURRENT_POSITIONS
            }
    
    def can_open_new_position(self) -> tuple[bool, str]:
        """Check if new position can be opened based on risk limits"""
        risk_metrics = self.get_portfolio_risk()
        
        # Check max positions
        if risk_metrics['at_max_positions']:
            return False, "MAX_POSITIONS_REACHED"
        
        # Check margin usage
        if risk_metrics['margin_used_pct'] > 90:  # 90% margin used
            return False, "MARGIN_LIMIT"
        
        # Check if square-off time
        if self.is_square_off_time():
            return False, "SQUARE_OFF_TIME"
        
        return True, "OK"
    
    def cleanup_closed_position(self, symbol: str):
        """Remove risk tracking for closed position"""
        self.stop_losses.pop(symbol, None)
        self.trailing_stops.pop(symbol, None)
        self.take_profits.pop(symbol, None)
        self.position_high_prices.pop(symbol, None)
        logger.info(f"{symbol}: Risk tracking cleaned up")
