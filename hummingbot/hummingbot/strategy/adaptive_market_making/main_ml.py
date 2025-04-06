from decimal import Decimal
try:
    import numpy as np
    import pandas as pd
except ImportError:
    import sys
    import subprocess
    import os
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "numpy"])
    import numpy as np
    import pandas as pd

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType, TradeType
import time
import logging
import os
from typing import Dict, List, Optional
import datetime

# Import ML model components
from hummingbot.strategy.adaptive_market_making.models.ml_models import FeatureEngineering, LSTMModel, EnsembleModel, OnlineModelTrainer, MarketRegimeDetector

class AdaptiveMarketMakingMLStrategy(StrategyPyBase):
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
    
    # ML Model parameters
    use_ml: bool = True
    ml_data_buffer_size: int = 5000
    ml_update_interval: int = 3600  # Update ML models every hour
    ml_confidence_threshold: float = 0.65  # Minimum confidence for ML signals
    ml_signal_weight: float = 0.35  # Weight of ML signal in final decision
    ml_model_dir: str = "./models"  # Directory for storing ML models
    
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
                 trailing_stop_pct: Decimal = Decimal("0.02"),
                 use_ml: bool = True,
                 ml_data_buffer_size: int = 5000,
                 ml_update_interval: int = 3600,
                 ml_confidence_threshold: float = 0.65,
                 ml_signal_weight: float = 0.35,
                 ml_model_dir: str = "./models"):
        
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
        
        # ML Model parameters
        self.use_ml = use_ml
        self.ml_data_buffer_size = ml_data_buffer_size
        self.ml_update_interval = ml_update_interval
        self.ml_confidence_threshold = ml_confidence_threshold
        self.ml_signal_weight = ml_signal_weight
        self.ml_model_dir = ml_model_dir
        
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
        
        # ML Model components
        if self.use_ml:
            # Initialize ML components
            self._feature_engineering = FeatureEngineering()
            self._online_trainer = OnlineModelTrainer(
                data_buffer_size=self.ml_data_buffer_size,
                update_interval=self.ml_update_interval,
                models_dir=self.ml_model_dir,
                feature_engineering=self._feature_engineering
            )
            self._market_regime_detector = MarketRegimeDetector(lookback_window=100)
            self._ml_prediction = {"signal": 0, "confidence": 0.5, "raw_prediction": 0.5}
            self._market_regime = {"regime": "unknown", "confidence": 0.0, "trend_direction": 0}
        
        # Register event listeners
        self.add_markets([market_info.market])
        
        self.logger().info("Adaptive Market Making strategy initialized.")
        if self.use_ml:
            self.logger().info("ML components initialized with model directory: " + self.ml_model_dir)
            # Create models directory if it doesn't exist
            os.makedirs(self.ml_model_dir, exist_ok=True)

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
        open_prices = np.array([float(candle.open) for candle in candles])
        timestamps = np.array([candle.timestamp for candle in candles])
        
        # Calculate price data based on source
        if self.bb_source == "hl2":
            price_data = (high_prices + low_prices) / 2
        elif self.bb_source == "hlc3":
            price_data = (high_prices + low_prices + close_prices) / 3
        elif self.bb_source == "ohlc4":
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
            
        # ML Model integration
        if self.use_ml and len(candles) > 0:
            # Prepare data for ML model
            latest_candle = candles[-1]
            
            # Create a dictionary with OHLCV data
            candle_data = {
                "timestamp": latest_candle.timestamp,
                "open": float(latest_candle.open),
                "high": float(latest_candle.high),
                "low": float(latest_candle.low),
                "close": float(latest_candle.close),
                "volume": float(latest_candle.volume),
                "date": datetime.datetime.fromtimestamp(latest_candle.timestamp / 1000.0)
            }
            
            # Add data to ML model buffer
            self._online_trainer.add_data_point(candle_data)
            
            # Detect market regime
            self._market_regime = self._market_regime_detector.detect_regime(close_prices)
            
            # Get ML prediction
            if len(self._online_trainer.data_buffer) >= 100:  # Ensure enough data for prediction
                self._ml_prediction = self._online_trainer.get_prediction(candle_data)
                
                # Log ML prediction
                self.logger().info(f"ML Prediction: Signal={self._ml_prediction['signal']}, "
                                   f"Confidence={self._ml_prediction['confidence']:.4f}, "
                                   f"Market Regime={self._market_regime['regime']}, "
                                   f"Regime Confidence={self._market_regime['confidence']:.4f}")
                
                # Adjust indicator scores based on ML prediction
                if self._ml_prediction["confidence"] >= self.ml_confidence_threshold:
                    ml_impact = int(30 * self._ml_prediction["confidence"] * self._ml_prediction["signal"])
                    self._indicator_scores["ml"] = ml_impact
                else:
                    self._indicator_scores["ml"] = 0
    
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
        
        # Base spread (within min/max bounds)
        base_spread = (self.max_spread + self.min_spread) / 2
        
        # Get volatility adjustment
        atr = self.calculate_atr(self._historical_prices, 14)
        current_price = self._historical_prices[-1] if len(self._historical_prices) > 0 else Decimal("0")
        normalized_atr = atr / current_price if current_price > 0 else 0
        
        # Increase spread in volatile markets
        volatility_component = normalized_atr * self.volatility_adjustment * 50
        
        # Inventory adjustment
        inventory_ratio = self.calculate_inventory_ratio()
        inventory_factor = 0
        
        if inventory_ratio > self.max_inventory_ratio:
            # Too much base asset, prioritize selling
            inventory_factor = (inventory_ratio - self.max_inventory_ratio) * 3
        elif inventory_ratio < self.min_inventory_ratio:
            # Too little base asset, prioritize buying
            inventory_factor = (self.min_inventory_ratio - inventory_ratio) * -3
            
        # ML model adjustments
        ml_adjustment = 0
        if self.use_ml and "ml" in self._indicator_scores:
            # Get ML signal impact
            ml_adjustment = self._indicator_scores["ml"] / 200
            
            # Factor in market regime detection
            if self._market_regime["regime"] == "trending" and self._market_regime["confidence"] > 0.6:
                # In trending markets, tighten spread to follow trend
                trend_direction = self._market_regime["trend_direction"]
                if trend_direction > 0:  # Uptrend
                    # Decrease buy spread, increase sell spread for uptrends
                    ml_adjustment -= 0.05 * self._market_regime["confidence"]
                else:  # Downtrend
                    # Increase buy spread, decrease sell spread for downtrends
                    ml_adjustment += 0.05 * self._market_regime["confidence"]
            
            elif self._market_regime["regime"] == "volatile" and self._market_regime["confidence"] > 0.6:
                # In volatile markets, widen spread to reduce risk
                ml_adjustment += 0.1 * self._market_regime["confidence"]
            
            elif self._market_regime["regime"] == "ranging" and self._market_regime["confidence"] > 0.6:
                # In ranging markets, tighten spread to capture small movements
                ml_adjustment -= 0.03 * self._market_regime["confidence"]
                
        # Combine all factors with weights (total score has highest weight)
        total_adjustment = (
            (total_score / 250) * 0.5 +  # Technical indicators (50%)
            volatility_component * 0.2 +  # Volatility (20%)
            inventory_factor * 0.15 +     # Inventory management (15%)
            ml_adjustment * self.ml_signal_weight  # ML predictions (set by ml_signal_weight parameter)
        )
        
        # Adjust base spread
        adjusted_spread = base_spread * (1 + total_adjustment)
        
        # Ensure within min/max bounds
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
        """Calculate order amounts for buy and sell orders with dynamic position sizing based on indicators and ML predictions"""
        
        # Get base amount (default)
        base_amount = self.order_amount
        
        # Get indicator score
        total_score = sum(self._indicator_scores.values())
        
        # Get inventory ratio
        inventory_ratio = self.calculate_inventory_ratio()
        target_ratio = (self.max_inventory_ratio + self.min_inventory_ratio) / 2
        
        # Adjust buy and sell amounts based on inventory
        buy_adjustment = 1.0
        sell_adjustment = 1.0
        
        # If we have too much inventory, reduce buy orders
        if inventory_ratio > self.max_inventory_ratio:
            buy_adjustment = max(0.2, 1 - (inventory_ratio - self.max_inventory_ratio) * 3)
            sell_adjustment = min(2.0, 1 + (inventory_ratio - target_ratio) * 2)
        # If we have too little inventory, reduce sell orders
        elif inventory_ratio < self.min_inventory_ratio:
            sell_adjustment = max(0.2, 1 - (self.min_inventory_ratio - inventory_ratio) * 3)
            buy_adjustment = min(2.0, 1 + (target_ratio - inventory_ratio) * 2)
            
        # Calculate position size based on market conditions
        if total_score > 50:  # Strong bullish
            condition_adjustment_buy = 1.25
            condition_adjustment_sell = 0.80
        elif total_score < -50:  # Strong bearish
            condition_adjustment_buy = 0.80
            condition_adjustment_sell = 1.25
        else:
            condition_adjustment_buy = 1.0 + (total_score / 200)
            condition_adjustment_sell = 1.0 - (total_score / 200)
            
        # ML model adjustments for order sizing
        ml_buy_adjustment = 1.0
        ml_sell_adjustment = 1.0
        
        if self.use_ml and hasattr(self, "_ml_prediction"):
            # Only apply ML adjustments if confidence is high enough
            if self._ml_prediction["confidence"] >= self.ml_confidence_threshold:
                # Adjust based on ML signal and confidence
                if self._ml_prediction["signal"] > 0:  # Bullish
                    ml_factor = self._ml_prediction["confidence"] * self.ml_signal_weight * 2
                    ml_buy_adjustment = 1.0 + ml_factor
                    ml_sell_adjustment = 1.0 - (ml_factor / 2)
                elif self._ml_prediction["signal"] < 0:  # Bearish
                    ml_factor = self._ml_prediction["confidence"] * self.ml_signal_weight * 2
                    ml_buy_adjustment = 1.0 - (ml_factor / 2)
                    ml_sell_adjustment = 1.0 + ml_factor
                    
            # Additional adjustment based on market regime
            if hasattr(self, "_market_regime") and self._market_regime["confidence"] > 0.5:
                regime = self._market_regime["regime"]
                
                if regime == "volatile":
                    # In volatile markets, reduce position sizes
                    vol_factor = self._market_regime["confidence"] * 0.4
                    ml_buy_adjustment *= (1.0 - vol_factor)
                    ml_sell_adjustment *= (1.0 - vol_factor)
                elif regime == "trending" and self._market_regime["trend_direction"] != 0:
                    # In trending markets, increase size in trend direction
                    trend_factor = self._market_regime["confidence"] * 0.3
                    if self._market_regime["trend_direction"] > 0:  # Uptrend
                        ml_buy_adjustment *= (1.0 + trend_factor)
                    else:  # Downtrend
                        ml_sell_adjustment *= (1.0 + trend_factor)
                        
        # Combine all adjustments
        final_buy_adjustment = buy_adjustment * condition_adjustment_buy * ml_buy_adjustment
        final_sell_adjustment = sell_adjustment * condition_adjustment_sell * ml_sell_adjustment
        
        # Ensure adjustments are within reasonable limits (20% to 200% of base)
        final_buy_adjustment = max(0.2, min(2.0, final_buy_adjustment))
        final_sell_adjustment = max(0.2, min(2.0, final_sell_adjustment))
        
        # Apply adjustments to base amount
        buy_amount = base_amount * Decimal(str(final_buy_adjustment))
        sell_amount = base_amount * Decimal(str(final_sell_adjustment))
        
        # Log adjustments if they're significant
        if abs(final_buy_adjustment - 1.0) > 0.1 or abs(final_sell_adjustment - 1.0) > 0.1:
            self.logger().info(f"Order size adjustments: buy={final_buy_adjustment:.2f}, sell={final_sell_adjustment:.2f}")
            if self.use_ml and hasattr(self, "_ml_prediction") and self._ml_prediction["confidence"] >= self.ml_confidence_threshold:
                self.logger().info(f"ML impact: signal={self._ml_prediction['signal']}, confidence={self._ml_prediction['confidence']:.2f}")
        
        return buy_amount, sell_amount
    
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
        
        # Further adjustments based on ML model predictions
        ml_influence = False
        if self.use_ml and hasattr(self, "_ml_prediction") and self._ml_prediction["confidence"] >= self.ml_confidence_threshold:
            ml_signal = self._ml_prediction["signal"]
            ml_confidence = self._ml_prediction["confidence"]
            
            self.logger().info(f"Applying ML adjustments: Signal={ml_signal}, Confidence={ml_confidence:.4f}")
            
            # Mark that ML influenced this order
            ml_influence = True
            
            # Adjust order prices based on ML predictions
            if ml_signal > 0:  # Bullish prediction
                # Make buy more aggressive, sell less aggressive
                buy_price = buy_price * Decimal(str(1 + 0.05 * ml_confidence))  # Increase buy price to improve fill likelihood
                buy_amount = buy_amount * Decimal(str(1 + 0.2 * ml_confidence))  # Increase buy size
                
                # For sell orders, either increase price or do nothing depending on confidence
                if ml_confidence > 0.8:  # Very high confidence
                    sell_price = sell_price * Decimal(str(1 + 0.03 * ml_confidence))  # Still place sells but at higher prices
                
            elif ml_signal < 0:  # Bearish prediction
                # Make sell more aggressive, buy less aggressive
                sell_price = sell_price * Decimal(str(1 - 0.05 * ml_confidence))  # Decrease sell price to improve fill likelihood
                sell_amount = sell_amount * Decimal(str(1 + 0.2 * ml_confidence))  # Increase sell size
                
                # For buy orders, either decrease price or do nothing depending on confidence
                if ml_confidence > 0.8:  # Very high confidence
                    buy_price = buy_price * Decimal(str(1 - 0.03 * ml_confidence))  # Still place buys but at lower prices
            
            # Additional adjustments based on market regime
            if hasattr(self, "_market_regime") and self._market_regime["confidence"] > 0.6:
                regime = self._market_regime["regime"]
                
                if regime == "trending_volatile":
                    # In trending volatile markets, be more aggressive in the trend direction
                    trend_direction = self._market_regime["trend_direction"]
                    if trend_direction > 0 and ml_signal > 0:  # Strong uptrend signal
                        buy_amount = buy_amount * Decimal("1.2")
                        buy_price = buy_price * Decimal("1.01")  # More aggressive on buy side
                    elif trend_direction < 0 and ml_signal < 0:  # Strong downtrend signal
                        sell_amount = sell_amount * Decimal("1.2")
                        sell_price = sell_price * Decimal("0.99")  # More aggressive on sell side
                
                elif regime == "ranging" and self._market_regime["confidence"] > 0.7:
                    # In ranging markets, place orders closer to the bands
                    if hasattr(self, "_bb_state"):
                        bb_width = self._bb_state["width"]
                        if bb_width < 0.03:  # Narrow bands indicating tight range
                            buy_price = max(buy_price, Decimal(str(self._bb_state["lower"] * 1.01)))
                            sell_price = min(sell_price, Decimal(str(self._bb_state["upper"] * 0.99)))
        
        # Apply trailing stop if triggered
        if stop_triggered:
            self.logger().info("Trailing stop triggered - skipping buy orders")
            buy_amount = Decimal("0")
        
        # Clear existing orders before placing new ones
        await self.cancel_all_orders()
        
        # Place orders with metadata
        metadata = {"ml_influence": ml_influence}
        
        # Place buy order if amount is positive
        if buy_amount > Decimal("0"):
            await self.place_order(TradeType.BUY, buy_price, buy_amount, metadata)
            
        # Place sell order if amount is positive
        if sell_amount > Decimal("0"):
            await self.place_order(TradeType.SELL, sell_price, sell_amount, metadata)
    
    async def place_order(self, trade_type, price, amount, metadata=None):
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
            "timestamp": time.time(),
            "metadata": metadata
        }
        
        self.logger().info(f"Placed {'buy' if trade_type is TradeType.BUY else 'sell'} order {order_id} "
                         f"for {amount} {self.market_info.base_asset} at {price} {self.market_info.quote_asset}")
    
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
        
        # Use market regime detection from ML model if available
        market_regime = None
        regime_confidence = 0.0
        
        if self.use_ml and hasattr(self, "_market_regime"):
            market_regime = self._market_regime.get("regime")
            regime_confidence = self._market_regime.get("confidence", 0.0)
            trend_direction = self._market_regime.get("trend_direction", 0)
            
            if regime_confidence > 0.6:
                self.logger().info(f"Adjusting strategy based on ML market regime: {market_regime} "
                                 f"(confidence: {regime_confidence:.4f}, trend: {trend_direction})")
                
                # Adjust parameters based on market regime
                if market_regime == "trending":
                    # In trending markets, use tighter spreads to capture trend movement
                    self.min_spread = Decimal("0.0015")  # 0.15%
                    self.max_spread = Decimal("0.008")   # 0.8%
                    
                    # Update inventory targets based on trend direction
                    if trend_direction > 0:  # Uptrend
                        # Hold more base asset in uptrends
                        self.max_inventory_ratio = 0.7
                        self.min_inventory_ratio = 0.4
                    else:  # Downtrend
                        # Hold less base asset in downtrends
                        self.max_inventory_ratio = 0.4
                        self.min_inventory_ratio = 0.15
                        
                elif market_regime == "ranging":
                    # In ranging markets, use wider spreads to profit from oscillations
                    self.min_spread = Decimal("0.002")   # 0.2%
                    self.max_spread = Decimal("0.012")   # 1.2%
                    
                    # Balanced inventory for range markets
                    self.max_inventory_ratio = 0.6
                    self.min_inventory_ratio = 0.3
                    
                elif market_regime == "volatile" or market_regime == "trending_volatile":
                    # In volatile markets, use wider spreads to account for risk
                    self.min_spread = Decimal("0.004")   # 0.4%
                    self.max_spread = Decimal("0.025")   # 2.5%
                    
                    # Tighter inventory bands to reduce exposure
                    self.max_inventory_ratio = 0.5
                    self.min_inventory_ratio = 0.25
                    
                    # Increase trailing stop percentage in volatile markets
                    self.trailing_stop_pct = Decimal("0.03")  # 3%
                    
                    # If both ML and traditional indicators agree on direction in volatile markets
                    if hasattr(self, "_ml_prediction") and self._ml_prediction["confidence"] > 0.7:
                        ml_signal = self._ml_prediction["signal"]
                        
                        if ml_signal > 0 and total_score > 30:  # Both bullish
                            # More aggressive with strong bullish consensus
                            self.max_inventory_ratio = 0.65
                        elif ml_signal < 0 and total_score < -30:  # Both bearish
                            # More conservative with strong bearish consensus
                            self.max_inventory_ratio = 0.3
                
                # Log parameter adjustments
                self.logger().info(f"Adjusted parameters for {market_regime} regime: "
                                 f"spread=[{self.min_spread}-{self.max_spread}], "
                                 f"inventory=[{self.min_inventory_ratio}-{self.max_inventory_ratio}]")
        else:
            # Fallback to traditional indicator-based adjustments if no ML model
            if hasattr(self, "_bb_state"):
                bb = self._bb_state
                
                # Calculate volatility from band width
                volatility = bb['width']
                
                # Detect trends using crossovers
                if bb['crossover']:
                    bb_signal = -2  # Strong bearish
                elif bb['crossunder']:
                    bb_signal = 2   # Strong bullish
                else:
                    bb_signal = 0
                    
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
    
    def calculate_performance_metrics(self):
        """Calculate performance metrics including ML model contribution"""
        # Check if we have enough data
        if not self._start_base_balance or not self._start_quote_balance or not self._start_price:
            return None
            
        # Get current balances and price
        current_base_balance = self.market_info.base_balance
        current_quote_balance = self.market_info.quote_balance
        current_price = self.market_info.get_mid_price()
        
        # Calculate current portfolio value
        current_base_value_in_quote = current_base_balance * current_price
        current_total_value = current_base_value_in_quote + current_quote_balance
        
        # Calculate initial portfolio value
        initial_base_value_in_quote = self._start_base_balance * self._start_price
        initial_total_value = initial_base_value_in_quote + self._start_quote_balance
        
        # Calculate profit/loss
        total_profit = current_total_value - initial_total_value
        profit_percent = (total_profit / initial_total_value) * 100 if initial_total_value > 0 else 0
        
        # Calculate HODL comparison
        hodl_base_value = self._start_base_balance * current_price
        hodl_total_value = hodl_base_value + self._start_quote_balance
        hodl_profit = hodl_total_value - initial_total_value
        hodl_profit_percent = (hodl_profit / initial_total_value) * 100 if initial_total_value > 0 else 0
        
        # Calculate alpha (excess return over HODL)
        alpha = profit_percent - hodl_profit_percent
        
        # Calculate win rate
        win_rate = (self._win_trades / self._total_trades) * 100 if self._total_trades > 0 else 0
        
        # Calculate average profit per trade
        avg_profit_per_trade = self._trade_profit / self._total_trades if self._total_trades > 0 else 0
        
        # Calculate running time
        running_time = time.time() - self._start_time
        hours, remainder = divmod(int(running_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        running_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Calculate Sharpe ratio approximation (if enough trades)
        sharpe_ratio = 0
        if len(self._trade_values) > 10:
            returns = np.diff(self._trade_values) / self._trade_values[:-1]
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(365) if np.std(returns) > 0 else 0
            
        # ML model contribution metrics
        ml_contribution = None
        if self.use_ml and hasattr(self, "_ml_prediction") and self._total_trades > 0:
            total_ml_influence_trades = sum(1 for trade_id, order in self._current_orders.items() 
                                         if hasattr(order, "metadata") and 
                                         order.metadata.get("ml_influence", False))
            
            ml_contribution = {
                "ml_trades": total_ml_influence_trades,
                "ml_trade_percent": (total_ml_influence_trades / self._total_trades) * 100,
                "ml_confidence_avg": getattr(self, "_ml_confidence_sum", 0) / total_ml_influence_trades
                                    if total_ml_influence_trades > 0 else 0
            }
        
        return {
            "total_profit": total_profit,
            "profit_percent": profit_percent,
            "hodl_profit": hodl_profit,
            "hodl_profit_percent": hodl_profit_percent,
            "alpha": alpha,
            "win_rate": win_rate,
            "avg_profit_per_trade": avg_profit_per_trade,
            "total_trades": self._total_trades,
            "win_trades": self._win_trades,
            "loss_trades": self._loss_trades,
            "total_fees": self._total_fees,
            "running_time": running_time_str,
            "sharpe_ratio": sharpe_ratio,
            "ml_contribution": ml_contribution
        }
    
    async def format_status(self) -> str:
        """
        Format status message with enhanced info including ML model metrics
        """
        if not self._ready_to_trade:
            return "Market connectors are not ready."
            
        lines = []
        mid_price = self.market_info.get_mid_price()
        spread = self.calculate_adaptive_spread()
        
        # Assets and balance info
        base_asset = self.market_info.base_asset
        quote_asset = self.market_info.quote_asset
        base_balance = self.market_info.base_balance
        quote_balance = self.market_info.quote_balance
            
        # Format status message
        lines.extend([
            f"Exchange: {self.market_info.market.display_name}",
            f"Market: {base_asset}-{quote_asset}",
            f"Mid price: {mid_price:.8f}",
            f"Spread: {spread:.6f} | Min: {self.min_spread:.6f} | Max: {self.max_spread:.6f}",
            f"Inventory ratio: {self.calculate_inventory_ratio():.4f}",
            f"Base balance: {base_balance:.6f} {base_asset}",
            f"Quote balance: {quote_balance:.6f} {quote_asset}",
        ])
        
        # Technical indicator scores
        indicator_lines = [
            "\nTechnical Indicators:",
            f"RSI: {self._indicator_scores['rsi']} | MACD: {self._indicator_scores['macd']}",
            f"EMA: {self._indicator_scores['ema']} | BBands: {self._indicator_scores['bbands']}",
            f"Volume: {self._indicator_scores['volume']} | Total: {sum(self._indicator_scores.values())}"
        ]
        lines.extend(indicator_lines)
        
        # ML model information
        if self.use_ml:
            ml_lines = [
                "\nML Model Metrics:",
                f"Model Dir: {self.ml_model_dir}",
                f"Data Points: {len(self._online_trainer.data_buffer) if hasattr(self, '_online_trainer') else 0}",
                f"Signal: {self._ml_prediction['signal'] if hasattr(self, '_ml_prediction') else 'N/A'}",
                f"Confidence: {self._ml_prediction['confidence']:.4f if hasattr(self, '_ml_prediction') else 'N/A'}",
                f"Market Regime: {self._market_regime['regime'] if hasattr(self, '_market_regime') else 'unknown'}",
                f"Regime Confidence: {self._market_regime['confidence']:.4f if hasattr(self, '_market_regime') else 'N/A'}"
            ]
            lines.extend(ml_lines)
        
        # Active orders
        active_orders = len(self._current_orders)
        if active_orders > 0:
            lines.append("\nActive Orders:")
            for order_id, order in self._current_orders.items():
                order_type = "Buy" if order.is_buy else "Sell"
                age = int(time.time() - order.timestamp / 1000)
                lines.append(f"{order_type} {order.quantity} @ {order.price:.8f} | Age: {age}s")
                
        # Performance metrics
        performance_metrics = self.calculate_performance_metrics()
        if performance_metrics:
            lines.extend([
                "\nPerformance Metrics:",
                f"Total profit: {performance_metrics['total_profit']:.6f} {quote_asset}",
                f"Profit %: {performance_metrics['profit_percent']:.2f}%",
                f"Win rate: {performance_metrics['win_rate']:.2f}%",
                f"Total trades: {performance_metrics['total_trades']}",
                f"Total fees: {performance_metrics['total_fees']:.6f} {quote_asset}",
                f"Running time: {performance_metrics['running_time']}"
            ])
            
        return "\n".join(lines)
    
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
