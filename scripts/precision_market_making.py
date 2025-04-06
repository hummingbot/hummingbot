import logging
from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd
import pandas_ta as ta  # For technical analysis

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory, CandlesConfig
from hummingbot.connector.connector_base import ConnectorBase

class PrecisionMarketMakingStrategy(ScriptStrategyBase):
    """
    Advanced Market Making Strategy incorporating:
    - Volatility-based spread adjustment using ATR
    - Trend analysis using RSI and MACD
    - Risk management with position limits
    - Multi-timeframe analysis
    """
    
    # Core parameters
    trading_pair = "ETH-USDT"
    exchange = "binance_paper_trade"
    order_refresh_time = 15  # seconds
    order_amount = Decimal("0.01")  # Base order size
    
    # Risk parameters
    max_position_pct = Decimal("0.5")  # Maximum position size as % of portfolio
    min_spread = Decimal("0.001")  # Minimum spread 0.1%
    max_spread = Decimal("0.05")  # Maximum spread 5%
    
    # Volatility parameters
    atr_length = 14
    volatility_multiplier = Decimal("1.5")
    
    # Trend parameters
    rsi_length = 14
    rsi_threshold_high = 70
    rsi_threshold_low = 30
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9
    
    # Market data timeframes
    primary_candles = None  # 1m candles
    secondary_candles = None  # 15m candles
    
    # Track timestamps
    create_timestamp = 0
    
    # Markets configuration
    markets = {exchange: {trading_pair}}
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.setup_market_data()
    
    def setup_market_data(self):
        """Initialize market data feeds"""
        # Primary timeframe for quick reactions (1m)
        self.primary_candles = CandlesFactory.get_candle(
            CandlesConfig(
                connector=self.exchange,
                trading_pair=self.trading_pair,
                interval="1m",
                max_records=100
            )
        )
        
        # Secondary timeframe for trend confirmation (15m)
        self.secondary_candles = CandlesFactory.get_candle(
            CandlesConfig(
                connector=self.exchange,
                trading_pair=self.trading_pair,
                interval="15m",
                max_records=100
            )
        )
        
        # Start the candles
        self.primary_candles.start()
        self.secondary_candles.start()
    
    def on_stop(self):
        """Clean up when strategy stops"""
        if self.primary_candles:
            self.primary_candles.stop()
        if self.secondary_candles:
            self.secondary_candles.stop()
    
    def on_tick(self):
        """Main strategy logic executed on each tick"""
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            
            # Create and execute order proposal
            proposal = self.create_proposal()
            proposal_adjusted = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            
            # Update timestamp for next order refresh
            self.create_timestamp = self.current_timestamp + self.order_refresh_time
    
    def calculate_dynamic_spreads(self) -> tuple[Decimal, Decimal]:
        """Calculate spreads based on market volatility"""
        df = self.primary_candles.candles_df
        if df.empty:
            return self.min_spread, self.min_spread
        
        # Calculate ATR
        df.ta.atr(length=self.atr_length, append=True)
        atr_col = f"ATR_{self.atr_length}"
        
        if atr_col not in df.columns or df[atr_col].isna().all():
            return self.min_spread, self.min_spread
        
        current_atr = df[atr_col].iloc[-1]
        avg_atr = df[atr_col].mean()
        
        # Calculate volatility multiplier
        vol_multiplier = Decimal(str(current_atr / avg_atr))
        base_spread = self.min_spread * vol_multiplier * self.volatility_multiplier
        
        # Ensure spread is within bounds
        adjusted_spread = min(max(base_spread, self.min_spread), self.max_spread)
        
        return adjusted_spread, adjusted_spread
    
    def analyze_market_trend(self) -> dict:
        """Analyze market trend using multiple indicators"""
        df = self.secondary_candles.candles_df
        if df.empty:
            return {"trend": "neutral", "strength": Decimal("0")}
        
        # Calculate RSI
        df.ta.rsi(length=self.rsi_length, append=True)
        rsi_col = f"RSI_{self.rsi_length}"
        
        # Calculate MACD
        macd_data = df.ta.macd(
            fast=self.macd_fast,
            slow=self.macd_slow,
            signal=self.macd_signal
        )
        df = pd.concat([df, macd_data], axis=1)
        
        if rsi_col not in df.columns:
            return {"trend": "neutral", "strength": Decimal("0")}
        
        current_rsi = df[rsi_col].iloc[-1]
        
        # Determine trend
        trend = "neutral"
        if current_rsi > self.rsi_threshold_high:
            trend = "overbought"
        elif current_rsi < self.rsi_threshold_low:
            trend = "oversold"
        
        # Calculate trend strength (0-1)
        trend_strength = Decimal(str(abs(current_rsi - 50) / 50))
        
        return {
            "trend": trend,
            "strength": trend_strength
        }
    
    def calculate_order_size(self, base_size: Decimal) -> Decimal:
        """Adjust order size based on position and risk parameters"""
        # Get current position
        base_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[0])
        quote_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[1])
        
        # Calculate position value in quote currency
        current_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        position_value = (base_balance * current_price) + quote_balance
        
        # Calculate maximum position size
        max_position_size = position_value * self.max_position_pct
        
        # Adjust order size based on current position
        return min(base_size, max_position_size / current_price)
    
    def create_proposal(self) -> List[OrderCandidate]:
        """Create order proposals based on market analysis"""
        # Get market analysis
        spreads = self.calculate_dynamic_spreads()
        trend = self.analyze_market_trend()
        
        # Get reference price
        ref_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, PriceType.MidPrice)
        
        # Adjust spreads based on trend
        bid_spread, ask_spread = spreads
        if trend["trend"] == "overbought":
            # Wider ask spread, tighter bid spread when overbought
            ask_spread = ask_spread * (Decimal("1") + trend["strength"])
            bid_spread = bid_spread * (Decimal("1") - trend["strength"] * Decimal("0.5"))
        elif trend["trend"] == "oversold":
            # Wider bid spread, tighter ask spread when oversold
            bid_spread = bid_spread * (Decimal("1") + trend["strength"])
            ask_spread = ask_spread * (Decimal("1") - trend["strength"] * Decimal("0.5"))
        
        # Calculate order prices
        buy_price = ref_price * (Decimal("1") - bid_spread)
        sell_price = ref_price * (Decimal("1") + ask_spread)
        
        # Calculate order size
        order_size = self.calculate_order_size(self.order_amount)
        
        # Create order candidates
        buy_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=order_size,
            price=buy_price
        )
        
        sell_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=order_size,
            price=sell_price
        )
        
        return [buy_order, sell_order]
    
    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        """Adjust order proposals to account for available budget"""
        return self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
    
    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        """Place orders from proposal"""
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
    
    def cancel_all_orders(self):
        """Cancel all active orders"""
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)
    
    def did_fill_order(self, event: OrderFilledEvent):
        """Callback when order is filled"""
        msg = (
            f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} "
            f"{self.exchange} at {round(event.price, 2)}"
        )
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
    
    def format_status(self) -> str:
        """Format strategy status for display"""
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        
        lines = []
        
        # Get balances
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        
        # Get active orders
        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])
        
        # Get market analysis
        spreads = self.calculate_dynamic_spreads()
        trend = self.analyze_market_trend()
        
        lines.extend(["\n----------------------------------------------------------------------\n"])
        lines.extend(["  Market Analysis:"])
        lines.extend([f"  Bid Spread: {spreads[0]:.4%} | Ask Spread: {spreads[1]:.4%}"])
        lines.extend([f"  Trend: {trend['trend']} | Strength: {float(trend['strength']):.2%}"])
        
        # Show recent candles
        if self.primary_candles and not self.primary_candles.candles_df.empty:
            lines.extend(["\n  Recent Price Action (1m):"])
            recent_candles = self.primary_candles.candles_df.tail(5).iloc[::-1]
            lines.extend(["    " + line for line in recent_candles.to_string(index=False).split("\n")])
        
        return "\n".join(lines)