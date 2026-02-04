"""
Direct WEEX Exchange Order Check
=================================
Queries the WEEX API directly to see what orders are actually on the exchange,
bypassing Hummingbot's internal order tracker.

This helps diagnose tracking issues by comparing:
- What the tracker thinks (in-memory state)
- What's actually on the exchange (API reality)
"""
from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class WeexCheckLiveOrders(ScriptStrategyBase):
    """
    One-time check of actual orders on WEEX exchange via API.
    Compares tracker state vs exchange reality.
    """
    markets = {"weex": {"VCC-USDT"}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self._check_complete = False

    def on_tick(self):
        """Check orders once and exit"""
        if self._check_complete:
            return

        weex = self.connectors.get("weex")
        if not weex or not weex.ready:
            self.logger().info("⏳ Waiting for WEEX connector to be ready...")
            return

        # Run async check
        safe_ensure_future = self.safe_ensure_future  # noqa
        safe_ensure_future(self._check_orders())

        self._check_complete = True
        # Stop after check completes
        self._clock.stop()

    async def _check_orders(self):
        """Query WEEX API directly for open orders"""
        weex = self.connectors["weex"]

        separator = "=" * 70
        divider = "-" * 70

        self.logger().info(f"\n{separator}")
        self.logger().info("WEEX EXCHANGE ORDER VERIFICATION")
        self.logger().info(separator)

        # 1. Check what the tracker thinks
        self.logger().info("\n📊 IN-MEMORY TRACKER STATE:")
        self.logger().info(divider)

        active_orders = self.get_active_orders(connector_name="weex")
        if active_orders:
            self.logger().info(f"  Tracker shows {len(active_orders)} active orders:")
            for order in active_orders:
                side = "BUY " if order.is_buy else "SELL"
                self.logger().info(f"    {side} {order.quantity:>10.2f} VCC @ {order.price:.8f}")
        else:
            self.logger().info("  ⚠️  Tracker shows NO active orders")

        # 2. Query exchange directly via API
        self.logger().info("\n🌐 LIVE EXCHANGE API QUERY:")
        self.logger().info(divider)

        try:
            # Use the connector's API method to get open orders from exchange
            # This bypasses the tracker and hits the actual WEEX API
            from hummingbot.connector.exchange.weex import weex_constants as CONSTANTS

            symbol = await weex.exchange_symbol_associated_to_pair(trading_pair="VCC-USDT")

            # Direct API call to get open orders
            api_response = await weex._api_get(
                path_url=CONSTANTS.OPEN_ORDERS_PATH_URL,
                params={"symbol": symbol},
                is_auth_required=True,
                limit_id=CONSTANTS.OPEN_ORDERS_LIMIT_ID
            )

            # Parse response
            orders_data = api_response.get("data", []) if isinstance(api_response, dict) else []

            if orders_data:
                self.logger().info(f"  ✅ Exchange has {len(orders_data)} LIVE orders:")

                buy_orders = []
                sell_orders = []

                for order in orders_data:
                    order_id = order.get("orderId", "unknown")
                    client_order_id = order.get("clientOrderId", "N/A")
                    side = order.get("side", "").upper()
                    price = Decimal(str(order.get("price", 0)))
                    quantity = Decimal(str(order.get("quantity", 0)))
                    filled = Decimal(str(order.get("filledQuantity", 0)))
                    status = order.get("status", "unknown")

                    order_info = {
                        "price": price,
                        "quantity": quantity,
                        "filled": filled,
                        "status": status,
                        "client_id": client_order_id,
                        "exchange_id": order_id
                    }

                    if side == "BUY":
                        buy_orders.append(order_info)
                    else:
                        sell_orders.append(order_info)

                # Display buy orders
                if buy_orders:
                    self.logger().info(f"\n  BUY ORDERS ({len(buy_orders)}):")
                    for o in sorted(buy_orders, key=lambda x: x["price"], reverse=True):
                        self.logger().info(
                            f"    {o['price']:.8f} × {o['quantity']:>10.2f} VCC "
                            f"(filled: {o['filled']:.2f}, status: {o['status']})"
                        )
                        self.logger().info(f"      Client ID: {o['client_id']}")

                # Display sell orders
                if sell_orders:
                    self.logger().info(f"\n  SELL ORDERS ({len(sell_orders)}):")
                    for o in sorted(sell_orders, key=lambda x: x["price"]):
                        self.logger().info(
                            f"    {o['price']:.8f} × {o['quantity']:>10.2f} VCC "
                            f"(filled: {o['filled']:.2f}, status: {o['status']})"
                        )
                        self.logger().info(f"      Client ID: {o['client_id']}")

            else:
                self.logger().info("  ⚠️  Exchange API returned NO open orders")
                self.logger().info("  (All orders have been filled or canceled)")

        except Exception as e:
            self.logger().error(f"  ✗ Error querying exchange API: {e}", exc_info=True)

        # 3. Comparison summary
        self.logger().info("\n📋 DIAGNOSIS:")
        self.logger().info(divider)

        tracker_count = len(active_orders)
        exchange_count = len(orders_data) if orders_data else 0

        if tracker_count == exchange_count:
            self.logger().info(f"  ✅ MATCH: Both tracker and exchange show {tracker_count} orders")
        else:
            self.logger().info("  ⚠️  MISMATCH:")
            self.logger().info(f"     Tracker:  {tracker_count} orders")
            self.logger().info(f"     Exchange: {exchange_count} orders")

            if exchange_count > tracker_count:
                self.logger().info("\n  🔍 POSSIBLE CAUSES:")
                self.logger().info("     • Orders created outside this bot session")
                self.logger().info("     • Tracker not receiving WebSocket updates")
                self.logger().info("     • Order creation confirmed but tracker not updated")
                self.logger().info("     • Multiple bots running with same API keys")
            elif tracker_count > exchange_count:
                self.logger().info("\n  🔍 POSSIBLE CAUSES:")
                self.logger().info("     • Orders canceled on exchange but tracker not notified")
                self.logger().info("     • WebSocket disconnection missed cancel events")
                self.logger().info("     • Orders filled but tracker state stale")

        self.logger().info(f"\n{separator}")

        # Stop the strategy
        self.stop()

    def on_status(self):
        return "Checking live orders on WEEX exchange..."
