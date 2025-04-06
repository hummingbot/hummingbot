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
from typing import Dict, List, Optional, Tuple, Any

# Hummingbot imports
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType, PriceType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
import yaml

# Try to import pandas_ta for technical analysis
try:
    import pandas_ta as ta
except ImportError:
    logging.warning("pandas_ta not installed. Installing it is recommended: pip install pandas_ta")

class PrecisionTradingStrategy(ScriptStrategyBase):
    """
    Advanced Market Making Strategy with Adaptive Parameters
    
    This strategy incorporates:
    - Volatility indicators for dynamic spread adjustment
    - Trend analysis for directional bias
    - Market regime detection for optimal parameter selection
    - Inventory management for risk control
    - Multi-timeframe analysis for better market understanding
    """
    
    # Default values (will be overridden by config)
    exchange = "binance_paper_trade"
    trading_pair = "BTC-USDT"
    order_refresh_time = 30.0  # seconds
    order_amount = Decimal("0.01")
    min_spread = Decimal("0.002")
    max_spread = Decimal("0.02")
    target_inventory_ratio = Decimal("0.5")
    risk_profile = "moderate"
    
    # Technical parameters
    short_window = 20
    long_window = 50
    rsi_length = 14
    bb_length = 20
    atr_length = 14
    
    # Markets config
    markets = {}
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        """Initialize the strategy"""
        super().__init__(connectors)
        
        # Load configuration
        self.load_config()
        
        # Set up markets
        self.markets = {self.exchange: {self.trading_pair}}
        
        # Initialize data structures
        self._last_order_refresh_timestamp = 0
        self._create_timestamp = 0
        self._candles = {}
        self._indicators = {}
        self._market_regime = {"regime": "ranging", "confidence": 0.0}
        self._total_score = 0.0
        
        # Start candle feeds
        self._initialize_candles()
        
        # Logger setup
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("Precision Trading Strategy initialized")
    
    def load_config(self):
        """Load configuration from config file"""
        try:
            with open("config/strategy_config.yaml", 'r') as file:
                config = yaml.safe_load(file)
                
                # Market parameters
                self.exchange = config.get("exchange", self.exchange)
                self.trading_pair = config.get("trading_pair", self.trading_pair)
                self.order_refresh_time = float(config.get("order_refresh_time", self.order_refresh_time))
                
                # Order parameters
                self.order_amount = Decimal(str(config.get("order_amount", self.order_amount)))
                self.min_spread = Decimal(str(config.get("min_spread", self.min_spread)))
                self.max_spread = Decimal(str(config.get("max_spread", self.max_spread)))
                
                # Technical parameters
                self.short_window = int(config.get("short_window", self.short_window))
                self.long_window = int(config.get("long_window", self.long_window))
                self.rsi_length = int(config.get("rsi_length", self.rsi_length))
                self.bb_length = int(config.get("bb_length", self.bb_length))
                self.atr_length = int(config.get("atr_length", self.atr_length))
                
                # Risk parameters
                self.risk_profile = config.get("risk_profile", self.risk_profile)
                self.target_inventory_ratio = Decimal(str(config.get("target_inventory_ratio", self.target_inventory_ratio)))
                
                # Candle intervals
                self.candle_intervals = config.get("candle_intervals", ["1m", "5m", "15m", "1h"])
                self.max_records = int(config.get("max_records", 100))
                
                # Load indicator weights
                self._indicator_weights = config.get("indicator_weights", {
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
                })
                
                # Load timeframe weights
                self._timeframe_weights = config.get("timeframe_weights", {
                    '1m': 0.15,
                    '5m': 0.25,
                    '15m': 0.35,
                    '1h': 0.25
                })
                
                self.logger.info(f"Configuration loaded from strategy_config.yaml")
                
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.logger.info("Using default configuration values")
    
    def _initialize_candles(self):
        """Initialize candle factories for each timeframe"""
        try:
            for interval in self.candle_intervals:
                candles_config = CandlesConfig(
                    connector=self.exchange,
                    trading_pair=self.trading_pair,
                    interval=interval,
                    max_records=self.max_records
                )
                candle_factory = CandlesFactory.get_candle(candles_config)
                self._candles[interval] = candle_factory
                candle_factory.start()
                self.logger.info(f"Started candles for {interval} timeframe")
                
        except Exception as e:
            self.logger.error(f"Error initializing candles: {e}")
    
    def on_stop(self):
        """Stop candles when strategy stops"""
        try:
            for interval, candle in self._candles.items():
                candle.stop()
                self.logger.info(f"Stopped candles for {interval} timeframe")
        except Exception as e:
            self.logger.error(f"Error stopping candles: {e}")
    
    def on_tick(self):
        """Main strategy logic executed on each tick"""
        try:
            current_time = self.current_timestamp
            
            # Check if it's time to refresh orders
            if self._create_timestamp <= current_time:
                self.logger.info("Running strategy tick logic")
                
                # Cancel existing orders
                self.cancel_all_orders()
                
                # Update market data and indicators
                self._update_market_data()
                
                # Detect market regime
                self._detect_market_regime()
                
                # Generate signal score
                self._generate_signal_score()
                
                # Create and place orders
                proposal = self._create_orders()
                proposal_adjusted = self.adjust_proposal_to_budget(proposal)
                self.place_orders(proposal_adjusted)
                
                # Update timestamp for next refresh
                self._create_timestamp = current_time + self.order_refresh_time
                
        except Exception as e:
            self.logger.error(f"Error in on_tick: {e}")
    
    def _update_market_data(self):
        """Update market data and calculate indicators for all timeframes"""
        try:
            for interval, candle in self._candles.items():
                df = candle.candles_df
                if df is not None and not df.empty:
                    self._indicators[interval] = self._calculate_indicators_for_timeframe(interval, df)
                    self.logger.debug(f"Updated indicators for {interval} timeframe")
                else:
                    self.logger.warning(f"No data available for {interval} timeframe")
        except Exception as e:
            self.logger.error(f"Error updating market data: {e}")
    
    def _calculate_indicators_for_timeframe(self, interval, df):
        """Calculate technical indicators for a specific timeframe"""
        try:
            # Create a copy to avoid modifying the original dataframe
            df = df.copy()
            
            # RSI
            df.ta.rsi(length=self.rsi_length, append=True)
            
            # MACD
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            
            # Bollinger Bands
            df.ta.bbands(length=self.bb_length, std=2, append=True)
            
            # EMAs
            df.ta.ema(length=9, append=True)
            df.ta.ema(length=21, append=True)
            df.ta.ema(length=50, append=True)
            df.ta.ema(length=200, append=True)
            
            # ATR for volatility
            df.ta.atr(length=self.atr_length, append=True)
            
            # Volume indicators
            if 'volume' in df.columns:
                df.ta.vwap(append=True)
                df['volume_sma'] = df['volume'].rolling(window=20).mean()
                df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            return df
    
    def _detect_market_regime(self):
        """Detect the current market regime based on indicators"""
        try:
            # Use the 15-minute timeframe for regime detection
            timeframe = "15m"
            if timeframe not in self._indicators:
                self.logger.warning(f"No data for {timeframe} timeframe, using default regime")
                return
                
            df = self._indicators[timeframe]
            if df is None or df.empty:
                self.logger.warning(f"Empty dataframe for {timeframe}, using default regime")
                return
                
            # Volatility analysis using ATR
            atr_col = f"ATR_{self.atr_length}"
            if atr_col in df.columns:
                current_atr = df[atr_col].iloc[-1]
                avg_atr = df[atr_col].iloc[-20:].mean()
                volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
            else:
                volatility_ratio = 1.0
                
            # Trend analysis using EMAs
            ema9_col = f"EMA_9"
            ema50_col = f"EMA_50"
            if ema9_col in df.columns and ema50_col in df.columns:
                ema9 = df[ema9_col].iloc[-1]
                ema50 = df[ema50_col].iloc[-1]
                ema_ratio = abs(ema9 - ema50) / ema50 if ema50 > 0 else 0
            else:
                ema_ratio = 0
                
            # RSI for range detection
            rsi_col = f"RSI_{self.rsi_length}"
            if rsi_col in df.columns:
                rsi_values = df[rsi_col].iloc[-20:].values
                rsi_range = np.max(rsi_values) - np.min(rsi_values)
            else:
                rsi_range = 30  # Default middle value
                
            # Determine regime based on indicators
            if volatility_ratio > 1.5:
                regime = "volatile"
                confidence = min(1.0, (volatility_ratio - 1.5) * 2)
            elif ema_ratio > 0.02 and rsi_range < 40:
                regime = "trending"
                confidence = min(1.0, ema_ratio * 50)
            else:
                regime = "ranging"
                confidence = min(1.0, (50 - rsi_range) / 30)
                
            self._market_regime = {
                "regime": regime,
                "confidence": confidence
            }
            
            self.logger.info(f"Market regime: {regime} (confidence: {confidence:.2f})")
            
        except Exception as e:
            self.logger.error(f"Error detecting market regime: {e}")
            self._market_regime = {"regime": "ranging", "confidence": 0.0}
    
    def _generate_signal_score(self):
        """Generate a weighted signal score based on indicators and market regime"""
        try:
            total_score = 0
            total_weight = 0
            regime = self._market_regime["regime"]
            
            # Get weights for the current market regime
            indicator_weights = self._indicator_weights.get(regime, self._indicator_weights["ranging"])
            
            # Process each timeframe
            for interval, weight in self._timeframe_weights.items():
                if interval not in self._indicators:
                    continue
                    
                df = self._indicators[interval]
                if df is None or df.empty:
                    continue
                
                timeframe_score = 0
                
                # RSI Analysis
                rsi_col = f"RSI_{self.rsi_length}"
                if rsi_col in df.columns:
                    rsi = df[rsi_col].iloc[-1]
                    # RSI signals: 
                    # - Below 30: Strong buy (1.0)
                    # - 30-45: Moderate buy (0.5)
                    # - 45-55: Neutral (0)
                    # - 55-70: Moderate sell (-0.5)
                    # - Above 70: Strong sell (-1.0)
                    if rsi < 30:
                        rsi_score = 1.0
                    elif rsi < 45:
                        rsi_score = 0.5
                    elif rsi < 55:
                        rsi_score = 0
                    elif rsi < 70:
                        rsi_score = -0.5
                    else:
                        rsi_score = -1.0
                    
                    timeframe_score += rsi_score * indicator_weights.get("RSI", 0.15)
                
                # MACD Analysis
                if "MACD_12_26_9" in df.columns and "MACDs_12_26_9" in df.columns:
                    macd = df["MACD_12_26_9"].iloc[-1]
                    macd_signal = df["MACDs_12_26_9"].iloc[-1]
                    
                    # MACD signals:
                    # - MACD > Signal and both positive: Strong buy (1.0)
                    # - MACD > Signal but one/both negative: Moderate buy (0.5)
                    # - MACD < Signal but one/both positive: Moderate sell (-0.5)
                    # - MACD < Signal and both negative: Strong sell (-1.0)
                    if macd > macd_signal:
                        if macd > 0 and macd_signal > 0:
                            macd_score = 1.0
                        else:
                            macd_score = 0.5
                    else:
                        if macd < 0 and macd_signal < 0:
                            macd_score = -1.0
                        else:
                            macd_score = -0.5
                    
                    timeframe_score += macd_score * indicator_weights.get("MACD", 0.25)
                
                # EMA Analysis
                ema9_col = "EMA_9"
                ema21_col = "EMA_21"
                ema50_col = "EMA_50"
                
                if ema9_col in df.columns and ema21_col in df.columns and ema50_col in df.columns:
                    ema9 = df[ema9_col].iloc[-1]
                    ema21 = df[ema21_col].iloc[-1]
                    ema50 = df[ema50_col].iloc[-1]
                    
                    # EMA signals based on alignment:
                    # - ema9 > ema21 > ema50: Strong uptrend (1.0)
                    # - ema9 > ema21 but ema21 < ema50: Potential reversal up (0.5)
                    # - ema9 < ema21 but ema21 > ema50: Potential reversal down (-0.5)
                    # - ema9 < ema21 < ema50: Strong downtrend (-1.0)
                    if ema9 > ema21:
                        if ema21 > ema50:
                            ema_score = 1.0
                        else:
                            ema_score = 0.5
                    else:
                        if ema21 > ema50:
                            ema_score = -0.5
                        else:
                            ema_score = -1.0
                    
                    timeframe_score += ema_score * indicator_weights.get("EMA", 0.20)
                
                # Bollinger Bands Analysis
                bb_mid = f"BBM_{self.bb_length}_2.0"
                bb_upper = f"BBU_{self.bb_length}_2.0"
                bb_lower = f"BBL_{self.bb_length}_2.0"
                
                if bb_mid in df.columns and bb_upper in df.columns and bb_lower in df.columns:
                    close = df["close"].iloc[-1]
                    bb_mid_val = df[bb_mid].iloc[-1]
                    bb_upper_val = df[bb_upper].iloc[-1]
                    bb_lower_val = df[bb_lower].iloc[-1]
                    
                    # Position relative to Bollinger Bands:
                    # - Close near lower band: Buy signal (range: 0.5 to 1.0)
                    # - Close near upper band: Sell signal (range: -0.5 to -1.0)
                    # - Close near middle band: Neutral (range: -0.25 to 0.25)
                    bb_width = bb_upper_val - bb_lower_val
                    if bb_width > 0:
                        # Normalize position within the bands
                        pos = (close - bb_lower_val) / bb_width
                        
                        if pos <= 0.2:
                            bb_score = 1.0 - pos
                        elif pos >= 0.8:
                            bb_score = -1.0 + (1.0 - pos)
                        else:
                            # Closer to middle band - neutral to slight bias
                            bb_score = 0.5 - pos
                    else:
                        bb_score = 0
                    
                    timeframe_score += bb_score * indicator_weights.get("BB", 0.15)
                
                # Aggregate the timeframe score
                total_score += timeframe_score * weight
                total_weight += weight
            
            # Calculate final weighted score
            self._total_score = total_score / total_weight if total_weight > 0 else 0
            
            self.logger.info(f"Generated signal score: {self._total_score:.4f}")
            
        except Exception as e:
            self.logger.error(f"Error generating signal score: {e}")
            self._total_score = 0
    
    def _create_orders(self) -> List[OrderCandidate]:
        """Create order candidates based on market analysis"""
        try:
            # Get mid price
            mid_price = self._get_mid_price(self.connectors[self.exchange], self.trading_pair)
            if mid_price is None:
                self.logger.error("Could not get mid price")
                return []
            
            # Calculate spreads adjusted by signal score
            bid_spread = self._calculate_bid_spread()
            ask_spread = self._calculate_ask_spread()
            
            # Calculate order prices
            bid_price = mid_price * (Decimal("1") - bid_spread)
            ask_price = mid_price * (Decimal("1") + ask_spread)
            
            # Adjust for minimum price increments if needed
            # bid_price = self._quantize_price(bid_price)
            # ask_price = self._quantize_price(ask_price)
            
            # Calculate order sizes based on inventory
            inventory_ratio = self._calculate_inventory_ratio()
            
            # Adjust order amounts based on inventory ratio and signal score
            order_amount_buy = self.order_amount
            order_amount_sell = self.order_amount
            
            if inventory_ratio > self.target_inventory_ratio:
                # More inventory than target, reduce buy order size
                inventory_skew = (inventory_ratio - self.target_inventory_ratio) / self.target_inventory_ratio
                order_amount_buy = self.order_amount * max(Decimal("0.1"), Decimal("1") - Decimal(str(inventory_skew)))
            elif inventory_ratio < self.target_inventory_ratio:
                # Less inventory than target, reduce sell order size
                inventory_skew = (self.target_inventory_ratio - inventory_ratio) / self.target_inventory_ratio
                order_amount_sell = self.order_amount * max(Decimal("0.1"), Decimal("1") - Decimal(str(inventory_skew)))
            
            # Further adjust based on signal score
            if self._total_score > 0:
                # Positive score indicates buy bias
                score_factor = min(Decimal("2"), Decimal("1") + Decimal(str(abs(self._total_score))))
                order_amount_buy *= score_factor
                order_amount_sell /= score_factor
            elif self._total_score < 0:
                # Negative score indicates sell bias
                score_factor = min(Decimal("2"), Decimal("1") + Decimal(str(abs(self._total_score))))
                order_amount_sell *= score_factor
                order_amount_buy /= score_factor
            
            # Create order candidates
            orders = []
            
            # Buy order
            buy_order = OrderCandidate(
                trading_pair=self.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.BUY,
                amount=order_amount_buy,
                price=bid_price
            )
            orders.append(buy_order)
            
            # Sell order
            sell_order = OrderCandidate(
                trading_pair=self.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.SELL,
                amount=order_amount_sell,
                price=ask_price
            )
            orders.append(sell_order)
            
            self.logger.info(f"Created orders - Buy: {order_amount_buy} @ {bid_price}, Sell: {order_amount_sell} @ {ask_price}")
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Error creating orders: {e}")
            return []
    
    def _calculate_bid_spread(self) -> Decimal:
        """Calculate bid spread based on market conditions"""
        try:
            # Base spread adjusted by volatility
            volatility_adjustment = self._get_volatility_adjustment()
            base_spread = self.min_spread * (Decimal("1") + volatility_adjustment)
            
            # Adjust for market regime
            regime = self._market_regime["regime"]
            confidence = Decimal(str(self._market_regime["confidence"]))
            
            if regime == "volatile":
                # Wider spreads in volatile markets
                regime_factor = Decimal("1.5") * confidence
                base_spread *= (Decimal("1") + regime_factor)
            elif regime == "ranging":
                # Slightly wider spreads in ranging markets
                regime_factor = Decimal("1.2") * confidence
                base_spread *= (Decimal("1") + regime_factor)
            
            # Adjust for signal score - tighter spreads when bullish
            signal_adjustment = max(Decimal("-0.5"), min(Decimal("0.5"), Decimal(str(self._total_score))))
            if signal_adjustment > 0:
                # Bullish signal - tighter buy spreads
                base_spread *= (Decimal("1") - signal_adjustment * Decimal("0.5"))
            else:
                # Bearish signal - wider buy spreads
                base_spread *= (Decimal("1") + abs(signal_adjustment) * Decimal("0.5"))
            
            # Ensure spread is within bounds
            final_spread = max(self.min_spread, min(self.max_spread, base_spread))
            
            return final_spread
            
        except Exception as e:
            self.logger.error(f"Error calculating bid spread: {e}")
            return self.min_spread
    
    def _calculate_ask_spread(self) -> Decimal:
        """Calculate ask spread based on market conditions"""
        try:
            # Base spread adjusted by volatility
            volatility_adjustment = self._get_volatility_adjustment()
            base_spread = self.min_spread * (Decimal("1") + volatility_adjustment)
            
            # Adjust for market regime
            regime = self._market_regime["regime"]
            confidence = Decimal(str(self._market_regime["confidence"]))
            
            if regime == "volatile":
                # Wider spreads in volatile markets
                regime_factor = Decimal("1.5") * confidence
                base_spread *= (Decimal("1") + regime_factor)
            elif regime == "ranging":
                # Slightly wider spreads in ranging markets
                regime_factor = Decimal("1.2") * confidence
                base_spread *= (Decimal("1") + regime_factor)
            
            # Adjust for signal score - tighter spreads when bearish
            signal_adjustment = max(Decimal("-0.5"), min(Decimal("0.5"), Decimal(str(self._total_score))))
            if signal_adjustment < 0:
                # Bearish signal - tighter sell spreads
                base_spread *= (Decimal("1") - abs(signal_adjustment) * Decimal("0.5"))
            else:
                # Bullish signal - wider sell spreads
                base_spread *= (Decimal("1") + signal_adjustment * Decimal("0.5"))
            
            # Ensure spread is within bounds
            final_spread = max(self.min_spread, min(self.max_spread, base_spread))
            
            return final_spread
            
        except Exception as e:
            self.logger.error(f"Error calculating ask spread: {e}")
            return self.min_spread
    
    def _get_volatility_adjustment(self) -> Decimal:
        """Calculate volatility adjustment based on ATR"""
        try:
            # Use the 5m timeframe for volatility calculation
            timeframe = "5m"
            if timeframe not in self._indicators:
                return Decimal("0")
                
            df = self._indicators[timeframe]
            if df is None or df.empty:
                return Decimal("0")
                
            # Get ATR values
            atr_col = f"ATR_{self.atr_length}"
            if atr_col not in df.columns:
                return Decimal("0")
                
            current_atr = df[atr_col].iloc[-1]
            avg_atr = df[atr_col].iloc[-20:].mean()
            
            # Calculate volatility ratio
            if avg_atr > 0:
                volatility_ratio = current_atr / avg_atr
                
                # Convert to Decimal and normalize
                volatility_adjustment = Decimal(str(volatility_ratio - 1))
                
                # Apply maximum adjustment
                return max(Decimal("-0.5"), min(Decimal("2"), volatility_adjustment))
            else:
                return Decimal("0")
                
        except Exception as e:
            self.logger.error(f"Error calculating volatility adjustment: {e}")
            return Decimal("0")
    
    def cancel_all_orders(self):
        """Cancel all active orders"""
        try:
            for order in self.get_active_orders(connector_name=self.exchange):
                self.cancel(self.exchange, order.trading_pair, order.client_order_id)
                self.logger.info(f"Canceled order {order.client_order_id}")
        except Exception as e:
            self.logger.error(f"Error canceling orders: {e}")
    
    def _calculate_inventory_ratio(self) -> Decimal:
        """Calculate the current inventory ratio"""
        try:
            connector = self.connectors[self.exchange]
            base_asset, quote_asset = self.trading_pair.split("-")
            
            # Get balances
            base_balance = connector.get_balance(base_asset)
            quote_balance = connector.get_balance(quote_asset)
            
            # Get mid price
            mid_price = self._get_mid_price(connector, self.trading_pair)
            if mid_price is None or mid_price == Decimal("0"):
                return Decimal("0.5")  # Default to neutral if can't get price
            
            # Calculate total value and ratio
            base_value = base_balance * mid_price
            total_value = base_value + quote_balance
            
            if total_value == Decimal("0"):
                return Decimal("0.5")  # Default to neutral if no balance
            
            inventory_ratio = base_value / total_value
            
            return inventory_ratio
            
        except Exception as e:
            self.logger.error(f"Error calculating inventory ratio: {e}")
            return Decimal("0.5")  # Default to neutral
    
    def _get_mid_price(self, connector: ConnectorBase, trading_pair: str) -> Optional[Decimal]:
        """Get mid price for a trading pair"""
        try:
            return connector.get_price_by_type(trading_pair, PriceType.MidPrice)
        except Exception as e:
            self.logger.error(f"Error getting mid price: {e}")
            return None
    
    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        """Adjust order proposals to account for available budget"""
        try:
            return self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
        except Exception as e:
            self.logger.error(f"Error adjusting proposal to budget: {e}")
            return []
    
    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        """Place orders from proposal"""
        try:
            for order in proposal:
                if order.order_side == TradeType.SELL:
                    self.sell(
                        connector_name=self.exchange,
                        trading_pair=order.trading_pair,
                        amount=order.amount,
                        order_type=order.order_type,
                        price=order.price
                    )
                else:
                    self.buy(
                        connector_name=self.exchange,
                        trading_pair=order.trading_pair,
                        amount=order.amount,
                        order_type=order.order_type,
                        price=order.price
                    )
                self.logger.info(f"Placed {order.order_side.name} order: {order.amount} @ {order.price}")
        except Exception as e:
            self.logger.error(f"Error placing orders: {e}")
    
    def did_fill_order(self, event: OrderFilledEvent):
        """Called when an order is filled"""
        msg = (f"{event.trade_type.name} {round(event.amount, 4)} {event.trading_pair} @ {round(event.price, 4)}")
        self.logger.info(f"Order filled: {msg}")
        self.notify_hb_app_with_timestamp(msg)
    
    def format_status(self) -> str:
        """Format status display"""
        if not self.ready_to_trade:
            return "Market connectors are not ready."
            
        lines = []
        
        # Balances section
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        
        # Orders section
        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])
        
        # Market analysis section
        lines.extend(["\n  Market Analysis:"])
        
        # Current regime and signal
        regime = self._market_regime["regime"]
        confidence = self._market_regime["confidence"]
        lines.append(f"    Regime: {regime.capitalize()} (confidence: {confidence:.2f})")
        lines.append(f"    Signal Score: {self._total_score:.4f} ({('Bullish' if self._total_score > 0 else 'Bearish') if self._total_score != 0 else 'Neutral'})")
        
        # Current spreads
        mid_price = self._get_mid_price(self.connectors[self.exchange], self.trading_pair)
        bid_spread = self._calculate_bid_spread() if mid_price else Decimal("0")
        ask_spread = self._calculate_ask_spread() if mid_price else Decimal("0")
        
        lines.append(f"    Bid Spread: {float(bid_spread) * 100:.2f}% | Ask Spread: {float(ask_spread) * 100:.2f}%")
        
        # Inventory management
        inventory_ratio = self._calculate_inventory_ratio()
        lines.append(f"    Inventory Ratio: {float(inventory_ratio) * 100:.2f}% (Target: {float(self.target_inventory_ratio) * 100:.2f}%)")
        
        # Technical indicators from 15m timeframe
        if "15m" in self._indicators and self._indicators["15m"] is not None:
            df = self._indicators["15m"]
            
            rsi_col = f"RSI_{self.rsi_length}"
            if rsi_col in df.columns:
                rsi_value = df[rsi_col].iloc[-1]
                lines.append(f"    RSI(14): {rsi_value:.2f}")
            
            atr_col = f"ATR_{self.atr_length}"
            if atr_col in df.columns:
                atr_value = df[atr_col].iloc[-1]
                avg_atr = df[atr_col].iloc[-20:].mean()
                lines.append(f"    ATR(14): {atr_value:.6f} (Ratio: {atr_value/avg_atr:.2f})")
            
            if "MACD_12_26_9" in df.columns and "MACDs_12_26_9" in df.columns:
                macd = df["MACD_12_26_9"].iloc[-1]
                macd_signal = df["MACDs_12_26_9"].iloc[-1]
                lines.append(f"    MACD: {macd:.6f} | Signal: {macd_signal:.6f}")
        
        return "\n".join(lines) 