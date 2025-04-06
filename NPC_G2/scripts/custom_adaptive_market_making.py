#!/usr/bin/env python3

"""
Custom Adaptive Market Making Strategy for BITS GOA Assignment

This strategy combines multiple technical indicators, volatility analysis,
trend detection, and sophisticated risk management to create an adaptive
market making strategy for cryptocurrency trading.

Features:
- Dynamic spread adjustment based on volatility
- Trend analysis using RSI, EMA, and MACD
- Risk management through inventory control
- Position sizing based on volatility and market regime
- Support and resistance detection
"""

import logging
import time
import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory, CandlesConfig
from hummingbot.connector.connector_base import ConnectorBase


class CustomAdaptiveMarketMaking(ScriptStrategyBase):
    """
    Custom Adaptive Market Making Strategy that combines technical analysis,
    volatility-based spread adjustment, and risk management for optimal performance.
    """
    
    # Basic parameters
    exchange = "binance_paper_trade"
    trading_pair = "ETH-USDT"
    order_amount = 0.01
    min_spread = 0.001  # 0.1%
    max_spread = 0.01   # 1%
    order_refresh_time = 15.0  # seconds
    max_order_age = 300.0  # seconds
    
    # Technical indicator parameters
    rsi_length = 14
    rsi_overbought = 70
    rsi_oversold = 30
    ema_short = 12
    ema_medium = 21
    ema_long = 50
    bb_length = 20
    bb_std = 2.0
    
    # Risk management parameters
    target_inventory_ratio = 0.5  # 50% base, 50% quote
    max_position_pct = 0.2  # Maximum position size as % of portfolio
    stop_loss_pct = 0.05  # 5% stop loss
    take_profit_pct = 0.1  # 10% take profit
    max_drawdown = 0.15  # 15% max drawdown
    
    # Volatility parameters
    volatility_adjustment = 1.0
    trend_strength_impact = 0.5
    
    # Candle settings
    candle_exchange = "binance"
    candle_interval = "1m"
    max_candles = 1000
    
    # Get base/quote from trading pair
    base, quote = trading_pair.split("-")
    
    # Define markets to connect
    markets = {exchange: {trading_pair}}
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        
        # Initialize candles for each timeframe
        self.candles = CandlesFactory.get_candle(
            CandlesConfig(
                connector=self.candle_exchange,
                trading_pair=self.trading_pair,
                interval=self.candle_interval,
                max_records=self.max_candles
            )
        )
        
        # Start candles feeds
        self.candles.start()
        
        # Internal state variables
        self._last_order_refresh_timestamp = 0
        self._active_orders = {}
        self._cached_indicators = {}
        self._market_regime = {"regime": "unknown", "confidence": 0.0, "trend_direction": 0}
        self._trailing_stops = {}
        self._total_score = 50
        self._current_volatility = 0.0
        self._current_inventory_ratio = 0.5
        
        # Support/resistance levels
        self.support_levels = []
        self.resistance_levels = []
        
        # Trade records
        self.trade_records = []
        
        # Entry prices for stop-loss/take-profit
        self.entry_prices = {}
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Check if pandas_ta is available, otherwise implement simple indicators
        try:
            import pandas_ta as ta
        except ImportError:
            # Create a simple TA functions namespace if pandas_ta is not available
            class SimpleTa:
                @staticmethod
                def rsi(close, length=14):
                    delta = close.diff()
                    up, down = delta.copy(), delta.copy()
                    up[up < 0] = 0
                    down[down > 0] = 0
                    roll_up = up.rolling(length).mean()
                    roll_down = down.abs().rolling(length).mean()
                    rs = roll_up / roll_down
                    rsi = 100.0 - (100.0 / (1.0 + rs))
                    return pd.Series(rsi, name=f"RSI_{length}")
                
                @staticmethod
                def ema(close, length=30):
                    ema = close.ewm(span=length, adjust=False).mean()
                    return pd.Series(ema, name=f"EMA_{length}")
                
                @staticmethod
                def macd(close, fast=12, slow=26, signal=9):
                    ema_fast = close.ewm(span=fast, adjust=False).mean()
                    ema_slow = close.ewm(span=slow, adjust=False).mean()
                    macd_line = ema_fast - ema_slow
                    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
                    histogram = macd_line - signal_line
                    return pd.Series(macd_line, name="MACD"), pd.Series(signal_line, name="MACD_signal"), pd.Series(histogram, name="MACD_hist")
                
                @staticmethod
                def bbands(close, length=20, std=2.0):
                    sma = close.rolling(length).mean()
                    std_dev = close.rolling(length).std()
                    upper = sma + (std_dev * std)
                    lower = sma - (std_dev * std)
                    return pd.Series(upper, name=f"BBU_{length}_{std}"), pd.Series(sma, name=f"BBM_{length}_{std}"), pd.Series(lower, name=f"BBL_{length}_{std}")
                
                @staticmethod
                def atr(high, low, close, length=14):
                    tr1 = high - low
                    tr2 = abs(high - close.shift())
                    tr3 = abs(low - close.shift())
                    tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
                    atr = tr.rolling(length).mean()
                    return pd.Series(atr, name=f"ATR_{length}")
                
                @staticmethod
                def natr(high, low, close, length=14):
                    tr1 = high - low
                    tr2 = abs(high - close.shift())
                    tr3 = abs(low - close.shift())
                    tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
                    atr = tr.rolling(length).mean()
                    natr = (atr / close) * 100
                    return pd.Series(natr, name=f"NATR_{length}")
            
            # Set the ta namespace to our simple implementation
            pd.DataFrame.ta = SimpleTa()
        
        self.logger.info("Custom Adaptive Market Making Strategy initialized.")
    
    def on_stop(self):
        """Stop strategy and cleanup resources"""
        self.candles.stop()
        self.logger.info("Strategy stopped.")
    
    def on_tick(self):
        """Main execution loop called on each clock tick"""
        current_timestamp = self.current_timestamp
        
        # Skip if not time to refresh yet
        if current_timestamp - self._last_order_refresh_timestamp < self.order_refresh_time:
            return
        
        # Update market data and indicators
        if not self.update_market_data():
            return
        
        # Cancel all active orders
        self.cancel_all_orders()
        
        # Place new orders based on current market conditions
        self.place_orders()
        
        # Update timestamp
        self._last_order_refresh_timestamp = current_timestamp
    
    def update_market_data(self) -> bool:
        """Update market data and calculate indicators"""
        if self.candles.candles_df is None or self.candles.candles_df.empty:
            self.logger.warning("No candle data available.")
            return False
        
        try:
            # Calculate core indicators
            df = self.get_candles_with_indicators()
            if df is None or df.empty:
                return False
            
            # Calculate market regime
            self._market_regime = self.detect_market_regime(df)
            
            # Calculate current volatility
            self._current_volatility = self.calculate_current_volatility(df)
            
            # Update support/resistance levels
            self.update_support_resistance(df)
            
            # Update inventory ratio
            self.update_inventory_ratio()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error updating market data: {str(e)}")
            return False
    
    def get_candles_with_indicators(self) -> pd.DataFrame:
        """Add technical indicators to candles dataframe"""
        if self.candles.candles_df is None or self.candles.candles_df.empty:
            return None
        
        df = self.candles.candles_df.copy()
        
        try:
            # Add RSI
            rsi_series = pd.DataFrame.ta.rsi(df['close'], length=self.rsi_length)
            df[f'RSI_{self.rsi_length}'] = rsi_series
            
            # Add EMAs
            ema_short_series = pd.DataFrame.ta.ema(df['close'], length=self.ema_short)
            df[f'EMA_{self.ema_short}'] = ema_short_series
            
            ema_medium_series = pd.DataFrame.ta.ema(df['close'], length=self.ema_medium)
            df[f'EMA_{self.ema_medium}'] = ema_medium_series
            
            ema_long_series = pd.DataFrame.ta.ema(df['close'], length=self.ema_long)
            df[f'EMA_{self.ema_long}'] = ema_long_series
            
            # Add MACD
            macd_line, signal_line, histogram = pd.DataFrame.ta.macd(df['close'], fast=12, slow=26, signal=9)
            df['MACD'] = macd_line
            df['MACD_signal'] = signal_line
            df['MACD_hist'] = histogram
            
            # Add Bollinger Bands
            upper, middle, lower = pd.DataFrame.ta.bbands(df['close'], length=self.bb_length, std=self.bb_std)
            df[f'BBU_{self.bb_length}_{self.bb_std}'] = upper
            df[f'BBM_{self.bb_length}_{self.bb_std}'] = middle
            df[f'BBL_{self.bb_length}_{self.bb_std}'] = lower
            
            # Add ATR for volatility measurement
            df[f'ATR_14'] = pd.DataFrame.ta.atr(df['high'], df['low'], df['close'], length=14)
            
            # Add normalized ATR (NATR)
            df[f'NATR_14'] = pd.DataFrame.ta.natr(df['high'], df['low'], df['close'], length=14)
            
        except Exception as e:
            self.logger.error(f"Error calculating indicators: {str(e)}")
            # Return dataframe even if some indicators failed
            
        return df
    
    def detect_market_regime(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect current market regime (trending, ranging, or volatile)
        """
        if df is None or df.empty or len(df) < 30:
            return {"regime": "unknown", "confidence": 0.0, "trend_direction": 0}
        
        # Get most recent values
        atr = df['ATR_14'].iloc[-1] if 'ATR_14' in df.columns else 0
        natr = df[f'NATR_14'].iloc[-1] if 'NATR_14' in df.columns else 0
        rsi = df[f'RSI_{self.rsi_length}'].iloc[-1] if f'RSI_{self.rsi_length}' in df.columns else 50
        
        # Check short vs long EMA for trend
        ema_short = df[f'EMA_{self.ema_short}'].iloc[-1] if f'EMA_{self.ema_short}' in df.columns else 0
        ema_long = df[f'EMA_{self.ema_long}'].iloc[-1] if f'EMA_{self.ema_long}' in df.columns else 0
        
        # Calculate price changes for recent candles
        close_prices = df['close'].iloc[-20:].values
        pct_changes = np.abs(np.diff(close_prices) / close_prices[:-1])
        
        # Determine regime
        if natr > 0.03:  # High volatility (3%+ daily range)
            regime = "volatile"
            confidence = min(1.0, natr * 10)  # Scale confidence with volatility
            trend_direction = 1 if ema_short > ema_long else -1 if ema_short < ema_long else 0
        elif np.mean(pct_changes) < 0.001 and np.std(pct_changes) < 0.002:  # Very low volatility
            regime = "ranging"
            confidence = 0.7
            trend_direction = 0
        elif abs(rsi - 50) > 15:  # Strong trend (RSI away from middle)
            regime = "trending"
            confidence = min(1.0, abs(rsi - 50) / 30)  # Scale with RSI distance from neutral
            trend_direction = 1 if rsi > 50 else -1
        else:
            regime = "normal"
            confidence = 0.5
            trend_direction = 1 if ema_short > ema_long else -1 if ema_short < ema_long else 0
        
        return {
            "regime": regime,
            "confidence": float(confidence),
            "trend_direction": trend_direction
        }
    
    def calculate_current_volatility(self, df: pd.DataFrame) -> float:
        """Calculate current market volatility"""
        if df is None or df.empty or 'NATR_14' not in df.columns:
            return 0.02  # Default volatility
        
        # Use Normalized ATR as volatility measure
        return float(df['NATR_14'].iloc[-1])
    
    def update_support_resistance(self, df: pd.DataFrame):
        """Update support and resistance levels"""
        if df is None or df.empty or len(df) < 30:
            return
        
        # Get high/low prices
        highs = df['high'].values
        lows = df['low'].values
        
        # Simple detection of swing highs and lows
        window = 5  # Look 5 candles left and right
        
        # Find local minima (support)
        self.support_levels = []
        for i in range(window, len(lows) - window):
            if all(lows[i] <= lows[i-j] for j in range(1, window+1)) and \
               all(lows[i] <= lows[i+j] for j in range(1, window+1)):
                self.support_levels.append(float(lows[i]))
        
        # Find local maxima (resistance)
        self.resistance_levels = []
        for i in range(window, len(highs) - window):
            if all(highs[i] >= highs[i-j] for j in range(1, window+1)) and \
               all(highs[i] >= highs[i+j] for j in range(1, window+1)):
                self.resistance_levels.append(float(highs[i]))
        
        # Keep only recent levels
        self.support_levels = self.support_levels[-5:] if len(self.support_levels) > 5 else self.support_levels
        self.resistance_levels = self.resistance_levels[-5:] if len(self.resistance_levels) > 5 else self.resistance_levels
    
    def update_inventory_ratio(self):
        """Update current inventory ratio"""
        connector = self.connectors[self.exchange]
        
        # Get balances
        base_balance = connector.get_balance(self.base)
        quote_balance = connector.get_balance(self.quote)
        
        # Get current price
        mid_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        
        # Calculate base value in quote currency
        base_value_in_quote = base_balance * mid_price
        
        # Calculate total portfolio value in quote currency
        total_portfolio_value = base_value_in_quote + quote_balance
        
        # Calculate ratio
        if total_portfolio_value > 0:
            self._current_inventory_ratio = float(base_value_in_quote / total_portfolio_value)
        else:
            self._current_inventory_ratio = 0.5  # Default to balanced
    
    def calculate_dynamic_spreads(self) -> Tuple[Decimal, Decimal]:
        """
        Calculate dynamic bid and ask spreads based on market conditions
        """
        # Base spread on volatility
        volatility_factor = min(3.0, max(1.0, self._current_volatility * 100))
        base_spread = self.min_spread * Decimal(str(volatility_factor))
        
        # Adjust for trend direction
        trend_direction = self._market_regime["trend_direction"]
        trend_confidence = Decimal(str(self._market_regime["confidence"]))
        
        # Adjust spreads for inventory management
        inventory_skew = Decimal(str(self._current_inventory_ratio - self.target_inventory_ratio))
        
        # More base than target: tighter bid spread, wider ask spread
        # Less base than target: wider bid spread, tighter ask spread
        bid_spread = base_spread * (Decimal("1.0") - inventory_skew * Decimal("2.0"))
        ask_spread = base_spread * (Decimal("1.0") + inventory_skew * Decimal("2.0"))
        
        # Ensure spreads remain within limits
        bid_spread = max(self.min_spread, min(self.max_spread, bid_spread))
        ask_spread = max(self.min_spread, min(self.max_spread, ask_spread))
        
        return bid_spread, ask_spread
    
    def calculate_dynamic_order_size(self) -> Tuple[Decimal, Decimal]:
        """
        Calculate dynamic order sizes based on inventory and market conditions
        """
        # Base size
        base_size = Decimal(str(self.order_amount))
        
        # Inventory management
        inventory_skew = self._current_inventory_ratio - self.target_inventory_ratio
        
        # Adjust order sizes based on inventory skew
        buy_size_factor = 1.0 + min(0.5, max(-0.5, -inventory_skew * 2.0))
        sell_size_factor = 1.0 + min(0.5, max(-0.5, inventory_skew * 2.0))
        
        # Calculate sizes
        buy_size = base_size * Decimal(str(buy_size_factor))
        sell_size = base_size * Decimal(str(sell_size_factor))
        
        # Ensure minimum order size
        min_order_size = Decimal("0.001")
        buy_size = max(min_order_size, buy_size)
        sell_size = max(min_order_size, sell_size)
        
        return buy_size, sell_size
    
    def is_price_near_level(self, price: float, levels: List[float], threshold_pct: float = 0.01) -> bool:
        """Check if price is near any support/resistance level"""
        if not levels:
            return False
        
        for level in levels:
            if abs(price - level) / price < threshold_pct:
                return True
        
        return False
    
    def place_orders(self):
        """Create and place orders based on current market conditions"""
        connector = self.connectors[self.exchange]
        if not connector.ready:
            self.logger.error("Connector not ready")
            return
        
        # Get current price
        mid_price = connector.get_price_by_type(self.trading_pair, PriceType.MidPrice)
        if mid_price is None:
            self.logger.error("Unable to get mid price")
            return
        
        # Calculate dynamic spreads
        bid_spread, ask_spread = self.calculate_dynamic_spreads()
        
        # Calculate dynamic order sizes
        buy_amount, sell_amount = self.calculate_dynamic_order_size()
        
        # Calculate prices
        buy_price = mid_price * (Decimal("1") - bid_spread)
        sell_price = mid_price * (Decimal("1") + ask_spread)
        
        # Check if we're near support/resistance levels and adjust prices
        current_price = float(mid_price)
        
        # Adjust buy price if near support level
        if self.is_price_near_level(float(buy_price), self.support_levels):
            # If near support, we can be more aggressive with buy
            buy_price = buy_price * Decimal("1.001")  # Slightly higher price
        
        # Adjust sell price if near resistance level
        if self.is_price_near_level(float(sell_price), self.resistance_levels):
            # If near resistance, we can be more aggressive with sell
            sell_price = sell_price * Decimal("0.999")  # Slightly lower price
            
        # Check market regime and adjust strategy
        regime = self._market_regime["regime"]
        if regime == "volatile":
            # In volatile market, widen spreads for safety
            buy_price = buy_price * Decimal("0.995")
            sell_price = sell_price * Decimal("1.005")
        elif regime == "trending":
            # In trending market, adjust based on trend direction
            trend_direction = self._market_regime["trend_direction"]
            if trend_direction > 0:  # Uptrend
                # Be more aggressive with sells, conservative with buys
                buy_price = buy_price * Decimal("0.997")
                sell_price = sell_price * Decimal("1.003")
            else:  # Downtrend
                # Be more aggressive with buys, conservative with sells
                buy_price = buy_price * Decimal("1.003")
                sell_price = sell_price * Decimal("0.997")
        
        # Create order candidates
        buy_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=buy_amount,
            price=buy_price
        )
        
        sell_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=sell_amount,
            price=sell_price
        )
        
        # Adjust to available budget
        orders = self.adjust_proposal_to_budget([buy_order, sell_order])
        
        # Place orders
        for order in orders:
            self.place_order(order)
        
        # Log order details
        self.logger.info(f"Placed orders - Buy: {buy_amount}@{buy_price}, Sell: {sell_amount}@{sell_price}")
        self.logger.info(f"Market regime: {regime} | Inventory ratio: {self._current_inventory_ratio:.2f}")
    
    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        """Adjust order proposals to available budget"""
        adjusted = self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=False)
        return adjusted
    
    def place_order(self, order: OrderCandidate):
        """Place a single order"""
        try:
            if order.order_side == TradeType.BUY:
                self.buy(
                    connector_name=self.exchange,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    order_type=order.order_type,
                    price=order.price
                )
            else:
                self.sell(
                    connector_name=self.exchange,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    order_type=order.order_type,
                    price=order.price
                )
        except Exception as e:
            self.logger.error(f"Error placing order: {str(e)}")
    
    def cancel_all_orders(self):
        """Cancel all active orders"""
        for order in self.get_active_orders(connector_name=self.exchange):
            try:
                self.cancel(self.exchange, order.trading_pair, order.client_order_id)
            except Exception as e:
                self.logger.error(f"Error canceling order {order.client_order_id}: {str(e)}")
    
    def did_fill_order(self, event: OrderFilledEvent):
        """Handle order filled event"""
        # Log fill
        fill_info = f"{event.trade_type.name} {event.amount} {event.trading_pair} @ {event.price}"
        self.logger.info(f"Order filled: {fill_info}")
        
        # Record fill for stop-loss/take-profit tracking
        self.entry_prices[event.trading_pair] = event.price
        
        # Add to trade records
        self.trade_records.append({
            "time": self.current_timestamp,
            "trading_pair": event.trading_pair,
            "type": event.trade_type.name,
            "price": event.price,
            "amount": event.amount,
            "fee": event.trade_fee.flat_fees[0].amount if event.trade_fee.flat_fees else 0
        })
        
        # Check if we need to update inventory management
        self.update_inventory_ratio()
    
    def format_status(self) -> str:
        """Format status display"""
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        
        lines = []
        
        # Display balances
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        
        # Display active orders
        try:
            orders_df = self.active_orders_df()
            lines.extend(["", "  Active Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except Exception:
            lines.extend(["", "  No active orders."])
        
        # Display market indicators
        lines.extend(["\n  Market Indicators:"])
        lines.extend([f"    Market Regime: {self._market_regime['regime']} (Confidence: {self._market_regime['confidence']:.2f})"])
        lines.extend([f"    Trend Direction: {self._market_regime['trend_direction']}"])
        lines.extend([f"    Current Volatility: {self._current_volatility:.4f}"])
        
        # Display inventory status
        lines.extend(["\n  Inventory Management:"])
        lines.extend([f"    Current Ratio: {self._current_inventory_ratio:.4f} | Target: {self.target_inventory_ratio:.4f}"])
        lines.extend([f"    Inventory Skew: {self._current_inventory_ratio - self.target_inventory_ratio:.4f}"])
        
        # Display spread information
        bid_spread, ask_spread = self.calculate_dynamic_spreads()
        lines.extend(["\n  Current Spreads:"])
        lines.extend([f"    Bid Spread: {float(bid_spread) * 100:.4f}% | Ask Spread: {float(ask_spread) * 100:.4f}%"])
        
        # Display recent indicators
        if self.candles.candles_df is not None and not self.candles.candles_df.empty:
            df = self.get_candles_with_indicators()
            if df is not None and not df.empty:
                lines.extend(["\n  Recent Technical Indicators:"])
                
                # Get last row of indicators
                last_row = df.iloc[-1]
                
                # Display RSI
                rsi_col = f"RSI_{self.rsi_length}"
                if rsi_col in df.columns:
                    rsi = last_row[rsi_col]
                    lines.extend([f"    RSI: {rsi:.2f} ({'Overbought' if rsi > self.rsi_overbought else 'Oversold' if rsi < self.rsi_oversold else 'Neutral'})"])
                
                # Display EMA relationship
                short_col = f"EMA_{self.ema_short}"
                long_col = f"EMA_{self.ema_long}"
                if short_col in df.columns and long_col in df.columns:
                    ema_short = last_row[short_col]
                    ema_long = last_row[long_col]
                    ema_diff = (ema_short - ema_long) / ema_long * 100
                    lines.extend([f"    EMA Relationship: {ema_diff:.2f}% ({'Bullish' if ema_diff > 0 else 'Bearish'})"])
                
                # Display BB width as volatility indicator
                bb_upper = f"BBU_{self.bb_length}_{self.bb_std}"
                bb_lower = f"BBL_{self.bb_length}_{self.bb_std}"
                if bb_upper in df.columns and bb_lower in df.columns:
                    bb_width = (last_row[bb_upper] - last_row[bb_lower]) / last_row["close"] * 100
                    lines.extend([f"    BB Width: {bb_width:.2f}%"])
        
        return "\n".join(lines)
