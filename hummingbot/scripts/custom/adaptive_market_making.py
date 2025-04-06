from decimal import Decimal
import numpy as np
import pandas as pd
import pandas_ta as ta
import time
from typing import Dict, List, Tuple, Optional, Any

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType, TradeType, MarketEvent, OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AdaptiveMarketMaking(ScriptStrategyBase):
    """
    A market making strategy that adapts to market conditions using technical indicators.
    """
    
    def __init__(self, 
                connector_name: str = "binance_paper_trade",
                trading_pair: str = "ETH-USDT",
                order_amount: Decimal = Decimal("0.1"),
                min_spread: Decimal = Decimal("0.001"),  # 0.1%
                max_spread: Decimal = Decimal("0.01"),   # 1%
                order_refresh_time: float = 30.0,
                max_order_age: float = 3600.0,
                rsi_length: int = 14,
                rsi_overbought: Decimal = Decimal("70"),
                rsi_oversold: Decimal = Decimal("30"),
                ema_short: int = 12,
                ema_long: int = 120,
                bb_length: int = 20,
                bb_std: float = 2.0,
                target_inventory_ratio: Decimal = Decimal("0.5"),
                min_order_amount: Decimal = Decimal("0.01"),
                volatility_adjustment: Decimal = Decimal("1.0"),
                trailing_stop_pct: Decimal = Decimal("0.02"),  # 2%
                signal_threshold: Decimal = Decimal("50"),  # Min signal score (0-100) to place orders
                ):
        super().__init__()
        
        # Strategy parameters
        self.connector_name = connector_name
        self.trading_pair = trading_pair
        self.order_amount = order_amount
        self.min_spread = min_spread
        self.max_spread = max_spread
        self.order_refresh_time = order_refresh_time
        self.max_order_age = max_order_age
        self.rsi_length = rsi_length
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.bb_length = bb_length
        self.bb_std = bb_std
        self.target_inventory_ratio = target_inventory_ratio
        self.min_order_amount = min_order_amount
        self.volatility_adjustment = volatility_adjustment
        self.trailing_stop_pct = trailing_stop_pct
        self.signal_threshold = signal_threshold
        
        # Runtime variables
        self.market = None
        self.base_asset, self.quote_asset = self.trading_pair.split("-")
        self.price_data = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        self.indicators = {}
        self.last_order_refresh_time = 0
        self.active_orders = []
        self.trailing_stops = {}
        self.market_regime = "unknown"
        
        # Register markets
        self.markets = {connector_name: {trading_pair}}
        
    def on_tick(self):
        """
        Called on each clock tick.
        """
        # Check if it's time to refresh orders
        current_time = time.time()
        elapsed_time = current_time - self.last_order_refresh_time
        
        if elapsed_time < self.order_refresh_time:
            # Not time to refresh yet
            self.check_trailing_stops()
            return
            
        # Update market data and calculate indicators
        self.update_market_data()
        self.calculate_indicators()
        self.detect_market_regime()
        
        # Cancel existing orders
        self.cancel_all_orders()
        
        # Create new orders based on current market conditions
        signal_score = self.calculate_signal_score()
        self.logger().info(f"Signal score: {signal_score:.2f}, Market regime: {self.market_regime}")
        
        if signal_score >= self.signal_threshold:
            spread = self.calculate_adaptive_spread()
            bid_price, ask_price = self.calculate_order_prices(spread)
            bid_amount, ask_amount = self.calculate_order_sizes()
            
            self.place_orders(bid_price, ask_price, bid_amount, ask_amount)
            
        self.last_order_refresh_time = current_time
    
    def update_market_data(self):
        """
        Update the price data with the latest market information.
        """
        connector = self.connectors[self.connector_name]
        
        # Get recent candles
        candles = connector.get_candles(
            trading_pair=self.trading_pair,
            interval="1m",
            max_records=1000
        )
        
        if candles:
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
            
            # Ensure numeric values
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col])
                
            self.price_data = df
    
    def calculate_indicators(self):
        """
        Calculate technical indicators based on price data.
        """
        if len(self.price_data) < self.ema_long:
            # Not enough data
            return
            
        # RSI
        self.indicators["rsi"] = ta.rsi(self.price_data["close"], length=self.rsi_length)
        
        # MACD
        macd = ta.macd(self.price_data["close"], fast=self.ema_short, slow=26, signal=9)
        self.indicators["macd"] = macd["MACD_12_26_9"]
        self.indicators["macd_signal"] = macd["MACDs_12_26_9"]
        self.indicators["macd_hist"] = macd["MACDh_12_26_9"]
        
        # EMAs
        self.indicators["ema_short"] = ta.ema(self.price_data["close"], length=self.ema_short)
        self.indicators["ema_long"] = ta.ema(self.price_data["close"], length=self.ema_long)
        
        # Bollinger Bands
        bb = ta.bbands(self.price_data["close"], length=self.bb_length, std=self.bb_std)
        self.indicators["bb_upper"] = bb["BBU_20_2.0"]
        self.indicators["bb_middle"] = bb["BBM_20_2.0"]
        self.indicators["bb_lower"] = bb["BBL_20_2.0"]
        
        # Volatility (ATR)
        self.indicators["atr"] = ta.atr(self.price_data["high"], self.price_data["low"], self.price_data["close"], length=14)
    
    def detect_market_regime(self):
        """
        Detect the current market regime based on indicators.
        """
        if len(self.price_data) < self.ema_long or "atr" not in self.indicators:
            self.market_regime = "unknown"
            return
            
        current_price = self.get_mid_price()
        current_atr = self.indicators["atr"].iloc[-1]
        avg_price = self.price_data["close"].mean()
        
        # Calculate volatility ratio (ATR as % of price)
        volatility_ratio = float(current_atr / avg_price)
        
        # Trend detection
        ema_short_current = self.indicators["ema_short"].iloc[-1]
        ema_long_current = self.indicators["ema_long"].iloc[-1]
        ema_diff_percent = abs(float((ema_short_current - ema_long_current) / ema_long_current))
        
        # Classify market regimes
        if ema_diff_percent > 0.02:  # EMAs differ by more than 2%
            if volatility_ratio > 0.015:  # High volatility (>1.5% of price)
                self.market_regime = "trending_volatile"
            else:
                self.market_regime = "trending"
        else:
            if volatility_ratio > 0.015:
                self.market_regime = "volatile"
            else:
                self.market_regime = "ranging"
    
    def calculate_signal_score(self) -> Decimal:
        """
        Calculate a composite signal score (0-100) based on all indicators.
        """
        if len(self.price_data) < self.ema_long or "rsi" not in self.indicators:
            return Decimal("0")
            
        # Get current indicator values
        current_price = self.get_mid_price()
        current_rsi = self.indicators["rsi"].iloc[-1]
        current_macd = self.indicators["macd"].iloc[-1]
        current_macd_signal = self.indicators["macd_signal"].iloc[-1]
        current_ema_short = self.indicators["ema_short"].iloc[-1]
        current_ema_long = self.indicators["ema_long"].iloc[-1]
        current_bb_upper = self.indicators["bb_upper"].iloc[-1]
        current_bb_lower = self.indicators["bb_lower"].iloc[-1]
        current_bb_middle = self.indicators["bb_middle"].iloc[-1]
        
        # RSI score (0-20)
        rsi_score = 10  # Neutral
        if current_rsi < self.rsi_oversold:
            # Oversold - bullish
            rsi_score = 20
        elif current_rsi > self.rsi_overbought:
            # Overbought - bearish
            rsi_score = 0
            
        # MACD score (0-25)
        macd_score = 12.5  # Neutral
        if current_macd > current_macd_signal and current_macd > 0:
            # Strong bullish
            macd_score = 25
        elif current_macd > current_macd_signal:
            # Weak bullish
            macd_score = 18.75
        elif current_macd < current_macd_signal and current_macd < 0:
            # Strong bearish
            macd_score = 0
        elif current_macd < current_macd_signal:
            # Weak bearish
            macd_score = 6.25
            
        # EMA score (0-20)
        ema_score = 10  # Neutral
        if current_ema_short > current_ema_long:
            # Bullish trend
            ema_distance = (current_ema_short - current_ema_long) / current_ema_long
            ema_score = min(20, 10 + float(ema_distance * 1000))
        else:
            # Bearish trend
            ema_distance = (current_ema_long - current_ema_short) / current_ema_long
            ema_score = max(0, 10 - float(ema_distance * 1000))
            
        # Bollinger Bands score (0-20)
        bb_score = 10  # Neutral
        bb_width = (current_bb_upper - current_bb_lower) / current_bb_middle
        price_position = (current_price - current_bb_lower) / (current_bb_upper - current_bb_lower)
        
        if price_position < 0.2:
            # Near lower band - bullish
            bb_score = 20
        elif price_position > 0.8:
            # Near upper band - bearish
            bb_score = 0
        else:
            # Middle range - neutral with slight adjustment
            bb_score = 10 + (0.5 - float(price_position)) * 20
            
        # Volume score (0-15)
        volume_score = 7.5  # Neutral
        if len(self.price_data) >= 20:
            current_volume = self.price_data["volume"].iloc[-1]
            avg_volume = self.price_data["volume"].iloc[-20:].mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            if volume_ratio > 1.5:
                # High volume - stronger signal
                volume_score = 15
            elif volume_ratio < 0.5:
                # Low volume - weaker signal
                volume_score = 0
                
        # Combine scores
        total_score = rsi_score + macd_score + ema_score + bb_score + volume_score
        
        return Decimal(str(total_score))
    
    def calculate_adaptive_spread(self) -> Decimal:
        """
        Calculate an adaptive spread based on market conditions.
        """
        # Base spread
        spread = (self.min_spread + self.max_spread) / Decimal("2")
        
        # Adjust based on market regime
        if self.market_regime == "trending":
            # Tighter spreads in trending markets
            spread = self.min_spread * Decimal("1.2")
        elif self.market_regime == "volatile" or self.market_regime == "trending_volatile":
            # Wider spreads in volatile markets
            spread = self.max_spread * Decimal("0.8")
        elif self.market_regime == "ranging":
            # Medium spreads in ranging markets
            spread = (self.min_spread + self.max_spread) / Decimal("2")
            
        # Adjust based on volatility
        if "atr" in self.indicators:
            current_atr = self.indicators["atr"].iloc[-1]
            avg_price = self.price_data["close"].mean()
            volatility_ratio = Decimal(str(float(current_atr / avg_price)))
            volatility_factor = self.volatility_adjustment * volatility_ratio * Decimal("100")
            spread = spread + volatility_factor
            
        # Ensure within bounds
        spread = max(self.min_spread, min(self.max_spread, spread))
        
        return spread
    
    def calculate_order_prices(self, spread: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Calculate the bid and ask prices based on the spread.
        """
        mid_price = self.get_mid_price()
        
        # Adjust spread based on inventory ratio
        current_inventory_ratio = self.get_inventory_ratio()
        inventory_skew = (current_inventory_ratio - self.target_inventory_ratio) * Decimal("2")
        
        # If we have too much base asset, increase ask spread and decrease bid spread
        # If we have too little base asset, decrease ask spread and increase bid spread
        bid_adjustment = -inventory_skew * self.min_spread
        ask_adjustment = inventory_skew * self.min_spread
        
        # Calculate bid and ask spreads
        bid_spread = max(Decimal("0.0001"), (spread / Decimal("2")) + bid_adjustment)
        ask_spread = max(Decimal("0.0001"), (spread / Decimal("2")) + ask_adjustment)
        
        # Calculate prices
        bid_price = mid_price * (Decimal("1") - bid_spread)
        ask_price = mid_price * (Decimal("1") + ask_spread)
        
        return self.round_price(bid_price), self.round_price(ask_price)
    
    def calculate_order_sizes(self) -> Tuple[Decimal, Decimal]:
        """
        Calculate the bid and ask order sizes based on inventory.
        """
        current_inventory_ratio = self.get_inventory_ratio()
        inventory_skew = current_inventory_ratio - self.target_inventory_ratio
        
        # Base sizes
        base_bid_size = self.order_amount
        base_ask_size = self.order_amount
        
        # Adjust order sizes based on inventory skew
        if inventory_skew > 0:
            # We have more base than target, increase ask size
            ask_size_factor = Decimal("1") + min(Decimal("1"), abs(inventory_skew) * Decimal("2"))
            bid_size_factor = Decimal("1") - min(Decimal("0.8"), abs(inventory_skew))
        else:
            # We have less base than target, increase bid size
            ask_size_factor = Decimal("1") - min(Decimal("0.8"), abs(inventory_skew))
            bid_size_factor = Decimal("1") + min(Decimal("1"), abs(inventory_skew) * Decimal("2"))
            
        # Calculate final sizes
        bid_size = max(self.min_order_amount, base_bid_size * bid_size_factor)
        ask_size = max(self.min_order_amount, base_ask_size * ask_size_factor)
        
        return self.round_amount(bid_size), self.round_amount(ask_size)
    
    def place_orders(self, bid_price: Decimal, ask_price: Decimal, bid_amount: Decimal, ask_amount: Decimal):
        """
        Place bid and ask orders at the specified prices and amounts.
        """
        connector = self.connectors[self.connector_name]
        
        # Place bid order
        if bid_amount > self.min_order_amount:
            order_id = connector.buy(
                trading_pair=self.trading_pair,
                price=bid_price,
                amount=bid_amount,
                order_type=OrderType.LIMIT,
            )
            self.logger().info(f"Placed bid order: {order_id} {bid_amount} {self.base_asset} at {bid_price} {self.quote_asset}")
            
        # Place ask order
        if ask_amount > self.min_order_amount:
            order_id = connector.sell(
                trading_pair=self.trading_pair,
                price=ask_price,
                amount=ask_amount,
                order_type=OrderType.LIMIT,
            )
            self.logger().info(f"Placed ask order: {order_id} {ask_amount} {self.base_asset} at {ask_price} {self.quote_asset}")
    
    def cancel_all_orders(self):
        """
        Cancel all active orders.
        """
        connector = self.connectors[self.connector_name]
        connector.cancel_all(self.trading_pair)
        self.active_orders = []
    
    def get_mid_price(self) -> Decimal:
        """
        Get the current mid price from the order book.
        """
        connector = self.connectors[self.connector_name]
        order_book: OrderBook = connector.get_order_book(self.trading_pair)
        return order_book.get_price_for_volume(True, 0.5).result_price
    
    def get_inventory_ratio(self) -> Decimal:
        """
        Calculate the ratio of base asset to total assets value.
        """
        connector = self.connectors[self.connector_name]
        base_balance = connector.get_available_balance(self.base_asset)
        quote_balance = connector.get_available_balance(self.quote_asset)
        
        mid_price = self.get_mid_price()
        total_value_in_quote = quote_balance + (base_balance * mid_price)
        
        if total_value_in_quote == Decimal("0"):
            return Decimal("0.5")  # Default to 50% if no balance
            
        base_value_in_quote = base_balance * mid_price
        return base_value_in_quote / total_value_in_quote
    
    def check_trailing_stops(self):
        """
        Check if any trailing stops have been triggered.
        """
        current_price = self.get_mid_price()
        
        # For demonstration, simple implementation
        if "high_water_mark" not in self.trailing_stops:
            self.trailing_stops["high_water_mark"] = current_price
        else:
            # Update high water mark if price increased
            if current_price > self.trailing_stops["high_water_mark"]:
                self.trailing_stops["high_water_mark"] = current_price
            
            # Check if trailing stop triggered
            stop_price = self.trailing_stops["high_water_mark"] * (Decimal("1") - self.trailing_stop_pct)
            
            if current_price < stop_price:
                self.logger().info(f"Trailing stop triggered at {current_price} (stop: {stop_price})")
                # Could implement position reduction here
                self.trailing_stops["high_water_mark"] = current_price
    
    def did_fill_order(self, event: OrderFilledEvent):
        """
        Called when an order is filled.
        """
        self.logger().info(f"Order filled: {event.order_id} {event.amount} {event.base_asset} at {event.price} {event.quote_asset}")
    
    def round_price(self, price: Decimal) -> Decimal:
        """
        Round price to appropriate precision.
        """
        connector = self.connectors[self.connector_name]
        price_precision = connector.get_order_price_quantum(self.trading_pair, price)
        return (price // price_precision) * price_precision
    
    def round_amount(self, amount: Decimal) -> Decimal:
        """
        Round amount to appropriate precision.
        """
        connector = self.connectors[self.connector_name]
        amount_precision = connector.get_order_size_quantum(self.trading_pair, amount)
        return (amount // amount_precision) * amount_precision 