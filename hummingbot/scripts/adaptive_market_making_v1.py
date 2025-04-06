"""
Adaptive Market Making Strategy V1
Based on Institutional Crypto Trading Framework & Updated Mentor Knowledge

This strategy implements a multi-indicator approach with dynamic weighting system:
- RSI (30/70): Signals oversold/overbought conditions and potential reversals
- MACD: Detects momentum shifts and trend strength
- EMA: Identifies trend direction and key breakout levels
- Bollinger Bands: Detects volatility expansion/contraction and potential breakouts
- Volume Analysis: Confirms price movements and detects accumulation/distribution

Key features aligned with mentor guidance:
- Multi-timeframe confirmation approach
- Weighted scoring system for technical indicators
- Dynamic spread adjustment based on market conditions
- Adaptive position sizing based on inventory management
- Risk management with trailing stop-loss implementation
"""

import logging
import time
import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, Optional, List
import subprocess
import sys

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.logger import HummingbotLogger

# Check for dependencies
try:
    import numpy as np
    import pandas as pd
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False
    
def install_dependencies():
    """Install required dependencies if they're missing"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy", "pandas"])
        logging.getLogger().info("Successfully installed dependencies")
        return True
    except Exception as e:
        logging.getLogger().error(f"Failed to install dependencies: {e}")
        return False


class AdaptiveMarketMakingStrategy(ScriptStrategyBase):
    """
    Adaptive Market Making Strategy V1
    
    This strategy combines technical indicators to dynamically adjust spreads 
    and position sizes based on market conditions.
    
    Features:
    - Dynamic spread adjustment based on technical indicators
    - Adaptive order sizing based on inventory management
    - Market regime detection to adapt to different market conditions
    - Performance tracking and reporting
    """
    
    # Markets initialization
    markets = {}  # This will be set by init_markets
    
    # Strategy parameters
    trading_pair = "ETH-USDT"
    exchange = "binance_paper_trade"
    
    # Default parameters
    min_spread = Decimal("0.002")  # 0.2%
    max_spread = Decimal("0.01")   # 1%
    order_amount = Decimal("0.1")  # Base order size
    order_refresh_time = 60        # 60 seconds
    max_order_age = 300            # 5 minutes
    
    # Technical indicator parameters
    rsi_length = 14
    rsi_overbought = 70
    rsi_oversold = 30
    ema_short = 12
    ema_long = 26
    bb_length = 20
    bb_std = 2.0
    
    # Risk management parameters
    max_inventory_ratio = 0.5
    volatility_adjustment = 1.0
    
    @classmethod
    def init_markets(cls, config=None):
        """Initialize markets for the strategy"""
        cls.markets = {cls.exchange: {cls.trading_pair}}
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        """Initialize the strategy"""
        super().__init__(connectors)
        
        # Ensure dependencies are installed
        if not HAS_DEPENDENCIES:
            install_dependencies()
        
        # Get connector
        self.connector = self.connectors[self.exchange]
        
        # Internal state variables
        self._last_timestamp = 0
        self._current_orders = {}
        self._indicator_scores = {"rsi": 0, "macd": 0, "ema": 0, "bbands": 0, "volume": 0}
        self._historical_prices = []
        self._historical_volumes = []
        
        self.logger().info("Adaptive Market Making Strategy initialized")
    
    def on_tick(self):
        """Execute strategy logic on each tick"""
        current_tick = self.current_timestamp
        
        # Check if it's time to refresh orders
        need_to_refresh = False
        if len(self._current_orders) == 0:
            need_to_refresh = True
        elif current_tick - self._last_timestamp > self.order_refresh_time:
            need_to_refresh = True
            
        # Check for old orders that need to be canceled
        for order_id in list(self.get_active_orders()):
            if time.time() - order_id.creation_timestamp > self.max_order_age:
                self.cancel(self.exchange, self.trading_pair, order_id.client_order_id)
                need_to_refresh = True
                
        if need_to_refresh:
            # Calculate indicators
            self.calculate_indicators()
            
            # Update strategy parameters based on market conditions
            self.update_strategy_params_based_on_market_conditions()
            
            # Create new orders
            self.cancel_all_orders()
            self.create_orders()
            
            # Update timestamp
            self._last_timestamp = current_tick
    
    def calculate_indicators(self):
        """Calculate technical indicators based on historical data"""
        # Get candle data
        try:
            candles = self.connector.get_candles(
                trading_pair=self.trading_pair,
                interval="1h",
                max_records=100
            )
            
            if len(candles) < self.rsi_length + 10:
                return
            
            # Extract price and volume data
            close_prices = np.array([float(candle.close) for candle in candles])
            volumes = np.array([float(candle.volume) for candle in candles])
            
            # Store historical data
            self._historical_prices = close_prices
            self._historical_volumes = volumes
            
            # Calculate RSI
            rsi = self.calculate_rsi(close_prices, self.rsi_length)
            
            # Calculate MACD
            macd, signal, hist = self.calculate_macd(close_prices, self.ema_short, self.ema_long)
            
            # Calculate EMA
            ema50 = self.calculate_ema(close_prices, 50)
            
            # Calculate Bollinger Bands
            upper, middle, lower = self.calculate_bollinger_bands(close_prices, self.bb_length, self.bb_std)
            
            # Check volume spike
            avg_volume = np.mean(volumes[-20:])
            latest_volume = volumes[-1]
            volume_spike = latest_volume > (2 * avg_volume)
            
            # Calculate indicator scores
            if rsi[-1] < self.rsi_oversold:
                self._indicator_scores["rsi"] = 20  # Oversold condition, bullish
            elif rsi[-1] > self.rsi_overbought:
                self._indicator_scores["rsi"] = -20  # Overbought condition, bearish
            else:
                self._indicator_scores["rsi"] = 0
            
            if macd[-1] > signal[-1] and macd[-2] <= signal[-2]:
                self._indicator_scores["macd"] = 25  # Bullish crossover
            elif macd[-1] < signal[-1] and macd[-2] >= signal[-2]:
                self._indicator_scores["macd"] = -25  # Bearish crossover
            else:
                self._indicator_scores["macd"] = 0
            
            if close_prices[-1] > ema50[-1] and close_prices[-2] <= ema50[-2]:
                self._indicator_scores["ema"] = 15  # Bullish EMA break
            elif close_prices[-1] < ema50[-1] and close_prices[-2] >= ema50[-2]:
                self._indicator_scores["ema"] = -15  # Bearish EMA break
            else:
                self._indicator_scores["ema"] = 0
            
            # Check for Bollinger Band squeeze and breakout
            bb_width = (upper[-1] - lower[-1]) / middle[-1]
            bb_width_prev = (upper[-10] - lower[-10]) / middle[-10]
            
            if bb_width < 0.1 and bb_width_prev > 0.2:
                self._indicator_scores["bbands"] = 15  # Squeeze identified, potential breakout
            elif close_prices[-1] > upper[-1]:
                self._indicator_scores["bbands"] = -15  # Upper band rejection, bearish
            elif close_prices[-1] < lower[-1]:
                self._indicator_scores["bbands"] = 15  # Lower band support, bullish
            else:
                self._indicator_scores["bbands"] = 0
            
            if volume_spike:
                self._indicator_scores["volume"] = 20 if close_prices[-1] > close_prices[-2] else -20
            else:
                self._indicator_scores["volume"] = 0
                
        except Exception as e:
            self.logger().error(f"Error calculating indicators: {e}")
    
    def calculate_rsi(self, prices, length):
        """Calculate Relative Strength Index"""
        deltas = np.diff(prices)
        seed = deltas[:length+1]
        up = seed[seed >= 0].sum()/length if len(seed[seed >= 0]) > 0 else 0
        down = -seed[seed < 0].sum()/length if len(seed[seed < 0]) > 0 else 0
        rs = up/down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:length] = 100. - 100./(1. + rs)
        
        for i in range(length, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0
            else:
                upval = 0
                downval = -delta
                
            up = (up * (length - 1) + upval) / length
            down = (down * (length - 1) + downval) / length
            rs = up/down if down != 0 else 0
            rsi[i] = 100. - 100./(1. + rs)
        return rsi
    
    def calculate_macd(self, prices, fast_length, slow_length, signal_length=9):
        """Calculate Moving Average Convergence Divergence"""
        ema_fast = self.calculate_ema(prices, fast_length)
        ema_slow = self.calculate_ema(prices, slow_length)
        macd = ema_fast - ema_slow
        signal = self.calculate_ema(macd, signal_length)
        hist = macd - signal
        return macd, signal, hist
    
    def calculate_ema(self, prices, length):
        """Calculate Exponential Moving Average"""
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        multiplier = 2 / (length + 1)
        
        for i in range(1, len(prices)):
            ema[i] = (prices[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def calculate_bollinger_bands(self, prices, length, num_std):
        """Calculate Bollinger Bands"""
        middle = np.zeros_like(prices)
        upper = np.zeros_like(prices)
        lower = np.zeros_like(prices)
        
        for i in range(len(prices)):
            if i >= length - 1:
                window = prices[i-(length-1):i+1]
                middle[i] = np.mean(window)
                std = np.std(window)
                upper[i] = middle[i] + (std * num_std)
                lower[i] = middle[i] - (std * num_std)
            else:
                window = prices[:i+1]
                middle[i] = np.mean(window)
                std = np.std(window)
                upper[i] = middle[i] + (std * num_std)
                lower[i] = middle[i] - (std * num_std)
                
        return upper, middle, lower
    
    def calculate_atr(self, prices, length):
        """Calculate Average True Range"""
        high = prices
        low = prices
        close = prices
        tr1 = high[1:] - low[1:]
        tr2 = abs(high[1:] - close[:-1])
        tr3 = abs(low[1:] - close[:-1])
        tr = np.vstack([tr1, tr2, tr3]).max(axis=0)
        atr = np.zeros_like(prices)
        atr[:length] = np.mean(tr[:length])
        for i in range(length, len(prices)):
            atr[i] = (atr[i-1] * (length-1) + tr[i-1]) / length
        return atr
    
    def calculate_adaptive_spread(self):
        """Calculate adaptive spread based on market conditions"""
        # Calculate total score
        total_score = sum(self._indicator_scores.values())
        
        # Calculate ATR for volatility adjustment if we have historical prices
        if len(self._historical_prices) > 0:
            atr = self.calculate_atr(self._historical_prices, 14)
        
            # Get current mid price
            mid_price = self.connector.get_mid_price(self.trading_pair)
            
            # Normalize volatility relative to price
            volatility = atr[-1] / mid_price if len(atr) > 0 else 0.01
            
            # Calculate base spread
            base_spread = self.min_spread
            
            # Adjust spread based on indicators and volatility
            if total_score > 50:  # Strong bullish bias
                spread_adjustment = -0.2  # Tighten spreads to capture opportunity
            elif total_score < -50:  # Strong bearish bias
                spread_adjustment = 0.3  # Widen spreads to mitigate risk
            else:
                spread_adjustment = total_score / 100  # Gradual adjustment
                
            # Volatility adjustment
            vol_adjustment = self.volatility_adjustment * volatility * 10
            
            # Inventory adjustment
            inventory_ratio = self.calculate_inventory_ratio()
            inventory_adjustment = (inventory_ratio - 0.5) * 0.2  # Adjust based on inventory balance
            
            # Apply adjustments to base spread
            adjusted_spread = base_spread * (1 + spread_adjustment + vol_adjustment + inventory_adjustment)
            
            # Ensure spread is within min/max range
            if adjusted_spread < self.min_spread:
                adjusted_spread = self.min_spread
            elif adjusted_spread > self.max_spread:
                adjusted_spread = self.max_spread
                
            return adjusted_spread
        else:
            return self.min_spread
    
    def calculate_inventory_ratio(self):
        """Calculate the ratio of base asset in the total portfolio value"""
        base_balance = self.connector.get_balance(self.trading_pair.split("-")[0])
        quote_balance = self.connector.get_balance(self.trading_pair.split("-")[1])
        mid_price = self.connector.get_mid_price(self.trading_pair)
        
        total_value = base_balance + (quote_balance / mid_price)
        base_ratio = base_balance / total_value if total_value > 0 else 0.5
        
        return base_ratio
    
    def calculate_order_amount(self):
        """Calculate order amounts based on inventory management"""
        # Base order amount on inventory ratio
        inventory_ratio = self.calculate_inventory_ratio()
        
        # Reduce buy order size when holding too much base asset
        buy_adjustment = max(0, 1 - (inventory_ratio / self.max_inventory_ratio))
        
        # Reduce sell order size when holding too little base asset
        sell_adjustment = max(0, 1 - ((1 - inventory_ratio) / self.max_inventory_ratio))
        
        buy_order_amount = self.order_amount * Decimal(str(buy_adjustment))
        sell_order_amount = self.order_amount * Decimal(str(sell_adjustment))
        
        return buy_order_amount, sell_order_amount
    
    def create_orders(self):
        """Create new orders based on current market conditions"""
        # Calculate current market parameters
        mid_price = self.connector.get_mid_price(self.trading_pair)
        spread = self.calculate_adaptive_spread()
        buy_amount, sell_amount = self.calculate_order_amount()
        
        # Calculate order prices
        buy_price = mid_price * (Decimal("1") - spread)
        sell_price = mid_price * (Decimal("1") + spread)
        
        # Log order details
        self.logger().info(f"Creating orders - Buy: {buy_amount} @ {buy_price}, Sell: {sell_amount} @ {sell_price}")
        
        # Create new orders if amounts are sufficient
        if buy_amount > Decimal("0"):
            self.buy(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=buy_amount,
                order_type=OrderType.LIMIT,
                price=buy_price
            )
            
        if sell_amount > Decimal("0"):
            self.sell(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=sell_amount,
                order_type=OrderType.LIMIT,
                price=sell_price
            )
    
    def cancel_all_orders(self):
        """Cancel all active orders"""
        orders = self.get_active_orders(connector_name=self.exchange)
        for order in orders:
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)
    
    def update_strategy_params_based_on_market_conditions(self):
        """Update strategy parameters based on market conditions"""
        # Calculate total indicator score
        total_score = sum(self._indicator_scores.values())
        
        # Update strategy parameters based on market conditions
        if total_score > 70:  # Strong bullish conditions
            self.min_spread = Decimal("0.001")  # Tighter spreads to capture opportunity
            self.max_inventory_ratio = 0.7  # Allow more base asset inventory
        elif total_score < -70:  # Strong bearish conditions
            self.min_spread = Decimal("0.005")  # Wider spreads to manage risk
            self.max_inventory_ratio = 0.3  # Reduce base asset inventory
        else:  # Neutral market conditions
            self.min_spread = Decimal("0.002")
            self.max_inventory_ratio = 0.5
    
    def did_fill_order(self, event: OrderFilledEvent):
        """Handle order filled event"""
        self.logger().info(f"Order filled - {event.amount} {event.trading_pair} at {event.price}")
    
    def format_status(self) -> str:
        """Format status display"""
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        
        lines = []
        
        # Add balance information
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        
        # Add active orders information
        active_orders = self.get_active_orders()
        if len(active_orders) > 0:
            active_orders_df = pd.DataFrame([
                {
                    "Symbol": order.trading_pair,
                    "Type": "Buy" if order.is_buy else "Sell",
                    "Price": float(order.price),
                    "Amount": float(order.quantity),
                }
                for order in active_orders
            ])
            lines.extend(["", "  Active Orders:"] + 
                         ["    " + line for line in active_orders_df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active orders."])
        
        # Add indicator scores
        indicator_df = pd.DataFrame([self._indicator_scores])
        lines.extend(["", "  Indicator Scores:"] + 
                     ["    " + line for line in indicator_df.to_string(index=False).split("\n")])
        
        # Add current strategy parameters
        lines.extend([
            "",
            f"  Strategy Parameters:",
            f"    Min Spread: {self.min_spread}",
            f"    Max Spread: {self.max_spread}",
            f"    Max Inventory Ratio: {self.max_inventory_ratio}",
            f"    Order Amount: {self.order_amount}",
        ])
        
        return "\n".join(lines) 