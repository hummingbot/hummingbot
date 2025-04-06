#!/usr/bin/env python3
"""
Precision Trading Strategy

This script implements an advanced market making strategy that adapts to market conditions
using volatility indicators, trend analysis, and comprehensive risk management.
It builds upon the basic Pure Market Making approach with enhanced features:

1. Multi-timeframe technical analysis
2. Adaptive order sizing and spread calculation
3. Market regime detection
4. Risk-adjusted position management
5. Weighted indicator system

The strategy is designed for Hummingbot and follows the script strategy pattern.
"""

import numpy as np
import pandas as pd
import time
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Any

# Hummingbot imports
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType, PriceType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from pydantic import Field, validator
from hummingbot.client.settings import ClientFieldData

# Try to import pandas_ta for technical analysis
try:
    import pandas_ta as ta
except ImportError:
    logging.warning("pandas_ta not installed. Installing it is recommended: pip install pandas_ta")


class PrecisionTradingConfig(StrategyV2ConfigBase):
    """Configuration parameters for Precision Trading strategy"""
    
    # Market parameters
    exchange: str = Field(
        default="binance_paper_trade",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the exchange name (default: binance_paper_trade):"
        )
    )
    
    trading_pair: str = Field(
        default="BTC-USDT",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the trading pair (default: BTC-USDT):"
        )
    )
    
    # Technical analysis parameters
    short_window: int = Field(
        default=20,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter short window for indicators (default: 20):"
        )
    )
    
    long_window: int = Field(
        default=50,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter long window for indicators (default: 50):"
        )
    )
    
    rsi_length: int = Field(
        default=14,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter RSI period length (default: 14):"
        )
    )
    
    bb_length: int = Field(
        default=20,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter Bollinger Bands period (default: 20):"
        )
    )
    
    atr_length: int = Field(
        default=14,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter ATR period length (default: 14):"
        )
    )
    
    # Market making parameters
    order_amount: Decimal = Field(
        default=Decimal("0.01"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the order amount in base asset (default: 0.01):"
        )
    )
    
    min_spread: Decimal = Field(
        default=Decimal("0.002"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the minimum spread (default: 0.002 or 0.2%):"
        )
    )
    
    max_spread: Decimal = Field(
        default=Decimal("0.02"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the maximum spread (default: 0.02 or 2%):"
        )
    )
    
    order_refresh_time: float = Field(
        default=30.0,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter order refresh time in seconds (default: 30):"
        )
    )
    
    # Risk management parameters
    risk_profile: str = Field(
        default="moderate",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter risk profile (conservative, moderate, aggressive):"
        )
    )
    
    target_inventory_ratio: Decimal = Field(
        default=Decimal("0.5"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter target inventory ratio (0-1, default: 0.5):"
        )
    )
    
    # Candle configuration
    candle_intervals: List[str] = Field(
        default=["1m", "5m", "15m", "1h"],
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter comma-separated candle intervals (default: 1m,5m,15m,1h):"
        )
    )
    
    max_records: int = Field(
        default=100,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter maximum candle records to fetch (default: 100):"
        )
    )
    
    @validator("risk_profile")
    def validate_risk_profile(cls, v):
        """Validate risk profile input"""
        valid_profiles = ["conservative", "moderate", "aggressive"]
        if v.lower() not in valid_profiles:
            raise ValueError(f"Risk profile must be one of: {', '.join(valid_profiles)}")
        return v.lower()
    
    @validator("candle_intervals")
    def validate_candle_intervals(cls, v):
        """Validate candle intervals"""
        if isinstance(v, str):
            # Handle comma-separated string input
            intervals = [interval.strip() for interval in v.split(",")]
            return intervals
        return v


