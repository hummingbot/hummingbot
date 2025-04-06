from decimal import Decimal
import numpy as np
import pandas as pd
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType, TradeType
import time

class AdaptiveMarketMakingStrategy(StrategyPyBase):
    # Strategy parameters
    market_info: MarketTradingPairTuple
    min_spread: Decimal
    max_spread: Decimal
    order_amount: Decimal
    order_refresh_time: float
    max_order_age: float
    
    # Technical indicator parameters
    rsi_length: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    ema_short: int = 12
    ema_long: int = 26
    bb_length: int = 20
    bb_std: float = 2.0
    
    # Risk management parameters
    max_inventory_ratio: float = 0.5
    volatility_adjustment: float = 1.0
    
    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 min_spread: Decimal,
                 max_spread: Decimal,
                 order_amount: Decimal,
                 order_refresh_time: float = 10.0,
                 max_order_age: float = 300.0,
                 rsi_length: int = 14,
                 ema_short: int = 12,
                 ema_long: int = 26,
                 bb_length: int = 20,
                 max_inventory_ratio: float = 0.5,
                 volatility_adjustment: float = 1.0):
        
        super().__init__()
        self.market_info = market_info
        self.min_spread = min_spread
        self.max_spread = max_spread
        self.order_amount = order_amount
        self.order_refresh_time = order_refresh_time
        self.max_order_age = max_order_age
        
        # Technical indicator parameters
        self.rsi_length = rsi_length
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.bb_length = bb_length
        self.bb_std = bb_std
        
        # Risk management parameters
        self.max_inventory_ratio = max_inventory_ratio
        self.volatility_adjustment = volatility_adjustment
        
        # Internal state variables
        self._last_timestamp = 0
        self._current_orders = {}
        self._last_spread_adjustment = time.time()
        self._indicator_scores = {"rsi": 0, "macd": 0, "ema": 0, "bbands": 0, "volume": 0}
        self._historical_prices = []
        self._historical_volumes = []
        
        # Register event listeners
        self.add_markets([market_info.market])

    async def calculate_indicators(self):
        # Get historical data
        candles = await self.market_info.market.get_candles(
            trading_pair=self.market_info.trading_pair,
            interval="1h",
            limit=100
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
    
    def calculate_rsi(self, prices, length):
        deltas = np.diff(prices)
        seed = deltas[:length+1]
        up = seed[seed >= 0].sum()/length
        down = -seed[seed < 0].sum()/length
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
        ema_fast = self.calculate_ema(prices, fast_length)
        ema_slow = self.calculate_ema(prices, slow_length)
        macd = ema_fast - ema_slow
        signal = self.calculate_ema(macd, signal_length)
        hist = macd - signal
        return macd, signal, hist
    
    def calculate_ema(self, prices, length):
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        multiplier = 2 / (length + 1)
        
        for i in range(1, len(prices)):
            ema[i] = (prices[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def calculate_bollinger_bands(self, prices, length, num_std):
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
    
    def calculate_adaptive_spread(self):
        # Calculate total score
        total_score = sum(self._indicator_scores.values())
        
        # Calculate ATR for volatility adjustment
        atr = self.calculate_atr(self._historical_prices, 14)
        
        # Current mid price
        mid_price = self.market_info.get_mid_price()
        
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
        adjusted_spread = max(self.min_spread, min(self.max_spread, adjusted_spread))
        
        return Decimal(str(adjusted_spread))
    
    def calculate_atr(self, prices, length):
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
    
    def calculate_inventory_ratio(self):
        base_balance = self.market_info.base_balance
        quote_balance = self.market_info.quote_balance
        mid_price = self.market_info.get_mid_price()
        
        total_value = base_balance + (quote_balance / mid_price)
        base_ratio = base_balance / total_value if total_value > 0 else 0.5
        
        return base_ratio
    
    def calculate_order_amount(self):
        # Base order amount on inventory ratio
        inventory_ratio = self.calculate_inventory_ratio()
        
        # Reduce buy order size when holding too much base asset
        buy_adjustment = max(0, 1 - (inventory_ratio / self.max_inventory_ratio))
        
        # Reduce sell order size when holding too little base asset
        sell_adjustment = max(0, 1 - ((1 - inventory_ratio) / self.max_inventory_ratio))
        
        buy_order_amount = self.order_amount * Decimal(str(buy_adjustment))
        sell_order_amount = self.order_amount * Decimal(str(sell_adjustment))
        
        return buy_order_amount, sell_order_amount
    
    async def create_orders(self):
        # Calculate current market parameters
        mid_price = self.market_info.get_mid_price()
        spread = self.calculate_adaptive_spread()
        buy_amount, sell_amount = self.calculate_order_amount()
        
        # Calculate order prices
        buy_price = mid_price * (Decimal("1") - spread)
        sell_price = mid_price * (Decimal("1") + spread)
        
        # Cancel existing orders
        await self.cancel_all_orders()
        
        # Create new orders if amounts are sufficient
        if buy_amount > Decimal("0"):
            await self.place_order(TradeType.BUY, buy_price, buy_amount)
            
        if sell_amount > Decimal("0"):
            await self.place_order(TradeType.SELL, sell_price, sell_amount)
    
    async def place_order(self, trade_type, price, amount):
        order_id = self.market_info.market.buy(
            self.market_info.trading_pair,
            amount,
            OrderType.LIMIT,
            price
        ) if trade_type is TradeType.BUY else self.market_info.market.sell(
            self.market_info.trading_pair,
            amount,
            OrderType.LIMIT,
            price
        )
        
        self._current_orders[order_id] = {
            "trade_type": trade_type,
            "price": price,
            "amount": amount,
            "timestamp": time.time()
        }
        
        return order_id
    
    async def cancel_all_orders(self):
        for order_id in list(self._current_orders.keys()):
            await self.market_info.market.cancel(self.market_info.trading_pair, order_id)
            del self._current_orders[order_id]
    
    async def cancel_old_orders(self):
        current_time = time.time()
        for order_id, order_details in list(self._current_orders.items()):
            if current_time - order_details["timestamp"] > self.max_order_age:
                await self.market_info.market.cancel(self.market_info.trading_pair, order_id)
                del self._current_orders[order_id]
    
    def update_strategy_params_based_on_market_conditions(self):
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
    
    async def format_status(self) -> str:
        """
        Returns a status string formatted to be displayed.
        """
        if not self._historical_prices:
            return "No data collected yet..."
        
        mid_price = self.market_info.get_mid_price()
        base_balance = self.market_info.base_balance
        quote_balance = self.market_info.quote_balance
        inventory_ratio = self.calculate_inventory_ratio()
        
        status_msg = (
            f"Strategy: Adaptive Market Making\n"
            f"Trading Pair: {self.market_info.trading_pair}\n"
            f"Mid Price: {mid_price:.6f}\n"
            f"Base Balance: {base_balance:.6f}\n"
            f"Quote Balance: {quote_balance:.6f}\n"
            f"Inventory Ratio: {inventory_ratio:.2%}\n"
            f"\nIndicator Scores:\n"
            f"RSI: {self._indicator_scores['rsi']}\n"
            f"MACD: {self._indicator_scores['macd']}\n"
            f"EMA: {self._indicator_scores['ema']}\n"
            f"BBands: {self._indicator_scores['bbands']}\n"
            f"Volume: {self._indicator_scores['volume']}\n"
            f"Total Score: {sum(self._indicator_scores.values())}\n"
            f"\nCurrent Spread: {self.calculate_adaptive_spread():.2%}\n"
            f"Active Orders: {len(self._current_orders)}\n"
        )
        
        return status_msg
    
    async def tick(self):
        current_time = time.time()
        
        # Only run the strategy every order_refresh_time seconds
        if current_time - self._last_timestamp < self.order_refresh_time:
            return
        
        self._last_timestamp = current_time
        
        # Calculate indicators
        await self.calculate_indicators()
        
        # Update strategy parameters
        self.update_strategy_params_based_on_market_conditions()
        
        # Cancel old orders
        await self.cancel_old_orders()
        
        # Create new orders
        await self.create_orders()
        
    def did_fill_order(self, order_filled_event):
        """
        Our order got filled, update inventory and track trades.
        """
        order_id = order_filled_event.order_id
        if order_id in self._current_orders:
            del self._current_orders[order_id]
            # Immediately create new orders to maintain market presence
            self.hummingbot_application.invoke_async(self.create_orders())
    
    def did_fail_order(self, order_failed_event):
        """
        Our order failed, remove it from tracking.
        """
        order_id = order_failed_event.order_id
        if order_id in self._current_orders:
            del self._current_orders[order_id]
    
    def did_cancel_order(self, cancelled_event):
        """
        Order was canceled, remove from tracking.
        """
        order_id = cancelled_event.order_id
        if order_id in self._current_orders:
            del self._current_orders[order_id]
