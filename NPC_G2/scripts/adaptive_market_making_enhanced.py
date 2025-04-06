#!/usr/bin/env python3

"""
Enhanced Adaptive Market Making Strategy

This script implements an advanced market making strategy that adapts to market conditions
using multiple technical indicators and a modular architecture for maximum flexibility.
The strategy is designed to be fully compatible with the latest Hummingbot framework.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Union, Any
import numpy as np
import pandas as pd
import pandas_ta as ta
from pykalman import KalmanFilter
import time
import logging

# Hummingbot imports
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase
from pydantic import Field, validator
from hummingbot.client.settings import ClientFieldData
from hummingbot.core.utils.async_utils import safe_ensure_future


class AdaptiveMarketMakingConfig(StrategyV2ConfigBase):
    """Configuration parameters for Adaptive Market Making strategy"""
    
    # Market parameters
    markets: Dict[str, Set[str]] = Field(
        default={"binance_perpetual": {"BTC-USDT"}},
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter markets in format 'exchange1.tp1,tp2:exchange2.tp1,tp2':"
        )
    )
    
    # Candle configuration for technical indicators
    candles_config: List[CandlesConfig] = Field(
        default=[
            CandlesConfig(connector="binance_perpetual", trading_pair="BTC-USDT", interval="1m", max_records=500),
            CandlesConfig(connector="binance_perpetual", trading_pair="BTC-USDT", interval="5m", max_records=500)
        ],
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter candle configs in format 'exchange1.tp1.interval1.max_records:exchange2.tp2.interval2.max_records':"
        )
    )
    
    # Market making parameters
    bid_spread: Decimal = Field(
        default=Decimal("0.002"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the bid spread (default is 0.002 or 0.2%):"
        )
    )
    
    ask_spread: Decimal = Field(
        default=Decimal("0.002"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the ask spread (default is 0.002 or 0.2%):"
        )
    )
    
    order_amount: Decimal = Field(
        default=Decimal("0.01"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the order amount in base asset:"
        )
    )
    
    order_refresh_time: float = Field(
        default=30.0,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the order refresh time in seconds:"
        )
    )
    
    # Kalman filter parameters
    kalman_process_variance: float = Field(
        default=0.00001,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the Kalman filter process variance (default is 0.00001):"
        )
    )
    
    kalman_observation_variance: float = Field(
        default=0.001,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the Kalman filter observation variance (default is 0.001):"
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
            prompt=lambda mi: "Enter target inventory ratio (0-1, default is 0.5):"
        )
    )
    
    stop_loss_pct: Decimal = Field(
        default=Decimal("0.02"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter stop loss percentage (default is 0.02 or 2%):"
        )
    )
    
    take_profit_pct: Decimal = Field(
        default=Decimal("0.03"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter take profit percentage (default is 0.03 or 3%):"
        )
    )
    
    # Indicator weights
    bb_weight: Decimal = Field(
        default=Decimal("0.3"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter Bollinger Bands indicator weight (0-1):"
        )
    )
    
    rsi_weight: Decimal = Field(
        default=Decimal("0.2"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter RSI indicator weight (0-1):"
        )
    )
    
    ema_weight: Decimal = Field(
        default=Decimal("0.3"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter EMA indicator weight (0-1):"
        )
    )
    
    vwap_weight: Decimal = Field(
        default=Decimal("0.2"),
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter VWAP indicator weight (0-1):"
        )
    )
    
    # Validate indicator weights sum to 1
    @validator('vwap_weight')
    def check_weights_sum(cls, v, values):
        total = float(v)
        for weight in ['bb_weight', 'rsi_weight', 'ema_weight']:
            if weight in values:
                total += float(values[weight])
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"Indicator weights must sum to 1.0 (current sum: {total})")
        return v


class AdaptiveMarketMaking(DirectionalStrategyBase):
    """
    Enhanced Adaptive Market Making Strategy
    
    This strategy combines multiple technical indicators including Kalman-enhanced
    Bollinger Bands to create a dynamic market making strategy that adapts to
    changing market conditions.
    """
    
    def __init__(self, config: AdaptiveMarketMakingConfig):
        """Initialize the strategy with configuration"""
        super().__init__(config)
        self.config = config
        
        # Initialize strategy state
        self._last_tick_timestamp = 0
        self._active_orders = {}
        self._market_regime = {"regime": "unknown", "confidence": 0.0}
        self._total_score = 0.0
        self._kalman_filters = {}
        
        # Initialize candles
        self._candles = [CandlesFactory.get_candle(c) for c in config.candles_config]
        for candle in self._candles:
            candle.start()
        
        # Data structures for indicator values
        self._indicators = {}
        self._last_calculated_timestamp = 0
        
        # Market regimes
        self.REGIME_RANGING = "ranging"
        self.REGIME_TRENDING = "trending"
        self.REGIME_VOLATILE = "volatile"
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger().info("Adaptive Market Making Strategy Initialized")
    
    def on_tick(self):
        """
        Main strategy logic executed on each tick
        """
        current_tick = time.time()
        
        # Only process if enough time has passed since last tick
        if current_tick - self._last_tick_timestamp < self.config.order_refresh_time:
            return
            
        self._last_tick_timestamp = current_tick
        
        # Check if we need to recalculate indicators (every minute)
        if current_tick - self._last_calculated_timestamp > 60:
            self._calculate_indicators()
            self._last_calculated_timestamp = current_tick
            
        # Detect market regime
        self._detect_market_regime()
        
        # Generate signal score
        self._generate_signal_score()
        
        # Cancel existing orders if needed
        self._cancel_active_orders()
        
        # Create new orders
        self._create_orders()
        
        # Log status
        self.logger().info(f"Market regime: {self._market_regime['regime']} (confidence: {self._market_regime['confidence']:.2f})")
        self.logger().info(f"Signal score: {self._total_score:.2f}")
    
    def _calculate_indicators(self):
        """Calculate all technical indicators"""
        for candle_config in self._candles:
            interval = candle_config.interval
            try:
                # Skip if we don't have enough data
                if candle_config.candles is None or len(candle_config.candles) < 30:
                    self.logger().info(f"Not enough candle data for {interval} timeframe")
                    continue

                # Get price data
                candles_df = candle_config.candles
                
                # Ensure data is numeric and contains no invalid values
                numeric_columns = ['open', 'high', 'low', 'close', 'volume']
                for col in numeric_columns:
                    if col in candles_df.columns:
                        # Replace any non-numeric values with NaN and then forward fill
                        candles_df[col] = pd.to_numeric(candles_df[col], errors='coerce')
                        candles_df[col] = candles_df[col].fillna(method='ffill')
                
                # Create indicators dictionary for this timeframe if it doesn't exist
                if interval not in self._indicators:
                    self._indicators[interval] = {}
                
                # Store latest close price
                self._indicators[interval]['close'] = float(candles_df['close'].iloc[-1])
                
                # Calculate Kalman filter on close prices with error handling
                try:
                    kf = KalmanFilter(
                        transition_matrices=[1],
                        observation_matrices=[1],
                        initial_state_mean=float(candles_df['close'].iloc[0]),
                        initial_state_covariance=[1],
                        observation_covariance=[float(self.config.kalman_observation_variance)],
                        transition_covariance=[float(self.config.kalman_process_variance)]
                    )
                    
                    # Convert data to properly formatted numpy array
                    close_prices = pd.to_numeric(candles_df['close'], errors='coerce').fillna(method='ffill').values
                    
                    # Get Kalman filtered prices
                    state_means, _ = kf.filter(close_prices)
                    self._indicators[interval]['kalman_price'] = float(state_means[-1][0])
                except Exception as e:
                    self.logger().error(f"Error calculating Kalman filter: {e}")
                    self._indicators[interval]['kalman_price'] = float(candles_df['close'].iloc[-1])
                
                # Calculate various technical indicators using pandas_ta
                try:
                    # RSI
                    rsi = ta.rsi(candles_df['close'], length=14)
                    # BB
                    bbands = ta.bbands(candles_df['close'], length=20, std=2.0)
                    # EMA
                    ema_short = ta.ema(candles_df['close'], length=12)
                    ema_long = ta.ema(candles_df['close'], length=26)
                    # VWAP
                    vwap = ta.vwap(candles_df['high'], candles_df['low'], candles_df['close'], candles_df['volume'])
                    
                    # Merge all indicators to the indicators dict
                    for indicator_df in [rsi, bbands, ema_short, ema_long, vwap]:
                        if indicator_df is not None and not indicator_df.empty:
                            for col in indicator_df.columns:
                                self._indicators[interval][col] = float(indicator_df[col].iloc[-1])
                    
                    # Calculate BB position (where price is within the bands, 0 to 1)
                    if 'BBU_20_2.0' in self._indicators[interval] and 'BBL_20_2.0' in self._indicators[interval]:
                        bb_upper = self._indicators[interval]['BBU_20_2.0']
                        bb_lower = self._indicators[interval]['BBL_20_2.0']
                        close = self._indicators[interval]['close']
                        
                        # Calculate where the close price is within the bands (0 = at lower band, 1 = at upper band)
                        bb_range = bb_upper - bb_lower
                        if bb_range > 0:
                            self._indicators[interval]['bb_pos'] = (close - bb_lower) / bb_range
                        else:
                            self._indicators[interval]['bb_pos'] = 0.5
                    
                    # Calculate EMA signal (-1 to 1 based on crossovers)
                    if 'EMA_12' in self._indicators[interval] and 'EMA_26' in self._indicators[interval]:
                        ema_short_val = self._indicators[interval]['EMA_12']
                        ema_long_val = self._indicators[interval]['EMA_26']
                        
                        # Normalized difference between short and long EMAs
                        ema_diff = (ema_short_val - ema_long_val) / ema_long_val
                        self._indicators[interval]['ema_signal'] = min(max(ema_diff * 10, -1), 1)  # Scale and clamp
                except Exception as e:
                    self.logger().error(f"Error calculating technical indicators: {e}")
            
            except Exception as e:
                self.logger().error(f"Error in _calculate_indicators for {interval}: {e}")
                continue
    
    def _detect_market_regime(self):
        """Detect the current market regime"""
        if not self._indicators:
            self._market_regime = {"regime": "unknown", "confidence": 0.0}
            return
            
        # Use the shorter timeframe for regime detection
        short_interval = self._candles[0].interval
        
        if short_interval not in self._indicators:
            self._market_regime = {"regime": "unknown", "confidence": 0.0}
            return
            
        indicators = self._indicators[short_interval]
        
        # Calculate Bollinger Bandwidth
        bb_bandwidth = (indicators['BBU_20_2.0'] - indicators['BBL_20_2.0']) / indicators['BBM_20_2.0']
        
        # Calculate RSI trend
        rsi = indicators['RSI_14']
        
        # Calculate price deviation from EMA
        ema_deviation = abs(indicators['ema_signal'])
        
        # Decision logic for market regime
        if bb_bandwidth > 0.05:  # High bandwidth suggests volatility
            confidence = min(1.0, bb_bandwidth * 10)
            regime = self.REGIME_VOLATILE
        elif ema_deviation > 0.5:  # Strong EMA signal suggests trending
            confidence = min(1.0, ema_deviation)
            regime = self.REGIME_TRENDING
        else:  # Default to ranging
            confidence = min(1.0, 1 - ema_deviation)
            regime = self.REGIME_RANGING
            
        self._market_regime = {"regime": regime, "confidence": confidence}
    
    def _generate_signal_score(self):
        """Generate overall signal score (-1 to 1)"""
        if not self._indicators:
            self._total_score = 0.0
            return
            
        # Default weights for each timeframe
        timeframe_weights = {
            "1m": 0.7,
            "5m": 0.3
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for candle in self._candles:
            if candle.interval not in self._indicators:
                continue
                
            interval_weight = timeframe_weights.get(candle.interval, 0.1)
            indicators = self._indicators[candle.interval]
            
            # Calculate weighted score for this timeframe
            bb_score = (indicators['bb_pos'] - 0.5) * 2  # -1 to 1
            rsi_score = indicators['rsi_normalized']
            ema_score = indicators['ema_signal']
            vwap_score = indicators['vwap_signal']
            
            # Apply indicator weights from config
            timeframe_score = (
                float(self.config.bb_weight) * bb_score +
                float(self.config.rsi_weight) * rsi_score +
                float(self.config.ema_weight) * ema_score +
                float(self.config.vwap_weight) * vwap_score
            )
            
            # Adjust score based on market regime
            if self._market_regime["regime"] == self.REGIME_RANGING:
                # In ranging markets, enhance mean reversion signals
                timeframe_score = -1 * bb_score * 0.8 + timeframe_score * 0.2
            elif self._market_regime["regime"] == self.REGIME_TRENDING:
                # In trending markets, enhance trend following signals
                timeframe_score = ema_score * 0.8 + timeframe_score * 0.2
            elif self._market_regime["regime"] == self.REGIME_VOLATILE:
                # In volatile markets, reduce signal strength
                timeframe_score = timeframe_score * 0.5
                
            # Add to total
            total_score += timeframe_score * interval_weight
            total_weight += interval_weight
            
        # Normalize final score to -1 to 1 range
        if total_weight > 0:
            self._total_score = total_score / total_weight
        else:
            self._total_score = 0.0
    
    def _cancel_active_orders(self):
        """Cancel all active orders"""
        for connector_name, connector in self.connectors.items():
            for trading_pair in self.config.markets.get(connector_name, set()):
                open_orders = self.get_active_orders(connector_name, trading_pair)
                for order in open_orders:
                    safe_ensure_future(connector.cancel(trading_pair, order.client_order_id))
                    self.logger().info(f"Cancelling order {order.client_order_id}")
        
        # Clear active orders dictionary
        self._active_orders = {}
    
    def _create_orders(self):
        """Create new orders based on signal and market regime"""
        for connector_name, connector in self.connectors.items():
            for trading_pair in self.config.markets.get(connector_name, set()):
                # Get reference price
                price = self._get_mid_price(connector, trading_pair)
                if price is None:
                    continue
                    
                # Adjust spreads based on signal score and market regime
                bid_spread = float(self.config.bid_spread)
                ask_spread = float(self.config.ask_spread)
                
                # Adjust spread based on market regime
                regime_multiplier = 1.0
                if self._market_regime["regime"] == self.REGIME_VOLATILE:
                    regime_multiplier = 2.0  # Widen spreads in volatile markets
                elif self._market_regime["regime"] == self.REGIME_RANGING:
                    regime_multiplier = 0.8  # Tighten spreads in ranging markets
                    
                # Adjust spread based on signal score
                signal_adjustment = abs(self._total_score) * 0.5
                
                # Final spread calculation
                bid_spread = bid_spread * regime_multiplier * (1 + signal_adjustment)
                ask_spread = ask_spread * regime_multiplier * (1 + signal_adjustment)
                
                # Calculate bid and ask prices
                bid_price = price * Decimal(1 - bid_spread)
                ask_price = price * Decimal(1 + ask_spread)
                
                # Get order size
                base_order_size = self.config.order_amount
                
                # Adjust order size based on inventory ratio
                if self._total_score > 0:  # Bullish signal
                    bid_size = base_order_size * Decimal(1 + abs(self._total_score))
                    ask_size = base_order_size * Decimal(1 - abs(self._total_score) * 0.5)
                else:  # Bearish signal
                    bid_size = base_order_size * Decimal(1 - abs(self._total_score) * 0.5)
                    ask_size = base_order_size * Decimal(1 + abs(self._total_score))
                
                # Create bid order if size is sufficient
                if bid_size > connector.get_order_size_quantum(trading_pair, bid_size):
                    order_id = safe_ensure_future(
                        connector.buy(trading_pair, bid_size, OrderType.LIMIT, bid_price)
                    )
                    self._active_orders[order_id] = {
                        "type": "bid",
                        "price": bid_price,
                        "amount": bid_size,
                        "created_at": time.time()
                    }
                    self.logger().info(f"Creating bid order: {bid_size} @ {bid_price}")
                
                # Create ask order if size is sufficient
                if ask_size > connector.get_order_size_quantum(trading_pair, ask_size):
                    order_id = safe_ensure_future(
                        connector.sell(trading_pair, ask_size, OrderType.LIMIT, ask_price)
                    )
                    self._active_orders[order_id] = {
                        "type": "ask",
                        "price": ask_price,
                        "amount": ask_size,
                        "created_at": time.time()
                    }
                    self.logger().info(f"Creating ask order: {ask_size} @ {ask_price}")
    
    def _get_mid_price(self, connector: ConnectorBase, trading_pair: str) -> Optional[Decimal]:
        """Get mid price from orderbook"""
        orderbook = connector.get_order_book(trading_pair)
        if orderbook.get_price_for_volume(True, 0.1).result_price is None or orderbook.get_price_for_volume(False, 0.1).result_price is None:
            return None
        bid_price = orderbook.get_price_for_volume(True, 0.1).result_price
        ask_price = orderbook.get_price_for_volume(False, 0.1).result_price
        return (bid_price + ask_price) / Decimal(2)
    
    def format_status(self) -> str:
        """
        Returns a status string formatted to be displayed in the Hummingbot CLI.
        """
        if not self.ready_to_trade:
            return "Strategy not ready to trade."
            
        lines = []
        lines.append("Adaptive Market Making Strategy")
        
        # Market conditions
        lines.append(f"\nMarket Regime: {self._market_regime['regime']} "
                     f"(Confidence: {self._market_regime['confidence']:.2f})")
        lines.append(f"Signal Score: {self._total_score:.2f}")
        
        # Active orders
        lines.append("\nActive Orders:")
        if not self._active_orders:
            lines.append("  No active orders")
        else:
            for order_id, order_data in self._active_orders.items():
                order_age = time.time() - order_data["created_at"]
                lines.append(f"  {order_data['type'].upper()}: {order_data['amount']} @ {order_data['price']} "
                            f"(age: {order_age:.1f}s)")
        
        # Technical indicators (from shortest timeframe)
        if self._indicators and self._candles and len(self._candles) > 0:
            short_interval = self._candles[0].interval
            if short_interval in self._indicators:
                ind = self._indicators[short_interval]
                lines.append("\nKey Indicators:")
                lines.append(f"  RSI: {ind.get('RSI_14', 0):.2f}")
                lines.append(f"  BB Width: {(ind.get('BBU_20_2.0', 0) - ind.get('BBL_20_2.0', 0)) / ind.get('BBM_20_2.0', 1):.4f}")
                lines.append(f"  BB Position: {ind.get('bb_pos', 0):.2f}")
                lines.append(f"  EMA Signal: {ind.get('ema_signal', 0):.2f}")
        
        return "\n".join(lines)
    
    def get_signal(self) -> int:
        """
        Gets the trading signal (-1, 0, 1) for DirectionalStrategyBase compatibility.
        Returns:
            int: -1 for sell, 0 for neutral, 1 for buy
        """
        if not hasattr(self, '_total_score'):
            return 0
            
        if self._total_score > 0.3:
            return 1
        elif self._total_score < -0.3:
            return -1
        else:
            return 0
    
    def market_data_extra_info(self) -> List[str]:
        """
        Provides additional market data for display.
        Returns:
            List[str]: Formatted strings with market data.
        """
        lines = []
        
        # Add indicators from each timeframe
        for candle in self._candles:
            if candle.interval in self._indicators:
                ind = self._indicators[candle.interval]
                lines.append(f"Timeframe: {candle.interval}")
                lines.append(f"  Close: {ind.get('close', 0):.2f}")
                lines.append(f"  Kalman Price: {ind.get('kalman_price', 0):.2f}")
                lines.append(f"  RSI: {ind.get('RSI_14', 0):.2f}")
                lines.append(f"  BB Upper: {ind.get('BBU_20_2.0', 0):.2f}")
                lines.append(f"  BB Middle: {ind.get('BBM_20_2.0', 0):.2f}")
                lines.append(f"  BB Lower: {ind.get('BBL_20_2.0', 0):.2f}")
                lines.append(f"  VWAP: {ind.get('VWAP_D', 0):.2f}")
                lines.append("")
        
        return lines


# Create strategy instance
def start(config: AdaptiveMarketMakingConfig):
    strategy = AdaptiveMarketMaking(config)
    return strategy