class PrecisionTradingStrategy(ScriptStrategyBase):
    """Precision Trading Strategy with Adaptive Market Making"""
    
    def __init__(self, config: PrecisionTradingConfig):
        """Initialize the strategy"""
        super().__init__()
        self.config = config
        
        # Set up markets
        self.exchange = config.exchange
        self.trading_pair = config.trading_pair
        self.markets = {self.exchange: {self.trading_pair}}
        
        # Strategy parameters
        self.order_amount = config.order_amount
        self.min_spread = config.min_spread
        self.max_spread = config.max_spread
        self.order_refresh_time = config.order_refresh_time
        self.target_inventory_ratio = config.target_inventory_ratio
        self.risk_profile = config.risk_profile
        
        # Technical analysis parameters
        self.short_window = config.short_window
        self.long_window = config.long_window
        self.rsi_length = config.rsi_length
        self.bb_length = config.bb_length
        self.atr_length = config.atr_length
        
        # Initialize data structures
        self._last_order_refresh_timestamp = 0
        self._active_orders = {}
        self._candles = {}
        self._indicators = {}
        self._market_regime = {"regime": "ranging", "confidence": 0.0}
        self._total_score = 0.0
        
        # Initialize indicator weights for different market regimes
        self._indicator_weights = {
            'trending': {
                'RSI': 0.15,
                'MACD': 0.25,
                'EMA': 0.20,
                'BB': 0.15,
                'VOLUME': 0.15,
                'ATR': 0.10
            },
            'volatile': {
                'RSI': 0.20,
                'MACD': 0.15,
                'EMA': 0.15,
                'BB': 0.25,
                'VOLUME': 0.15,
                'ATR': 0.10
            },
            'ranging': {
                'RSI': 0.25,
                'MACD': 0.15,
                'EMA': 0.10,
                'BB': 0.25,
                'VOLUME': 0.10,
                'ATR': 0.15
            }
        }
        
        # Initialize timeframe weights
        self._timeframe_weights = {
            '1m': 0.15,
            '5m': 0.25,
            '15m': 0.35,
            '1h': 0.25
        }
        
        # Set up candle feeds
        self._initialize_candles()
        
        # Log initialization
        self.logger().info(f"Initialized Precision Trading Strategy with {self.trading_pair} on {self.exchange}")
        self.logger().info(f"Risk profile: {self.risk_profile}, Target inventory ratio: {self.target_inventory_ratio}")
    
    def _initialize_candles(self):
        """Initialize candle factories for each timeframe"""
        for interval in self.config.candle_intervals:
            candles_config = CandlesConfig(
                connector=self.exchange,
                trading_pair=self.trading_pair,
                interval=interval,
                max_records=self.config.max_records
            )
            candle_factory = CandlesFactory.get_candle(candles_config)
            self._candles[interval] = candle_factory
            self.logger().info(f"Initialized {interval} candles for {self.trading_pair}")
    
    def on_tick(self):
        """Main strategy logic executed on each tick"""
        if not self.ready_to_trade:
            return
            
        current_tick = time.time()
        
        # Check if we need to refresh orders
        if current_tick - self._last_order_refresh_timestamp > self.order_refresh_time:
            # Update market data and indicators
            self._update_market_data()
            
            # Detect market regime
            self._detect_market_regime()
            
            # Generate trading signals
            self._generate_signal_score()
            
            # Create new orders
            self._create_orders()
            
            # Update timestamp
            self._last_order_refresh_timestamp = current_tick
            
            # Log status
            self.logger().info(f"Market regime: {self._market_regime['regime']} (confidence: {self._market_regime['confidence']:.2f})")
            self.logger().info(f"Signal score: {self._total_score:.2f}")
    
    def _update_market_data(self):
        """Update candle data and calculate indicators for all timeframes"""
        try:
            for interval, candle_factory in self._candles.items():
                df = candle_factory.candles_df
                if df is None or df.empty:
                    self.logger().warning(f"No data available for {interval} timeframe")
                    continue
                    
                # Calculate indicators for this timeframe
                self._calculate_indicators_for_timeframe(interval, df)
        except Exception as e:
            self.logger().error(f"Error updating market data: {e}", exc_info=True)
    
    def _calculate_indicators_for_timeframe(self, interval, df):
        """Calculate technical indicators for the specified timeframe"""
        try:
            if df is None or df.empty:
                return
                
            # Make a copy of the dataframe to avoid modifying the original
            df = df.copy()
            
            # Check if we have enough data points for valid calculations
            min_required_points = max(self.rsi_length, self.bb_length, self.atr_length, 26)  # 26 for MACD
            if len(df) < min_required_points:
                self.logger().warning(f"Not enough data points for {interval} (have {len(df)}, need {min_required_points})")
                return
            
            # Calculate basic indicators
            # RSI
            df.ta.rsi(length=self.rsi_length, append=True)
            
            # MACD
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            
            # EMA
            df.ta.ema(length=self.short_window, append=True)
            df.ta.ema(length=self.long_window, append=True)
            
            # Bollinger Bands
            df.ta.bbands(length=self.bb_length, std=2.0, append=True)
            
            # ATR for volatility measurement
            df.ta.atr(length=self.atr_length, append=True)
            
            # Volume indicators (if volume data is available)
            if 'volume' in df.columns:
                df.ta.vwap(append=True)
            
            # Calculate BB position
            if f'BBL_{self.bb_length}_2.0' in df.columns and f'BBU_{self.bb_length}_2.0' in df.columns:
                df['bb_range'] = df[f'BBU_{self.bb_length}_2.0'] - df[f'BBL_{self.bb_length}_2.0']
                df['bb_pos'] = (df['close'] - df[f'BBL_{self.bb_length}_2.0']) / df['bb_range']
            
            # Calculate EMA signal (trend strength)
            if f'EMA_{self.short_window}' in df.columns and f'EMA_{self.long_window}' in df.columns:
                df['ema_signal'] = df[f'EMA_{self.short_window}'] / df[f'EMA_{self.long_window}'] - 1
            
            # Store the latest indicator values
            if df.empty:
                return
                
            latest = df.iloc[-1]
            indicators = {}
            
            # Store all indicators
            for col in df.columns:
                if col in latest:
                    indicators[col] = latest[col]
            
            # Store indicators for this timeframe
            self._indicators[interval] = indicators
            
            # Log some key indicators
            if f'RSI_{self.rsi_length}' in indicators:
                self.logger().debug(f"{interval} RSI: {indicators[f'RSI_{self.rsi_length}']:.2f}")
            if 'bb_pos' in indicators:
                self.logger().debug(f"{interval} BB Position: {indicators['bb_pos']:.2f}")
                
        except Exception as e:
            self.logger().error(f"Error calculating indicators for {interval}: {e}", exc_info=True)
    
    def _detect_market_regime(self):
        """Detect the current market regime"""
        try:
            # Default to ranging
            regime = "ranging"
            confidence = 0.5
            
            # Use 1-hour timeframe for regime detection if available
            timeframe = "1h" if "1h" in self._indicators else list(self._indicators.keys())[0] if self._indicators else None
            
            if timeframe is None or timeframe not in self._indicators:
                self._market_regime = {"regime": regime, "confidence": confidence}
                return
                
            ind = self._indicators[timeframe]
            
            # Get ATR and calculate normalized ATR (NATR)
            atr_col = f'ATR_{self.atr_length}'
            if atr_col in ind and 'close' in ind and ind['close'] > 0:
                atr = ind[atr_col]
                close = ind['close']
                natr = (atr / close) * 100
                
                # Check Bollinger Band width
                bb_width = 0
                if f'BBU_{self.bb_length}_2.0' in ind and f'BBL_{self.bb_length}_2.0' in ind and f'BBM_{self.bb_length}_2.0' in ind:
                    upper = ind[f'BBU_{self.bb_length}_2.0']
                    lower = ind[f'BBL_{self.bb_length}_2.0']
                    middle = ind[f'BBM_{self.bb_length}_2.0']
                    bb_width = (upper - lower) / middle
                
                # Check EMA trend
                ema_trend = 0
                if 'ema_signal' in ind:
                    ema_trend = ind['ema_signal']
                
                # Determine regime
                if natr > 3 and bb_width > 0.05:  # High volatility
                    regime = "volatile"
                    confidence = min(1.0, natr / 5.0)
                elif abs(ema_trend) > 0.02:  # Strong trend
                    regime = "trending"
                    confidence = min(1.0, abs(ema_trend) / 0.03)
                else:  # Ranging market
                    regime = "ranging"
                    confidence = 1.0 - min(0.8, abs(ema_trend) / 0.03)
            
            self._market_regime = {"regime": regime, "confidence": confidence}
            
        except Exception as e:
            self.logger().error(f"Error detecting market regime: {e}", exc_info=True)
            self._market_regime = {"regime": "ranging", "confidence": 0.5}
    
    def _generate_signal_score(self):
        """Generate overall signal score (-1 to 1)"""
        try:
            total_score = 0
            total_weight = 0
            
            # Get current market regime
            regime = self._market_regime["regime"]
            
            # Process each timeframe
            for interval, weight in self._timeframe_weights.items():
                if interval not in self._indicators:
                    continue
                    
                # Get indicators for this timeframe
                ind = self._indicators[interval]
                
                # RSI component (-1 to 1 scale)
                rsi_score = 0
                rsi_col = f'RSI_{self.rsi_length}'
                if rsi_col in ind:
                    rsi = ind[rsi_col]
                    if rsi < 30:
                        rsi_score = (30 - rsi) / 30  # Bullish when RSI is low
                    elif rsi > 70:
                        rsi_score = -1 * (rsi - 70) / 30  # Bearish when RSI is high
                    else:
                        # Neutral zone - slight signal based on direction
                        rsi_score = (50 - rsi) / 40  # Small score, positive below 50, negative above
                
                # Bollinger Band component
                bb_score = 0
                if 'bb_pos' in ind:
                    bb_pos = ind['bb_pos']
                    if bb_pos < 0.2:
                        bb_score = (0.2 - bb_pos) * 5  # Bullish when price near lower band
                    elif bb_pos > 0.8:
                        bb_score = -1 * (bb_pos - 0.8) * 5  # Bearish when price near upper band
                    else:
                        bb_score = 0  # Neutral in the middle
                
                # EMA trend component
                ema_score = 0
                if 'ema_signal' in ind:
                    ema_signal = ind['ema_signal']
                    ema_score = min(1, max(-1, ema_signal * 10))  # Scale to -1 to 1
                
                # MACD component
                macd_score = 0
                if 'MACD_12_26_9' in ind and 'MACDs_12_26_9' in ind:
                    macd = ind['MACD_12_26_9']
                    macd_signal = ind['MACDs_12_26_9']
                    
                    if macd > macd_signal:
                        macd_score = min(1, (macd - macd_signal) * 100)  # Bullish MACD crossover
                    else:
                        macd_score = max(-1, (macd - macd_signal) * 100)  # Bearish MACD crossover
                
                # Volume component
                volume_score = 0
                # Simplified volume analysis
                
                # ATR component (volatility)
                atr_score = 0
                atr_col = f'ATR_{self.atr_length}'
                if atr_col in ind and 'close' in ind and ind['close'] > 0:
                    atr = ind[atr_col]
                    close = ind['close']
                    natr = (atr / close) * 100
                    
                    # Higher ATR typically means more volatile market
                    # In trending regime, high volatility can be good for trend continuation
                    if regime == "trending":
                        atr_score = min(1, natr / 5) * np.sign(ema_score)  # Use trend direction
                    else:
                        # In ranging or volatile regimes, high ATR can signal mean reversion
                        atr_score = -min(1, natr / 5) * np.sign(bb_score)  # Counter BB direction
                
                # Weight scores by current regime
                weighted_score = (
                    rsi_score * self._indicator_weights[regime]['RSI'] +
                    macd_score * self._indicator_weights[regime]['MACD'] +
                    ema_score * self._indicator_weights[regime]['EMA'] +
                    bb_score * self._indicator_weights[regime]['BB'] +
                    volume_score * self._indicator_weights[regime]['VOLUME'] +
                    atr_score * self._indicator_weights[regime]['ATR']
                )
                
                # Add to total
                total_score += weighted_score * weight
                total_weight += weight
            
            # Calculate final score
            if total_weight > 0:
                self._total_score = total_score / total_weight
            else:
                self._total_score = 0
                
        except Exception as e:
            self.logger().error(f"Error generating signal score: {e}", exc_info=True)
            self._total_score = 0
    
    def _create_orders(self):
        """Create new orders based on signal and market regime"""
        try:
            if not self.ready_to_trade:
                return
                
            # Cancel existing orders
            self._cancel_active_orders()
            
            # Get connector
            connector = self.connectors[self.exchange]
            
            # Get mid price
            mid_price = self._get_mid_price(connector, self.trading_pair)
            if mid_price is None:
                self.logger().warning("Unable to get mid price, skipping order creation")
                return
            
            # Calculate adaptive spreads based on market conditions and signal
            bid_spread = self._calculate_bid_spread()
            ask_spread = self._calculate_ask_spread()
            
            # Calculate prices
            bid_price = mid_price * (Decimal("1") - bid_spread)
            ask_price = mid_price * (Decimal("1") + ask_spread)
            
            # Round prices to ticker price precision
            bid_price = connector.quantize_order_price(self.trading_pair, bid_price)
            ask_price = connector.quantize_order_price(self.trading_pair, ask_price)
            
            # Calculate order sizes based on inventory management
            inventory_ratio = self._calculate_inventory_ratio()
            
            # Adjust order sizes based on inventory
            # If we have too much base asset, increase sell size and decrease buy size
            # If we have too little base asset, increase buy size and decrease sell size
            inventory_target_ratio = self.target_inventory_ratio
            inventory_adjustment = Decimal("1") + Decimal("0.5") * abs(inventory_ratio - inventory_target_ratio)
            
            if inventory_ratio > inventory_target_ratio:
                # Too much base asset, increase sell size
                buy_size_pct = Decimal("1")
                sell_size_pct = inventory_adjustment
            else:
                # Too little base asset, increase buy size
                buy_size_pct = inventory_adjustment
                sell_size_pct = Decimal("1")
            
            # Apply risk profile to base order size and spreads
            base_order_size = self.order_amount
            
            if self.risk_profile == "conservative":
                base_order_size = base_order_size * Decimal("0.5")
            elif self.risk_profile == "aggressive":
                base_order_size = base_order_size * Decimal("1.5")
            
            # Calculate final order sizes
            bid_size = base_order_size * buy_size_pct
            ask_size = base_order_size * sell_size_pct
            
            # Get exchange minimum order size and ensure compliance
            try:
                min_order_size = connector.get_min_order_amount(self.trading_pair)
            except Exception:
                min_order_size = Decimal("0.0001")  # Default fallback if method not available
            
            # Ensure order sizes meet minimum requirements
            bid_size = max(min_order_size, bid_size)
            ask_size = max(min_order_size, ask_size)
            
            # Quantize order sizes
            bid_size = connector.quantize_order_amount(self.trading_pair, bid_size)
            ask_size = connector.quantize_order_amount(self.trading_pair, ask_size)
            
            # Check if order sizes meet minimum requirements
            if bid_size > Decimal("0") and ask_size > Decimal("0"):
                # Create buy order
                buy_order_id = self.buy(
                    connector_name=self.exchange,
                    trading_pair=self.trading_pair,
                    amount=bid_size,
                    order_type=OrderType.LIMIT,
                    price=bid_price
                )
                
                # Create sell order
                sell_order_id = self.sell(
                    connector_name=self.exchange,
                    trading_pair=self.trading_pair,
                    amount=ask_size,
                    order_type=OrderType.LIMIT,
                    price=ask_price
                )
                
                # Track orders
                if buy_order_id:
                    self._active_orders[buy_order_id] = {
                        "type": "buy",
                        "price": bid_price,
                        "amount": bid_size,
                        "created_at": time.time()
                    }
                    
                if sell_order_id:
                    self._active_orders[sell_order_id] = {
                        "type": "sell",
                        "price": ask_price,
                        "amount": ask_size,
                        "created_at": time.time()
                    }
                
                self.logger().info(f"Created new orders - BUY: {bid_size} @ {bid_price}, SELL: {ask_size} @ {ask_price}")
                self.logger().info(f"Current spreads - BID: {bid_spread:.2%}, ASK: {ask_spread:.2%}")
        except Exception as e:
            self.logger().error(f"Error creating orders: {e}", exc_info=True)
    
    def _calculate_bid_spread(self) -> Decimal:
        """Calculate adaptive bid spread"""
        try:
            # Start with base spread
            spread = self.min_spread
            
            # Adjust based on signal score (-1 to 1)
            # Negative score (bearish) = wider spread on buys
            # Positive score (bullish) = tighter spread on buys
            signal_adjustment = Decimal(str(-0.5 * self._total_score)) * Decimal("0.01")
            
            # Adjust based on volatility
            volatility_adjustment = self._get_volatility_adjustment()
            
            # Adjust based on market regime
            regime_adjustment = Decimal("0")
            if self._market_regime["regime"] == "volatile":
                regime_adjustment = Decimal("0.001") * Decimal(str(self._market_regime["confidence"]))
            elif self._market_regime["regime"] == "trending" and self._total_score < 0:
                # Widen spread in downtrend
                regime_adjustment = Decimal("0.001") * Decimal(str(self._market_regime["confidence"]))
            
            # Combine adjustments
            final_spread = spread + signal_adjustment + volatility_adjustment + regime_adjustment
            
            # Ensure spread is within limits
            return max(self.min_spread, min(self.max_spread, final_spread))
        except Exception as e:
            self.logger().error(f"Error calculating bid spread: {e}", exc_info=True)
            return self.min_spread
    
    def _calculate_ask_spread(self) -> Decimal:
        """Calculate adaptive ask spread"""
        try:
            # Start with base spread
            spread = self.min_spread
            
            # Adjust based on signal score (-1 to 1)
            # Negative score (bearish) = tighter spread on sells
            # Positive score (bullish) = wider spread on sells
            signal_adjustment = Decimal(str(0.5 * self._total_score)) * Decimal("0.01")
            
            # Adjust based on volatility
            volatility_adjustment = self._get_volatility_adjustment()
            
            # Adjust based on market regime
            regime_adjustment = Decimal("0")
            if self._market_regime["regime"] == "volatile":
                regime_adjustment = Decimal("0.001") * Decimal(str(self._market_regime["confidence"]))
            elif self._market_regime["regime"] == "trending" and self._total_score > 0:
                # Widen spread in uptrend
                regime_adjustment = Decimal("0.001") * Decimal(str(self._market_regime["confidence"]))
            
            # Combine adjustments
            final_spread = spread + signal_adjustment + volatility_adjustment + regime_adjustment
            
            # Ensure spread is within limits
            return max(self.min_spread, min(self.max_spread, final_spread))
        except Exception as e:
            self.logger().error(f"Error calculating ask spread: {e}", exc_info=True)
            return self.min_spread
    
    def _get_volatility_adjustment(self) -> Decimal:
        """Get spread adjustment based on volatility"""
        try:
            # Default adjustment
            adjustment = Decimal("0")
            
            # Use 5m timeframe for volatility if available
            available_timeframes = list(self._indicators.keys())
            if not available_timeframes:
                return adjustment
                
            timeframe = "5m" if "5m" in available_timeframes else available_timeframes[0]
            
            if timeframe in self._indicators:
                ind = self._indicators[timeframe]
                atr_col = f'ATR_{self.atr_length}'
                
                if atr_col in ind and 'close' in ind and ind['close'] > 0:
                    atr = ind[atr_col]
                    close = ind['close']
                    
                    # NATR as percentage
                    natr = (atr / close) * 100
                    
                    # Scale NATR to a spread adjustment
                    # Typical NATR ranges: <1% low volatility, 1-3% normal, >3% high
                    if natr < 1:
                        adjustment = Decimal("0.0005")  # 0.05% increase for low vol
                    elif natr < 3:
                        adjustment = Decimal("0.001") * Decimal(str(natr))  # 0.1-0.3% increase for normal vol
                    else:
                        adjustment = Decimal("0.003") * Decimal(str(min(5, natr)))  # 0.9-1.5% increase for high vol
                        
                    # Log volatility information
                    self.logger().debug(f"Volatility (NATR): {natr:.2f}%, Spread adjustment: {adjustment:.4f}")
            
            return adjustment
        except Exception as e:
            self.logger().error(f"Error calculating volatility adjustment: {e}", exc_info=True)
            return Decimal("0.001")  # Default fallback value
    
    def _cancel_active_orders(self):
        """Cancel all active orders"""
        try:
            for connector_name, trading_pairs in self.markets.items():
                for trading_pair in trading_pairs:
                    orders = self.get_active_orders(connector_name=connector_name, trading_pair=trading_pair)
                    for order in orders:
                        self.cancel(connector_name, trading_pair, order.client_order_id)
            
            # Clear tracking dictionary
            self._active_orders = {}
        except Exception as e:
            self.logger().error(f"Error cancelling orders: {e}", exc_info=True)
    
    def _calculate_inventory_ratio(self) -> Decimal:
        """Calculate the ratio of base asset to total portfolio value"""
        try:
            if not self.ready_to_trade:
                return Decimal("0.5")
                
            connector = self.connectors[self.exchange]
            base, quote = self.trading_pair.split("-")
            
            # Get balances
            base_balance = connector.get_available_balance(base)
            quote_balance = connector.get_available_balance(quote)
            
            # Get mid price
            mid_price = self._get_mid_price(connector, self.trading_pair)
            if mid_price is None or mid_price == Decimal("0"):
                return Decimal("0.5")
            
            # Calculate total value in quote currency
            total_value = base_balance * mid_price + quote_balance
            
            if total_value == Decimal("0"):
                return Decimal("0.5")
                
            # Calculate ratio of base asset value to total value
            base_value = base_balance * mid_price
            return base_value / total_value
        except Exception as e:
            self.logger().error(f"Error calculating inventory ratio: {e}", exc_info=True)
            return Decimal("0.5")
    
    def _get_mid_price(self, connector: ConnectorBase, trading_pair: str) -> Optional[Decimal]:
        """Get mid price from orderbook"""
        try:
            orderbook = connector.get_order_book(trading_pair)
            if orderbook.get_price_for_volume(True, 0.1).result_price is None or \
               orderbook.get_price_for_volume(False, 0.1).result_price is None:
                return None
            bid_price = orderbook.get_price_for_volume(True, 0.1).result_price
            ask_price = orderbook.get_price_for_volume(False, 0.1).result_price
            return (bid_price + ask_price) / Decimal("2")
        except Exception as e:
            self.logger().error(f"Error getting mid price: {e}", exc_info=True)
            return None
    
    def format_status(self) -> str:
        """Format status for display in Hummingbot"""
        if not self.ready_to_trade:
            return "Strategy not ready to trade."
            
        lines = []
        lines.append("Precision Trading Strategy")
        
        # Add market info
        connector = self.connectors[self.exchange]
        mid_price = self._get_mid_price(connector, self.trading_pair)
        lines.append(f"\nTrading Pair: {self.trading_pair} @ {self.exchange}")
        lines.append(f"Current price: {mid_price:.8g}")
        
        # Add market regime
        lines.append(f"\nMarket Regime: {self._market_regime['regime'].capitalize()} "
                     f"(Confidence: {self._market_regime['confidence']:.2f})")
        lines.append(f"Signal Score: {self._total_score:.2f}")
        
        # Show current spreads
        bid_spread = self._calculate_bid_spread()
        ask_spread = self._calculate_ask_spread()
        lines.append(f"Current Spreads: Bid {bid_spread:.2%}, Ask {ask_spread:.2%}")
        
        # Show inventory information
        inventory_ratio = self._calculate_inventory_ratio()
        lines.append(f"Inventory Ratio: {inventory_ratio:.2%} (Target: {self.target_inventory_ratio:.2%})")
        
        # Show active orders
        lines.append("\nActive Orders:")
        active_orders = self.get_active_orders(connector_name=self.exchange)
        if not active_orders:
            lines.append("  No active orders")
        else:
            for order in active_orders:
                lines.append(f"  {order.order_side.name}: {order.amount} @ {order.price:.8g}")
        
        # Show key technical indicators
        lines.append("\nKey Indicators:")
        for interval in sorted(self._indicators.keys()):
            ind = self._indicators[interval]
            lines.append(f"  {interval}:")
            
            # RSI
            rsi_col = f'RSI_{self.rsi_length}'
            if rsi_col in ind:
                lines.append(f"    RSI: {ind[rsi_col]:.2f}")
                
            # BB position
            if 'bb_pos' in ind:
                lines.append(f"    BB Position: {ind['bb_pos']:.2f}")
                
            # ATR
            atr_col = f'ATR_{self.atr_length}'
            if atr_col in ind and 'close' in ind and ind['close'] > 0:
                natr = (ind[atr_col] / ind['close']) * 100
                lines.append(f"    NATR: {natr:.2f}%")
                
            # MACD
            if 'MACD_12_26_9' in ind and 'MACDs_12_26_9' in ind:
                macd_diff = ind['MACD_12_26_9'] - ind['MACDs_12_26_9']
                lines.append(f"    MACD Diff: {macd_diff:.6f}")
        
        return "\n".join(lines)

