import logging
from decimal import Decimal
from typing import Dict, List

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.event.events import OrderFilledEvent, BuyOrderCompletedEvent, SellOrderCompletedEvent


class RebalancingMarketMakingStrategy(ScriptStrategyBase):
    """
    Rebalancing Market Making (RMM) Strategy
    This strategy aims to maintain a target inventory ratio by placing orders that rebalance the portfolio.
    """
    # Define the trading pair and exchange
    trading_pair = "INJ-USDT"
    exchange = "binance_paper_trade"

    # Strategy parameters
    inventory_target_base_pct = Decimal("0.7")  # Target base asset percentage (50%)
    threshold = Decimal("0.001")  # Threshold for rebalancing (1%)
    initial_rebalance_spread = Decimal("0.00")  # Spread for initial rebalance order (0.05%)
    order_refresh_time = 3600  # Time in seconds before refreshing orders

    # Define the market for the strategy
    markets = {exchange: {trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        # Initialize counters for tracking orders and volumes
        self.total_sell_volume = 0
        self.total_buy_volume = 0
        self.total_sell_orders = 0
        self.total_buy_orders = 0
        self.create_timestamp = 0

    def on_tick(self):
        # Check if it's time to refresh orders
        if self.create_timestamp <= self.current_timestamp:
            # Cancel all existing orders
            self.cancel_all_orders()
            # Create a new order proposal
            proposal: List[OrderCandidate] = self.create_proposal()
            # Adjust the proposal to fit within the available budget
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            # Place the adjusted orders
            self.place_orders(proposal_adjusted)
            # Set the next order refresh time
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

    def create_proposal(self) -> List[OrderCandidate]:
        # Calculate the current inventory ratio
        current_inventory_ratio = self.calculate_inventory_ratio()
        # Get the current mid-price
        mid_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)

        if self.is_within_range(current_inventory_ratio):
            # Scenario B: Create balanced orders
            # Calculate buy and sell prices based on the threshold
            buy_price = mid_price * (Decimal("1") - self.threshold)
            sell_price = mid_price * (Decimal("1") + self.threshold)
            # Calculate the order amount
            amount = self.calculate_order_amount()

            # Create buy and sell order candidates
            buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                       order_side=TradeType.BUY, amount=amount, price=buy_price)
            sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                        order_side=TradeType.SELL, amount=amount, price=sell_price)
            return [buy_order, sell_order]
        else:
            # Scenario A: Create rebalance order
            # Determine if we need to buy or sell to rebalance
            is_buy = current_inventory_ratio < self.inventory_target_base_pct
            # Calculate the rebalance price with the initial spread
            rebalance_price = mid_price * (Decimal("1") - self.initial_rebalance_spread if is_buy
                                           else Decimal("1") + self.initial_rebalance_spread)
            # Calculate the amount needed to rebalance
            amount = self.calculate_rebalance_amount(current_inventory_ratio)

            # Create the rebalance order candidate
            rebalance_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                             order_side=TradeType.BUY if is_buy else TradeType.SELL,
                                             amount=amount, price=rebalance_price)
            return [rebalance_order]

    def calculate_inventory_ratio(self) -> Decimal:
        # Get the available balances
        base_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[0])
        quote_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[1])
        # Get the current mid-price
        mid_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        # Calculate the total portfolio value in terms of the base asset
        total_value = base_balance + quote_balance / mid_price
        # Calculate and return the inventory ratio
        return base_balance / total_value if total_value > 0 else Decimal("0")

    def is_within_range(self, current_ratio: Decimal) -> bool:
        # Check if the current ratio is within the target range
        return (self.inventory_target_base_pct - self.threshold
                <= current_ratio
                <= self.inventory_target_base_pct + self.threshold)

    def calculate_order_amount(self) -> Decimal:
        # Get the available balances
        base_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[0])
        quote_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[1])
        # Get the current mid-price
        mid_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        # Calculate the total portfolio value in terms of the base asset
        total_value = base_balance + quote_balance / mid_price
        # Calculate the order amount as a fraction of the total value
        return (total_value * self.threshold) / Decimal("2")

    def calculate_rebalance_amount(self, current_ratio: Decimal) -> Decimal:
        # Get the available balances
        base_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[0])
        quote_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[1])
        # Get the current mid-price
        mid_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        # Calculate the total portfolio value in terms of the base asset
        total_value = base_balance + quote_balance / mid_price
        # Calculate the target base asset amount
        target_base_amount = total_value * self.inventory_target_base_pct
        # Calculate the amount needed to rebalance
        return abs(target_base_amount - base_balance)

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        # Adjust the order proposal to fit within the available budget
        return self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            if order.amount > 0:
                # Place the order if the amount is greater than zero
                self.buy(self.exchange, order.trading_pair, order.amount, order.order_type, order.price) if order.order_side == TradeType.BUY else self.sell(self.exchange, order.trading_pair, order.amount, order.order_type, order.price)
            else:
                # Log a message if there's not enough balance to place the order
                self.logger().info(f"Not enough balance to place the {order.order_side} order")

    def cancel_all_orders(self):
        # Cancel all active orders
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        # Log the filled order details
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.exchange} "
               f"at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        # Update the total buy/sell volumes
        self.total_buy_volume += event.amount if event.trade_type == TradeType.BUY else 0
        self.total_sell_volume += event.amount if event.trade_type == TradeType.SELL else 0

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        # Increment the total buy orders counter
        self.total_buy_orders += 1

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        # Increment the total sell orders counter
        self.total_sell_orders += 1

    def format_status(self) -> str:
        # Check if the strategy is ready to trade
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        # Add balance information to the status
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        # Add active orders information to the status
        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active orders."])

        # Add strategy performance metrics to the status
        mid_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        current_inventory_ratio = self.calculate_inventory_ratio()
        lines.extend(["\n----------------------------------------------------"])
        lines.extend([f"  Inventory Target: {self.inventory_target_base_pct:.1%}"])
        lines.extend([f"  Current Inventory Ratio: {current_inventory_ratio:.1%}"])
        lines.extend([f"  Threshold: {self.threshold:.1%}"])
        lines.extend([f"  Mid Price: {mid_price:.4f}"])
        lines.extend([f"  Total Buy Orders: {self.total_buy_orders} | Total Sell Orders: {self.total_sell_orders}"])
        lines.extend([f"  Total Buy Volume: {self.total_buy_volume:.4f} | Total Sell Volume: {self.total_sell_volume:.4f}"])
        lines.extend(["----------------------------------------------------"])

        # Return the formatted status string
        return "\n".join(lines)
