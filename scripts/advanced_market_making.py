import logging
from decimal import Decimal
from typing import Dict, List

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory, CandlesConfig
from hummingbot.connector.connector_base import ConnectorBase

class AdvancedMarketMaking(ScriptStrategyBase):
    """
    Advanced Market Making Strategy for BITS GOA Assignment
    
    This strategy combines:
    1. Dynamic spread adjustment based on volatility (using NATR)
    2. Trend analysis using RSI and moving averages
    3. Risk management through inventory control
    4. Dynamic order sizing based on volatility and inventory
    """
    
    # Basic strategy parameters
    bid_spread = 0.0001
    ask_spread = 0.0001
    order_refresh_time = 15  # in seconds
    order_amount = 0.01
    max_order_age = 300  # in seconds
    create_timestamp = 0
    trading_pair = "ETH-USDT"  # default, can be changed
    exchange = "binance_paper_trade"  # default, can be changed
    price_source = PriceType.MidPrice
    
    # Parse trading pair to get base and quote
    base, quote = trading_pair.split('-')
    
    # Candles configuration
    candle_exchange = "binance"
    candles_interval = "1m"  # Use 1-minute candles for quick response
    candles_length = 30  # Look back 30 candles for indicators
    max_records = 1000  # Maximum number of candle records to store
    
    # Volatility parameters
    bid_spread_scalar = 120  # Higher scalar for bid (buying) to be more conservative
    ask_spread_scalar = 60   # Lower scalar for ask (selling) to be more aggressive in selling
    
    # Trend analysis parameters
    trend_window_short = 8   # Short-term EMA window
    trend_window_medium = 21 # Medium-term EMA window
    trend_window_long = 55   # Long-term EMA window
    rsi_window = 14          # Standard RSI window
    # RSI thresholds
    rsi_overbought = 70
    rsi_oversold = 30
    
    # Price shift parameters
    max_shift_spread = 0.00001  # Maximum allowed price shift (in %)
    price_multiplier = 1
    trend_scalar = -1  # Negative means we're contrarian (sell in uptrend, buy in downtrend)
    
    # Inventory management parameters
    target_base_ratio = 0.5  # Target inventory ratio (50% base, 50% quote)
    current_base_ratio = 0.5  # Will be calculated in runtime
    inventory_range_multiplier = 3.0  # How strongly to adjust for inventory imbalance
    min_order_amount = 0.001  # Minimum order size
    max_order_amount = 0.1    # Maximum order size
    order_adjustment_factor = 0.8  # Factor to adjust order size based on volatility
    
    # Risk management parameters
    max_position_value = 1000.0  # Maximum position value in quote currency
    stop_loss_pct = 0.05         # Stop loss at 5% adverse move
    take_profit_pct = 0.10       # Take profit at 10% favorable move
    max_open_orders = 10         # Maximum number of open orders
    
    # Initialize candles
    candles = CandlesFactory.get_candle(CandlesConfig(
        connector=candle_exchange,
        trading_pair=trading_pair,
        interval=candles_interval,
        max_records=max_records
    ))
    
    # Define markets to connect to
    markets = {exchange: {trading_pair}}
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.candles.start()
        self.last_processed_candle = None
        self.avg_volatility = 0
        self.stop_loss_activated = False
        self.take_profit_activated = False
        
        # Store trade entry prices for stop loss/take profit calculations
        self.trade_entry_prices = {}
        self.trading_pairs_suspended = set()
        
        self.log_with_clock(logging.INFO, "Advanced Market Making Strategy initialized.")
        self.notify_hb_app_with_timestamp("Advanced Market Making Strategy initialized.")
    
    def on_stop(self):
        """Stop the strategy and release resources."""
        self.candles.stop()
        self.log_with_clock(logging.INFO, "Strategy stopped.")
    
    def on_tick(self):
        """
        This function is called frequently and is the main operation function of the strategy.
        It performs the core logic of the strategy including:
        - Cancelling old orders
        - Updating market parameters
        - Creating new order proposals
        - Placing orders
        """
        if self.create_timestamp <= self.current_timestamp:
            # Cancel all existing orders
            self.cancel_all_orders()
            
            # Check if we should update our indicators and create new orders
            candles_df = self.get_candles_with_features()
            if candles_df is not None and not candles_df.empty:
                # Update market parameters
                self.update_market_parameters(candles_df)
                
                # Check stop loss and take profit conditions
                if self.check_risk_conditions():
                    # Create new order proposals
                    proposal: List[OrderCandidate] = self.create_proposal()
                    
                    # Adjust proposals to available budget
                    proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
                    
                    # Place the orders
                    self.place_orders(proposal_adjusted)
            
            # Set timestamp for next order refresh
            self.create_timestamp = self.order_refresh_time + self.current_timestamp
    
    def get_candles_with_features(self):
        """
        Enhance candles dataframe with technical indicators.
        """
        if self.candles.candles_df is None or self.candles.candles_df.empty:
            return None
        
        candles_df = self.candles.candles_df.copy()
        
        # Add Normalized Average True Range for volatility
        candles_df.ta.natr(length=self.candles_length, scalar=1, append=True)
        
        # Add RSI for trend detection
        candles_df.ta.rsi(length=self.rsi_window, append=True)
        
        # Add EMAs for trend detection
        candles_df.ta.ema(length=self.trend_window_short, append=True)
        candles_df.ta.ema(length=self.trend_window_medium, append=True)
        candles_df.ta.ema(length=self.trend_window_long, append=True)
        
        # Add Bollinger Bands for volatility-based boundaries
        candles_df.ta.bbands(length=20, std=2, append=True)
        
        # Calculate bid and ask spreads based on volatility
        candles_df['bid_spread_bps'] = candles_df[f"NATR_{self.candles_length}"] * self.bid_spread_scalar * 10000
        candles_df['ask_spread_bps'] = candles_df[f"NATR_{self.candles_length}"] * self.ask_spread_scalar * 10000
        
        # Add MACD for additional trend confirmation
        candles_df.ta.macd(fast=12, slow=26, signal=9, append=True)
        
        return candles_df
    
    def update_market_parameters(self, candles_df):
        """
        Update market parameters based on the latest candle data.
        This includes spreads, multipliers, and inventory ratios.
        """
        if candles_df.empty:
            return
        
        # Update spreads based on volatility
        natr_value = candles_df[f"NATR_{self.candles_length}"].iloc[-1]
        self.bid_spread = max(0.0001, natr_value * self.bid_spread_scalar)
        self.ask_spread = max(0.0001, natr_value * self.ask_spread_scalar)
        
        # Store average volatility for order sizing
        self.avg_volatility = natr_value
        
        # Update trend multiplier based on RSI
        rsi = candles_df[f"RSI_{self.rsi_window}"].iloc[-1]
        self.price_multiplier = (rsi - 50) / 50 * self.max_shift_spread * self.trend_scalar
        
        # Update inventory ratios
        base_bal = self.connectors[self.exchange].get_balance(self.base)
        base_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        base_bal_in_quote = base_bal * base_price
        quote_bal = self.connectors[self.exchange].get_balance(self.quote)
        total_value = base_bal_in_quote + quote_bal
        
        if total_value > 0:
            self.current_base_ratio = float(base_bal_in_quote / total_value)
        else:
            self.current_base_ratio = 0.5  # Default to balanced if no funds
        
        # Calculate inventory skew multiplier
        delta = ((self.target_base_ratio - self.current_base_ratio) / self.target_base_ratio)
        inventory_delta = max(-1, min(1, delta))
        inventory_multiplier = inventory_delta * self.max_shift_spread * self.inventory_range_multiplier
        
        # Calculate adjusted reference price
        orig_price = base_price
        self.reference_price = orig_price * Decimal(str(1 + self.price_multiplier)) * Decimal(str(1 + inventory_multiplier))
        
        # Log parameter updates
        self.log_with_clock(
            logging.INFO,
            f"Parameters updated: Bid Spread: {self.bid_spread:.6f}, Ask Spread: {self.ask_spread:.6f}, "
            f"Base Ratio: {self.current_base_ratio:.4f}, Reference Price: {self.reference_price:.4f}"
        )
    
    def check_risk_conditions(self):
        """
        Check risk conditions like stop loss and take profit.
        Returns True if it's safe to continue trading, False if trading should stop.
        """
        # Check if any trading pair is suspended
        if self.trading_pair in self.trading_pairs_suspended:
            return False
        
        # Get current price
        current_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        
        # Check stop loss condition
        if self.trading_pair in self.trade_entry_prices:
            entry_price = self.trade_entry_prices[self.trading_pair]
            
            # For long positions (we own base currency)
            if self.current_base_ratio > self.target_base_ratio:
                if current_price < entry_price * (1 - self.stop_loss_pct):
                    self.log_with_clock(logging.WARNING, f"Stop loss triggered for {self.trading_pair}")
                    self.trading_pairs_suspended.add(self.trading_pair)
                    return False
                elif current_price > entry_price * (1 + self.take_profit_pct):
                    self.log_with_clock(logging.INFO, f"Take profit triggered for {self.trading_pair}")
                    # We don't suspend trading, just note the take profit
                    self.take_profit_activated = True
            
            # For short positions (we own quote currency)
            else:
                if current_price > entry_price * (1 + self.stop_loss_pct):
                    self.log_with_clock(logging.WARNING, f"Stop loss triggered for {self.trading_pair}")
                    self.trading_pairs_suspended.add(self.trading_pair)
                    return False
                elif current_price < entry_price * (1 - self.take_profit_pct):
                    self.log_with_clock(logging.INFO, f"Take profit triggered for {self.trading_pair}")
                    # We don't suspend trading, just note the take profit
                    self.take_profit_activated = True
        
        # Check if we have too many open orders
        if len(self.get_active_orders(connector_name=self.exchange)) >= self.max_open_orders:
            self.log_with_clock(logging.WARNING, f"Maximum open orders reached ({self.max_open_orders})")
            return False
        
        return True
    
    def calculate_dynamic_order_amount(self):
        """
        Calculate dynamic order amount based on volatility and inventory.
        Higher volatility = smaller orders
        Further from target inventory = larger rebalancing orders
        """
        # Base amount on volatility
        volatility_factor = max(0.2, 1.0 - self.avg_volatility * 20)  # Reduce size as volatility increases
        
        # Adjust based on inventory imbalance (larger orders when further from target)
        inventory_deviation = abs(self.current_base_ratio - self.target_base_ratio)
        inventory_factor = 1.0 + (inventory_deviation * 2)  # Increase size with deviation
        
        # Calculate dynamic amount within bounds
        dynamic_amount = self.order_amount * volatility_factor * inventory_factor * self.order_adjustment_factor
        
        # Ensure within min/max bounds
        dynamic_amount = max(self.min_order_amount, min(self.max_order_amount, dynamic_amount))
        
        return Decimal(str(dynamic_amount))
    
    def create_proposal(self) -> List[OrderCandidate]:
        """
        Create buy and sell order proposals.
        """
        # Get the best bid and ask from the order book
        best_bid = self.connectors[self.exchange].get_price(self.trading_pair, False)
        best_ask = self.connectors[self.exchange].get_price(self.trading_pair, True)
        
        # Calculate our buy and sell prices based on spreads and reference price
        buy_price = min(self.reference_price * Decimal(1 - self.bid_spread), best_bid)
        sell_price = max(self.reference_price * Decimal(1 + self.ask_spread), best_ask)
        
        # Calculate dynamic order amount
        order_amount = self.calculate_dynamic_order_amount()
        
        # Adjust order amount based on inventory skew
        inventory_skew = self.current_base_ratio - self.target_base_ratio
        buy_amount = order_amount * Decimal(1.0 + min(0.5, max(-0.5, -inventory_skew)))
        sell_amount = order_amount * Decimal(1.0 + min(0.5, max(-0.5, inventory_skew)))
        
        # Create the order candidates
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
        
        return [buy_order, sell_order]
    
    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        """
        Adjust the order proposals to the available budget.
        """
        proposal_adjusted = self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=False)
        return proposal_adjusted
    
    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        """
        Place orders on the exchange.
        """
        for order in proposal:
            self.place_order(connector_name=self.exchange, order=order)
    
    def place_order(self, connector_name: str, order: OrderCandidate):
        """
        Place a single order on the exchange.
        """
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price
            )
        elif order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price
            )
    
    def cancel_all_orders(self):
        """
        Cancel all active orders.
        """
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)
    
    def did_fill_order(self, event: OrderFilledEvent):
        """
        Handle order filled events.
        """
        # Log the fill event
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.exchange} at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
        
        # Record entry price for stop loss / take profit
        self.trade_entry_prices[event.trading_pair] = event.price
    
    def format_status(self) -> str:
        """
        Returns status of the strategy with detailed information.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        
        lines = []
        
        # Display balances
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        
        # Display active orders
        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])
        
        # Display spread information
        ref_price = self.reference_price
        best_bid = self.connectors[self.exchange].get_price(self.trading_pair, False)
        best_ask = self.connectors[self.exchange].get_price(self.trading_pair, True)
        best_bid_spread = (ref_price - best_bid) / ref_price
        best_ask_spread = (best_ask - ref_price) / ref_price
        
        lines.extend(["\n----------------------------------------------------------------------\n"])
        lines.extend(["  Spreads:"])
        lines.extend([f"  Bid Spread (bps): {self.bid_spread * 10000:.4f} | Best Bid Spread (bps): {best_bid_spread * 10000:.4f}"])
        lines.extend([f"  Ask Spread (bps): {self.ask_spread * 10000:.4f} | Best Ask Spread (bps): {best_ask_spread * 10000:.4f}"])
        
        # Display inventory management information
        lines.extend(["\n----------------------------------------------------------------------\n"])
        lines.extend(["  Inventory Management:"])
        lines.extend([f"  Target Base Ratio: {self.target_base_ratio:.4f} | Current Base Ratio: {self.current_base_ratio:.4f}"])
        lines.extend([f"  Inventory Skew: {self.current_base_ratio - self.target_base_ratio:.4f}"])
        
        # Display risk management information
        lines.extend(["\n----------------------------------------------------------------------\n"])
        lines.extend(["  Risk Management:"])
        lines.extend([f"  Stop Loss: {self.stop_loss_pct * 100:.2f}% | Take Profit: {self.take_profit_pct * 100:.2f}%"])
        lines.extend([f"  Stop Loss Activated: {self.stop_loss_activated} | Take Profit Activated: {self.take_profit_activated}"])
        
        # Display indicators and candles
        lines.extend(["\n----------------------------------------------------------------------\n"])
        candles_df = self.get_candles_with_features()
        if candles_df is not None and not candles_df.empty:
            lines.extend([f"  Candles: {self.candles.name} | Interval: {self.candles.interval}", ""])
            
            # Get relevant indicators for display
            display_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                               f"RSI_{self.rsi_window}", f"NATR_{self.candles_length}",
                               f"EMA_{self.trend_window_short}", f"EMA_{self.trend_window_medium}"]
            
            # Filter to display only existing columns
            display_columns = [col for col in display_columns if col in candles_df.columns]
            
            # Display last 5 candles with indicators
            lines.extend(["    " + line for line in candles_df[display_columns].tail(5).iloc[::-1].to_string(index=False).split("\n")])
        
        return "\n".join(lines)
