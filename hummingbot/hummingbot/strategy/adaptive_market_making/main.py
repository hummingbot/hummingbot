from decimal import Decimal
import numpy as np
import pandas as pd
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType, TradeType
import time
import logging
from typing import Dict, List

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
    # Bollinger Bands parameters
    bb_length1: int = 120  # 1st Length
    bb_length2: int = 12   # 2nd Length
    bb_ma_type: str = "EMA"  # MA Type
    bb_source: str = "hl2"  # Source
    bb_std: float = 2.0
    # VWAP parameters
    vwap_length: int = 1
    vwap_source: str = "close"
    vwap_offset: int = 0
    # Additional BB parameters
    bb_price_data: str = "hl2"  # Price Data source
    bb_lookback: int = 24
    bb_show_cross: bool = True
    bb_gain: float = 10000
    bb_use_kalman: bool = True
    
    # Risk management parameters
    max_inventory_ratio: float = 0.5
    min_inventory_ratio: float = 0.3  # Added min ratio to maintain balanced inventory
    volatility_adjustment: float = 1.0
    max_position_value: Decimal = Decimal("inf")  # Added position limit
    trailing_stop_pct: Decimal = Decimal("0.02")  # Added 2% trailing stop
    
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
                 bb_length1: int = 120,
                 bb_length2: int = 12,
                 bb_ma_type: str = "EMA",
                 bb_source: str = "hl2",
                 bb_std: float = 2.0,
                 vwap_length: int = 1,
                 vwap_source: str = "close",
                 vwap_offset: int = 0,
                 bb_price_data: str = "hl2",
                 bb_lookback: int = 24,
                 bb_show_cross: bool = True,
                 bb_gain: float = 10000,
                 bb_use_kalman: bool = True,
                 max_inventory_ratio: float = 0.5,
                 min_inventory_ratio: float = 0.3,
                 volatility_adjustment: float = 1.0,
                 max_position_value: Decimal = Decimal("inf"),
                 trailing_stop_pct: Decimal = Decimal("0.02")):
        
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
        # Bollinger Bands parameters
        self.bb_length1 = bb_length1
        self.bb_length2 = bb_length2
        self.bb_ma_type = bb_ma_type
        self.bb_source = bb_source
        self.bb_std = bb_std
        # VWAP parameters
        self.vwap_length = vwap_length
        self.vwap_source = vwap_source
        self.vwap_offset = vwap_offset
        # Additional BB parameters
        self.bb_price_data = bb_price_data
        self.bb_lookback = bb_lookback
        self.bb_show_cross = bb_show_cross
        self.bb_gain = bb_gain
        self.bb_use_kalman = bb_use_kalman
        
        # Risk management parameters
        self.max_inventory_ratio = max_inventory_ratio
        self.min_inventory_ratio = min_inventory_ratio
        self.volatility_adjustment = volatility_adjustment
        self.max_position_value = max_position_value
        self.trailing_stop_pct = trailing_stop_pct
        
        # Internal state variables
        self._last_timestamp = 0
        self._current_orders = {}
        self._last_spread_adjustment = time.time()
        self._indicator_scores = {"rsi": 0, "macd": 0, "ema": 0, "bbands": 0, "volume": 0}
        self._historical_prices = []
        self._historical_volumes = []
        self._trailing_stop_price = None
        
        # Performance tracking
        self._start_base_balance = None
        self._start_quote_balance = None
        self._start_price = None
        self._start_time = time.time()
        self._trade_profit = Decimal("0")
        self._total_fees = Decimal("0")
        self._total_trades = 0
        self._win_trades = 0
        self._loss_trades = 0
        self._trade_values = []
        
        # Register event listeners
        self.add_markets([market_info.market])
        
        self.logger().info("Adaptive Market Making strategy initialized.")

    async def calculate_indicators(self):
        # Get historical data
        candles = await self.market_info.market.get_candles(
            trading_pair=self.market_info.trading_pair,
            interval="1h",
            limit=max(150, self.bb_length1 + self.bb_lookback + 10)  # Ensure enough data for BB calculation
        )
        
        if len(candles) < self.bb_length1 + 10:
            return
        
        # Extract price and volume data
        close_prices = np.array([float(candle.close) for candle in candles])
        high_prices = np.array([float(candle.high) for candle in candles])
        low_prices = np.array([float(candle.low) for candle in candles])
        volumes = np.array([float(candle.volume) for candle in candles])
        
        # Calculate price data based on source
        if self.bb_source == "hl2":
            price_data = (high_prices + low_prices) / 2
        elif self.bb_source == "hlc3":
            price_data = (high_prices + low_prices + close_prices) / 3
        elif self.bb_source == "ohlc4":
            open_prices = np.array([float(candle.open) for candle in candles])
            price_data = (open_prices + high_prices + low_prices + close_prices) / 4
        else:  # Default to close
            price_data = close_prices
        
        # Store historical data
        self._historical_prices = close_prices
        self._historical_volumes = volumes
        
        # Calculate RSI
        rsi = self.calculate_rsi(close_prices, self.rsi_length)
        
        # Calculate MACD
        macd, signal, hist = self.calculate_macd(close_prices, self.ema_short, self.ema_long)
        
        # Calculate EMA
        ema50 = self.calculate_ema(close_prices, 50)
        
        # Calculate Bollinger Bands with modified parameters
        upper, middle, lower, crossover, crossunder = self.calculate_bollinger_bands_enhanced(
            price_data, 
            high_prices,
            low_prices,
            close_prices,
            volumes
        )
        
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
            
        # Add scoring for BB crossovers
        if self.bb_show_cross:
            # Find the most recent crossover/crossunder in the last 5 bars
            recent_crossover = np.any(crossover[-5:])
            recent_crossunder = np.any(crossunder[-5:])
            
            if recent_crossover:
                self._indicator_scores["bbands"] -= 20  # Price crossing above upper band is bearish
            elif recent_crossunder:
                self._indicator_scores["bbands"] += 20  # Price crossing below lower band is bullish
                
        # Track BB states for strategy decisions
        self._bb_state = {
            "upper": upper[-1],
            "middle": middle[-1],
            "lower": lower[-1],
            "width": bb_width,
            "crossover": np.any(crossover[-3:]),  # Any crossover in last 3 bars
            "crossunder": np.any(crossunder[-3:])  # Any crossunder in last 3 bars
        }
        
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
    
    def calculate_bollinger_bands_enhanced(self, prices, high_prices, low_prices, close_prices, volumes):
        # Create arrays to store the results
        n = len(prices)
        upper = np.zeros_like(prices)
        middle = np.zeros_like(prices)
        lower = np.zeros_like(prices)
        crossover = np.zeros_like(prices, dtype=bool)
        crossunder = np.zeros_like(prices, dtype=bool)
        
        # Calculate price data for BB calculation
        if self.bb_price_data == "hl2":
            price_data = (high_prices + low_prices) / 2
        else:  # Default to close
            price_data = close_prices
        
        # Calculate VWAP if needed
        if self.vwap_source == "close":
            vwap_data = close_prices
        elif self.vwap_source == "hl2":
            vwap_data = (high_prices + low_prices) / 2
        else:
            vwap_data = close_prices
            
        vwap = self.calculate_vwap(vwap_data, volumes, self.vwap_length, self.vwap_offset)
        
        # Calculate first middle band (MA1)
        if self.bb_ma_type == "EMA":
            middle = self.calculate_ema(prices, self.bb_length1)
        else:  # Default to SMA
            for i in range(n):
                if i >= self.bb_length1 - 1:
                    middle[i] = np.mean(prices[i-(self.bb_length1-1):i+1])
                else:
                    middle[i] = np.mean(prices[:i+1])
        
        # Calculate second middle band (MA2) if bb_length2 > 0
        if self.bb_length2 > 0:
            if self.bb_ma_type == "EMA":
                ma2 = self.calculate_ema(prices, self.bb_length2)
            else:  # Default to SMA
                ma2 = np.zeros_like(prices)
                for i in range(n):
                    if i >= self.bb_length2 - 1:
                        ma2[i] = np.mean(prices[i-(self.bb_length2-1):i+1])
                    else:
                        ma2[i] = np.mean(prices[:i+1])
        else:
            ma2 = middle  # If no second length specified, use the first
        
        # Calculate standard deviation
        std = np.zeros_like(prices)
        for i in range(n):
            if i >= self.bb_length1 - 1:
                window = prices[i-(self.bb_length1-1):i+1]
                std[i] = np.std(window)
            else:
                window = prices[:i+1]
                std[i] = np.std(window)
        
        # Apply Kalman filter if enabled
        if self.bb_use_kalman:
            middle = self.apply_kalman_filter(middle)
            std = self.apply_kalman_filter(std)
        
        # Calculate bands with gain adjustment
        gain_factor = self.bb_gain / 10000.0  # Normalize gain
        for i in range(n):
            upper[i] = middle[i] + (std[i] * self.bb_std * gain_factor)
            lower[i] = middle[i] - (std[i] * self.bb_std * gain_factor)
        
        # Check for crossovers/crossunders if enabled
        if self.bb_show_cross:
            for i in range(1, n):
                crossover[i] = price_data[i] > upper[i] and price_data[i-1] <= upper[i-1]
                crossunder[i] = price_data[i] < lower[i] and price_data[i-1] >= lower[i-1]
        
        return upper, middle, lower, crossover, crossunder
    
    def calculate_vwap(self, prices, volumes, length, offset):
        """
        Calculate Volume Weighted Average Price (VWAP)
        """
        n = len(prices)
        vwap = np.zeros_like(prices)
        
        for i in range(n):
            if i < offset:
                vwap[i] = prices[i]
                continue
                
            start_idx = max(0, i - length + 1)
            price_vol = np.sum(prices[start_idx:i+1] * volumes[start_idx:i+1])
            vol_sum = np.sum(volumes[start_idx:i+1])
            
            if vol_sum > 0:
                vwap[i] = price_vol / vol_sum
            else:
                vwap[i] = prices[i]
        
        return vwap
    
    def apply_kalman_filter(self, data, process_variance=1e-5, measurement_variance=1e-3):
        """
        Apply Kalman filter to the input data
        """
        n = len(data)
        filtered_data = np.zeros_like(data)
        
        # Initial state
        filtered_data[0] = data[0]
        prediction = data[0]
        prediction_variance = 1.0
        
        for i in range(1, n):
            # Prediction step
            prediction_variance += process_variance
            
            # Update step
            kalman_gain = prediction_variance / (prediction_variance + measurement_variance)
            filtered_data[i] = prediction + kalman_gain * (data[i] - prediction)
            prediction = filtered_data[i]
            prediction_variance = (1 - kalman_gain) * prediction_variance
        
        return filtered_data
    
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
        
        # Enhanced inventory adjustment - non-linear adjustment
        inventory_ratio = self.calculate_inventory_ratio()
        target_ratio = (self.max_inventory_ratio + self.min_inventory_ratio) / 2
        deviation = inventory_ratio - target_ratio
        
        # Apply non-linear adjustment based on distance from target
        inventory_adjustment = deviation * abs(deviation) * 2
        
        # Apply adjustments to base spread
        adjusted_spread = base_spread * (1 + spread_adjustment + vol_adjustment + inventory_adjustment)
        
        # Ensure spread is within min/max range
        adjusted_spread = max(self.min_spread, min(self.max_spread, adjusted_spread))
        
        self.logger().info(f"Spread adjustments: indicator={spread_adjustment:.4f}, "
                          f"volatility={vol_adjustment:.4f}, inventory={inventory_adjustment:.4f}")
        
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
        """
        Enhanced order amount calculation with improved inventory management
        """
        # Base order amount on inventory ratio
        inventory_ratio = self.calculate_inventory_ratio()
        target_ratio = (self.max_inventory_ratio + self.min_inventory_ratio) / 2
        
        # Calculate base asset value in quote terms
        mid_price = self.market_info.get_mid_price()
        base_balance = self.market_info.base_balance
        base_value = base_balance * mid_price
        
        # Check if total position exceeds max position value
        total_value = base_value + self.market_info.quote_balance
        position_limit_factor = min(Decimal("1"), self.max_position_value / total_value) if total_value > 0 else Decimal("1")
        
        # Progressive scaling based on distance from target ratio
        buy_adjustment = 1.0
        sell_adjustment = 1.0
        
        if inventory_ratio > target_ratio:
            # Too much base asset, reduce buy orders and increase sell orders
            distance = (inventory_ratio - target_ratio) / (self.max_inventory_ratio - target_ratio)
            buy_adjustment = max(0.2, 1 - (distance * 1.5))  # Reduce more aggressively
            sell_adjustment = min(2.0, 1 + distance)  # Increase sell size
        else:
            # Too little base asset, increase buy orders and reduce sell orders
            distance = (target_ratio - inventory_ratio) / (target_ratio - self.min_inventory_ratio)
            buy_adjustment = min(2.0, 1 + distance)  # Increase buy size
            sell_adjustment = max(0.2, 1 - (distance * 1.5))  # Reduce more aggressively
        
        # Apply position limit factor
        buy_order_amount = self.order_amount * Decimal(str(buy_adjustment)) * Decimal(str(position_limit_factor))
        sell_order_amount = self.order_amount * Decimal(str(sell_adjustment)) * Decimal(str(position_limit_factor))
        
        self.logger().info(f"Order amount adjustments: inventory_ratio={inventory_ratio:.4f}, "
                          f"buy_adjustment={buy_adjustment:.4f}, sell_adjustment={sell_adjustment:.4f}")
        
        return buy_order_amount, sell_order_amount
    
    def check_and_update_trailing_stop(self):
        """
        Implements a trailing stop mechanism to limit downside risk
        """
        if not self._historical_prices or len(self._historical_prices) < 2:
            return False
        
        current_price = self._historical_prices[-1]
        
        # Initialize trailing stop if not set
        if self._trailing_stop_price is None:
            self._trailing_stop_price = current_price * (1 - self.trailing_stop_pct)
            return False
        
        # Update trailing stop if price moves up
        if current_price > self._trailing_stop_price / (1 - self.trailing_stop_pct):
            self._trailing_stop_price = current_price * (1 - self.trailing_stop_pct)
        
        # Check if stop is triggered
        if current_price < self._trailing_stop_price:
            self.logger().warning(f"Trailing stop triggered at {current_price}, stop level: {self._trailing_stop_price}")
            return True
        
        return False
    
    async def create_orders(self):
        # Calculate current market parameters
        mid_price = self.market_info.get_mid_price()
        spread = self.calculate_adaptive_spread()
        buy_amount, sell_amount = self.calculate_order_amount()
        
        # Calculate order prices
        buy_price = mid_price * (Decimal("1") - spread)
        sell_price = mid_price * (Decimal("1") + spread)
        
        # Check trailing stop
        stop_triggered = self.check_and_update_trailing_stop()
        
        # Adjust orders based on Bollinger Bands
        if hasattr(self, "_bb_state"):
            bb = self._bb_state
            current_price = Decimal(str(self._historical_prices[-1]))
            bb_upper = Decimal(str(bb['upper']))
            bb_lower = Decimal(str(bb['lower']))
            bb_middle = Decimal(str(bb['middle']))
            
            # Adjust buy price based on lower band
            if current_price < bb_lower * Decimal("1.01"):  # Price near or below lower band
                # More aggressive buy close to lower band
                buy_price = max(current_price * Decimal("0.995"), bb_lower * Decimal("0.99"))
                # Increase buy amount on strong signals
                if bb['crossunder']:
                    buy_amount = buy_amount * Decimal("1.5")
                    self.logger().info(f"Increasing buy amount due to BB lower band crossunder")
            
            # Adjust sell price based on upper band
            if current_price > bb_upper * Decimal("0.99"):  # Price near or above upper band
                # More aggressive sell close to upper band
                sell_price = min(current_price * Decimal("1.005"), bb_upper * Decimal("1.01"))
                # Increase sell amount on strong signals
                if bb['crossover']:
                    sell_amount = sell_amount * Decimal("1.5")
                    self.logger().info(f"Increasing sell amount due to BB upper band crossover")
            
            # Additional logic for price between bands
            if current_price > bb_middle and current_price < bb_upper:
                # In upper half of the bands, favor selling
                sell_amount = sell_amount * Decimal("1.1")
                buy_amount = buy_amount * Decimal("0.9")
            elif current_price < bb_middle and current_price > bb_lower:
                # In lower half of the bands, favor buying
                buy_amount = buy_amount * Decimal("1.1")
                sell_amount = sell_amount * Decimal("0.9")
        
        if stop_triggered:
            # Only place sell orders if stop is triggered
            sell_amount = self.market_info.base_balance * Decimal("0.5")  # Sell half of base asset
            buy_amount = Decimal("0")
            self.logger().warning(f"Risk management: trailing stop triggered, only placing sell orders")
        
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
        
        # Check Bollinger Bands state
        bb_signal = 0
        if hasattr(self, "_bb_state"):
            bb = self._bb_state
            
            # Calculate volatility from band width
            volatility = bb['width']
            
            # Detect trends using crossovers
            if bb['crossover']:
                bb_signal = -2  # Strong bearish
            elif bb['crossunder']:
                bb_signal = 2   # Strong bullish
                
            # Check price position relative to bands
            current_price = self._historical_prices[-1]
            band_position = (current_price - bb['lower']) / (bb['upper'] - bb['lower'])
            
            if band_position > 0.8:  # Near upper band
                bb_signal -= 1
            elif band_position < 0.2:  # Near lower band
                bb_signal += 1
                
            # Adjust parameters based on volatility
            if volatility > 0.04:  # High volatility
                self.max_spread = Decimal("0.01")  # Wider spreads to account for volatility
            elif volatility < 0.01:  # Low volatility
                self.max_spread = Decimal("0.003")  # Tighter spreads for better execution
            else:  # Medium volatility
                self.max_spread = Decimal("0.005")
        
        # Update strategy parameters based on combined signals
        if (total_score > 70) or (bb_signal > 1):  # Strong bullish conditions
            self.min_spread = Decimal("0.001")  # Tighter spreads to capture opportunity
            self.max_inventory_ratio = 0.7  # Allow more base asset inventory
            self.logger().info(f"Adjusting for bullish market: min_spread={self.min_spread}, max_inventory_ratio={self.max_inventory_ratio}")
        elif (total_score < -70) or (bb_signal < -1):  # Strong bearish conditions
            self.min_spread = Decimal("0.005")  # Wider spreads to manage risk
            self.max_inventory_ratio = 0.3  # Reduce base asset inventory
            self.logger().info(f"Adjusting for bearish market: min_spread={self.min_spread}, max_inventory_ratio={self.max_inventory_ratio}")
        else:  # Neutral market conditions
            self.min_spread = Decimal("0.002")
            self.max_inventory_ratio = 0.5
            self.logger().info(f"Adjusting for neutral market: min_spread={self.min_spread}, max_inventory_ratio={self.max_inventory_ratio}")
    
    def calculate_performance_metrics(self):
        """
        Calculate advanced performance metrics for the strategy
        """
        if self._start_base_balance is None or self._start_price is None:
            # Initialize tracking on first call
            self._start_base_balance = self.market_info.base_balance
            self._start_quote_balance = self.market_info.quote_balance
            self._start_price = self.market_info.get_mid_price()
            return {}
        
        current_price = self.market_info.get_mid_price()
        current_base = self.market_info.base_balance
        current_quote = self.market_info.quote_balance
        
        # Calculate portfolio values in quote currency
        start_value = self._start_base_balance * self._start_price + self._start_quote_balance
        current_value = current_base * current_price + current_quote
        
        # Hold value (if just held the initial position)
        hold_value = self._start_base_balance * current_price + self._start_quote_balance
        
        # Calculate metrics
        pnl = current_value - start_value
        pnl_pct = (pnl / start_value) if start_value > 0 else Decimal("0")
        vs_hold = (current_value - hold_value) / hold_value if hold_value > 0 else Decimal("0")
        
        # Calculate Sharpe-like ratio if we have trade data
        sharpe = Decimal("0")
        if len(self._trade_values) > 1:
            returns = [self._trade_values[i] / self._trade_values[i-1] - 1 for i in range(1, len(self._trade_values))]
            avg_return = sum(returns) / len(returns)
            std_dev = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe = avg_return / std_dev if std_dev > 0 else Decimal("0")
        
        win_rate = self._win_trades / self._total_trades if self._total_trades > 0 else 0
        
        metrics = {
            "start_time": self._start_time,
            "duration": time.time() - self._start_time,
            "start_base": self._start_base_balance,
            "start_quote": self._start_quote_balance,
            "current_base": current_base,
            "current_quote": current_quote,
            "start_price": self._start_price,
            "current_price": current_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "vs_hold": vs_hold,
            "fees": self._total_fees,
            "total_trades": self._total_trades,
            "win_rate": win_rate,
            "sharpe": sharpe
        }
        
        return metrics
    
    async def format_status(self) -> str:
        """
        Returns an enhanced status string with detailed performance metrics
        """
        if not self._historical_prices:
            return "No data collected yet..."
        
        mid_price = self.market_info.get_mid_price()
        base_balance = self.market_info.base_balance
        quote_balance = self.market_info.quote_balance
        inventory_ratio = self.calculate_inventory_ratio()
        
        # Get performance metrics
        metrics = self.calculate_performance_metrics()
        
        # Format durations
        duration_seconds = int(metrics.get("duration", 0))
        days, remainder = divmod(duration_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        # Add Bollinger Bands information if available
        bb_info = ""
        if hasattr(self, "_bb_state"):
            bb = self._bb_state
            bb_info = (
                f"\nBollinger Bands (IDEAL BB with MA):\n"
                f"1st Length: {self.bb_length1}, 2nd Length: {self.bb_length2}\n"
                f"MA Type: {self.bb_ma_type}, Source: {self.bb_source}\n"
                f"VWAP: L={self.vwap_length}, S={self.vwap_source}, O={self.vwap_offset}\n"
                f"Lookback: {self.bb_lookback}, Gain: {self.bb_gain}, Kalman: {self.bb_use_kalman}\n"
                f"Upper Band: {bb['upper']:.6f}\n"
                f"Middle Band: {bb['middle']:.6f}\n"
                f"Lower Band: {bb['lower']:.6f}\n"
                f"Band Width: {bb['width']:.4f}\n"
                f"Recent Crossover: {'Yes' if bb['crossover'] else 'No'}\n"
                f"Recent Crossunder: {'Yes' if bb['crossunder'] else 'No'}\n"
            )
        
        status_msg = (
            f"Strategy: Adaptive Market Making\n"
            f"Trading Pair: {self.market_info.trading_pair}\n"
            f"Mid Price: {mid_price:.6f}\n"
            f"Base Balance: {base_balance:.6f}\n"
            f"Quote Balance: {quote_balance:.6f}\n"
            f"Inventory Ratio: {inventory_ratio:.2%} (Target: {(self.max_inventory_ratio + self.min_inventory_ratio)/2:.2%})\n"
            f"{bb_info}"
            f"\nIndicator Scores:\n"
            f"RSI: {self._indicator_scores['rsi']}\n"
            f"MACD: {self._indicator_scores['macd']}\n"
            f"EMA: {self._indicator_scores['ema']}\n"
            f"BBands: {self._indicator_scores['bbands']}\n"
            f"Volume: {self._indicator_scores['volume']}\n"
            f"Total Score: {sum(self._indicator_scores.values())}\n"
            f"\nPerformance (Running: {duration_str}):\n"
            f"PnL: {metrics.get('pnl', 0):.6f} ({metrics.get('pnl_pct', 0):.2%})\n"
            f"vs. HODL: {metrics.get('vs_hold', 0):.2%}\n"
            f"Win Rate: {metrics.get('win_rate', 0):.2%}\n"
            f"Trades: {metrics.get('total_trades', 0)}\n"
            f"Fees: {metrics.get('fees', 0):.6f}\n"
            f"Sharpe: {metrics.get('sharpe', 0):.4f}\n"
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
        
        # Calculate performance metrics for logging
        _ = self.calculate_performance_metrics()
        
        # Cancel old orders
        await self.cancel_old_orders()
        
        # Create new orders
        await self.create_orders()
    
    def did_fill_order(self, order_filled_event):
        """
        Enhanced order fill tracking with trade metrics
        """
        order_id = order_filled_event.order_id
        price = order_filled_event.price
        amount = order_filled_event.amount
        trade_type = order_filled_event.trade_type
        fee = order_filled_event.trade_fee
        
        # Track trading metrics
        self._total_trades += 1
        
        # Calculate trade profit/loss (simplified)
        mid_price = self.market_info.get_mid_price()
        if trade_type is TradeType.BUY:
            # For buys, profit if bought below mid price
            trade_pnl = (mid_price - price) * amount
        else:
            # For sells, profit if sold above mid price
            trade_pnl = (price - mid_price) * amount
        
        # Update win/loss counters
        if trade_pnl > 0:
            self._win_trades += 1
        
        # Accumulate profit
        self._trade_profit += trade_pnl
        
        # Track fees
        fee_amount = sum(token.amount for token in fee.flat_fees)
        self._total_fees += fee_amount
        
        # Track portfolio value for Sharpe ratio calculation
        current_value = (self.market_info.base_balance * mid_price) + self.market_info.quote_balance
        self._trade_values.append(current_value)
        
        # Log trade information
        self.logger().info(f"Order filled - type: {trade_type}, "
                          f"price: {price}, amount: {amount}, "
                          f"trade_pnl: {trade_pnl}, fee: {fee_amount}")
        
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
