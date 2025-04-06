#!/usr/bin/env python3
"""
Institutional Crypto Trading Framework Strategy

This strategy implements:
1. Smart Weighting System (Adaptive Points Matrix)
2. Multi-Timeframe Quantum Confirmation
3. Gamma-Ray Entry System
4. Adaptive Risk Nucleus
"""

import logging
import time
import math
import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from collections import deque

# Hummingbot imports
from hummingbot.core.data_type.candles import CandlesFactory
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class InstitutionalCryptoFramework(ScriptStrategyBase):
    """
    Implementation of the Institutional Crypto Trading Framework
    
    Features:
    - Smart Weighting System (Adaptive Points Matrix)
    - Multi-Timeframe Quantum Confirmation
    - Gamma-Ray Entry System
    - Adaptive Risk Nucleus
    - Hedge Mode Support
    """
    
    # Trading parameters
    trading_pair = "BTC-USDT"  # Trading Bitcoin instead of Ethereum
    exchange = "binance_paper_trade"  # Can be configured
    order_amount = Decimal("0.001")  # Base asset amount per order (smaller for BTC due to higher value)
    min_spread = Decimal("0.002")  # Minimum spread as 0.2%
    max_spread = Decimal("0.02")  # Maximum spread as 2%
    target_base_pct = Decimal("0.5")  # Target base asset percentage
    leverage = 20  # Using 20x leverage
    hedge_mode = True  # Enable hedge mode
    order_refresh_time = 30  # Refresh orders every 30 seconds
    
    # Risk management parameters adjusted for 20x leverage
    stop_loss_pct = Decimal("0.02")  # 2% stop loss (considering 20x leverage = 40% of position)
    take_profit_pct = Decimal("0.03")  # 3% take profit (60% gain on position)
    trailing_stop_activation_pct = Decimal("0.015")  # Activate trailing stop at 1.5% profit
    trailing_stop_trailing_delta = Decimal("0.005")  # Trail by 0.5%
    max_position_size = Decimal("0.05")  # Maximum 5% of portfolio per position due to high leverage
    max_total_positions = 2  # Maximum number of simultaneous positions in hedge mode
    
    # Slippage buffer parameters
    stop_loss_slippage_buffer = Decimal("0.005")  # 0.5% buffer for stop loss orders
    take_profit_slippage_buffer = Decimal("0.005")  # 0.5% buffer for take profit orders
    
    # Position tracking for hedge mode
    long_position = {
        "active": False,
        "entry_price": Decimal("0"),
        "size": Decimal("0"),
        "highest_price": Decimal("0"),
        "trailing_stop_active": False,
        "trailing_stop_price": Decimal("0")
    }
    short_position = {
        "active": False,
        "entry_price": Decimal("0"),
        "size": Decimal("0"),
        "lowest_price": Decimal("0"),
        "trailing_stop_active": False,
        "trailing_stop_price": Decimal("0")
    }
    
    # Cooldown between trades (in seconds)
    trade_cooldown = 60
    
    # Technical indicator parameters
    # Short timeframe (15m)
    short_candle_interval = 900  # 15 minutes in seconds
    short_window = 100  # Number of candles to fetch for short timeframe
    
    # Medium timeframe (1h)
    medium_candle_interval = 3600  # 1 hour in seconds
    medium_window = 100  # Number of candles to fetch for medium timeframe
    
    # Long timeframe (4h)
    long_candle_interval = 14400  # 4 hours in seconds
    long_window = 100  # Number of candles to fetch for long timeframe
    
    # Indicator parameters
    rsi_length = 14
    rsi_overbought = 70
    rsi_oversold = 30
    
    ema_short = 9
    ema_medium = 21
    ema_long = 50
    ema_very_long = 200
    
    bb_length = 20
    bb_std = 2.0
    
    atr_length = 14
    
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9
    
    # Markets to apply the strategy
    markets = {exchange: {trading_pair}}
    
    def __init__(self, connectors: Dict[str, Any]):
        """Initialize the strategy"""
        super().__init__(connectors)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("=========== STRATEGY INITIALIZATION START ===========")
        
        # Initialize candle factories for different timeframes
        try:
            self.logger.info(f"Initializing candles for {self.exchange} {self.trading_pair}")
            self.short_candles = self._initialize_candles(
                connector_name=self.exchange, 
                trading_pair=self.trading_pair, 
                interval=self.short_candle_interval, 
                max_records=self.short_window
            )
            
            self.medium_candles = self._initialize_candles(
                connector_name=self.exchange, 
                trading_pair=self.trading_pair, 
                interval=self.medium_candle_interval, 
                max_records=self.medium_window
            )
            
            self.long_candles = self._initialize_candles(
                connector_name=self.exchange, 
                trading_pair=self.trading_pair, 
                interval=self.long_candle_interval, 
                max_records=self.long_window
            )
            self.logger.info("Candle initialization complete")
        except Exception as e:
            self.logger.error(f"Error initializing candles: {str(e)}", exc_info=True)
        
        # Store indicator data
        self.indicators = {
            "short": {},
            "medium": {},
            "long": {}
        }
        
        # Store calculated signals
        self.signals = {
            "short": {},
            "medium": {},
            "long": {}
        }
        
        # Store weighting system scores
        self.score = {
            "total": 0,
            "components": {}
        }
        
        # Order tracking
        self.last_order_timestamp = 0
        self.create_timestamp = 0
        
        self.logger.info("Institutional Crypto Framework Strategy initialized")
    
    def _initialize_candles(self, connector_name: str, trading_pair: str, interval: int, max_records: int):
        """Initialize a candle factory for the given parameters"""
        self.logger.info(f"Creating candle factory: {connector_name}, {trading_pair}, {interval}s, {max_records} records")
        try:
            if connector_name not in self.connectors:
                self.logger.error(f"Connector {connector_name} not found in available connectors: {list(self.connectors.keys())}")
                return None
                
            connector = self.connectors[connector_name]
            if not connector.ready:
                self.logger.warning(f"Connector {connector_name} is not ready")
                
            candle = CandlesFactory.get_candle(
                connector=connector,
                trading_pair=trading_pair,
                interval=interval,
                max_records=max_records
            )
            return candle
        except Exception as e:
            self.logger.error(f"Error creating candle factory: {str(e)}", exc_info=True)
            return None
    
    def on_tick(self):
        """Main strategy logic executed on each tick"""
        try:
            current_timestamp = self.current_timestamp
            
            # Check if it's time to refresh orders
            if (current_timestamp - self.last_order_timestamp) < self.order_refresh_time:
                return
            
            # Add more detailed logging
            self.logger.info(f"On tick called at {current_timestamp}")
            
            # Check connector status
            if self.exchange not in self.connectors:
                self.logger.error(f"Connector {self.exchange} not found")
                return
                
            connector = self.connectors[self.exchange]
            if not connector.ready:
                self.logger.warning(f"Connector {self.exchange} is not ready")
                return
            
            # Update market data and indicators
            if not self._update_market_data():
                self.logger.warning("Failed to update market data")
                return
            
            # Manage any active positions
            self._manage_active_position()
            
            # Run the signal generation process
            self.logger.info("Generating trading signals")
            entry_signal = self._generate_trading_signals()
            
            if entry_signal:
                self.logger.info(f"Entry signal generated: {entry_signal}")
                self._enter_position(entry_signal)
            else:
                self.logger.info("No entry signal, running market making")
                # If no clear directional signal, run market making logic
                self._run_market_making()
            
            # Update last order timestamp
            self.last_order_timestamp = current_timestamp
        
        except Exception as e:
            self.logger.error(f"Error in on_tick: {e}", exc_info=True)
    
    def _update_market_data(self) -> bool:
        """Update candle data and calculate indicators for all timeframes"""
        try:
            self.logger.info("Updating market data for all timeframes")
            # Update candles for each timeframe
            for timeframe, candles in [
                ("short", self.short_candles),
                ("medium", self.medium_candles),
                ("long", self.long_candles)
            ]:
                if candles is None:
                    self.logger.error(f"{timeframe} candles are None")
                    return False
                    
                self.logger.info(f"Updating indicators for {timeframe} timeframe")
                if not self._update_indicators_for_timeframe(timeframe, candles):
                    self.logger.warning(f"Failed to update indicators for {timeframe} timeframe")
                    return False
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error updating market data: {e}", exc_info=True)
            return False
    
    def _update_indicators_for_timeframe(self, timeframe: str, candles) -> bool:
        """Calculate technical indicators for the specified timeframe"""
        candles.update_candles()
        
        if candles.candles_df is None or len(candles.candles_df) < self.ema_very_long:
            self.logger.info(f"Not enough data for {timeframe} timeframe")
            return False
        
        df = candles.candles_df.copy()
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=self.rsi_length).mean()
        avg_loss = loss.rolling(window=self.rsi_length).mean()
        rs = avg_gain / avg_loss.replace(0, 0.001)  # Avoid division by zero
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Calculate EMAs
        df[f'ema_{self.ema_short}'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df[f'ema_{self.ema_medium}'] = df['close'].ewm(span=self.ema_medium, adjust=False).mean()
        df[f'ema_{self.ema_long}'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        df[f'ema_{self.ema_very_long}'] = df['close'].ewm(span=self.ema_very_long, adjust=False).mean()
        
        # Calculate MACD
        ema_fast = df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=self.macd_signal, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Calculate Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=self.bb_length).mean()
        df['bb_std'] = df['close'].rolling(window=self.bb_length).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * self.bb_std)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * self.bb_std)
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.atr_length).mean()
        
        # Calculate NATR (Normalized ATR)
        df['natr'] = (df['atr'] / df['close']) * 100
        
        # Store calculated indicators
        self.indicators[timeframe] = {
            'rsi': df['rsi'].iloc[-1],
            'ema_short': df[f'ema_{self.ema_short}'].iloc[-1],
            'ema_medium': df[f'ema_{self.ema_medium}'].iloc[-1],
            'ema_long': df[f'ema_{self.ema_long}'].iloc[-1],
            'ema_very_long': df[f'ema_{self.ema_very_long}'].iloc[-1],
            'macd': df['macd'].iloc[-1],
            'macd_signal': df['macd_signal'].iloc[-1],
            'macd_hist': df['macd_hist'].iloc[-1],
            'macd_hist_prev': df['macd_hist'].iloc[-2] if len(df) > 2 else 0,
            'bb_upper': df['bb_upper'].iloc[-1],
            'bb_middle': df['bb_middle'].iloc[-1],
            'bb_lower': df['bb_lower'].iloc[-1],
            'bb_width': (df['bb_upper'].iloc[-1] - df['bb_lower'].iloc[-1]) / df['bb_middle'].iloc[-1],
            'bb_width_prev': (df['bb_upper'].iloc[-2] - df['bb_lower'].iloc[-2]) / df['bb_middle'].iloc[-2] if len(df) > 2 else 0,
            'atr': df['atr'].iloc[-1],
            'natr': df['natr'].iloc[-1],
            'close': df['close'].iloc[-1],
            'high': df['high'].iloc[-1],
            'low': df['low'].iloc[-1],
            'volume': df['volume'].iloc[-1],
            'avg_volume': df['volume'].rolling(window=20).mean().iloc[-1],
        }
        
        # Calculate support and resistance (simple method)
        highs = df['high'].rolling(window=10).max()
        lows = df['low'].rolling(window=10).min()
        self.indicators[timeframe]['support'] = lows.iloc[-1]
        self.indicators[timeframe]['resistance'] = highs.iloc[-1]
        
        # Check for volume spike
        self.indicators[timeframe]['volume_spike'] = df['volume'].iloc[-1] > (df['volume'].rolling(window=20).mean().iloc[-1] * 2)
        
        return True
    
    def _generate_trading_signals(self) -> str:
        """Generate trading signals based on the Smart Weighting System and Multi-Timeframe Confirmation"""
        # Calculate signals for each timeframe
        self._calculate_signals_by_timeframe()
        
        # Apply the Smart Weighting System
        signal_score = self._apply_smart_weighting_system()
        
        # Apply Multi-Timeframe Quantum Confirmation
        confirmed_direction = self._apply_multi_timeframe_confirmation()
        
        # Apply Gamma-Ray Entry System
        gamma_signal = self._apply_gamma_ray_entry_system(confirmed_direction)
        
        self.logger.info(f"Signal score: {signal_score:.2f}, Direction: {confirmed_direction}, Gamma signal: {gamma_signal}")
        
        return gamma_signal
    
    def _calculate_signals_by_timeframe(self):
        """Calculate basic signals for each timeframe"""
        for timeframe in ['short', 'medium', 'long']:
            ind = self.indicators[timeframe]
            signals = {}
            
            # Trend signals
            signals['is_uptrend'] = ind['ema_short'] > ind['ema_medium'] > ind['ema_long']
            signals['is_downtrend'] = ind['ema_short'] < ind['ema_medium'] < ind['ema_long']
            signals['above_long_ema'] = ind['close'] > ind['ema_very_long']
            signals['below_long_ema'] = ind['close'] < ind['ema_very_long']
            
            # RSI signals
            signals['is_overbought'] = ind['rsi'] > self.rsi_overbought
            signals['is_oversold'] = ind['rsi'] < self.rsi_oversold
            
            # MACD signals
            signals['macd_bullish_cross'] = ind['macd_hist'] > 0 and ind['macd_hist_prev'] < 0
            signals['macd_bearish_cross'] = ind['macd_hist'] < 0 and ind['macd_hist_prev'] > 0
            signals['macd_bullish'] = ind['macd'] > ind['macd_signal']
            signals['macd_bearish'] = ind['macd'] < ind['macd_signal']
            
            # Bollinger Band signals
            signals['price_above_upper_band'] = ind['close'] > ind['bb_upper']
            signals['price_below_lower_band'] = ind['close'] < ind['bb_lower']
            signals['bb_squeeze'] = ind['bb_width'] < (ind['bb_width_prev'] * 0.9)
            signals['bb_expansion'] = ind['bb_width'] > (ind['bb_width_prev'] * 1.1)
            
            # Volume signals
            signals['high_volume'] = ind['volume_spike']
            
            # Support/Resistance signals
            signals['near_support'] = abs(ind['close'] - ind['support']) / ind['close'] < 0.01
            signals['near_resistance'] = abs(ind['close'] - ind['resistance']) / ind['close'] < 0.01
            signals['broke_resistance'] = ind['close'] > ind['resistance'] and ind['high'] > ind['resistance'] * 1.005
            signals['broke_support'] = ind['close'] < ind['support'] and ind['low'] < ind['support'] * 0.995
            
            # Store signals for this timeframe
            self.signals[timeframe] = signals
    
    def _apply_smart_weighting_system(self) -> float:
        """
        Apply the Smart Weighting System to calculate a score for the current market condition
        Returns a score between 0 and 100
        """
        score = 0
        components = {}
        
        # ATR-based volatility adjustment
        volatility_level = self.indicators['medium']['natr']
        if volatility_level < 2:  # Low volatility
            volatility_regime = "low"
        elif volatility_level > 5:  # High volatility
            volatility_regime = "high"
        else:  # Medium volatility
            volatility_regime = "medium"
        
        # Adjust indicator weights based on timeframe and volatility regime
        for timeframe, base_weight in [("short", 0.6), ("medium", 0.3), ("long", 0.1)]:
            signals = self.signals[timeframe]
            ind = self.indicators[timeframe]
            tf_score = 0
            
            # RSI component (max 20 points)
            rsi_score = 0
            if signals['is_oversold'] and signals['above_long_ema']:
                # Bullish oversold condition
                rsi_score = 20
            elif signals['is_overbought'] and signals['below_long_ema']:
                # Bearish overbought condition
                rsi_score = -20
            elif 40 <= ind['rsi'] <= 60:
                # Neutral territory
                rsi_score = 0
            else:
                # Partial points based on distance from neutral
                rsi_score = (50 - ind['rsi']) / 2.5  # -20 to +20 range
            
            # Add low volatility adjustment if applicable
            if volatility_regime == "low" and abs(rsi_score) > 10:
                rsi_score *= 1.05  # 5% boost in low volatility
            
            tf_score += rsi_score
            
            # MACD component (max 25 points)
            macd_score = 0
            if signals['macd_bullish_cross']:
                macd_score = 25  # Strong bullish signal
            elif signals['macd_bearish_cross']:
                macd_score = -25  # Strong bearish signal
            elif signals['macd_bullish']:
                macd_score = 15  # Bullish momentum
            elif signals['macd_bearish']:
                macd_score = -15  # Bearish momentum
            
            # Add trend adjustment if applicable
            if (signals['is_uptrend'] and macd_score > 0) or (signals['is_downtrend'] and macd_score < 0):
                macd_score *= 1.1  # 10% boost when aligned with trend
            
            tf_score += macd_score
            
            # EMA component (max 15 points)
            ema_score = 0
            if signals['is_uptrend'] and signals['above_long_ema']:
                ema_score = 15  # Strong bullish trend
            elif signals['is_downtrend'] and signals['below_long_ema']:
                ema_score = -15  # Strong bearish trend
            elif ind['close'] > ind['ema_very_long']:
                ema_score = 8  # Above long-term average
            elif ind['close'] < ind['ema_very_long']:
                ema_score = -8  # Below long-term average
            
            # Add key level adjustment if close to EMA crossover
            if abs(ind['ema_short'] - ind['ema_long']) / ind['ema_long'] < 0.005:
                ema_score *= 1.15  # 15% boost at key levels
            
            tf_score += ema_score
            
            # Bollinger Bands component (max 15 points)
            bb_score = 0
            if signals['price_below_lower_band'] and signals['is_oversold']:
                bb_score = 15  # Strong bullish reversal signal
            elif signals['price_above_upper_band'] and signals['is_overbought']:
                bb_score = -15  # Strong bearish reversal signal
            elif signals['bb_squeeze']:
                bb_score = 5  # Potential breakout setup (direction neutral)
            
            # Add squeeze adjustment
            if signals['bb_squeeze']:
                bb_score *= 1.2  # 20% boost during squeeze
            
            tf_score += bb_score
            
            # Volume + Candle component (max 15 points)
            vol_score = 0
            if signals['high_volume']:
                if signals['is_uptrend']:
                    vol_score = 15  # Strong bullish volume
                elif signals['is_downtrend']:
                    vol_score = -15  # Strong bearish volume
                else:
                    vol_score = 5  # High volume but direction unclear
            
            # Add volume spike adjustment
            if ind['volume'] > ind['avg_volume'] * 2:
                vol_score *= 1.3  # 30% boost with 2x volume
            
            tf_score += vol_score
            
            # Support/Resistance component (max 10 points)
            sr_score = 0
            if signals['broke_resistance'] and signals['high_volume']:
                sr_score = 10  # Bullish breakout
            elif signals['broke_support'] and signals['high_volume']:
                sr_score = -10  # Bearish breakdown
            elif signals['near_support'] and signals['is_oversold']:
                sr_score = 8  # Potential bounce from support
            elif signals['near_resistance'] and signals['is_overbought']:
                sr_score = -8  # Potential rejection from resistance
            
            # Add major zone adjustment
            if signals['near_support'] or signals['near_resistance']:
                sr_score *= 1.5  # 50% boost at major zones
            
            tf_score += sr_score
            
            # Apply timeframe weight
            score += tf_score * base_weight
            
            # Store component score for logging
            components[timeframe] = tf_score
        
        # Normalize final score to 0-100 range
        normalized_score = min(max((score + 100) / 2, 0), 100)
        
        # Store score components for later reference
        self.score = {
            "total": normalized_score,
            "components": components,
            "raw_score": score
        }
        
        return normalized_score
    
    def _apply_multi_timeframe_confirmation(self) -> str:
        """
        Apply Multi-Timeframe Quantum Confirmation
        Returns "buy", "sell", or "neutral"
        """
        # Extract bullish/bearish signals from each timeframe
        short_bullish = self.signals['short']['is_uptrend'] or self.signals['short']['macd_bullish']
        short_bearish = self.signals['short']['is_downtrend'] or self.signals['short']['macd_bearish']
        
        medium_bullish = self.signals['medium']['is_uptrend'] or self.signals['medium']['macd_bullish']
        medium_bearish = self.signals['medium']['is_downtrend'] or self.signals['medium']['macd_bearish']
        
        long_bullish = self.signals['long']['is_uptrend'] or self.signals['long']['macd_bullish']
        long_bearish = self.signals['long']['is_downtrend'] or self.signals['long']['macd_bearish']
        
        # Check for alignment
        if short_bullish and medium_bullish and long_bullish:
            return "buy"  # All timeframes aligned bullish
        elif short_bearish and medium_bearish and long_bearish:
            return "sell"  # All timeframes aligned bearish
        elif medium_bullish and long_bullish:
            return "buy"  # Longer timeframes aligned bullish (more weight)
        elif medium_bearish and long_bearish:
            return "sell"  # Longer timeframes aligned bearish (more weight)
        else:
            return "neutral"  # No clear alignment
    
    def _apply_gamma_ray_entry_system(self, direction: str) -> str:
        """
        Apply the Gamma-Ray Entry System for high-quality signals
        Returns "buy", "sell", or "" (no signal)
        """
        if direction == "neutral":
            return ""
        
        total_points = 0
        
        # 1. Core Engine (60 Points)
        core_points = 0
        
        # MACD signal (20 points)
        if direction == "buy" and self.signals['medium']['macd_bullish_cross']:
            core_points += 20
        elif direction == "sell" and self.signals['medium']['macd_bearish_cross']:
            core_points += 20
        
        # EMA break with volume (25 points)
        m_ind = self.indicators['medium']
        if (direction == "buy" and 
            m_ind['close'] > m_ind['ema_long'] and 
            m_ind['volume'] > m_ind['avg_volume'] * 2):
            core_points += 25
        elif (direction == "sell" and 
              m_ind['close'] < m_ind['ema_long'] and 
              m_ind['volume'] > m_ind['avg_volume'] * 2):
            core_points += 25
        
        # RSI divergence (simplified implementation) (15 points)
        # Note: real divergence detection would be more complex
        if (direction == "buy" and 
            self.signals['medium']['is_oversold'] and 
            m_ind['close'] > m_ind['close'] * 0.98):  # Price making higher low
            core_points += 15
        elif (direction == "sell" and 
              self.signals['medium']['is_overbought'] and 
              m_ind['close'] < m_ind['close'] * 1.02):  # Price making lower high
            core_points += 15
        
        total_points += core_points
        
        # 2. Rocket Booster (30 Points)
        booster_points = 0
        
        # Bullish/Bearish candlestick cluster (simplified) (10 points)
        if direction == "buy" and m_ind['close'] > m_ind['ema_short']:
            booster_points += 10
        elif direction == "sell" and m_ind['close'] < m_ind['ema_short']:
            booster_points += 10
        
        # BBands squeeze resolution (12 points)
        if self.signals['medium']['bb_squeeze'] and self.signals['medium']['bb_expansion']:
            if direction == "buy" and m_ind['close'] > m_ind['bb_middle']:
                booster_points += 12
            elif direction == "sell" and m_ind['close'] < m_ind['bb_middle']:
                booster_points += 12
        
        # Funding rate reversal - not directly applicable in spot markets (8 points)
        # Substituting with RSI reversal
        if (direction == "buy" and 
            m_ind['rsi'] < 40 and 
            m_ind['rsi'] > self.indicators['medium']['rsi'] * 0.95):
            booster_points += 8
        elif (direction == "sell" and 
              m_ind['rsi'] > 60 and 
              m_ind['rsi'] < self.indicators['medium']['rsi'] * 1.05):
            booster_points += 8
        
        total_points += booster_points
        
        # 3. Quantum Igniter (10 Points) - simplified since we don't have all the data
        igniter_points = 5  # Base points
        
        # Check for timeframe alignment as a substitute for some metrics
        if (direction == "buy" and 
            self.signals['short']['is_uptrend'] and 
            self.signals['medium']['is_uptrend']):
            igniter_points += 5
        elif (direction == "sell" and 
              self.signals['short']['is_downtrend'] and 
              self.signals['medium']['is_downtrend']):
            igniter_points += 5
        
        total_points += igniter_points
        
        # Launch Sequence check
        if total_points >= 85:
            self.logger.info(f"Gamma-Ray Entry Signal: {direction.upper()} with {total_points} points")
            return direction
        else:
            self.logger.info(f"No Gamma-Ray Entry Signal: {total_points} points is below threshold (85)")
            return ""
    
    def _enter_position(self, signal: str):
        """Enter a new position based on the signal"""
        if signal not in ["buy", "sell"]:
            return
        
        # Get current price
        connector = self.connectors[self.exchange]
        mid_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        
        if mid_price is None:
            self.logger.error("Failed to get price for position entry")
            return
        
        # Calculate position size based on risk parameters
        position_size = self._calculate_position_size()
        
        if position_size <= 0:
            self.logger.warning("Position size is zero or negative, not entering position")
            return
        
        # Calculate stop loss and take profit levels with slippage buffer
        if signal == "buy":
            entry_price = mid_price
            stop_loss_price = entry_price * (Decimal("1") - self.stop_loss_pct - self.stop_loss_slippage_buffer)
            take_profit_price = entry_price * (Decimal("1") + self.take_profit_pct - self.take_profit_slippage_buffer)
            
            # Place market order for entry
            self.buy(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=position_size,
                order_type=OrderType.MARKET,
                price=mid_price
            )
            
            # Place stop loss order with slippage buffer
            self.sell(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=position_size,
                order_type=OrderType.STOP_LOSS,
                price=stop_loss_price
            )
            
            # Place take profit order with slippage buffer
            self.sell(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=position_size,
                order_type=OrderType.TAKE_PROFIT,
                price=take_profit_price
            )
            
            self.logger.info(f"LONG position entered at {entry_price} with size {position_size}")
            self.logger.info(f"Stop loss placed at {stop_loss_price} (including {self.stop_loss_slippage_buffer:.2%} buffer)")
            self.logger.info(f"Take profit placed at {take_profit_price} (including {self.take_profit_slippage_buffer:.2%} buffer)")
            
            self.long_position["active"] = True
            self.long_position["entry_price"] = entry_price
            self.long_position["size"] = position_size
            self.long_position["highest_price"] = entry_price
            self.long_position["trailing_stop_active"] = False
            self.long_position["trailing_stop_price"] = Decimal("0")
            
        elif signal == "sell":
            entry_price = mid_price
            stop_loss_price = entry_price * (Decimal("1") + self.stop_loss_pct + self.stop_loss_slippage_buffer)
            take_profit_price = entry_price * (Decimal("1") - self.take_profit_pct + self.take_profit_slippage_buffer)
            
            # Place market order for entry
            self.sell(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=position_size,
                order_type=OrderType.MARKET,
                price=mid_price
            )
            
            # Place stop loss order with slippage buffer
            self.buy(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=position_size,
                order_type=OrderType.STOP_LOSS,
                price=stop_loss_price
            )
            
            # Place take profit order with slippage buffer
            self.buy(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=position_size,
                order_type=OrderType.TAKE_PROFIT,
                price=take_profit_price
            )
            
            self.logger.info(f"SHORT position entered at {entry_price} with size {position_size}")
            self.logger.info(f"Stop loss placed at {stop_loss_price} (including {self.stop_loss_slippage_buffer:.2%} buffer)")
            self.logger.info(f"Take profit placed at {take_profit_price} (including {self.take_profit_slippage_buffer:.2%} buffer)")
            
            self.short_position["active"] = True
            self.short_position["entry_price"] = entry_price
            self.short_position["size"] = position_size
            self.short_position["lowest_price"] = entry_price
            self.short_position["trailing_stop_active"] = False
            self.short_position["trailing_stop_price"] = Decimal("0")
    
    def _calculate_position_size(self) -> Decimal:
        """Calculate position size based on risk parameters and available balance"""
        connector = self.connectors[self.exchange]
        
        # Get available balance
        base_balance = connector.get_available_balance(self.trading_pair.split("-")[0])
        quote_balance = connector.get_available_balance(self.trading_pair.split("-")[1])
        
        # Get current price
        mid_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        if mid_price is None:
            self.logger.error("Failed to get price for position size calculation")
            return Decimal("0")
        
        # Calculate total portfolio value in quote currency
        total_portfolio_value = (base_balance * mid_price) + quote_balance
        
        # Calculate maximum position value considering leverage
        max_position_value = (total_portfolio_value * self.max_position_size) * self.leverage
        
        # Calculate actual position size in base currency
        position_size = max_position_value / mid_price
        
        # Additional safety check for liquidation price
        # Ensure the position size won't get liquidated if price moves against stop loss
        liquidation_buffer = Decimal("1.1")  # 10% buffer above stop loss
        max_safe_position = (quote_balance * self.leverage) / (mid_price * liquidation_buffer)
        position_size = min(position_size, max_safe_position)
        
        # Ensure position size doesn't exceed available balance
        position_size = min(position_size, base_balance * self.leverage)
        
        # Round down to appropriate precision based on the trading pair
        position_size = self._round_down_position_size(position_size)
        
        self.logger.info(f"Calculated position size: {position_size} (Portfolio value: {total_portfolio_value}, Leverage: {self.leverage}x)")
        return position_size
    
    def _round_down_position_size(self, size: Decimal) -> Decimal:
        """Round down position size to appropriate precision"""
        # Note: In a real implementation, this would use exchange-specific rules
        # For this example, we'll round to 4 decimal places
        return Decimal(str(math.floor(float(size) * 10000) / 10000))
    
    def _manage_active_position(self):
        """Manage an active position with the Adaptive Risk Nucleus system"""
        connector = self.connectors[self.exchange]
        current_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        
        if current_price is None:
            self.logger.error("Failed to get price for position management")
            return
        
        # Calculate profit/loss percentage
        if self.long_position["active"]:
            pnl_pct = (current_price - self.long_position["entry_price"]) / self.long_position["entry_price"]
        elif self.short_position["active"]:
            pnl_pct = (self.short_position["entry_price"] - current_price) / self.short_position["entry_price"]
        else:
            return
        
        # Update highest/lowest price since entry for trailing stop
        if self.long_position["active"] and current_price > self.long_position["highest_price"]:
            self.long_position["highest_price"] = current_price
            # Activate trailing stop if profit exceeds threshold
            if not self.long_position["trailing_stop_active"] and pnl_pct >= self.trailing_stop_activation_pct:
                self.long_position["trailing_stop_active"] = True
                self.long_position["trailing_stop_price"] = current_price * (Decimal("1") - self.trailing_stop_trailing_delta)
                self.logger.info(f"Trailing stop activated at {self.long_position['trailing_stop_price']}")
        elif self.short_position["active"] and current_price < self.short_position["lowest_price"]:
            self.short_position["lowest_price"] = current_price
            # Activate trailing stop if profit exceeds threshold
            if not self.short_position["trailing_stop_active"] and pnl_pct >= self.trailing_stop_activation_pct:
                self.short_position["trailing_stop_active"] = True
                self.short_position["trailing_stop_price"] = current_price * (Decimal("1") + self.trailing_stop_trailing_delta)
                self.logger.info(f"Trailing stop activated at {self.short_position['trailing_stop_price']}")
        
        # If trailing stop is active, update stop price as price moves up
        elif self.long_position["active"] and self.long_position["trailing_stop_active"] and current_price > self.long_position["trailing_stop_price"] * (Decimal("1") + self.trailing_stop_trailing_delta):
            self.long_position["trailing_stop_price"] = current_price * (Decimal("1") - self.trailing_stop_trailing_delta)
            self.logger.info(f"Trailing stop updated to {self.long_position['trailing_stop_price']}")
        elif self.short_position["active"] and self.short_position["trailing_stop_active"] and current_price < self.short_position["trailing_stop_price"] * (Decimal("1") - self.trailing_stop_trailing_delta):
            self.short_position["trailing_stop_price"] = current_price * (Decimal("1") + self.trailing_stop_trailing_delta)
            self.logger.info(f"Trailing stop updated to {self.short_position['trailing_stop_price']}")
        
        # Check exit conditions
        exit_triggered = False
        exit_reason = ""
        
        # Check take profit (considering leverage)
        if pnl_pct >= self.take_profit_pct:
            exit_triggered = True
            exit_reason = f"Take profit hit at {pnl_pct:.2%} (Position gain: {(pnl_pct * self.leverage):.2%})"
        
        # Check stop loss (considering leverage)
        elif pnl_pct <= -self.stop_loss_pct:
            exit_triggered = True
            exit_reason = f"Stop loss hit at {pnl_pct:.2%} (Position loss: {(pnl_pct * self.leverage):.2%})"
        
        # Check trailing stop
        elif self.long_position["active"] and self.long_position["trailing_stop_active"] and current_price <= self.long_position["trailing_stop_price"]:
            exit_triggered = True
            exit_reason = f"Trailing stop hit at {current_price} (Trail price: {self.long_position['trailing_stop_price']})"
        elif self.short_position["active"] and self.short_position["trailing_stop_active"] and current_price >= self.short_position["trailing_stop_price"]:
            exit_triggered = True
            exit_reason = f"Trailing stop hit at {current_price} (Trail price: {self.short_position['trailing_stop_price']})"
        
        # Handle exit if triggered
        if exit_triggered:
            self._exit_position(exit_reason)
    
    def _exit_position(self, reason: str):
        """Exit the current position"""
        connector = self.connectors[self.exchange]
        current_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        
        if current_price is None:
            self.logger.error("Failed to get price for position exit")
            return
        
        # Calculate profit/loss
        if self.long_position["active"]:
            pnl_pct = (current_price - self.long_position["entry_price"]) / self.long_position["entry_price"]
            self.logger.info(f"Exiting LONG position via {reason} at {current_price}, P&L: {pnl_pct:.2%}")
            self.sell(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=self.long_position["size"],
                order_type=OrderType.MARKET,
                price=current_price
            )
            self.long_position["active"] = False
            self.long_position["entry_price"] = Decimal("0")
            self.long_position["size"] = Decimal("0")
            self.long_position["highest_price"] = Decimal("0")
            self.long_position["trailing_stop_active"] = False
            self.long_position["trailing_stop_price"] = Decimal("0")
        elif self.short_position["active"]:
            pnl_pct = (self.short_position["entry_price"] - current_price) / self.short_position["entry_price"]
            self.logger.info(f"Exiting SHORT position via {reason} at {current_price}, P&L: {pnl_pct:.2%}")
            self.buy(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                amount=self.short_position["size"],
                order_type=OrderType.MARKET,
                price=current_price
            )
            self.short_position["active"] = False
            self.short_position["entry_price"] = Decimal("0")
            self.short_position["size"] = Decimal("0")
            self.short_position["lowest_price"] = Decimal("0")
            self.short_position["trailing_stop_active"] = False
            self.short_position["trailing_stop_price"] = Decimal("0")
    
    def _run_market_making(self):
        """Run market making logic when no directional signal is present"""
        # Cancel any existing orders first
        self.cancel_all_orders()
        
        connector = self.connectors[self.exchange]
        mid_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        
        if mid_price is None:
            self.logger.warning("Unable to fetch price for market making")
            return
        
        # Calculate inventory metrics for spread adjustment
        inventory_ratio = self._calculate_inventory_ratio()
        
        # Adjust spreads based on market conditions and inventory
        buy_spread = self._calculate_buy_spread(inventory_ratio)
        sell_spread = self._calculate_sell_spread(inventory_ratio)
        
        # Calculate order prices
        buy_price = mid_price * (Decimal("1") - buy_spread)
        sell_price = mid_price * (Decimal("1") + sell_spread)
        
        # Calculate order sizes
        buy_order_size = self._calculate_buy_order_size(inventory_ratio)
        sell_order_size = self._calculate_sell_order_size(inventory_ratio)
        
        # Create order candidates
        order_candidates = []
        
        # Create buy order if we have enough quote balance
        quote_balance = connector.get_available_balance(self.trading_pair.split("-")[1])
        if quote_balance >= buy_price * buy_order_size:
            buy_order = OrderCandidate(
                trading_pair=self.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.BUY,
                amount=buy_order_size,
                price=buy_price
            )
            order_candidates.append(buy_order)
        
        # Create sell order if we have enough base balance
        base_balance = connector.get_available_balance(self.trading_pair.split("-")[0])
        if base_balance >= sell_order_size:
            sell_order = OrderCandidate(
                trading_pair=self.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.SELL,
                amount=sell_order_size,
                price=sell_price
            )
            order_candidates.append(sell_order)
        
        # Adjust orders to budget
        adjusted_candidates = connector.budget_checker.adjust_candidates(order_candidates, all_or_none=False)
        
        # Place orders
        for order in adjusted_candidates:
            if order.order_side == TradeType.BUY:
                self.buy(
                    connector_name=self.exchange,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    order_type=order.order_type,
                    price=order.price
                )
                self.logger.info(f"Placed market making BUY order for {order.amount} at {order.price}")
            else:
                self.sell(
                    connector_name=self.exchange,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    order_type=order.order_type,
                    price=order.price
                )
                self.logger.info(f"Placed market making SELL order for {order.amount} at {order.price}")
        
        # Update last order timestamp
        self.last_order_timestamp = self.current_timestamp
    
    def _calculate_inventory_ratio(self) -> float:
        """Calculate inventory ratio for spread adjustment"""
        connector = self.connectors[self.exchange]
        
        # Get balances
        base_balance = connector.get_balance(self.trading_pair.split("-")[0])
        quote_balance = connector.get_balance(self.trading_pair.split("-")[1])
        
        # Get mid price
        mid_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        if mid_price is None:
            # Default to 0.5 (neutral) if price can't be determined
            return 0.5
        
        # Convert base to quote value
        base_value = base_balance * mid_price
        
        # Calculate total value in quote terms
        total_value = base_value + quote_balance
        
        if total_value == Decimal("0"):
            # Default to 0.5 (neutral) if total value is zero
            return 0.5
        
        # Calculate ratio of base asset value to total value
        base_ratio = float(base_value / total_value)
        
        return base_ratio
    
    def _calculate_buy_spread(self, inventory_ratio: float) -> Decimal:
        """Calculate buy spread based on market conditions and inventory"""
        # Base spread calculation considering leverage
        volatility = self.indicators['medium']['natr']
        
        # Increase base spread for higher leverage
        leverage_factor = Decimal(str(math.sqrt(self.leverage) / 10))  # Square root to dampen the effect
        base_spread = Decimal(str(max(0.001, min(0.01, float(volatility) / 100)))) * (Decimal("1") + leverage_factor)
        
        # Ensure minimum spread for long positions
        min_long_spread = Decimal("0.02")  # 2% minimum spread for long positions
        
        # Adjust based on inventory ratio
        inventory_skew = float(self.target_base_pct) - inventory_ratio
        
        # If we have too much base asset, increase buy spread (less aggressive buys)
        # If we have too little base asset, decrease buy spread (more aggressive buys)
        inventory_adjustment = Decimal(str(max(-0.005, min(0.005, inventory_skew * 0.01))))
        
        # Calculate final spread
        adjusted_spread = base_spread - inventory_adjustment
        
        # Ensure spread is within allowed range
        adjusted_spread = max(min_long_spread, min(self.max_spread, adjusted_spread))
        
        self.logger.info(f"Buy spread: {adjusted_spread:.4%} (Base: {base_spread:.4%}, Leverage factor: {leverage_factor:.4f})")
        return adjusted_spread
    
    def _calculate_sell_spread(self, inventory_ratio: float) -> Decimal:
        """Calculate sell spread based on market conditions and inventory"""
        # Base spread calculation considering leverage
        volatility = self.indicators['medium']['natr']
        
        # Increase base spread for higher leverage
        leverage_factor = Decimal(str(math.sqrt(self.leverage) / 10))  # Square root to dampen the effect
        base_spread = Decimal(str(max(0.001, min(0.01, float(volatility) / 100)))) * (Decimal("1") + leverage_factor)
        
        # Ensure minimum spread for short positions
        min_short_spread = Decimal("0.02")  # 2% minimum spread for short positions
        
        # Adjust based on inventory ratio
        inventory_skew = inventory_ratio - float(self.target_base_pct)
        
        # If we have too much base asset, decrease sell spread (more aggressive sells)
        # If we have too little base asset, increase sell spread (less aggressive sells)
        inventory_adjustment = Decimal(str(max(-0.005, min(0.005, inventory_skew * 0.01))))
        
        # Calculate final spread
        adjusted_spread = base_spread - inventory_adjustment
        
        # Ensure spread is within allowed range
        adjusted_spread = max(min_short_spread, min(self.max_spread, adjusted_spread))
        
        self.logger.info(f"Sell spread: {adjusted_spread:.4%} (Base: {base_spread:.4%}, Leverage factor: {leverage_factor:.4f})")
        return adjusted_spread
    
    def _calculate_buy_order_size(self, inventory_ratio: float) -> Decimal:
        """Calculate buy order size based on inventory ratio"""
        # Base size
        base_size = self.order_amount
        
        # Adjust based on inventory ratio
        inventory_skew = float(self.target_base_pct) - inventory_ratio
        adjustment_factor = max(0.5, min(1.5, 1 + (inventory_skew * 1.0)))
        
        adjusted_size = base_size * Decimal(str(adjustment_factor))
        
        # Round down to appropriate precision
        return self._round_down_position_size(adjusted_size)
    
    def _calculate_sell_order_size(self, inventory_ratio: float) -> Decimal:
        """Calculate sell order size based on inventory ratio"""
        # Base size
        base_size = self.order_amount
        
        # Adjust based on inventory ratio
        inventory_skew = inventory_ratio - float(self.target_base_pct)
        adjustment_factor = max(0.5, min(1.5, 1 + (inventory_skew * 1.0)))
        
        adjusted_size = base_size * Decimal(str(adjustment_factor))
        
        # Round down to appropriate precision
        return self._round_down_position_size(adjusted_size)
    
    def cancel_all_orders(self):
        """Cancel all active orders"""
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)
    
    def did_fill_order(self, event: OrderFilledEvent):
        """Handle filled order event"""
        self.logger.info(f"Order filled: {event.amount} {event.trading_pair} at {event.price}")
    
    def format_status(self) -> str:
        """Format status for display in Hummingbot"""
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        
        lines = []
        lines.append("  Institution Crypto Framework Strategy")
        lines.append(f"  Trading pair: {self.trading_pair} on {self.exchange}")
        
        # Add market data
        connector = self.connectors[self.exchange]
        mid_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        lines.append(f"  Current price: {mid_price:.8g}")
        
        # Add indicator values
        lines.append("  Indicator Values:")
        for timeframe in ['short', 'medium', 'long']:
            if not self.indicators.get(timeframe):
                continue
            ind = self.indicators[timeframe]
            lines.append(f"    {timeframe.capitalize()} Timeframe:")
            lines.append(f"      RSI: {ind.get('rsi', 0):.2f}")
            lines.append(f"      MACD: {ind.get('macd', 0):.8g}, Signal: {ind.get('macd_signal', 0):.8g}")
            lines.append(f"      ATR: {ind.get('atr', 0):.8g}, NATR: {ind.get('natr', 0):.2f}%")
        
        # Add signal information
        lines.append("  Signal Information:")
        lines.append(f"    Score: {self.score.get('total', 0):.2f}/100")
        
        # Add position information if in a position
        if self.long_position["active"]:
            lines.append("  Active LONG Position:")
            lines.append(f"    Entry Price: {self.long_position['entry_price']:.8g}")
            if mid_price:
                pnl_pct = (mid_price - self.long_position["entry_price"]) / self.long_position["entry_price"]
                lines.append(f"    Current P&L: {pnl_pct:.2%}")
            if self.long_position["trailing_stop_active"]:
                lines.append(f"    Trailing Stop: {self.long_position['trailing_stop_price']:.8g}")
        elif self.short_position["active"]:
            lines.append("  Active SHORT Position:")
            lines.append(f"    Entry Price: {self.short_position['entry_price']:.8g}")
            if mid_price:
                pnl_pct = (self.short_position["entry_price"] - mid_price) / self.short_position["entry_price"]
                lines.append(f"    Current P&L: {pnl_pct:.2%}")
            if self.short_position["trailing_stop_active"]:
                lines.append(f"    Trailing Stop: {self.short_position['trailing_stop_price']:.8g}")
        
        # Add balance information
        base, quote = self.trading_pair.split("-")
        base_balance = connector.get_balance(base)
        quote_balance = connector.get_balance(quote)
        lines.append("  Balances:")
        lines.append(f"    {base}: {base_balance:.8g}")
        lines.append(f"    {quote}: {quote_balance:.8g}")
        
        # Add active orders
        active_orders = self.get_active_orders(connector_name=self.exchange)
        lines.append(f"  Active Orders ({len(active_orders)}):")
        for order in active_orders:
            lines.append(f"    {order.order_side.name} {order.amount} @ {order.price:.8g}")
        
        return "\n".join(lines)