# Initialize the strategy with YAML configuration file
import os
import yaml

def start():
    # Try to load configuration from YAML file
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 
                              "conf", "strategies", "conf_precision_trading_1.yml")
    
    try:
        print(f"Loading configuration from: {config_path}")
        with open(config_path, "r") as file:
            config_data = yaml.safe_load(file)
            
        # Extract parameters from YAML
        exchange = config_data.get("exchange", "binance")
        trading_pair = config_data.get("trading_pair", "BTC-USDT")
        order_amount = Decimal(str(config_data.get("order_amount", 0.01)))
        min_spread = Decimal(str(config_data.get("min_spread", 0.002)))
        max_spread = Decimal(str(config_data.get("max_spread", 0.02)))
        target_inventory_ratio = Decimal(str(config_data.get("target_inventory_ratio", 0.5)))
        risk_profile = config_data.get("risk_profile", "moderate")
        
        # Technical indicator parameters
        rsi_length = int(config_data.get("rsi_length", 14))
        bb_length = int(config_data.get("bb_length", 20))
        atr_length = int(config_data.get("atr_length", 14))
        short_window = int(config_data.get("short_window", 9))
        long_window = int(config_data.get("long_window", 21))
        
        # Get timeframe weights
        timeframe_weights = config_data.get("timeframe_weights", {
            "1m": 0.2,
            "5m": 0.3,
            "15m": 0.3,
            "1h": 0.2
        })
        
        # Default indicator weights by regime
        indicator_weights = {
            "trending": {
                "RSI": 0.1,
                "MACD": 0.3,
                "EMA": 0.3,
                "BB": 0.1,
                "VOLUME": 0.1,
                "ATR": 0.1
            },
            "ranging": {
                "RSI": 0.3,
                "MACD": 0.1,
                "EMA": 0.1,
                "BB": 0.3,
                "VOLUME": 0.1,
                "ATR": 0.1
            },
            "volatile": {
                "RSI": 0.2,
                "MACD": 0.2,
                "EMA": 0.1,
                "BB": 0.2,
                "VOLUME": 0.1,
                "ATR": 0.2
            }
        }
        
        print(f"Configuration loaded successfully. Exchange: {exchange}, Trading pair: {trading_pair}")
    except Exception as e:
        print(f"Error loading configuration: {e}")
        print("Using default configuration values...")
        
        # Default values if loading fails
        exchange = "binance"
        trading_pair = "BTC-USDT"
        order_amount = Decimal("0.01")
        min_spread = Decimal("0.002")
        max_spread = Decimal("0.02")
        target_inventory_ratio = Decimal("0.5")
        risk_profile = "moderate"
        rsi_length = 14
        bb_length = 20
        atr_length = 14
        short_window = 9
        long_window = 21
        timeframe_weights = {
            "1m": 0.2,
            "5m": 0.3,
            "15m": 0.3,
            "1h": 0.2
        }
        indicator_weights = {
            "trending": {
                "RSI": 0.1,
                "MACD": 0.3,
                "EMA": 0.3,
                "BB": 0.1,
                "VOLUME": 0.1,
                "ATR": 0.1
            },
            "ranging": {
                "RSI": 0.3,
                "MACD": 0.1,
                "EMA": 0.1,
                "BB": 0.3,
                "VOLUME": 0.1,
                "ATR": 0.1
            },
            "volatile": {
                "RSI": 0.2,
                "MACD": 0.2,
                "EMA": 0.1,
                "BB": 0.2,
                "VOLUME": 0.1,
                "ATR": 0.2
            }
        }
    
    # Create configuration object
    config = PrecisionTradingConfig(
        exchange=exchange,
        trading_pair=trading_pair,
        order_amount=order_amount,
        min_spread=min_spread,
        max_spread=max_spread,
        target_inventory_ratio=target_inventory_ratio,
        risk_profile=risk_profile,
        timeframe_weights=timeframe_weights,
        rsi_length=rsi_length,
        bb_length=bb_length,
        atr_length=atr_length,
        short_window=short_window,
        long_window=long_window,
        indicator_weights=indicator_weights
    )
    
    # Initialize and return the strategy
    strategy = PrecisionTradingStrategy(config)
    return strategy
