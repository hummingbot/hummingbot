#!/usr/bin/env python3

import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import pandas_ta as ta  # Using pandas_ta for potentially simpler indicator calculation
import scipy.stats as stats
from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/precision_trading_strategy.log")  # Log to a file in logs dir
    ]
)
# Use Hummingbot's logger
logger = logging.getLogger("PrecisionAlgorithmicTrading")
# Note: Hummingbot's default logging will also capture script logs if configured correctly.


class PrecisionTradingStrategyHummingbot(ScriptStrategyBase):
    """
    Precision Algorithmic Trading Strategy with Weighted Indicators
    (Optimized for Crypto Markets and adapted for Hummingbot)

    This strategy assigns weighted scores to indicators and combines them to generate
    high-probability signals based on risk tolerance and time horizon.
    It includes multi-timeframe analysis and trap detection.
    """

    # === Script Configurable Parameters ===
    exchange: str = "binance_perpetual"  # Use perpetual connector if applicable
    trading_pair: str = "BTC-USDT"       # Use Hummingbot format (e.g., BTC-USDT)

    # --- Strategy Parameters ---
    risk_level: str = "medium"         # "high", "medium", "low"
    time_horizon: str = "medium"       # "short", "medium", "long"
    position_size_pct: float = 0.05      # Percentage of available balance per trade (initial value)
    leverage: int = 2                    # Leverage to use (ensure it's set on the exchange/connector)

    # --- Technical Analysis ---
    # Using pandas_ta where possible for simplicity, lengths can be adjusted here
    rsi_length: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ema_short_len: int = 50
    ema_long_len: int = 200
    bb_length: int = 20
    bb_std: float = 2.0
    atr_length: int = 14
    sr_window: int = 10              # Window for finding swing highs/lows for S/R
    sr_group_threshold: float = 0.005  # Threshold for grouping S/R levels

    # --- Execution ---
    update_interval: int = 60         # How often to fetch data and recalculate (seconds)
    # Update interval for longer timeframes (multiples of update_interval)
    secondary_tf_update_multiplier: int = 5  # e.g., if update=60s, secondary updates every 5*60=300s
    long_tf_update_multiplier: int = 15      # e.g., primary updates every 15*60=900s

    # ======================================

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)

        self.connector: ConnectorBase = self.connectors[self.exchange]
        self.base_asset, self.quote_asset = self.trading_pair.split("-")

        # Strategy parameters initialization
        self.timeframes_config = self._set_timeframes()  # e.g., {'primary': '1h', 'secondary': '15m'}
        self.signal_threshold = self._set_signal_threshold()
        self.risk_params = self._set_risk_parameters()
        self.indicator_weights = self._set_indicator_weights()

        # Adjust position size based on loaded risk parameters
        self.position_size_pct = self.risk_params.get("position_size_pct", self.position_size_pct)
        self.max_leverage = self.risk_params.get("max_leverage", self.leverage)
        # Ensure configured leverage doesn't exceed risk profile max
        self.leverage = min(self.leverage, self.max_leverage)

        # Initialize data storage
        self.price_data: Dict[str, pd.DataFrame] = {}  # Store OHLCV dataframes per timeframe
        self.indicator_values: Dict[str, Dict] = {}    # Store calculated indicator values per timeframe
        self.indicator_scores: Dict[str, float] = {    # Initialize scores (normalized 0-100)
            "rsi": 50.0, "macd": 50.0, "ema": 50.0, "bbands": 50.0,
            "volume": 50.0, "support_resistance": 50.0
        }
        self.trap_indicators: Dict[str, float] = {
            "volume_delta": 0.0, "order_imbalance": 0.0, "bid_ask_spread": 0.0,
            "wick_rejection": 0.0, "upper_wick_ratio": 0.0, "lower_wick_ratio": 0.0
        }
        self.recent_trades: Optional[pd.DataFrame] = None
        self.order_book: Optional[Dict] = None
        self.current_spread: float = 0.0
        self.average_spread: float = 0.0
        self.spread_history: List[float] = []

        # Market state
        self.market_regime = {"regime": "unknown", "confidence": 0.0, "trend_direction": 0}
        self.total_score: float = 50.0

        # Support and resistance levels
        self.support_levels: List[float] = []
        self.resistance_levels: List[float] = []

        # Active position tracking (simplified for one position at a time)
        self.active_position: Optional[Dict] = None  # e.g., {'side': 'buy', 'entry_price': 50000, 'amount': 0.01, 'sl': 47500, 'tp': {}}

        # Timing
        self.last_update_time: float = 0
        self.last_secondary_tf_update: float = 0
        self.last_long_tf_update: float = 0  # Use for the longest timeframe if applicable

        logger.info(f"Precision Strategy initialized for {self.trading_pair} on {self.exchange}")
        logger.info(f"Risk Level: {self.risk_level}, Time Horizon: {self.time_horizon}")
        logger.info(f"Primary TF: {self.timeframes_config['primary']}, Secondary TF: {self.timeframes_config['secondary']}")
        logger.info(f"Signal Threshold: {self.signal_threshold}, Position Size Pct: {self.position_size_pct}, Leverage: {self.leverage}")
        logger.info(f"Stop Loss Pct: {self.risk_params['stop_loss_pct']}")

    # --- Parameter Setting Helpers (from original script) ---

    def _set_timeframes(self) -> Dict[str, str]:
        """Set primary and secondary timeframes based on time horizon"""
        # Map common time horizon terms to Hummingbot intervals
        mapping = {
            "short": {"primary": "1h", "secondary": "15m"},
            "medium": {"primary": "4h", "secondary": "1h"},
            "long": {"primary": "1d", "secondary": "4h"}
        }
        return mapping.get(self.time_horizon, mapping["medium"])  # Default to medium

    def _set_signal_threshold(self) -> float:
        """Set signal threshold based on time horizon"""
        mapping = {"short": 70.0, "medium": 75.0, "long": 80.0}
        return mapping.get(self.time_horizon, 75.0)  # Default to medium

    def _set_risk_parameters(self) -> Dict[str, Union[float, Dict]]:
        """Set risk parameters based on risk level"""
        if self.risk_level == "high":
            return {
                "stop_loss_pct": 0.05, "trailing_start": 0.1,
                "take_profit": {  # TP levels as % profit, size as % of position
                    "tp1": {"pct": 0.1, "size": 0.3}, "tp2": {"pct": 0.15, "size": 0.3}, "tp3": {"pct": 0.2, "size": 0.4}
                }, "position_size_pct": 0.1, "max_leverage": 10  # Adjusted max leverage
            }
        elif self.risk_level == "medium":
            return {
                "stop_loss_pct": 0.07, "trailing_start": 0.08,
                "take_profit": {
                    "tp1": {"pct": 0.07, "size": 0.5}, "tp2": {"pct": 0.12, "size": 0.5}
                }, "position_size_pct": 0.05, "max_leverage": 5
            }
        else:  # low risk
            return {
                "stop_loss_pct": 0.1, "trailing_start": 0.05,
                "take_profit": {
                    "tp1": {"pct": 0.08, "size": 0.5}, "tp2": {"pct": 0.12, "size": 0.5}
                }, "position_size_pct": 0.02, "max_leverage": 2
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

    # --- Data Fetching & Preparation ---

    async def fetch_market_data(self) -> bool:
        """Fetch market data using Hummingbot connectors"""
        success = True
        now = self.current_timestamp

        try:
            # --- Fetch OHLCV data ---
            # Always fetch primary timeframe data
            primary_tf = self.timeframes_config['primary']
            self.price_data['primary'] = await self.fetch_candles(primary_tf, limit=250)  # Fetch enough for indicators + lookback

            # Fetch secondary timeframe data less frequently
            secondary_tf = self.timeframes_config['secondary']
            if now - self.last_secondary_tf_update >= self.update_interval * self.secondary_tf_update_multiplier:
                 self.price_data['secondary'] = await self.fetch_candles(secondary_tf, limit=150)
                 self.last_secondary_tf_update = now

            # --- Fetch Order Book ---
            self.order_book = await self.connector.get_order_book(self.trading_pair)

            # --- Fetch Recent Trades ---
            # Note: get_trades is often limited; might not be sufficient for deep volume delta analysis
            try:
                trades = await self.connector.get_last_traded_prices(self.trading_pair, limit=100)
                # We need side info, which get_last_traded_prices doesn't provide reliably across connectors.
                # get_trade_history might be better but can be slow/rate-limited.
                # Placeholder: Using order book delta might be more feasible in Hummingbot.
                self.recent_trades = None  # Mark as unavailable for now
                logger.warning("Reliable recent trade side data not available via standard Hummingbot methods for volume delta.")
            except Exception as e:
                logger.warning(f"Could not fetch recent trades: {e}")
                self.recent_trades = None

            # --- Calculate Spread ---
            if self.order_book and self.order_book['bids'] and self.order_book['asks']:
                best_bid = float(self.order_book['bids'][0][0])
                best_ask = float(self.order_book['asks'][0][0])
                if best_bid > 0:
                    self.current_spread = (best_ask - best_bid) / best_bid
                else:
                    self.current_spread = 0.0

                self.spread_history.append(self.current_spread)
                if len(self.spread_history) > 50:
                    self.spread_history = self.spread_history[-50:]
                self.average_spread = np.mean(self.spread_history) if self.spread_history else 0.0
            else:
                self.current_spread = 0.0
                self.average_spread = 0.0

            logger.debug("Market data fetched successfully")

        except Exception as e:
            logger.error(f"Error fetching market data: {e}", exc_info=True)
            success = False

        # Check if essential primary data is available
        if 'primary' not in self.price_data or self.price_data['primary'].empty:
             logger.warning("Primary timeframe data is missing or empty.")
             success = False

        return success

    async def fetch_candles(self, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Helper to fetch OHLCV candles and return DataFrame"""
        try:
            candles = await self.connector.get_candles_df(
                trading_pair=self.trading_pair,
                interval=timeframe,
                max_records=limit
            )
            # Ensure correct column names and types
            candles.rename(columns={
                "open_time": "timestamp",  # Assuming connector provides open_time
                "quote_asset_volume": "volume"  # Or base_asset_volume depending on connector
            }, inplace=True)

            # If timestamp is not datetime, convert (depends on connector output)
            if not pd.api.types.is_datetime64_any_dtype(candles.index):
                 if "timestamp" in candles.columns and pd.api.types.is_numeric_dtype(candles["timestamp"]):
                     candles['timestamp'] = pd.to_datetime(candles['timestamp'], unit='ms')
                     candles.set_index('timestamp', inplace=True)
                 else:
                     # Fallback if timestamp format is unexpected
                     logger.warning(f"Unexpected timestamp format for {timeframe}. Index might be incorrect.")
                     # Attempt to use index if it looks like timestamps
                     if pd.api.types.is_numeric_dtype(candles.index):
                           candles.index = pd.to_datetime(candles.index, unit='ms')


            # Ensure standard OHLCV columns exist and are numeric
            ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in ohlcv_cols:
                if col not in candles.columns:
                    logger.error(f"Missing required column '{col}' in candle data for {timeframe}.")
                    return pd.DataFrame()  # Return empty if critical data missing
                candles[col] = pd.to_numeric(candles[col], errors='coerce')

            candles.dropna(subset=ohlcv_cols, inplace=True)  # Drop rows with NaN in essential columns

            # Sort by timestamp just in case
            candles.sort_index(inplace=True)

            return candles

        except Exception as e:
            logger.error(f"Error fetching candles for {timeframe}: {e}", exc_info=True)
            return pd.DataFrame()  # Return empty dataframe on error

    # --- Indicator Calculations (using pandas_ta where convenient) ---

    def calculate_indicators(self) -> None:
        """Calculate all technical indicators for available timeframes"""
        if not self.price_data:
            logger.warning("No price data available to calculate indicators.")
            return

        for tf_name, df in self.price_data.items():
            if df.empty or len(df) < self.ema_long_len:  # Need enough data for longest indicator
                logger.warning(f"Not enough data for {tf_name} timeframe ({len(df)} candles) to calculate all indicators.")
                continue

            # Use pandas_ta for common indicators
            df.ta.rsi(length=self.rsi_length, append=True)  # Appends 'RSI_14'
            df.ta.macd(fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal, append=True)  # Appends 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9'
            df.ta.ema(length=self.ema_short_len, append=True)  # Appends 'EMA_50'
            df.ta.ema(length=self.ema_long_len, append=True)  # Appends 'EMA_200'
            df.ta.bbands(length=self.bb_length, std=self.bb_std, append=True)  # Appends 'BBL_20_2.0', 'BBM_20_2.0', 'BBU_20_2.0', 'BBB_20_2.0', 'BBP_20_2.0'
            df.ta.atr(length=self.atr_length, append=True)  # Appends 'ATRr_14'

            # Store latest values
            latest_indicators = df.iloc[-1]
            self.indicator_values[tf_name] = {
                "rsi": latest_indicators.get(f'RSI_{self.rsi_length}', 50.0),
                "macd_line": latest_indicators.get(f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}', 0.0),
                "signal_line": latest_indicators.get(f'MACDs_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}', 0.0),
                "histogram": latest_indicators.get(f'MACDh_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}', 0.0),
                "ema_short": latest_indicators.get(f'EMA_{self.ema_short_len}', df['close'].iloc[-1]),
                "ema_long": latest_indicators.get(f'EMA_{self.ema_long_len}', df['close'].iloc[-1]),
                "bb_upper": latest_indicators.get(f'BBU_{self.bb_length}_{self.bb_std}', df['close'].iloc[-1] * 1.02),
                "bb_middle": latest_indicators.get(f'BBM_{self.bb_length}_{self.bb_std}', df['close'].iloc[-1]),
                "bb_lower": latest_indicators.get(f'BBL_{self.bb_length}_{self.bb_std}', df['close'].iloc[-1] * 0.98),
                "atr": latest_indicators.get(f'ATRr_{self.atr_length}', 0.0) * latest_indicators['close'] / 100 if latest_indicators.get(f'ATRr_{self.atr_length}') else 0.0,  # Convert ATR % to price value
                "volumes": df['volume'].values  # Keep array for volume checks
            }
            logger.debug(f"Indicators calculated for {tf_name}: {self.indicator_values[tf_name]}")

        # Calculate S/R and Trap indicators using primary timeframe data
        if 'primary' in self.price_data and not self.price_data['primary'].empty:
            self._find_support_resistance()
            self._calculate_trap_indicators()
        else:
             logger.warning("Cannot calculate S/R or Trap Indicators due to missing primary data.")


    def _find_support_resistance(self):
        """Find support and resistance levels using primary timeframe"""
        df = self.price_data.get('primary')
        if df is None or df.empty or len(df) < self.sr_window * 2 + 1:
            self.support_levels = []
            self.resistance_levels = []
            logger.debug("Not enough primary data for S/R calculation.")
            return

        # Using pandas_ta for finding pivots might be simpler, but implementing original logic:
        highs = []
        lows = []
        window = self.sr_window

        for i in range(window, len(df) - window):
            is_high = True
            for j in range(1, window + 1):
                if df['high'].iloc[i] <= df['high'].iloc[i - j] or df['high'].iloc[i] <= df['high'].iloc[i + j]:
                    is_high = False
                    break
            if is_high:
                highs.append(df['high'].iloc[i])

            is_low = True
            for j in range(1, window + 1):
                if df['low'].iloc[i] >= df['low'].iloc[i - j] or df['low'].iloc[i] >= df['low'].iloc[i + j]:
                    is_low = False
                    break
            if is_low:
                lows.append(df['low'].iloc[i])

        self.resistance_levels = self._group_levels(highs)
        self.support_levels = self._group_levels(lows)
        logger.debug(f"S/R Levels: Support={self.support_levels}, Resistance={self.resistance_levels}")


    def _group_levels(self, levels: List[float]) -> List[float]:
        """Group nearby price levels together"""
        if not levels:
            return []

        levels.sort()
        grouped = []
        current_group = [levels[0]]

        for i in range(1, len(levels)):
            price = levels[i]
            prev_price = current_group[-1]

            if abs(price - prev_price) / prev_price < self.sr_group_threshold:
                current_group.append(price)
            else:
                grouped.append(np.mean(current_group))
                current_group = [price]

        if current_group:
            grouped.append(np.mean(current_group))

        return grouped


    def _calculate_trap_indicators(self):
        """Calculate non-lagging indicators specifically for trap detection"""
        df_primary = self.price_data.get('primary')
        if df_primary is None or df_primary.empty:
             logger.debug("Cannot calculate trap indicators: Missing primary data.")
             return

        # 1. Volume Delta (Using Order Book Imbalance as proxy if recent trades unreliable)
        # If reliable trade data were available:
        # if self.recent_trades is not None and not self.recent_trades.empty and 'side' in self.recent_trades.columns:
        #     buy_volume = self.recent_trades[self.recent_trades['side'] == 'buy']['amount'].sum()
        #     sell_volume = self.recent_trades[self.recent_trades['side'] == 'sell']['amount'].sum()
        #     total_volume = buy_volume + sell_volume
        #     self.trap_indicators['volume_delta'] = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0.0
        # else:
        #     self.trap_indicators['volume_delta'] = 0.0 # Or use order book imbalance
        self.trap_indicators['volume_delta'] = 0.0  # Disabled due to data limitation


        # 2. Order Book Imbalance
        if self.order_book and self.order_book['bids'] and self.order_book['asks']:
            bid_volume = sum(float(order[1]) for order in self.order_book['bids'][:10])
            ask_volume = sum(float(order[1]) for order in self.order_book['asks'][:10])
            total_volume = bid_volume + ask_volume
            self.trap_indicators['order_imbalance'] = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0.0
        else:
            self.trap_indicators['order_imbalance'] = 0.0

        # 3. Bid-Ask Spread Change Rate
        if self.average_spread > 1e-9:  # Avoid division by zero
            self.trap_indicators['bid_ask_spread'] = (self.current_spread - self.average_spread) / self.average_spread
        else:
            self.trap_indicators['bid_ask_spread'] = 0.0

        # 4. Wick Rejection (using primary timeframe last candle)
        last_candle = df_primary.iloc[-1]
        candle_body = abs(last_candle['close'] - last_candle['open'])
        candle_range = last_candle['high'] - last_candle['low']

        if candle_range > 1e-9:  # Avoid division by zero
            upper_wick = last_candle['high'] - max(last_candle['open'], last_candle['close'])
            lower_wick = min(last_candle['open'], last_candle['close']) - last_candle['low']

            self.trap_indicators['upper_wick_ratio'] = upper_wick / candle_range
            self.trap_indicators['lower_wick_ratio'] = lower_wick / candle_range
            # Combined metric: long lower wick (bullish rejection) - long upper wick (bearish rejection)
            self.trap_indicators['wick_rejection'] = self.trap_indicators['lower_wick_ratio'] - self.trap_indicators['upper_wick_ratio']
        else:
            self.trap_indicators['wick_rejection'] = 0.0
            self.trap_indicators['upper_wick_ratio'] = 0.0
            self.trap_indicators['lower_wick_ratio'] = 0.0

        logger.debug(f"Trap Indicators: {self.trap_indicators}")

    # --- Market Regime & Scoring ---

    def calculate_market_regime(self):
        """Detect current market regime (trending, ranging, volatile) using primary TF"""
        df = self.price_data.get('primary')
        if df is None or len(df) < 50:
            self.market_regime = {"regime": "unknown", "confidence": 0.0, "trend_direction": 0}
            logger.debug("Not enough primary data for market regime calculation.")
            return

        price_window = df['close'].values[-50:]
        returns = np.diff(price_window) / price_window[:-1]
        # Use rolling std dev of returns for volatility measure
        volatility_std = pd.Series(returns).rolling(window=20).std().iloc[-1]  # Volatility over last 20 periods
        # Use ADX for trend strength (simpler than linear regression R value)
        df.ta.adx(length=14, append=True)  # Appends ADX_14, DMP_14, DMN_14
        adx = df['ADX_14'].iloc[-1]
        dmp = df['DMP_14'].iloc[-1]  # Positive Directional Movement
        dmn = df['DMN_14'].iloc[-1]  # Negative Directional Movement

        regime = "unknown"
        confidence = 0.0
        trend_direction = 0

        if adx > 25:  # Trending market
             regime = "trending"
             confidence = min(1.0, (adx - 20) / 30.0)  # Scale confidence between ADX 20-50
             trend_direction = 1 if dmp > dmn else -1

        elif adx < 20:  # Ranging market
             regime = "ranging"
             confidence = min(1.0, (25 - adx) / 15.0)  # Scale confidence for ADX < 25
             trend_direction = 0
        else:  # Indeterminate (ADX between 20-25)
             regime = "transition"
             confidence = 0.3  # Low confidence
             trend_direction = 1 if dmp > dmn else -1  # Tentative direction


        self.market_regime = {
            "regime": regime,
            "confidence": confidence,
            "trend_direction": trend_direction
        }
        logger.info(f"Market regime: {regime} (ADX: {adx:.2f}, Conf: {confidence:.2f}, Dir: {trend_direction})")


    def calculate_indicator_scores(self):
        """Calculate scores (0-100) for each indicator based on primary timeframe values"""
        if 'primary' not in self.indicator_values:
             logger.warning("Primary indicator values not available for scoring.")
             # Reset scores to neutral
             for k in self.indicator_scores: self.indicator_scores[k] = 50.0
             self.total_score = 50.0
             return

        ind = self.indicator_values['primary']
        df_primary = self.price_data['primary']
        current_price = df_primary['close'].iloc[-1]

        # --- RSI Score ---
        rsi = ind['rsi']
        rsi_divergence_bull = self._check_rsi_divergence(bearish=False)
        rsi_divergence_bear = self._check_rsi_divergence(bearish=True)

        if rsi <= 30:
            self.indicator_scores['rsi'] = 85.0 if rsi_divergence_bull else 75.0  # Bullish, higher if divergence
        elif rsi >= 70:
            self.indicator_scores['rsi'] = 15.0 if rsi_divergence_bear else 25.0  # Bearish, lower if divergence
        else:
            # Linear scale between 30 (score 75) and 70 (score 25)
            self.indicator_scores['rsi'] = 75.0 - (rsi - 30) * (50.0 / 40.0)

        # --- MACD Score ---
        macd_line = ind['macd_line']
        signal_line = ind['signal_line']
        # Normalize histogram by recent price volatility (ATR) for better comparison
        atr = ind['atr'] if ind['atr'] > 1e-9 else current_price * 0.01  # Use 1% price if ATR is zero
        norm_hist = ind['histogram'] / atr if atr > 0 else 0

        if macd_line > signal_line:  # Bullish crossover / MACD above signal
            base_score = 60.0 if macd_line > 0 else 55.0  # Higher base if above zero line
            strength_bonus = min(40.0, abs(norm_hist) * 50.0)  # Bonus based on normalized histogram magnitude
            self.indicator_scores['macd'] = min(100.0, base_score + strength_bonus)
        else:  # Bearish crossover / MACD below signal
            base_score = 40.0 if macd_line < 0 else 45.0  # Lower base if below zero line
            strength_penalty = min(40.0, abs(norm_hist) * 50.0)  # Penalty based on normalized histogram magnitude
            self.indicator_scores['macd'] = max(0.0, base_score - strength_penalty)

        # --- EMA Score ---
        ema_short = ind['ema_short']
        ema_long = ind['ema_long']
        volumes = ind['volumes']
        avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        volume_spike = volumes[-1] > avg_volume * 1.5 if avg_volume > 0 else False
        ema_bonus = 10.0 if volume_spike else 0.0  # Reduced bonus

        if current_price > ema_short > ema_long:
            self.indicator_scores['ema'] = 80.0 + ema_bonus  # Strong Bullish
        elif current_price > ema_short and current_price > ema_long:
            self.indicator_scores['ema'] = 70.0 + ema_bonus  # Bullish
        elif current_price > ema_long:
            self.indicator_scores['ema'] = 60.0  # Weak Bullish
        elif current_price < ema_short < ema_long:
            self.indicator_scores['ema'] = 20.0 - ema_bonus  # Strong Bearish
        elif current_price < ema_short and current_price < ema_long:
            self.indicator_scores['ema'] = 30.0 - ema_bonus  # Bearish
        elif current_price < ema_long:
            self.indicator_scores['ema'] = 40.0  # Weak Bearish
        else:
            self.indicator_scores['ema'] = 50.0  # Neutral / Crossing

        # --- Bollinger Bands Score ---
        upper_band = ind['bb_upper']
        middle_band = ind['bb_middle']
        lower_band = ind['bb_lower']
        band_width = (upper_band - lower_band) / middle_band if middle_band > 0 else 0
        bb_squeeze = band_width < 0.04  # Adjusted threshold for squeeze detection
        bb_bonus = 10.0 if bb_squeeze else 0.0

        if current_price <= lower_band * 1.005:  # Price touching or below lower band
            self.indicator_scores['bbands'] = 80.0 + bb_bonus
        elif current_price >= upper_band * 0.995:  # Price touching or above upper band
            self.indicator_scores['bbands'] = 20.0 - bb_bonus
        elif upper_band > lower_band:  # Price within bands
            position_val = (current_price - lower_band) / (upper_band - lower_band)
            self.indicator_scores['bbands'] = 20.0 + (position_val * 60.0)  # Scale 20-80 within bands
        else:  # Bands invalid or zero width
             self.indicator_scores['bbands'] = 50.0

        # --- Volume Score ---
        current_volume = volumes[-1]
        price_change = current_price - df_primary['close'].iloc[-2] if len(df_primary) > 1 else 0

        if avg_volume > 0:
            if current_volume > avg_volume * 2:  # Major spike
                self.indicator_scores['volume'] = 85.0 if price_change > 0 else 15.0
            elif current_volume > avg_volume * 1.5:  # Significant increase
                self.indicator_scores['volume'] = 70.0 if price_change > 0 else 30.0
            elif current_volume < avg_volume * 0.5:  # Low volume
                self.indicator_scores['volume'] = 40.0  # Generally neutral/negative confirmation
            else:  # Normal volume
                self.indicator_scores['volume'] = 55.0 if price_change > 0 else 45.0  # Slight bias with price direction
        else:
            self.indicator_scores['volume'] = 50.0

        # --- Support/Resistance Score ---
        self.indicator_scores['support_resistance'] = self._calculate_sr_score(current_price)

        # --- Calculate Total Weighted Score ---
        self.total_score = sum(
            self.indicator_scores[indicator] * self.indicator_weights[indicator]
            for indicator in self.indicator_scores
        )

        logger.info(f"Indicator Scores: { {k: round(v, 1) for k, v in self.indicator_scores.items()} }")
        logger.info(f"Total Weighted Score (Before Secondary): {self.total_score:.2f}")


    def _check_rsi_divergence(self, lookback=14, bearish=False) -> bool:
        """Check for RSI divergence using primary timeframe data"""
        df = self.price_data.get('primary')
        rsi_key = f'RSI_{self.rsi_length}'
        if df is None or rsi_key not in df.columns or len(df) < lookback + 2:
            return False

        # Find recent lows/highs in price and RSI
        price_series = df['low'] if not bearish else df['high']
        rsi_series = df[rsi_key]

        # Simplified check: Compare last point to the minimum/maximum in the lookback window (excluding the last point)
        try:
            window_price = price_series.iloc[-(lookback+1):-1]
            window_rsi = rsi_series.iloc[-(lookback+1):-1]

            if not bearish:  # Bullish divergence: price lower low, RSI higher low
                price_low_idx = window_price.idxmin()
                rsi_low_at_price_low = rsi_series.loc[price_low_idx]

                price_makes_lower_low = price_series.iloc[-1] < window_price.min()
                rsi_makes_higher_low = rsi_series.iloc[-1] > rsi_low_at_price_low  # Compare RSI now to RSI at previous price low

                return price_makes_lower_low and rsi_makes_higher_low and rsi_series.iloc[-1] < 50

            else:  # Bearish divergence: price higher high, RSI lower high
                price_high_idx = window_price.idxmax()
                rsi_high_at_price_high = rsi_series.loc[price_high_idx]

                price_makes_higher_high = price_series.iloc[-1] > window_price.max()
                rsi_makes_lower_high = rsi_series.iloc[-1] < rsi_high_at_price_high  # Compare RSI now to RSI at previous price high

                return price_makes_higher_high and rsi_makes_lower_high and rsi_series.iloc[-1] > 50

        except Exception as e:
            logger.error(f"Error checking RSI divergence: {e}", exc_info=True)
            return False


    def _calculate_sr_score(self, current_price: float) -> float:
        """Calculate score based on proximity to S/R levels"""
        if not self.support_levels and not self.resistance_levels:
            return 50.0  # Neutral

        closest_support = max([s for s in self.support_levels if s < current_price], default=None)
        closest_resistance = min([r for r in self.resistance_levels if r > current_price], default=None)

        if closest_support is None and closest_resistance is None:
            return 50.0
        if closest_support is None:
            closest_support = 0  # Treat price floor as support
        if closest_resistance is None:
            closest_resistance = float('inf')  # No ceiling

        support_dist = (current_price - closest_support) / current_price if current_price > 0 else float('inf')
        resistance_dist = (closest_resistance - current_price) / current_price if current_price > 0 else float('inf')

        proximity_threshold_strong = 0.005  # 0.5% for strong reaction zone
        proximity_threshold_weak = 0.015    # 1.5% for weaker zone

        if support_dist <= resistance_dist:  # Closer to support
            if support_dist < proximity_threshold_strong:
                return 85.0  # Very close to support
            elif support_dist < proximity_threshold_weak:
                return 70.0  # Near support
            else:
                return 60.0  # Moving towards support
        else:  # Closer to resistance
            if resistance_dist < proximity_threshold_strong:
                return 15.0  # Very close to resistance
            elif resistance_dist < proximity_threshold_weak:
                return 30.0  # Near resistance
            else:
                return 40.0  # Moving towards resistance


    # --- Trap Detection ---

    def detect_bull_trap(self, price: float, resistance_level: Optional[float] = None) -> Tuple[bool, float]:
        """Detect potential bull trap using non-lagging indicators"""
        if resistance_level is None:
            resistances_above = [r for r in self.resistance_levels if r > price * 0.995]  # Check slightly below too
            if not resistances_above:
                return False, 0.0
            resistance_level = min(resistances_above)

        # Condition: Price broke slightly above resistance OR shows strong upper wick near resistance
        is_breaking = price > resistance_level * 1.002  # Small breakout threshold
        is_rejecting_near = (price > resistance_level * 0.99) and (self.trap_indicators['upper_wick_ratio'] > 0.6)  # Strong upper wick near R

        if is_breaking or is_rejecting_near:
            trap_score = 0.0

            # 1. Volume confirmation lacking on breakout (use primary TF volume)
            volumes = self.indicator_values.get('primary', {}).get('volumes', [])
            if len(volumes) > 3:
                 avg_vol = np.mean(volumes[-4:-1])  # Avg volume before the current candle
                 if volumes[-1] < avg_vol * 0.9 and is_breaking:  # Lower volume on break
                     trap_score += 30.0

            # 2. Order book showing sell pressure
            if self.trap_indicators['order_imbalance'] < -0.15:  # More ask volume
                trap_score += 25.0

            # 3. Sudden spread widening (sign of volatility/pulling liquidity)
            if self.trap_indicators['bid_ask_spread'] > 0.3:  # Spread widened > 30% vs avg
                trap_score += 15.0

            # 4. Significant upper wick rejection (stronger signal than ratio alone)
            if self.trap_indicators['upper_wick_ratio'] > 0.6:  # Upper wick is > 60% of candle range
                trap_score += 30.0

            is_trap = trap_score >= 65  # Adjusted threshold
            if is_trap:
                logger.warning(f"Potential Bull Trap Detected! Score: {trap_score:.1f}")
            return is_trap, trap_score

        return False, 0.0


    def detect_bear_trap(self, price: float, support_level: Optional[float] = None) -> Tuple[bool, float]:
        """Detect potential bear trap using non-lagging indicators"""
        if support_level is None:
            supports_below = [s for s in self.support_levels if s < price * 1.005]  # Check slightly above too
            if not supports_below:
                return False, 0.0
            support_level = max(supports_below)

        # Condition: Price broke slightly below support OR shows strong lower wick near support
        is_breaking = price < support_level * 0.998  # Small breakdown threshold
        is_rejecting_near = (price < support_level * 1.01) and (self.trap_indicators['lower_wick_ratio'] > 0.6)  # Strong lower wick near S

        if is_breaking or is_rejecting_near:
            trap_score = 0.0

            # 1. Volume confirmation lacking on breakdown
            volumes = self.indicator_values.get('primary', {}).get('volumes', [])
            if len(volumes) > 3:
                 avg_vol = np.mean(volumes[-4:-1])
                 if volumes[-1] < avg_vol * 0.9 and is_breaking:  # Lower volume on break
                     trap_score += 30.0

            # 2. Order book showing buy pressure
            if self.trap_indicators['order_imbalance'] > 0.15:  # More bid volume
                trap_score += 25.0

            # 3. Sudden spread widening
            if self.trap_indicators['bid_ask_spread'] > 0.3:
                trap_score += 15.0

            # 4. Significant lower wick rejection
            if self.trap_indicators['lower_wick_ratio'] > 0.6:  # Lower wick is > 60% of candle range
                trap_score += 30.0

            is_trap = trap_score >= 65  # Adjusted threshold
            if is_trap:
                logger.warning(f"Potential Bear Trap Detected! Score: {trap_score:.1f}")
            return is_trap, trap_score

        return False, 0.0

    # --- Signal Generation & Execution ---

    def generate_final_signal(self) -> Optional[Dict]:
        """Combine scores, secondary confirmation, traps, and regime to generate final signal"""
        if 'primary' not in self.price_data or self.price_data['primary'].empty:
            return None  # Not enough data

        current_price = self.price_data['primary']['close'].iloc[-1]
        base_score = self.total_score
        final_signal = None  # 'buy', 'sell', or None
        confidence_modifier = 1.0  # Adjusts signal strength based on confirmations/warnings

        # --- Secondary Timeframe Confirmation ---
        secondary_tf = self.timeframes_config['secondary']
        secondary_score = 50.0  # Neutral default
        confirmed_by_secondary = False
        if secondary_tf in self.indicator_values:
             secondary_score = self._calculate_score_for_tf(secondary_tf)
             # Check if secondary score aligns with primary bias
             if base_score > 55 and secondary_score > 55:  # Both bullish
                 confirmed_by_secondary = True
                 confidence_modifier += 0.15  # Increase confidence
             elif base_score < 45 and secondary_score < 45:  # Both bearish
                 confirmed_by_secondary = True
                 confidence_modifier += 0.15  # Increase confidence
             elif (base_score > 55 and secondary_score < 45) or \
                  (base_score < 45 and secondary_score > 55):  # Conflicting signals
                  confidence_modifier -= 0.25  # Decrease confidence significantly
                  logger.info(f"Primary/Secondary timeframe conflict. Primary: {base_score:.1f}, Secondary: {secondary_score:.1f}")

        # --- Market Regime Filter ---
        regime = self.market_regime['regime']
        trend_dir = self.market_regime['trend_direction']

        if regime == "trending":
            # Favor trades in trend direction
            if trend_dir == 1 and base_score < 50:
                confidence_modifier -= 0.1  # Penalize shorts in uptrend
            if trend_dir == -1 and base_score > 50:
                confidence_modifier -= 0.1  # Penalize longs in downtrend
        elif regime == "ranging":
            # Favor reversals near S/R, penalize breakouts
             sr_score = self.indicator_scores['support_resistance']
             if (base_score > 65 and sr_score < 40) or (base_score < 35 and sr_score > 60):  # Signal pushing into S/R
                 confidence_modifier -= 0.15  # Penalize potential failed breakouts in range
        
        # --- Trap Detection Filter ---
        is_bull_trap, bull_trap_score = self.detect_bull_trap(current_price)
        is_bear_trap, bear_trap_score = self.detect_bear_trap(current_price)

        if is_bull_trap and base_score > 60:  # High score but potential bull trap
            logger.warning("Bull trap detected, suppressing potential BUY signal.")
            confidence_modifier = 0  # Suppress signal
        elif is_bear_trap and base_score < 40:  # Low score but potential bear trap
            logger.warning("Bear trap detected, suppressing potential SELL signal.")
            confidence_modifier = 0  # Suppress signal

        # --- Generate Final Signal ---
        final_score_adjusted = base_score * max(0, confidence_modifier)  # Apply confidence

        logger.info(f"Final Evaluation: Base Score={base_score:.1f}, Secondary Confirm={confirmed_by_secondary} ({secondary_score:.1f}), "
                    f"Regime='{regime}', Conf Mod={confidence_modifier:.2f}, Final Adj Score={final_score_adjusted:.1f}")

        if final_score_adjusted >= self.signal_threshold:
            final_signal = 'buy'
        elif final_score_adjusted <= (100 - self.signal_threshold):
            final_signal = 'sell'

        if final_signal:
            return {
                "signal": final_signal,
                "score": final_score_adjusted,
                "price": current_price,
                "confirmed_by_secondary": confirmed_by_secondary,
                "is_bull_trap": is_bull_trap,
                "is_bear_trap": is_bear_trap
            }
        else:
            return None


    def _calculate_score_for_tf(self, tf_name: str) -> float:
        """Calculate a simple weighted score for a given timeframe (used for secondary confirmation)"""
        if tf_name not in self.indicator_values:
            return 50.0  # Neutral if no data

        # Simplified scoring for secondary TF (can reuse parts of primary scoring logic if needed)
        ind = self.indicator_values[tf_name]
        df = self.price_data[tf_name]
        current_price = df['close'].iloc[-1]

        score = 50.0  # Start neutral
        weight = 1.0 / 3.0  # Equal weight for simplified check

        # RSI check
        if ind['rsi'] > 60:
            score += 20 * weight
        elif ind['rsi'] < 40:
            score -= 20 * weight

        # MACD check
        if ind['macd_line'] > ind['signal_line']:
            score += 20 * weight
        elif ind['macd_line'] < ind['signal_line']:
            score -= 20 * weight

        # EMA check
        if current_price > ind['ema_short']:
            score += 20 * weight
        elif current_price < ind['ema_short']:
            score -= 20 * weight

        return max(0.0, min(100.0, score))  # Clamp score 0-100


    def manage_active_position(self):
        """Check SL, TP, and Trailing Stops for the active position"""
        if self.active_position is None:
            return

        position = self.active_position
        side = position['side']
        entry_price = position['entry_price']
        amount = position['amount']
        initial_sl = position['initial_sl']
        current_sl = position['current_sl']  # This will be updated by trailing logic
        take_profit_levels = position['tp_levels']  # Dict like {'tp1': {'price': P, 'size_pct': S, 'active': True}, ...}
        trailing_start_price = position['trailing_start_price']
        highest_profit_price = position.get('highest_profit_price', entry_price)  # Track peak price for trailing SL

        try:
            current_price = self.connector.get_price(self.trading_pair, is_buy= side == 'sell')  # Use ask for closing buys, bid for closing sells
            if current_price is None:
                 logger.warning("Could not get current price to manage position.")
                 return
            current_price = float(current_price)

            # --- Stop Loss Check ---
            if side == 'buy' and current_price <= current_sl:
                logger.info(f"STOP LOSS triggered for BUY position at {current_price:.4f} (SL={current_sl:.4f}). Closing position.")
                self.close_position("Stop Loss Hit")
                return  # Exit after closing
            elif side == 'sell' and current_price >= current_sl:
                logger.info(f"STOP LOSS triggered for SELL position at {current_price:.4f} (SL={current_sl:.4f}). Closing position.")
                self.close_position("Stop Loss Hit")
                return  # Exit after closing

            # --- Take Profit Check ---
            remaining_amount = position['amount']  # Track amount left after partial TPs
            for tp_key, tp_info in take_profit_levels.items():
                if tp_info['active']:
                    tp_price = tp_info['price']
                    size_pct = tp_info['size_pct']
                    tp_triggered = False

                    if side == 'buy' and current_price >= tp_price:
                        tp_triggered = True
                    elif side == 'sell' and current_price <= tp_price:
                        tp_triggered = True

                    if tp_triggered:
                        tp_amount = amount * size_pct
                        logger.info(f"TAKE PROFIT {tp_key} triggered at {current_price:.4f} (TP={tp_price:.4f}). Closing {size_pct*100:.1f}% ({tp_amount:.6f}) of position.")
                        self.place_order(
                            side='sell' if side == 'buy' else 'buy',
                            price=current_price,  # Use market or adaptive limit
                            amount=tp_amount,
                            order_type=OrderType.MARKET,  # Use Market for TP/SL for higher fill probability
                            position_action=PositionAction.CLOSE  # Indicate it's closing part of a position
                        )
                        tp_info['active'] = False  # Deactivate this TP level
                        remaining_amount -= tp_amount

            # Check if all TPs are hit
            if all(not tp['active'] for tp in take_profit_levels.values()):
                 logger.info("All Take Profit levels hit.")

            # --- Trailing Stop Logic ---
            if trailing_start_price is not None:
                should_trail = False
                if side == 'buy' and current_price >= trailing_start_price:
                    should_trail = True
                    highest_profit_price = max(highest_profit_price, current_price)
                elif side == 'sell' and current_price <= trailing_start_price:
                    should_trail = True
                    highest_profit_price = min(highest_profit_price, current_price)  # Min price for sell profit

                self.active_position['highest_profit_price'] = highest_profit_price  # Store peak price

                if should_trail:
                    sl_distance = abs(entry_price * self.risk_params['stop_loss_pct'])  # Original SL distance
                    new_sl = 0.0

                    if side == 'buy':
                        new_sl = highest_profit_price - sl_distance
                        new_sl = max(new_sl, initial_sl, entry_price * 1.001)  # Ensure SL moves up
                    elif side == 'sell':
                        new_sl = highest_profit_price + sl_distance
                        new_sl = min(new_sl, initial_sl, entry_price * 0.999)  # Ensure SL moves down

                    if (side == 'buy' and new_sl > current_sl) or \
                       (side == 'sell' and new_sl < current_sl):
                         logger.info(f"Trailing Stop Loss updated. Old SL: {current_sl:.4f}, New SL: {new_sl:.4f}")
                         self.active_position['current_sl'] = new_sl
                         current_sl = new_sl

        except Exception as e:
            logger.error(f"Error managing active position: {e}", exc_info=True)

    def calculate_position_size(self) -> Optional[Decimal]:
        """Calculate order size based on risk % and available balance"""
        try:
            quote_balance = self.connector.get_available_balance(self.quote_asset)
            if quote_balance is None or quote_balance <= 0:
                logger.warning(f"Insufficient quote balance ({self.quote_asset}) to calculate position size.")
                return None

            risk_amount_quote = quote_balance * Decimal(str(self.position_size_pct))

            current_price = self.connector.get_price(self.trading_pair, is_buy=True)  # Use buy price for estimation
            if current_price is None:
                logger.warning("Could not get current price to calculate position size.")
                return None
            current_price = Decimal(str(current_price))

            base_amount_no_leverage = risk_amount_quote / current_price
            leveraged_base_amount = base_amount_no_leverage * Decimal(str(self.leverage))

            trading_rules = self.connector.trading_rules[self.trading_pair]
            quantized_amount = self.connector.quantize_order_amount(self.trading_pair, leveraged_base_amount)

            if quantized_amount < trading_rules.min_order_size:
                logger.warning(f"Calculated order size {quantized_amount} is below minimum {trading_rules.min_order_size}. Cannot place order.")
                return None

            return quantized_amount

        except Exception as e:
            logger.error(f"Error calculating position size: {e}", exc_info=True)
            return None

    def place_order(self, side: str, price: float, amount: Decimal, order_type: OrderType = OrderType.LIMIT, position_action: PositionAction = PositionAction.OPEN):
        """Helper function to place orders"""
        try:
            trade_type = TradeType.BUY if side == 'buy' else TradeType.SELL
            order_id = None

            quantized_price = self.connector.quantize_order_price(self.trading_pair, Decimal(str(price)))

            logger.info(f"Placing {position_action.name} {side.upper()} {order_type.name} order: "
                        f"Amount={amount}, Price={quantized_price if order_type == OrderType.LIMIT else 'MARKET'}")

            if order_type == OrderType.LIMIT:
                order_id = self.place_limit_order(
                    connector_name=self.exchange,
                    trading_pair=self.trading_pair,
                    side=trade_type,
                    price=quantized_price,
                    amount=amount,
                    position_action=position_action
                )
            elif order_type == OrderType.MARKET:
                 order_id = self.place_market_order(
                    connector_name=self.exchange,
                    trading_pair=self.trading_pair,
                    side=trade_type,
                    amount=amount,
                    position_action=position_action
                )

            if order_id:
                logger.info(f"Placed order {order_id}")
            else:
                logger.error("Order placement failed, no order ID returned.")

        except Exception as e:
            logger.error(f"Error placing {side} order: {e}", exc_info=True)

    def place_limit_order(self, connector_name: str, trading_pair: str, side: TradeType, price: Decimal, amount: Decimal, position_action: PositionAction):
        """Abstracted limit order placement"""
        if side == TradeType.BUY:
            return self.buy(connector_name, trading_pair, amount, OrderType.LIMIT, price, position_action=position_action)
        else:
            return self.sell(connector_name, trading_pair, amount, OrderType.LIMIT, price, position_action=position_action)

    def place_market_order(self, connector_name: str, trading_pair: str, side: TradeType, amount: Decimal, position_action: PositionAction):
        """Abstracted market order placement"""
        if side == TradeType.BUY:
            return self.buy(connector_name, trading_pair, amount, OrderType.MARKET, position_action=position_action)
        else:
            return self.sell(connector_name, trading_pair, amount, OrderType.MARKET, position_action=position_action)

    def close_position(self, reason: str):
        """Close the currently active position with a market order"""
        if self.active_position is None:
            logger.info("Close position called but no active position found.")
            return

        side_to_close = 'sell' if self.active_position['side'] == 'buy' else 'buy'
        amount_to_close = self.active_position['amount']

        logger.info(f"Closing position ({reason}). Placing {side_to_close.upper()} MARKET order for {amount_to_close:.6f} {self.base_asset}.")

        self.place_order(
            side=side_to_close,
            price=0,  # Price irrelevant for market order
            amount=amount_to_close,
            order_type=OrderType.MARKET,
            position_action=PositionAction.CLOSE
        )
        self.active_position = None

    # --- Hummingbot Core Methods ---

    def on_tick(self):
        """Main strategy logic executed periodically"""
        now = self.current_timestamp

        if now - self.last_update_time < self.update_interval:
            if self.active_position:
                self.manage_active_position()
            return

        self.last_update_time = now
        logger.debug(f"--- Tick Update @ {datetime.fromtimestamp(now)} ---")

        if self.active_position:
            self.manage_active_position()
            if self.active_position is None:
                 return

        # --- Execute New Entry Logic ---
        # New entry logic would be implemented here based on generated signal
        # This is currently commented out as per original implementation
        # Example:
        # final_signal_info = self.generate_final_signal()
        # if final_signal_info and self.active_position is None:
        #     signal = final_signal_info['signal']
        #     price = final_signal_info['price']
        #     position_size = self.calculate_position_size()
        #     if position_size is not None and position_size > 0:
        #         # Define SL and TP
        #         # Place entry order
        #         # Store active position info
        #         pass

    def did_fill_order(self, event: OrderFilledEvent):
        """Handle order fill events to update active position state"""
        order_id = event.order_id
        trade_type = event.trade_type
        amount = event.amount
        price = event.price
        position_action = event.position

        logger.info(f"Order Filled: {order_id}, Side: {trade_type}, Amount: {amount}, Price: {price}, Action: {position_action}")

        if self.active_position and self.active_position.get('status') == 'pending_entry':
             if (self.active_position['side'] == 'buy' and trade_type == TradeType.BUY) or \
                (self.active_position['side'] == 'sell' and trade_type == TradeType.SELL):
                 self.active_position['entry_price'] = float(price)
                 self.active_position['amount'] = float(amount)
                 self.active_position['status'] = 'active'
                 logger.info(f"Active position entry confirmed/updated: Side={self.active_position['side']}, Entry={self.active_position['entry_price']:.4f}, Amount={self.active_position['amount']:.6f}")

        elif position_action == PositionAction.CLOSE:
             logger.info(f"Position close/TP fill event received for order {order_id}.")

    def format_status(self) -> str:
        """Provide status information for the Hummingbot UI"""
        if not self.ready_to_trade:
            return "Strategy not ready. Waiting for connector..."

        lines = []
        active_orders = self.get_active_orders(self.exchange)

        lines.append(f"Market: {self.exchange} - {self.trading_pair}")
        primary_df = self.price_data.get('primary')
        if primary_df is not None and not primary_df.empty:
             last_price = primary_df['close'].iloc[-1]
             lines.append(f"Last Price: {last_price:.4f}")
        else:
             lines.append("Last Price: N/A")

        lines.append(f"Spread: {self.current_spread:.4%} (Avg: {self.average_spread:.4%})")
        lines.append(f"Regime: {self.market_regime['regime']} (Conf: {self.market_regime['confidence']:.1f}, Dir: {self.market_regime['trend_direction']})")
        lines.append(f"Total Score: {self.total_score:.2f} (Threshold: {self.signal_threshold})")
        lines.append(f"S/R Levels: Supports={self.support_levels}, Resistances={self.resistance_levels}")
        lines.append("-" * 30)

        if self.active_position:
            pos = self.active_position
            side = pos['side'].upper()
            entry = pos['entry_price']
            amount = pos['amount']
            sl = pos['current_sl']
            status = pos.get('status', 'unknown')
            lines.append(f"ACTIVE POSITION: {side} {amount:.6f} {self.base_asset}")
            lines.append(f"  Entry: {entry:.4f} | Status: {status}")
            lines.append(f"  Current SL: {sl:.4f}")
            try:
                current_price = self.connector.get_price(self.trading_pair, is_buy= side == 'SELL')
                pnl_pct = (float(current_price) - entry) / entry if side == 'BUY' else (entry - float(current_price)) / entry
                lines.append(f"  Est. PnL: {pnl_pct:.2%}")
            except Exception:
                 lines.append("  Est. PnL: N/A")

            lines.append(f"  TP Levels: { {k: f'{v['price']:.4f}' for k,v in pos['tp_levels'].items() if v['active']} }")
            if pos['trailing_start_price']:
                 lines.append(f"  Trailing Starts: {pos['trailing_start_price']:.4f} (Peak Price: {pos.get('highest_profit_price', entry):.4f})")

        else:
            lines.append("No active position.")

        lines.append("-" * 30)
        lines.append("Active Orders:")
        if active_orders:
             for order in active_orders:
                 lines.append(f"  {order.order_id} | {order.side.name} {order.amount:.6f} @ {order.price:.4f} ({order.position_action.name})")
        else:
             lines.append("  None")

        return "\n".join(lines)

    def on_stop(self):
        """Actions to perform when the strategy is stopped"""
        logger.info("Strategy stopped. Cancelling open orders...")
        if self.active_position:
             logger.warning("Strategy stopped with an active position. Manual intervention might be required.")
