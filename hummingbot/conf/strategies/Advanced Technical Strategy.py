from decimal import Decimal
import pandas as pd
import numpy as np
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.events import OrderFilledEvent
import time
import logging
from typing import Dict, List

class AdvancedTechnicalStrategy(ScriptStrategyBase):
    """
    An advanced trading strategy combining pure market making with technical indicators:
    - RSI for overbought/oversold signals
    - MACD for trend confirmation
    - EMA crossovers for longer-term trend direction
    - Bollinger Bands for volatility and price compression signals
    - Support/Resistance levels detection
    - Candlestick patterns recognition
    - Trailing stop-loss implementation
    """
    
    bid_spread = 0.1
    ask_spread = 1.0
    order_refresh_time = 30.0
    order_amount = 1.0
    
    # Technical indicators parameters
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought = 70
    
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9
    
    ema_period = 50
    
    bb_period = 20
    bb_std = 2
    
    # Stop loss parameters
    trailing_stop_pct = 5.0
    trailing_activation_pct = 10.0
    
    # Candle pattern recognition thresholds
    hammer_body_pct = 0.3
    engulfing_threshold = 1.2
    
    # Volume thresholds
    volume_ratio_threshold = 1.5
    
    def __init__(self, connectors: Dict):
        super().__init__(connectors)
        self.market = list(connectors.values())[0]
        self.base_asset, self.quote_asset = self.market.trading_pair.split("-")
        
        # Initialize storage for historical data
        self.price_data = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        self.last_candle_timestamp = 0
        self.candle_interval = 60  # 1-minute candles
        
        # Order tracking
        self.active_orders = {}
        self.last_trade_price = None
        self.highest_price = None
        self.stop_loss_price = None
        
        # Support/Resistance levels
        self.support_levels = []
        self.resistance_levels = []
        
        # Position tracking
        self.position_side = None  # 'long', 'short', or None
        self.entry_price = None
        
        # Initialize the timer for order refresh
        self.last_order_refresh_timestamp = 0
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    def on_tick(self):
        """Main execution loop that runs on each tick"""
        current_timestamp = self.current_timestamp
        
        # Update price data for technical analysis
        self.update_price_data()
        
        # Only proceed if we have enough data for analysis
        if len(self.price_data) < max(self.rsi_period, self.macd_slow + self.macd_signal, self.ema_period, self.bb_period):
            self.logger.info("Not enough data for technical analysis yet. Collecting data...")
            return
        
        # Calculate technical indicators
        self.calculate_indicators()
        
        # Check for trading signals
        signals = self.analyze_signals()
        
        # Execute trading decisions based on signals
        self.execute_strategy(signals)
        
        # Manage trailing stop-loss if in position
        if self.position_side is not None:
            self.manage_stop_loss()
        
        # Refresh orders if necessary
        if (current_timestamp - self.last_order_refresh_timestamp) > self.order_refresh_time:
            self.cancel_all_orders()
            if signals['overall'] != "standby":
                self.create_orders(signals['overall'])
            self.last_order_refresh_timestamp = current_timestamp
    
    def update_price_data(self):
        """Update price data for technical analysis"""
        current_timestamp = self.current_timestamp
        current_price = self.market.get_mid_price(self.market.trading_pair)
        
        # Update last trade price for stop loss calculation
        if self.last_trade_price is None:
            self.last_trade_price = current_price
        
        # Create new candle if interval has passed
        if (current_timestamp - self.last_candle_timestamp) >= self.candle_interval:
            # Get OHLCV data from the exchange if available
            try:
                # This is a placeholder - actual implementation would use the connector's methods to get candle data
                candles = self.market.get_candles(
                    trading_pair=self.market.trading_pair,
                    interval=self.candle_interval,
                    max_records=100
                )
                
                if candles and len(candles) > 0:
                    for candle in candles:
                        if candle.timestamp > self.last_candle_timestamp:
                            new_row = {
                                "timestamp": candle.timestamp,
                                "open": candle.open,
                                "high": candle.high,
                                "low": candle.low,
                                "close": candle.close,
                                "volume": candle.volume
                            }
                            self.price_data = pd.concat([self.price_data, pd.DataFrame([new_row])], ignore_index=True)
                    
                    self.last_candle_timestamp = candles[-1].timestamp
            except Exception as e:
                self.logger.error(f"Error fetching candles: {str(e)}")
                
                # Fallback: Create a simple candle with current price
                new_row = {
                    "timestamp": current_timestamp,
                    "open": current_price,
                    "high": current_price,
                    "low": current_price,
                    "close": current_price,
                    "volume": 0  # No volume data in fallback
                }
                self.price_data = pd.concat([self.price_data, pd.DataFrame([new_row])], ignore_index=True)
                self.last_candle_timestamp = current_timestamp
    
    def calculate_indicators(self):
        """Calculate all technical indicators"""
        closes = self.price_data["close"].values
        highs = self.price_data["high"].values
        lows = self.price_data["low"].values
        volumes = self.price_data["volume"].values
        
        # Calculate RSI
        delta = np.diff(closes)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.append([np.nan] * (self.rsi_period), np.convolve(gain, np.ones(self.rsi_period)/self.rsi_period, mode='valid'))
        avg_loss = np.append([np.nan] * (self.rsi_period), np.convolve(loss, np.ones(self.rsi_period)/self.rsi_period, mode='valid'))
        
        rs = avg_gain / np.where(avg_loss == 0, 0.001, avg_loss)  # Avoid division by zero
        rsi = 100 - (100 / (1 + rs))
        
        self.price_data["rsi"] = np.append([np.nan] * (len(closes) - len(rsi)), rsi)
        
        # Calculate MACD
        ema_fast = self.calculate_ema(closes, self.macd_fast)
        ema_slow = self.calculate_ema(closes, self.macd_slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, self.macd_signal)
        
        self.price_data["macd"] = macd_line
        self.price_data["macd_signal"] = signal_line
        self.price_data["macd_histogram"] = macd_line - signal_line
        
        # Calculate EMA
        self.price_data["ema"] = self.calculate_ema(closes, self.ema_period)
        
        # Calculate Bollinger Bands
        middle_band = self.price_data["close"].rolling(window=self.bb_period).mean()
        std_dev = self.price_data["close"].rolling(window=self.bb_period).std()
        upper_band = middle_band + (std_dev * self.bb_std)
        lower_band = middle_band - (std_dev * self.bb_std)
        
        self.price_data["bb_middle"] = middle_band
        self.price_data["bb_upper"] = upper_band
        self.price_data["bb_lower"] = lower_band
        self.price_data["bb_width"] = (upper_band - lower_band) / middle_band
        
        # Calculate average volume
        self.price_data["avg_volume"] = self.price_data["volume"].rolling(window=20).mean()
        
        # Detect support and resistance levels (simplified)
        self.detect_support_resistance()
        
        # Detect candlestick patterns
        self.detect_candlestick_patterns()
    
    def calculate_ema(self, data, period):
        """Calculate Exponential Moving Average"""
        ema = np.zeros_like(data)
        ema[:period] = np.nan
        
        # First value is SMA
        ema[period-1] = np.mean(data[:period])
        
        # EMA calculation
        multiplier = 2 / (period + 1)
        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
            
        return ema
    
    def detect_support_resistance(self):
        """Detect support and resistance levels using local minima and maxima"""
        if len(self.price_data) < 20:
            return
            
        # Use a simplified approach to find local minima and maxima
        lows = self.price_data["low"].values
        highs = self.price_data["high"].values
        
        # Find local minima (potential support)
        self.support_levels = []
        for i in range(2, len(lows)-2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                self.support_levels.append(lows[i])
        
        # Find local maxima (potential resistance)
        self.resistance_levels = []
        for i in range(2, len(highs)-2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                self.resistance_levels.append(highs[i])
        
        # Keep only the most recent levels (last 5)
        self.support_levels = sorted(self.support_levels)[-5:]
        self.resistance_levels = sorted(self.resistance_levels)[-5:]
    
    def detect_candlestick_patterns(self):
        """Detect candlestick patterns like hammers and engulfing patterns"""
        if len(self.price_data) < 5:
            return
            
        df = self.price_data.copy()
        df["body_size"] = abs(df["close"] - df["open"])
        df["shadow_upper"] = df["high"] - np.maximum(df["open"], df["close"])
        df["shadow_lower"] = np.minimum(df["open"], df["close"]) - df["low"]
        df["total_range"] = df["high"] - df["low"]
        
        # Detect hammer patterns
        df["is_hammer"] = False
        df["is_inverted_hammer"] = False
        for i in range(1, len(df)):
            # Hammer: small body, long lower shadow, small upper shadow
            if (df.iloc[i]["body_size"] < self.hammer_body_pct * df.iloc[i]["total_range"] and
                df.iloc[i]["shadow_lower"] > 2 * df.iloc[i]["body_size"] and
                df.iloc[i]["shadow_upper"] < 0.5 * df.iloc[i]["body_size"]):
                df.at[i, "is_hammer"] = True
            
            # Inverted hammer: small body, long upper shadow, small lower shadow
            if (df.iloc[i]["body_size"] < self.hammer_body_pct * df.iloc[i]["total_range"] and
                df.iloc[i]["shadow_upper"] > 2 * df.iloc[i]["body_size"] and
                df.iloc[i]["shadow_lower"] < 0.5 * df.iloc[i]["body_size"]):
                df.at[i, "is_inverted_hammer"] = True
        
        # Detect engulfing patterns
        df["is_bullish_engulfing"] = False
        df["is_bearish_engulfing"] = False
        for i in range(1, len(df)):
            # Bullish engulfing: previous red (close < open), current green (close > open), current body engulfs previous
            if (df.iloc[i-1]["close"] < df.iloc[i-1]["open"] and  # Previous red
                df.iloc[i]["close"] > df.iloc[i]["open"] and      # Current green
                df.iloc[i]["body_size"] > self.engulfing_threshold * df.iloc[i-1]["body_size"] and
                df.iloc[i]["open"] <= df.iloc[i-1]["close"] and
                df.iloc[i]["close"] >= df.iloc[i-1]["open"]):
                df.at[i, "is_bullish_engulfing"] = True
            
            # Bearish engulfing: previous green (close > open), current red (close < open), current body engulfs previous
            if (df.iloc[i-1]["close"] > df.iloc[i-1]["open"] and  # Previous green
                df.iloc[i]["close"] < df.iloc[i]["open"] and      # Current red
                df.iloc[i]["body_size"] > self.engulfing_threshold * df.iloc[i-1]["body_size"] and
                df.iloc[i]["open"] >= df.iloc[i-1]["close"] and
                df.iloc[i]["close"] <= df.iloc[i-1]["open"]):
                df.at[i, "is_bearish_engulfing"] = True
        
        self.price_data = df
    
    def analyze_signals(self):
        """Analyze all technical indicators and generate trading signals"""
        if len(self.price_data) < self.macd_slow + self.macd_signal:
            return {"overall": "standby"}
            
        # Get the latest data
        latest = self.price_data.iloc[-1]
        previous = self.price_data.iloc[-2] if len(self.price_data) > 1 else latest
        
        current_price = latest["close"]
        signals = {
            "rsi": "neutral",
            "macd": "neutral",
            "ema": "neutral",
            "bollinger": "neutral",
            "support_resistance": "neutral",
            "candlestick": "neutral",
            "overall": "standby"
        }
        
        # RSI signals
        if not np.isnan(latest["rsi"]) and not np.isnan(previous["rsi"]):
            if previous["rsi"] < self.rsi_oversold and latest["rsi"] > self.rsi_oversold:
                signals["rsi"] = "buy"  # Crossed above oversold
            elif previous["rsi"] > self.rsi_overbought and latest["rsi"] < self.rsi_overbought:
                signals["rsi"] = "sell"  # Crossed below overbought
            elif latest["rsi"] < self.rsi_oversold:
                signals["rsi"] = "oversold"
            elif latest["rsi"] > self.rsi_overbought:
                signals["rsi"] = "overbought"
        
        # MACD signals
        if (not np.isnan(latest["macd"]) and not np.isnan(latest["macd_signal"]) and
            not np.isnan(previous["macd"]) and not np.isnan(previous["macd_signal"])):
            if previous["macd"] < previous["macd_signal"] and latest["macd"] > latest["macd_signal"]:
                signals["macd"] = "buy"  # MACD crossed above signal line
            elif previous["macd"] > previous["macd_signal"] and latest["macd"] < latest["macd_signal"]:
                signals["macd"] = "sell"  # MACD crossed below signal line
        
        # EMA signals
        if not np.isnan(latest["ema"]):
            if previous["close"] < previous["ema"] and latest["close"] > latest["ema"]:
                signals["ema"] = "buy"  # Price crossed above EMA
            elif previous["close"] > previous["ema"] and latest["close"] < latest["ema"]:
                signals["ema"] = "sell"  # Price crossed below EMA
            elif latest["close"] > latest["ema"]:
                signals["ema"] = "bullish"  # Price above EMA
            elif latest["close"] < latest["ema"]:
                signals["ema"] = "bearish"  # Price below EMA
        
        # Bollinger Bands signals
        if (not np.isnan(latest["bb_upper"]) and not np.isnan(latest["bb_lower"]) and 
            not np.isnan(latest["bb_width"])):
            
            # Check for squeeze (bands narrowing)
            bb_width_avg = self.price_data["bb_width"].rolling(window=10).mean().iloc[-1]
            if latest["bb_width"] < 0.7 * bb_width_avg:
                signals["bollinger"] = "squeeze"  # Bollinger squeeze (potential breakout)
            
            # Price touching bands with volume
            if (latest["high"] >= latest["bb_upper"] and 
                latest["volume"] > self.volume_ratio_threshold * latest["avg_volume"]):
                signals["bollinger"] = "overbought_volume"  # Touch upper band with volume
            elif (latest["low"] <= latest["bb_lower"] and 
                  latest["volume"] > self.volume_ratio_threshold * latest["avg_volume"]):
                signals["bollinger"] = "oversold_volume"  # Touch lower band with volume
        
        # Support/Resistance signals
        if self.support_levels and self.resistance_levels:
            # Find closest support and resistance
            supports_below = [s for s in self.support_levels if s < current_price]
            resistances_above = [r for r in self.resistance_levels if r > current_price]
            
            closest_support = max(supports_below) if supports_below else None
            closest_resistance = min(resistances_above) if resistances_above else None
            
            # Check if price is near support or resistance
            if closest_support and (current_price - closest_support) / current_price < 0.02:  # Within 2%
                signals["support_resistance"] = "near_support"
            elif closest_resistance and (closest_resistance - current_price) / current_price < 0.02:  # Within 2%
                signals["support_resistance"] = "near_resistance"
            
            # Check for breakouts
            if previous["close"] < closest_resistance < latest["close"]:
                signals["support_resistance"] = "resistance_break"
            elif previous["close"] > closest_support > latest["close"]:
                signals["support_resistance"] = "support_break"
        
        # Candlestick pattern signals
        if latest["is_hammer"] and latest["volume"] > self.volume_ratio_threshold * latest["avg_volume"]:
            signals["candlestick"] = "bullish_hammer"
        elif latest["is_inverted_hammer"] and latest["volume"] > self.volume_ratio_threshold * latest["avg_volume"]:
            signals["candlestick"] = "bearish_hammer"
        elif latest["is_bullish_engulfing"] and latest["volume"] > self.volume_ratio_threshold * latest["avg_volume"]:
            signals["candlestick"] = "bullish_engulfing"
        elif latest["is_bearish_engulfing"] and latest["volume"] > self.volume_ratio_threshold * latest["avg_volume"]:
            signals["candlestick"] = "bearish_engulfing"
        
        # Combine signals for overall decision
        buy_signals = sum(1 for signal in signals.values() if signal in ["buy", "bullish", "oversold", "bullish_hammer", "bullish_engulfing", "near_support", "resistance_break", "oversold_volume"])
        sell_signals = sum(1 for signal in signals.values() if signal in ["sell", "bearish", "overbought", "bearish_hammer", "bearish_engulfing", "near_resistance", "support_break", "overbought_volume"])
        
        # Require at least 2 confirming signals for a trading decision
        if buy_signals >= 2 and buy_signals > sell_signals:
            signals["overall"] = "buy"
        elif sell_signals >= 2 and sell_signals > buy_signals:
            signals["overall"] = "sell"
        
        # Log the signals
        self.logger.info(f"Technical signals: {signals}")
        return signals
    
    def execute_strategy(self, signals):
        """Execute trading decisions based on signals"""
        current_price = self.price_data.iloc[-1]["close"]
        
        # Check for bear/bull traps (fake breakouts)
        if "support_break" in signals.values() and "bullish" in signals.values():
            self.logger.info("Possible bear trap detected! Bulls taking control after support break.")
        elif "resistance_break" in signals.values() and "bearish" in signals.values():
            self.logger.info("Possible bull trap detected! Bears taking control after resistance break.")
        
        # Execute based on overall signal
        if signals["overall"] == "buy" and self.position_side != "long":
            self.cancel_all_orders()
            self.position_side = "long"
            self.entry_price = current_price
            self.highest_price = current_price
            self.stop_loss_price = current_price * (1 - self.trailing_stop_pct/100)
            self.logger.info(f"BUY Signal! Entering long position at {current_price}")
            self.place_order("buy", current_price)
        
        elif signals["overall"] == "sell" and self.position_side != "short":
            self.cancel_all_orders()
            self.position_side = "short"
            self.entry_price = current_price
            self.highest_price = current_price
            self.stop_loss_price = current_price * (1 + self.trailing_stop_pct/100)
            self.logger.info(f"SELL Signal! Entering short position at {current_price}")
            self.place_order("sell", current_price)
    
    def manage_stop_loss(self):
        """Manage trailing stop-loss for open positions"""
        if self.position_side is None or self.stop_loss_price is None:
            return
            
        current_price = self.price_data.iloc[-1]["close"]
        
        if self.position_side == "long":
            # Update highest price and trailing stop if price increases
            if current_price > self.highest_price:
                self.highest_price = current_price
                # Only adjust stop-loss if price has moved enough
                price_move_pct = (self.highest_price - self.entry_price) / self.entry_price * 100
                if price_move_pct >= self.trailing_activation_pct:
                    # Move stop-loss up with the price
                    self.stop_loss_price = self.highest_price * (1 - self.trailing_stop_pct/100)
                    self.logger.info(f"Updated trailing stop-loss to {self.stop_loss_price}")
            
            # Check if stop-loss is hit
            if current_price <= self.stop_loss_price:
                self.logger.info(f"Stop-loss triggered at {current_price}. Exiting long position.")
                self.place_order("sell", current_price)
                self.position_side = None
                self.stop_loss_price = None
        
        elif self.position_side == "short":
            # Update lowest price and trailing stop if price decreases
            if current_price < self.highest_price:
                self.highest_price = current_price
                # Only adjust stop-loss if price has moved enough
                price_move_pct = (self.entry_price - self.highest_price) / self.entry_price * 100
                if price_move_pct >= self.trailing_activation_pct:
                    # Move stop-loss down with the price
                    self.stop_loss_price = self.highest_price * (1 + self.trailing_stop_pct/100)
                    self.logger.info(f"Updated trailing stop-loss to {self.stop_loss_price}")
            
            # Check if stop-loss is hit
            if current_price >= self.stop_loss_price:
                self.logger.info(f"Stop-loss triggered at {current_price}. Exiting short position.")
                self.place_order("buy", current_price)
                self.position_side = None
                self.stop_loss_price = None
    
    def create_orders(self, signal_type):
        """Create orders based on the signal type"""
        current_price = self.market.get_mid_price(self.market.trading_pair)
        
        if signal_type == "buy":
            # Adjust bid/ask spreads based on signal strength
            buy_price = current_price * (1 - self.bid_spread / 100)
            self.place_order("buy", buy_price)
        
        elif signal_type == "sell":
            # Adjust bid/ask spreads based on signal strength
            sell_price = current_price * (1 + self.ask_spread / 100)
            self.place_order("sell", sell_price)
    
    def place_order(self, side, price):
        """Place an order with the exchange"""
        try:
            if side == "buy":
                order_id = self.place_order(
                    connector_name=self.market.name,
                    trading_pair=self.market.trading_pair,
                    amount=self.order_amount,
                    is_buy=True,
                    order_type=OrderType.LIMIT,
                    price=Decimal(str(price))
                )
                self.logger.info(f"Placed buy order {order_id} at {price}")
                self.active_orders[order_id] = {"side": "buy", "price": price}
            else:
                order_id = self.place_order(
                    connector_name=self.market.name,
                    trading_pair=self.market.trading_pair,
                    amount=self.order_amount,
                    is_buy=False,
                    order_type=OrderType.LIMIT,
                    price=Decimal(str(price))
                )
                self.logger.info(f"Placed sell order {order_id} at {price}")
                self.active_orders[order_id] = {"side": "sell", "price": price}
        except Exception as e:
            self.logger.error(f"Error placing order: {str(e)}")
    
    def cancel_all_orders(self):
        """Cancel all active orders"""
        try:
            self.cancel_all_orders()
            self.active_orders = {}
            self.logger.info("Cancelled all active orders")
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {str(e)}")
    
    def did_fill_order(self, event: OrderFilledEvent):
        """Handle filled order events"""
        order_id = event.order_id
        if order_id in self.active_orders:
            fill_price = event.price
            fill_side = event.trade_type
            fill_amount = event.amount
            
            self.logger.info(f"Order {order_id} filled: {fill_side} {fill_amount} at {fill_price}")
            
            # Update position tracking
            if fill_side == TradeType.BUY:
                self.position_side = "long"
                self.entry_price = fill_price
                self.highest_price = fill_price
                self.stop_loss_price = fill_price * (1 - self.trailing_stop_pct/100)
            else:
                self.position_side = "short"
                self.entry_price = fill_price
                self.highest_price = fill_price
                self.stop_loss_price = fill_price * (1 + self.trailing_stop_pct/100)
            
            # Remove from active orders
            del self.active_orders[order_id]

def main():
    """Initialize and run the strategy"""
    # This function will be called by Hummingbot
    return AdvancedTechnicalStrategy
