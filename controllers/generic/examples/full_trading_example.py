from decimal import Decimal

from hummingbot.core.data_type.common import MarketDict, PriceType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, LimitChaserConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction


class FullTradingExampleConfig(ControllerConfigBase):
    controller_name: str = "examples.full_trading_example"
    connector_name: str = "binance_perpetual"
    trading_pair: str = "ETH-USDT"
    amount: Decimal = Decimal("0.1")
    spread: Decimal = Decimal("0.002")  # 0.2% spread
    max_open_orders: int = 3

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class FullTradingExample(ControllerBase):
    """
    Example controller demonstrating the full trading API built into ControllerBase.

    This controller shows how to use buy(), sell(), cancel(), open_orders(),
    and open_positions() methods for intuitive trading operations.
    """

    def __init__(self, config: FullTradingExampleConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

    async def update_processed_data(self):
        """Update market data for decision making."""
        mid_price = self.get_current_price(
            self.config.connector_name,
            self.config.trading_pair,
            PriceType.MidPrice
        )

        open_orders = self.open_orders(
            self.config.connector_name,
            self.config.trading_pair
        )

        open_positions = self.open_positions(
            self.config.connector_name,
            self.config.trading_pair
        )

        self.processed_data = {
            "mid_price": mid_price,
            "open_orders": open_orders,
            "open_positions": open_positions,
            "n_open_orders": len(open_orders)
        }

    def determine_executor_actions(self) -> list[ExecutorAction]:
        """
        Demonstrate different trading scenarios using the beautiful API.
        """
        actions = []
        mid_price = self.processed_data["mid_price"]
        n_open_orders = self.processed_data["n_open_orders"]

        # Scenario 1: Market buy with risk management
        if n_open_orders == 0:
            # Create a market buy with triple barrier for risk management
            triple_barrier = TripleBarrierConfig(
                stop_loss=Decimal("0.02"),      # 2% stop loss
                take_profit=Decimal("0.03"),    # 3% take profit
                time_limit=300                  # 5 minutes time limit
            )

            executor_id = self.buy(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                amount=self.config.amount,
                execution_strategy=ExecutionStrategy.MARKET,
                triple_barrier_config=triple_barrier,
                keep_position=True
            )

            self.logger().info(f"Created market buy order with triple barrier: {executor_id}")

        # Scenario 2: Limit orders with spread
        elif n_open_orders < self.config.max_open_orders:
            # Place limit buy below market
            buy_price = mid_price * (Decimal("1") - self.config.spread)
            buy_executor_id = self.buy(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                amount=self.config.amount,
                price=buy_price,
                execution_strategy=ExecutionStrategy.LIMIT_MAKER,
                keep_position=True
            )

            # Place limit sell above market
            sell_price = mid_price * (Decimal("1") + self.config.spread)
            sell_executor_id = self.sell(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                amount=self.config.amount,
                price=sell_price,
                execution_strategy=ExecutionStrategy.LIMIT_MAKER,
                keep_position=True
            )

            self.logger().info(f"Created limit orders - Buy: {buy_executor_id}, Sell: {sell_executor_id}")

        # Scenario 3: Limit chaser example
        elif n_open_orders < self.config.max_open_orders + 1:
            # Use limit chaser for better fill rates
            chaser_config = LimitChaserConfig(
                distance=Decimal("0.001"),         # 0.1% from best price
                refresh_threshold=Decimal("0.002")  # Refresh if price moves 0.2%
            )

            chaser_executor_id = self.buy(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                amount=self.config.amount,
                execution_strategy=ExecutionStrategy.LIMIT_CHASER,
                chaser_config=chaser_config,
                keep_position=True
            )

            self.logger().info(f"Created limit chaser order: {chaser_executor_id}")

        return actions  # Actions are handled automatically by the mixin

    def demonstrate_cancel_operations(self):
        """
        Example of how to use cancel operations.
        """
        # Cancel a specific order by executor ID
        open_orders = self.open_orders()
        if open_orders:
            executor_id = open_orders[0]['executor_id']
            success = self.cancel(executor_id)
            self.logger().info(f"Cancelled executor {executor_id}: {success}")

        # Cancel all orders for a specific trading pair
        cancelled_ids = self.cancel_all(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair
        )
        self.logger().info(f"Cancelled {len(cancelled_ids)} orders: {cancelled_ids}")

    def to_format_status(self) -> list[str]:
        """Display controller status with trading information."""
        lines = []

        if self.processed_data:
            mid_price = self.processed_data["mid_price"]
            open_orders = self.processed_data["open_orders"]
            open_positions = self.processed_data["open_positions"]

            lines.append("=== Beautiful Trading Example Controller ===")
            lines.append(f"Trading Pair: {self.config.trading_pair}")
            lines.append(f"Current Price: {mid_price:.6f}")
            lines.append(f"Open Orders: {len(open_orders)}")
            lines.append(f"Open Positions: {len(open_positions)}")

            if open_orders:
                lines.append("--- Open Orders ---")
                for order in open_orders:
                    lines.append(f"  {order['side']} {order['amount']:.4f} @ {order.get('price', 'MARKET')} "
                                 f"(Filled: {order['filled_amount']:.4f}) - {order['status']}")

            if open_positions:
                lines.append("--- Held Positions ---")
                for position in open_positions:
                    lines.append(f"  {position['side']} {position['amount']:.4f} @ {position['entry_price']:.6f} "
                                 f"(PnL: {position['pnl_percentage']:.2f}%)")

        return lines

    def get_custom_info(self) -> dict:
        """Return custom information for MQTT reporting."""
        if self.processed_data:
            return {
                "mid_price": float(self.processed_data["mid_price"]),
                "n_open_orders": len(self.processed_data["open_orders"]),
                "n_open_positions": len(self.processed_data["open_positions"]),
                "total_open_volume": sum(order["amount"] for order in self.processed_data["open_orders"])
            }
        return {}
