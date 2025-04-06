#!/usr/bin/env python3

"""
Precision Algorithmic Trading Strategy with Weighted Indicators
(Optimized for Crypto Markets)

This strategy assigns weighted scores to indicators and combines them to generate
high-probability signals based on risk tolerance and time horizon.
"""

import time
import logging
import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime
import ccxt
import scipy.stats as stats
import matplotlib.pyplot as plt
from scipy.linalg import cho_factor, cho_solve

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("trading_strategy.log")
    ]
)
logger = logging.getLogger("PrecisionAlgorithmicTrading")

class PrecisionTradingStrategy:
    """
    Precision Trading Strategy that combines multiple weighted indicators,
    multi-timeframe analysis, and advanced trap detection.
    """
    
    def __init__(self, 
                 exchange_id: str = "binance",
                 symbol: str = "BTC/USDT", 
                 risk_level: str = "medium",  # "high", "medium", "low"
                 time_horizon: str = "medium", # "short", "medium", "long"
                 api_key: str = None,
                 api_secret: str = None,
                 test_mode: bool = True):
        
        # Exchange setup
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.api_key = api_key
        self.api_secret = api_secret
        self.test_mode = test_mode
        
        # Initialize exchange connection
        self._initialize_exchange()
        
        # Strategy parameters
        self.risk_level = risk_level
        self.time_horizon = time_horizon
        
        # Set timeframes based on time horizon
        self.timeframes = self._set_timeframes()
        
        # Set scoring thresholds based on time horizon
        self.signal_threshold = self._set_signal_threshold()
        
        # Set stop-loss and take-profit levels based on risk level
        self.risk_params = self._set_risk_parameters()
        
        # Initialize data structures
        self.price_data = {}
        self.indicator_values = {}
        self.indicator_scores = {
            "rsi": 50,
            "macd": 50,
            "ema": 50,
            "bbands": 50,
            "volume": 50,
            "support_resistance": 50
        }
        self.trap_indicators = {
            "volume_delta": 0,
            "order_imbalance": 0,
            "bid_ask_spread": 0,
            "wick_rejection": 0
        }
        
        # Market state
        self.market_regime = {"regime": "unknown", "confidence": 0.0, "trend_direction": 0}
        self.total_score = 50
        
        # Support and resistance levels
        self.support_levels = []
        self.resistance_levels = []
        
        # Active trades
        self.active_positions = {}
        
        # Trading status
        self.last_update_time = 0
        self.update_interval = 60  # seconds
        
        logger.info(f"Strategy initialized with {risk_level} risk and {time_horizon} time horizon")

    def _initialize_exchange(self):
        """Initialize the exchange connection"""
        exchange_class = getattr(ccxt, self.exchange_id)
        self.exchange = exchange_class({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'} if not self.test_mode else {'defaultType': 'spot'}
        })
        
        if self.test_mode:
            # Use testnet if available
            if hasattr(self.exchange, 'set_sandbox_mode'):
                self.exchange.set_sandbox_mode(True)
                logger.info("Using exchange sandbox/testnet mode")
            else:
                logger.warning(f"{self.exchange_id} does not support sandbox mode. Using live API with no execution.")
        
        logger.info(f"Connected to {self.exchange_id} exchange")

    def _set_timeframes(self) -> Dict[str, str]:
        """Set primary and secondary timeframes based on time horizon"""
        if self.time_horizon == "short":
            return {"primary": "1h", "secondary": "15m"}
        elif self.time_horizon == "medium":
            return {"primary": "4h", "secondary": "1h"}
        else:  # long-term
            return {"primary": "1d", "secondary": "4h"}

    def _set_signal_threshold(self) -> float:
        """Set signal threshold based on time horizon"""
        if self.time_horizon == "short":
            return 70
        elif self.time_horizon == "medium":
            return 75
        else:  # long-term
            return 80

    def _set_risk_parameters(self) -> Dict[str, Union[float, Dict]]:
        """Set risk parameters based on risk level"""
        if self.risk_level == "high":
            return {
                "stop_loss_pct": 0.05,  # 5%
                "trailing_start": 0.1,   # 10% profit to start trailing
                "take_profit": {
                    "tp1": {"pct": 0.1, "size": 0.3},  # 10% profit, 30% position
                    "tp2": {"pct": 0.15, "size": 0.3}, # 15% profit, 30% position
                    "tp3": {"pct": 0.2, "size": 0.4}   # 20% profit, 40% position
                },
                "position_size_pct": 0.1,  # 10% of available capital
                "max_leverage": 3          # Up to 3x leverage
            }
        elif self.risk_level == "medium":
            return {
                "stop_loss_pct": 0.07,  # 7%
                "trailing_start": 0.08,  # 8% profit to start trailing
                "take_profit": {
                    "tp1": {"pct": 0.07, "size": 0.5},  # 7% profit, 50% position
                    "tp2": {"pct": 0.12, "size": 0.5}   # 12% profit, 50% position
                },
                "position_size_pct": 0.05,  # 5% of available capital
                "max_leverage": 2           # Up to 2x leverage
            }
        else:  # low risk
            return {
                "stop_loss_pct": 0.1,   # 10%
                "trailing_start": 0.05,  # 5% profit to start trailing
                "take_profit": {
                    "tp1": {"pct": 0.08, "size": 0.5},  # 8% profit, 50% position
                    "tp2": {"pct": 0.12, "size": 0.5}   # 12% profit, 50% position
                },
                "position_size_pct": 0.02,  # 2% of available capital
                "max_leverage": 1           # No leverage
            }

    def _set_indicator_weights(self) -> Dict[str, float]:
        """Set indicator weights based on time horizon"""
        if self.time_horizon == "short":
            return {
                "rsi": 0.10,
                "macd": 0.20,
                "ema": 0.15,
                "bbands": 0.20,
                "volume": 0.25,
                "support_resistance": 0.10
            }
        elif self.time_horizon == "medium":
            return {
                "rsi": 0.15,
                "macd": 0.20,
                "ema": 0.20,
                "bbands": 0.15,
                "volume": 0.15,
                "support_resistance": 0.15
            }
        else:  # long-term
            return {
                "rsi": 0.15,
                "macd": 0.20,
                "ema": 0.25,
                "bbands": 0.15,
                "volume": 0.10,
                "support_resistance": 0.15
            }

    def fetch_market_data(self) -> bool:
        """Fetch market data for all required timeframes"""
        try:
            # Fetch OHLCV data for primary and secondary timeframes
            for tf_name, tf in self.timeframes.items():
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe=tf, limit=100)
                
                # Convert to DataFrame
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                # Store data
                self.price_data[tf_name] = df
            
            # Fetch recent trades for order flow analysis
            trades = self.exchange.fetch_trades(self.symbol, limit=100)
            self.recent_trades = pd.DataFrame(trades)
            
            # Fetch order book for liquidity analysis
            self.order_book = self.exchange.fetch_order_book(self.symbol, limit=20)
            
            # Calculate bid-ask spread
            best_bid = self.order_book['bids'][0][0] if len(self.order_book['bids']) > 0 else 0
            best_ask = self.order_book['asks'][0][0] if len(self.order_book['asks']) > 0 else 0
            self.current_spread = (best_ask - best_bid) / best_bid if best_bid > 0 else 0
            
            # Calculate average spread (simple moving average)
            if not hasattr(self, 'spread_history'):
                self.spread_history = []
            
            self.spread_history.append(self.current_spread)
            if len(self.spread_history) > 50:
                self.spread_history = self.spread_history[-50:]
            
            self.average_spread = np.mean(self.spread_history)
            
            logger.info(f"Market data fetched successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return False

    def calculate_indicators(self) -> None:
        """Calculate all technical indicators for each timeframe"""
        for tf_name, df in self.price_data.items():
            close_prices = df['close'].values
            high_prices = df['high'].values
            low_prices = df['low'].values
            volumes = df['volume'].values
            
            # Calculate RSI
            rsi = self._calculate_rsi(close_prices)
            
            # Calculate MACD
            macd_line, signal_line, histogram = self._calculate_macd(close_prices)
            
            # Calculate EMAs
            ema_short = self._calculate_ema(close_prices, 50)  # 50-period EMA
            ema_long = self._calculate_ema(close_prices, 200)  # 200-period EMA
            
            # Calculate Bollinger Bands
            upper_band, middle_band, lower_band = self._calculate_bollinger_bands(close_prices)
            
            # Calculate ATR for volatility
            atr = self._calculate_atr(high_prices, low_prices, close_prices)
            
            # Store calculated indicators
            self.indicator_values[tf_name] = {
                "rsi": rsi,
                "macd_line": macd_line,
                "signal_line": signal_line,
                "histogram": histogram,
                "ema_short": ema_short,
                "ema_long": ema_long,
                "bb_upper": upper_band,
                "bb_middle": middle_band,
                "bb_lower": lower_band,
                "atr": atr,
                "volumes": volumes
            }
        
        # Calculate support/resistance levels
        self._find_support_resistance()
        
        # Calculate non-lagging trap indicators
        self._calculate_trap_indicators()

    def _calculate_rsi(self, prices, length=14):
        """Calculate Relative Strength Index"""
        if len(prices) < length + 1:
            return 50  # Default value if not enough data
            
        # Calculate price changes
        delta = np.diff(prices)
        
        # Separate gains and losses
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)
        
        # Calculate average gains and losses over the period
        avg_gain = np.mean(gains[:length])
        avg_loss = np.mean(losses[:length])
        
        # Initialize RSI for the first period
        if avg_loss == 0:
            return 100  # Avoid division by zero
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    def _calculate_macd(self, prices, fast_length=12, slow_length=26, signal_length=9):
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow_length:
            return 0, 0, 0  # Default values if not enough data
            
        # Calculate EMAs
        fast_ema = self._calculate_ema(prices, fast_length)
        slow_ema = self._calculate_ema(prices, slow_length)
        
        # Calculate MACD line
        macd_line = fast_ema - slow_ema
        
        # Calculate signal line (EMA of MACD line)
        signal_line = macd_line * 0.9  # Simplified approximation
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram

    def _calculate_ema(self, prices, length):
        """Calculate Exponential Moving Average"""
        if len(prices) < length:
            return prices[-1] if len(prices) > 0 else 0
            
        # Calculate multiplier
        multiplier = 2 / (length + 1)
        
        # Start with SMA for the first value
        ema = np.mean(prices[:length])
        
        # Calculate EMA for remaining prices
        for price in prices[length:]:
            ema = (price - ema) * multiplier + ema
            
        return ema

    def _calculate_bollinger_bands(self, prices, length=20, num_std=2.0):
        """Calculate Bollinger Bands"""
        if len(prices) < length:
            last_price = prices[-1] if len(prices) > 0 else 0
            return last_price * 1.02, last_price, last_price * 0.98
            
        # Calculate middle band (SMA)
        middle_band = np.mean(prices[-length:])
        
        # Calculate standard deviation
        std_dev = np.std(prices[-length:])
        
        # Calculate upper and lower bands
        upper_band = middle_band + (std_dev * num_std)
        lower_band = middle_band - (std_dev * num_std)
        
        return upper_band, middle_band, lower_band

    def _calculate_atr(self, high, low, close, length=14):
        """Calculate Average True Range"""
        if len(high) < 2:
            return 0
            
        # Calculate true ranges
        tr1 = high[1:] - low[1:]  # Current high - current low
        tr2 = np.abs(high[1:] - close[:-1])  # Current high - previous close
        tr3 = np.abs(low[1:] - close[:-1])   # Current low - previous close
        
        # True range is the maximum of the three
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        
        # Calculate average
        atr = np.mean(tr[-length:]) if len(tr) >= length else np.mean(tr)
        
        return atr

    def _find_support_resistance(self):
        """Find support and resistance levels"""
        # Use the primary timeframe for support/resistance
        df = self.price_data['primary']
        
        # Function to identify swing highs and lows
        def find_swings(df, window=5):
            highs = []
            lows = []
            
            for i in range(window, len(df) - window):
                # Check if this is a swing high
                if all(df['high'].iloc[i] > df['high'].iloc[i-j] for j in range(1, window+1)) and \
                   all(df['high'].iloc[i] > df['high'].iloc[i+j] for j in range(1, window+1)):
                    highs.append((df.index[i], df['high'].iloc[i]))
                
                # Check if this is a swing low
                if all(df['low'].iloc[i] < df['low'].iloc[i-j] for j in range(1, window+1)) and \
                   all(df['low'].iloc[i] < df['low'].iloc[i+j] for j in range(1, window+1)):
                    lows.append((df.index[i], df['low'].iloc[i]))
            
            return highs, lows
        
        # Find swing highs and lows
        highs, lows = find_swings(df)
        
        # Group nearby levels (within 0.5% of each other)
        def group_levels(levels, threshold=0.005):
            if not levels:
                return []
                
            # Sort by price
            sorted_levels = sorted(levels, key=lambda x: x[1])
            
            # Group nearby levels
            grouped = []
            current_group = [sorted_levels[0]]
            
            for i in range(1, len(sorted_levels)):
                current_price = sorted_levels[i][1]
                prev_price = current_group[-1][1]
                
                # If close to previous level, add to current group
                if abs(current_price - prev_price) / prev_price < threshold:
                    current_group.append(sorted_levels[i])
                else:
                    # Average the current group and start a new one
                    avg_price = sum(level[1] for level in current_group) / len(current_group)
                    grouped.append(avg_price)
                    current_group = [sorted_levels[i]]
            
            # Add the last group
            if current_group:
                avg_price = sum(level[1] for level in current_group) / len(current_group)
                grouped.append(avg_price)
            
            return grouped
        
        # Group and store support and resistance levels
        self.resistance_levels = group_levels(highs)
        self.support_levels = group_levels(lows)

    def _calculate_trap_indicators(self):
        """Calculate non-lagging indicators specifically for trap detection"""
        # 1. Volume Delta (Buy vs Sell Volume)
        if hasattr(self, 'recent_trades') and 'side' in self.recent_trades.columns:
            buy_volume = self.recent_trades[self.recent_trades['side'] == 'buy']['amount'].sum()
            sell_volume = self.recent_trades[self.recent_trades['side'] == 'sell']['amount'].sum()
            
            total_volume = buy_volume + sell_volume
            if total_volume > 0:
                self.trap_indicators['volume_delta'] = (buy_volume - sell_volume) / total_volume
            else:
                self.trap_indicators['volume_delta'] = 0
        
        # 2. Order Book Imbalance
        if hasattr(self, 'order_book'):
            bid_volume = sum(order[1] for order in self.order_book['bids'][:10])
            ask_volume = sum(order[1] for order in self.order_book['asks'][:10])
            
            total_volume = bid_volume + ask_volume
            if total_volume > 0:
                self.trap_indicators['order_imbalance'] = (bid_volume - ask_volume) / total_volume
            else:
                self.trap_indicators['order_imbalance'] = 0
        
        # 3. Bid-Ask Spread Change Rate
        if hasattr(self, 'current_spread') and hasattr(self, 'average_spread') and self.average_spread > 0:
            self.trap_indicators['bid_ask_spread'] = (self.current_spread - self.average_spread) / self.average_spread
        
        # 4. Wick Rejection (using primary timeframe)
        df = self.price_data['primary']
        if not df.empty:
            last_candle = df.iloc[-1]
            candle_body = abs(last_candle['close'] - last_candle['open'])
            
            if candle_body > 0:
                # For bullish candles
                if last_candle['close'] > last_candle['open']:
                    upper_wick = last_candle['high'] - last_candle['close']
                    lower_wick = last_candle['open'] - last_candle['low']
                # For bearish candles
                else:
                    upper_wick = last_candle['high'] - last_candle['open']
                    lower_wick = last_candle['close'] - last_candle['low']
                
                # Calculate wick-to-body ratio
                self.trap_indicators['upper_wick_ratio'] = upper_wick / candle_body if candle_body > 0 else 0
                self.trap_indicators['lower_wick_ratio'] = lower_wick / candle_body if candle_body > 0 else 0
                
                # Bullish rejection has long lower wick
                # Bearish rejection has long upper wick
                self.trap_indicators['wick_rejection'] = self.trap_indicators['lower_wick_ratio'] - self.trap_indicators['upper_wick_ratio']
            else:
                self.trap_indicators['wick_rejection'] = 0

    def calculate_market_regime(self):
        """Detect current market regime (trending, ranging, volatile)"""
        # Use primary timeframe for regime detection
        df = self.price_data['primary']
        
        if df.empty or len(df) < 50:
            self.market_regime = {"regime": "unknown", "confidence": 0.0, "trend_direction": 0}
            return
        
        # Get price window for analysis
        price_window = df['close'].values[-50:]
        
        # Calculate returns and volatility
        returns = np.diff(price_window) / price_window[:-1]
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        
        # Linear regression for trend analysis
        x = np.arange(len(price_window))
        slope, _, r_value, _, _ = stats.linregress(x, price_window)
        
        # Determine regime
        if volatility > 0.05:  # High volatility
            if abs(r_value) > 0.7:  # Strong trend
                regime = "trending_volatile"
                confidence = abs(r_value) * 0.8 + volatility * 4
                trend_direction = 1 if slope > 0 else -1
            else:
                regime = "volatile"
                confidence = volatility * 10
                trend_direction = 0
        else:  # Lower volatility
            if abs(r_value) > 0.7:  # Strong trend
                regime = "trending"
                confidence = abs(r_value)
                trend_direction = 1 if slope > 0 else -1
            else:
                regime = "ranging"
                confidence = 1 - abs(r_value)
                trend_direction = 0
        
        self.market_regime = {
            "regime": regime,
            "confidence": min(1.0, confidence),
            "trend_direction": trend_direction
        }
        
        logger.info(f"Market regime: {regime} (confidence: {confidence:.2f}, direction: {trend_direction})")

    def calculate_indicator_scores(self):
        """Calculate scores for each indicator based on values"""
        # Get values from primary timeframe
        ind = self.indicator_values['primary']
        
        # Get current price
        current_price = self.price_data['primary']['close'].iloc[-1]
        
        # RSI Score (0-100)
        rsi = ind['rsi']
        if rsi <= 30:
            # Check for RSI divergence
            if self._check_rsi_divergence():
                self.indicator_scores['rsi'] = 85  # Very bullish with divergence
            else:
                self.indicator_scores['rsi'] = 75  # Bullish (oversold)
        elif rsi >= 70:
            if self._check_rsi_divergence(bearish=True):
                self.indicator_scores['rsi'] = 15  # Very bearish with divergence
            else:
                self.indicator_scores['rsi'] = 25  # Bearish (overbought)
        else:
            # Linear interpolation between oversold and overbought
            normalized_rsi = (rsi - 30) / 40  # Scale between 30-70
            self.indicator_scores['rsi'] = 25 + (normalized_rsi * 50)  # Scale to 25-75
        
        # MACD Score (0-100)
        macd_line = ind['macd_line']
        signal_line = ind['signal_line']
        histogram = ind['histogram']
        
        if macd_line > signal_line:
            # Bullish MACD crossover
            if macd_line > 0:  # Above zero line (+10 points)
                strength = min(1.0, abs(macd_line - signal_line) / abs(signal_line) if signal_line != 0 else 0.5)
                self.indicator_scores['macd'] = 60 + (strength * 40)
            else:
                # Bullish crossover but below zero line
                strength = min(1.0, abs(macd_line - signal_line) / abs(signal_line) if signal_line != 0 else 0.5)
                self.indicator_scores['macd'] = 55 + (strength * 20)
        else:
            # Bearish MACD crossover
            if macd_line < 0:  # Below zero line (+10 points)
                strength = min(1.0, abs(macd_line - signal_line) / abs(signal_line) if signal_line != 0 else 0.5)
                self.indicator_scores['macd'] = 40 - (strength * 40)
            else:
                # Bearish crossover but above zero line
                strength = min(1.0, abs(macd_line - signal_line) / abs(signal_line) if signal_line != 0 else 0.5)
                self.indicator_scores['macd'] = 45 - (strength * 20)
        
        # EMA Score (0-100)
        ema_short = ind['ema_short']
        ema_long = ind['ema_long']
        
        # Calculate volume spike for EMA crossover
        volumes = ind['volumes']
        avg_volume = np.mean(volumes[-20:])
        volume_spike = volumes[-1] > avg_volume * 1.5
        
        ema_bonus = 15 if volume_spike else 0  # +15 points for volume spike
        
        if current_price > ema_short > ema_long:
            # Price above both EMAs and short above long (strongly bullish)
            self.indicator_scores['ema'] = 80 + ema_bonus
        elif current_price > ema_short:
            # Price above short EMA (bullish)
            self.indicator_scores['ema'] = 65 + ema_bonus
        elif current_price < ema_short < ema_long:
            # Price below both EMAs and short below long (strongly bearish)
            self.indicator_scores['ema'] = 20 - ema_bonus
        elif current_price < ema_short:
            # Price below short EMA (bearish)
            self.indicator_scores['ema'] = 35 - ema_bonus
        else:
            self.indicator_scores['ema'] = 50
        
        # Bollinger Bands Score (0-100)
        upper_band = ind['bb_upper']
        middle_band = ind['bb_middle']
        lower_band = ind['bb_lower']
        
        # Check for squeeze
        band_width = (upper_band - lower_band) / middle_band
        bb_squeeze = band_width < 0.03  # Tight bands indicate squeeze
        
        bb_bonus = 10 if bb_squeeze else 0  # +10 points for squeeze
        
        if current_price <= lower_band:
            # Price at or below lower band (bullish)
            self.indicator_scores['bbands'] = 80 + bb_bonus
        elif current_price >= upper_band:
            # Price at or above upper band (bearish)
            self.indicator_scores['bbands'] = 20 - bb_bonus
        else:
            # Calculate position within bands
            position = (current_price - lower_band) / (upper_band - lower_band)
            # Adjust score based on position
            self.indicator_scores['bbands'] = 20 + (position * 60)
        
        # Volume Score (0-100)
        current_volume = volumes[-1]
        
        if current_volume > avg_volume * 2:
            # Major volume spike
            self.indicator_scores['volume'] = 80 if current_price > self.price_data['primary']['close'].iloc[-2] else 20
        elif current_volume > avg_volume * 1.5:
            # Significant volume increase
            self.indicator_scores['volume'] = 70 if current_price > self.price_data['primary']['close'].iloc[-2] else 30
        elif current_volume < avg_volume * 0.5:
            # Low volume
            self.indicator_scores['volume'] = 40
        else:
            # Normal volume
            self.indicator_scores['volume'] = 50
        
        # Support/Resistance Score (0-100)
        self.indicator_scores['support_resistance'] = self._calculate_sr_score(current_price)
        
        # Calculate total score with weightings
        weights = self._set_indicator_weights()
        
        self.total_score = sum(
            score * weights[indicator] for indicator, score in self.indicator_scores.items()
        )
        
        logger.info(f"Total indicator score: {self.total_score:.2f}")
        logger.info(f"Individual scores: {self.indicator_scores}")

    def _check_rsi_divergence(self, lookback=10, bearish=False):
        """Check for RSI divergence (bullish or bearish)"""
        df = self.price_data['primary']
        if len(df) < lookback + 1:
            return False
        
        # Calculate RSI for period
        prices = df['close'].values[-lookback:]
        rsi_values = []
        for i in range(len(prices) - 13):
            rsi_values.append(self._calculate_rsi(prices[i:i+14]))
        
        if len(rsi_values) < 2:
            return False
        
        # Bullish divergence: price makes lower low but RSI makes higher low
        if not bearish:
            price_lower_low = df['low'].iloc[-1] < min(df['low'].iloc[-lookback:-1])
            rsi_higher_low = rsi_values[-1] > min(rsi_values[:-1])
            return price_lower_low and rsi_higher_low
            
        # Bearish divergence: price makes higher high but RSI makes lower high
        else:
            price_higher_high = df['high'].iloc[-1] > max(df['high'].iloc[-lookback:-1])
            rsi_lower_high = rsi_values[-1] < max(rsi_values[:-1])
            return price_higher_high and rsi_lower_high

    def _calculate_sr_score(self, current_price):
        """Calculate score based on proximity to support/resistance levels"""
        if not self.support_levels and not self.resistance_levels:
            return 50  # Neutral if no levels found
        
        # Find closest support and resistance
        closest_support = None
        closest_resistance = None
        
        if self.support_levels:
            # Filter support levels below current price
            supports_below = [level for level in self.support_levels if level < current_price]
            if supports_below:
                closest_support = max(supports_below)
        
        if self.resistance_levels:
            # Filter resistance levels above current price
            resistances_above = [level for level in self.resistance_levels if level > current_price]
            if resistances_above:
                closest_resistance = min(resistances_above)
        
        # Calculate distances (as percentage of price)
        support_distance = (current_price - closest_support) / current_price if closest_support else float('inf')
        resistance_distance = (closest_resistance - current_price) / current_price if closest_resistance else float('inf')
        
        # Score based on proximity to levels
        if support_distance < resistance_distance:
            # Closer to support (bullish)
            if support_distance < 0.01:  # Within 1% of support
                return 80  # Strong support bounce potential
            elif support_distance < 0.03:  # Within 3% of support
                return 70  # Near support
            else:
                return 60  # Approaching support
        else:
            # Closer to resistance (bearish)
            if resistance_distance < 0.01:  # Within 1% of resistance
                return 20  # Strong resistance rejection potential
            elif resistance_distance < 0.03:  # Within 3% of resistance
                return 30  # Near resistance
            else:
                return 40  # Approaching resistance

    def detect_bull_trap(self, price, resistance_level=None):
        """Detect potential bull trap using non-lagging indicators"""
        # If no resistance level provided, find closest one
        if resistance_level is None:
            if not self.resistance_levels:
                return False, 0
                
            # Find closest resistance level above price
            resistances_above = [r for r in self.resistance_levels if r > price]
            if not resistances_above:
                return False, 0
                
            resistance_level = min(resistances_above)
        
        # Check if price is breaking above resistance
        if price > resistance_level * 1.01:  # 1% breakout
            trap_score = 0
            
            # 1. Volume is declining
            volumes = self.indicator_values['primary']['volumes']
            if volumes[-1] < np.mean(volumes[-3:]):
                trap_score += 30
            
            # 2. Order book imbalance showing selling pressure
            if self.trap_indicators['order_imbalance'] < -0.2:
                trap_score += 25
            
            # 3. Sudden spread widening
            if self.trap_indicators['bid_ask_spread'] > 0.5:  # Spread widened by 50%+
                trap_score += 20
            
            # 4. Upper wick rejection
            if self.trap_indicators.get('upper_wick_ratio', 0) > 1.5:  # Long upper wick
                trap_score += 25
            
            return trap_score > 60, trap_score  # Bull trap if score > 60
        
        return False, 0

    def detect_bear_trap(self, price, support_level=None):
        """Detect potential bear trap using non-lagging indicators"""
        # If no support level provided, find closest one
        if support_level is None:
            if not self.support_levels:
                return False, 0
                
            # Find closest support level below price
            supports_below = [s for s in self.support_levels if s < price]
            if not supports_below:
                return False, 0
                
            support_level = max(supports_below)
        
        # Check if price is breaking below support
        if price < support_level * 0.99:  # 1% breakdown
            trap_score = 0
            
            # 1. Volume is declining
            volumes = self.indicator_values['primary']['volumes']
            if volumes[-1] < np.mean(volumes[-3:]):
                trap_score += 30
            
            # 2. Order book imbalance showing buying pressure
            if self.trap_indicators['order_imbalance'] > 0.2:
                trap_score += 25
            
            # 3. Sudden spread widening
            if self.trap_indicators['bid_ask_spread'] > 0.5:  # Spread widened by 50%+
                trap_score += 20
            
            # 4. Lower wick rejection
            if self.trap_indicators.get('lower_wick_ratio', 0) > 1.5:  # Long lower wick
                trap_score += 25
            
            return trap_score > 60, trap_score  # Bear trap if score > 60
        
        return False, 0

    def generate_signals(self) -> Dict[str, any]:
        """Generate trading signals based on indicator scores and trap detection"""
        current_price = self.price_data['primary']['close'].iloc[-1]
        
        # Check secondary timeframe for confirmation
        secondary_score = self._calculate_secondary_confirmation()
        confirmed_by_secondary = secondary_score > self.signal_threshold
        secondary_bonus = 10 if confirmed_by_secondary else 0
        
        # Calculate total score with secondary confirmation
        self.total_score += secondary_bonus
        
        logger.info(f"Total indicator score: {self.total_score:.2f}")
        logger.info(f"Individual scores: {self.indicator_scores}")

        return {
            "confirmed_by_secondary": confirmed_by_secondary,
            "secondary_score": secondary_score,
            "total_score": self.total_score
        }

    def get_price_history(self, price_type='close', length=200):
        """Get historical price data for technical analysis"""
        if not hasattr(self, '_price_history'):
            self._price_history = {'open': [], 'high': [], 'low': [], 'close': [], 'volume': []}
        
        if len(self._price_history[price_type]) < length:
            # Not enough data, return None
            return None
        
        return self._price_history[price_type][-length:]

    def on_tick(self):
        """Main strategy execution method, called on each clock tick"""
        current_timestamp = self.current_timestamp
        
        # Check if it's time to refresh orders
        if current_timestamp - self._last_timestamp < self.order_refresh_time:
            # Check trailing stops on each tick if we have any
            self.check_trailing_stops()
            return
        
        # Update last timestamp
        self._last_timestamp = current_timestamp
        
        # Update price history data
        self.update_price_history()
        
        # Calculate BB signals
        bb_signals = self.detect_bb_signals()
        
        # Only place orders if signal strength is sufficient
        if bb_signals["strength"] >= self.signal_threshold:
            # Cancel existing orders
            self.cancel_all_orders()
            
            # Set spread based on BB width
            bb_width = (bb_signals["bb_upper"] - bb_signals["bb_lower"]) / bb_signals["bb_middle"]
            adaptive_spread = self.min_spread + (bb_width * self.volatility_adjustment)
            adaptive_spread = max(float(self.min_spread), min(adaptive_spread, float(self.max_spread)))
            
            # Calculate mid price and bid/ask prices
            mid_price = self.get_mid_price()
            bid_price = mid_price * (Decimal("1") - Decimal(str(adaptive_spread)))
            ask_price = mid_price * (Decimal("1") + Decimal(str(adaptive_spread)))
            
            # Calculate order sizes
            buy_amount, sell_amount = self.calculate_order_amounts()
            
            # Place orders based on BB signal
            if bb_signals["signal"] == "buy":
                # Create buy order
                self.buy(
                    connector_name=self.connector_name,
                    trading_pair=self.trading_pair,
                    amount=buy_amount,
                    order_type=OrderType.LIMIT,
                    price=bid_price
                )
                self.logger().info(f"BB Buy Signal: Placed buy order for {buy_amount} @ {bid_price}")
            
            elif bb_signals["signal"] == "sell":
                # Create sell order
                self.sell(
                    connector_name=self.connector_name,
                    trading_pair=self.trading_pair,
                    amount=sell_amount,
                    order_type=OrderType.LIMIT,
                    price=ask_price
                )
                self.logger().info(f"BB Sell Signal: Placed sell order for {sell_amount} @ {ask_price}")
        
        # Log status update
        self.log_status_update()

    def calculate_bollinger_bands_with_kalman(self, prices: List[float], length: int = 20, num_std: float = 2.0, use_kalman: bool = True) -> Tuple[float, float, float]:
        """
        Calculate Bollinger Bands with optional Kalman filter
        
        Args:
            prices: List of price values
            length: Period for calculation (default: 20)
            num_std: Number of standard deviations (default: 2.0)
            use_kalman: Whether to use Kalman filter (default: True)
            
        Returns:
            Tuple of (upper band, middle band, lower band)
        """
        if len(prices) < length:
            return None, None, None
        
        # Apply Kalman filter if enabled
        if use_kalman:
            filtered_prices = self.apply_kalman_filter(prices)
        else:
            filtered_prices = prices
        
        # Calculate middle band (SMA)
        middle_band = np.mean(filtered_prices[-length:])
        
        # Calculate standard deviation
        std_dev = np.std(filtered_prices[-length:])
        
        # Calculate upper and lower bands
        upper_band = middle_band + (std_dev * num_std)
        lower_band = middle_band - (std_dev * num_std)
        
        return upper_band, middle_band, lower_band

    def apply_kalman_filter(self, data: List[float], process_variance: float = 1e-5, measurement_variance: float = 1e-3) -> List[float]:
        """
        Apply Kalman filter to price data to reduce noise
        
        Args:
            data: List of price values
            process_variance: Process variance parameter (Q)
            measurement_variance: Measurement variance parameter (R)
            
        Returns:
            List of filtered price values
        """
        n = len(data)
        if n < 2:
            return data
        
        # Initialize Kalman filter
        filtered_data = np.zeros(n)
        filtered_data[0] = data[0]
        
        # Initial state
        x_hat = data[0]
        p = 1.0
        
        # Process through all data points
        for i in range(1, n):
            # Prediction step
            x_hat_minus = x_hat
            p_minus = p + process_variance
            
            # Update step
            k = p_minus / (p_minus + measurement_variance)
            x_hat = x_hat_minus + k * (data[i] - x_hat_minus)
            p = (1 - k) * p_minus
            
            filtered_data[i] = x_hat
        
        return filtered_data.tolist()

    def calculate_ema(self, prices: List[float], length: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < length:
            return None
        
        alpha = 2.0 / (length + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = price * alpha + ema * (1 - alpha)
        
        return ema

    def calculate_hl2(self, high_prices: List[float], low_prices: List[float]) -> List[float]:
        """Calculate HL2 price series (high + low) / 2"""
        return [(h + l) / 2 for h, l in zip(high_prices, low_prices)]

    def detect_bb_signals(self) -> dict:
        """
        Detect trading signals based on Bollinger Bands and EMAs
        Returns a dictionary with signal information
        """
        # Get required price data
        high_prices = self.get_price_history('high')
        low_prices = self.get_price_history('low')
        close_prices = self.get_price_history('close')
        
        if not high_prices or not low_prices or not close_prices:
            return {"signal": "neutral", "strength": 0}
        
        # Calculate HL2 price series
        hl2_prices = self.calculate_hl2(high_prices, low_prices)
        
        # Calculate EMAs (120 and 12 periods as in your TradingView chart)
        ema_long = self.calculate_ema(hl2_prices, 120)  # Long-term EMA (120)
        ema_short = self.calculate_ema(hl2_prices, 12)  # Short-term EMA (12)
        
        # Calculate Bollinger Bands with Kalman filter
        upper_band, middle_band, lower_band = self.calculate_bollinger_bands_with_kalman(
            hl2_prices, 
            length=self.bb_length,
            num_std=self.bb_std,
            use_kalman=self.bb_use_kalman
        )
        
        if ema_long is None or ema_short is None or upper_band is None:
            return {"signal": "neutral", "strength": 0}
        
        # Current and previous prices
        current_price = close_prices[-1]
        prev_price = close_prices[-2]
        
        # Initialize signal variables
        signal = "neutral"
        strength = 0
        
        # Determine if price is crossing bands
        crossing_upper = prev_price <= upper_band and current_price > upper_band
        crossing_lower = prev_price >= lower_band and current_price < lower_band
        touching_upper = current_price >= upper_band * 0.995
        touching_lower = current_price <= lower_band * 1.005
        
        # Check EMA positions (trend confirmation)
        ema_bullish = ema_short > ema_long
        ema_bearish = ema_short < ema_long
        
        # Signal logic based on your TradingView setup
        if touching_lower and ema_bullish:
            # Bullish signal - price at lower band with bullish EMA cross
            signal = "buy"
            strength = 80
        elif touching_upper and ema_bearish:
            # Bearish signal - price at upper band with bearish EMA cross
            signal = "sell"
            strength = 80
        elif current_price < lower_band:
            # Price below lower band - potential bounce
            signal = "buy"
            strength = 60
        elif current_price > upper_band:
            # Price above upper band - potential reversal
            signal = "sell"
            strength = 60
        elif ema_bullish and current_price > middle_band:
            # Bullish trend confirmation
            signal = "buy"
            strength = 40
        elif ema_bearish and current_price < middle_band:
            # Bearish trend confirmation
            signal = "sell"
            strength = 40
        
        return {
            "signal": signal,
            "strength": strength,
            "bb_upper": upper_band,
            "bb_middle": middle_band,
            "bb_lower": lower_band,
            "ema_long": ema_long,
            "ema_short": ema_short,
            "price": current_price
        }
