"""
WEEX Account Monitoring Script
===============================
Uses read-only monitoring API keys to track account status.

This script can be run independently or as a Hummingbot strategy
to monitor your WEEX accounts without any trading capabilities.

Usage:
    1. Configure with your monitoring API keys (read-only)
    2. Run: import weex_monitor
    3. The script will display account status and exit
"""
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class WeexMonitorConfig(BaseClientModel):
    """Configuration for WEEX monitoring"""
    script_file_name: str = os.path.basename(__file__)
    exchange: str = Field(default="weex", description="Exchange name")
    trading_pair: str = Field(default="VCC-USDT", description="Trading pair to monitor (Hummingbot format: BASE-QUOTE)")
    monitoring_interval_seconds: int = Field(default=0, description="Monitoring interval (0 = one-time check)")


def to_weex_symbol(hb_pair: str) -> str:
    """Convert Hummingbot trading pair (e.g., VCC-USDT) to WEEX format (e.g., VCCUSDT-SPBL)"""
    if "-" in hb_pair:
        base, quote = hb_pair.split("-")
        return f"{base}{quote}-SPBL".replace("-", "")
    return hb_pair


class WeexMonitor(ScriptStrategyBase):
    """
    Monitoring bot for WEEX accounts.

    Uses read-only API keys to check:
    - Account balances
    - Open orders
    - Recent trades
    - Daily volume
    - P&L estimates
    """

    # Default markets (can be overridden by config)
    # NOTE: Use Hummingbot format (BASE-QUOTE), not WEEX format (BASEQUOTE_SPBL)
    markets = {"weex": {"VCC-USDT"}}

    @classmethod
    def init_markets(cls, config: WeexMonitorConfig):
        # Config should use Hummingbot format (BASE-QUOTE)
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: WeexMonitorConfig):
        super().__init__(connectors)
        self.config = config
        self._last_check_time = 0
        self._initial_balances = {}
        self._trade_count = 0
        self._volume_24h = Decimal("0")
        self._health_file = "/tmp/weex_mm_health.json"
        # Bypass ready check - we'll check manually
        self.ready_to_trade = True

        # DEBUG: Log connector info
        self.logger().info(f"WeexMonitor.__init__ called with {len(connectors)} connectors: {list(connectors.keys())}")
        for name, conn in connectors.items():
            self.logger().info(f"  Connector '{name}': type={type(conn).__name__}, ready={conn.ready}")
            self.logger().info(f"  Connector trading_pairs: {conn.trading_pairs}")
            self.logger().info(f"  Connector status_dict: {conn.status_dict}")

    def on_tick(self):
        """
        Main monitoring loop
        """
        current_time = self.current_timestamp

        # Check connector readiness
        weex = self.connectors.get("weex")
        if not weex:
            self.logger().warning("⚠️  WEEX connector not found")
            return

        # Wait for connector to be ready
        if not weex.ready:
            # Log waiting message periodically (every 5 seconds)
            if not hasattr(self, '_ready_wait_last_log') or current_time - self._ready_wait_last_log > 5:
                self.logger().info("⏳ Waiting for WEEX connector to initialize...")
                self.logger().info(f"   Status: {weex.status_dict}")
                self._ready_wait_last_log = current_time
            return

        # Check if enough time has passed (or first run)
        if current_time - self._last_check_time < self.config.monitoring_interval_seconds:
            return

        self._last_check_time = current_time

        # Run monitoring check
        self._run_monitoring_check()

        # For monitoring, run continuously
        self.logger().info(f"\nℹ️  Next update in {self.config.monitoring_interval_seconds} seconds. Press Ctrl+C to stop.")

    def _run_monitoring_check(self):
        """
        Execute monitoring checks and display results
        """
        weex = self.connectors.get("weex")

        if not weex:
            self.logger().warning("⚠️  WEEX connector not found in connectors dict")
            self._write_health_file(healthy=False, issues=["Connector not found"])
            return

        # Display header
        self.logger().info("\n" + "=" * 70)
        self.logger().info("  WEEX ACCOUNT MONITORING DASHBOARD")
        self.logger().info("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.logger().info(f"  Connector ready: {weex.ready}")
        self.logger().info("=" * 70)

        # Collect health info
        issues = []

        # 1. Check balances
        self._display_balances(weex)

        # 2. Check open orders
        self._display_open_orders(weex)

        # 3. Check recent activity
        self._display_recent_activity(weex)

        # 4. Check market status
        self._display_market_status(weex)

        # Write health file
        healthy = weex.ready and len(issues) == 0
        self._write_health_file(healthy=healthy, issues=issues)

        self.logger().info("=" * 70 + "\n")

    def _display_balances(self, weex):
        """Display account balances"""
        self.logger().info("\n📊 ACCOUNT BALANCES")
        self.logger().info("-" * 70)

        try:
            # Get available balances
            balances = weex.available_balances

            if not balances or len(balances) == 0:
                self.logger().info("  No balances available (connector may still be initializing)")
                self.logger().info(f"  Connector ready: {weex.ready}")
                return

            total_value_usd = Decimal("0")

            for asset, balance in balances.items():
                if balance > 0:
                    # Try to get USD value
                    usd_value = "N/A"
                    if asset == "USDT":
                        usd_value = f"${balance:.2f}"
                        total_value_usd += balance
                    elif asset == "VCC":
                        # Try to get VCC-USDT price
                        try:
                            mid_price = weex.get_mid_price(self.config.trading_pair)
                            if mid_price:
                                value = balance * Decimal(str(mid_price))
                                usd_value = f"${value:.2f}"
                                total_value_usd += value
                        except Exception:
                            pass
                    self.logger().info(f"  {asset:10s} {balance:>20.8f}  ~{usd_value}")

            self.logger().info("-" * 70)
            self.logger().info(f"  {'TOTAL (USD)':10s} {total_value_usd:>20.2f}")

        except Exception as e:
            self.logger().error(f"  ✗ Error fetching balances: {e}")

    def _display_open_orders(self, weex):
        """Display open orders"""
        self.logger().info("\n📝 OPEN ORDERS")
        self.logger().info("-" * 70)

        try:
            import time

            from hummingbot.core.utils.async_utils import safe_ensure_future

            # Initialize cache variables
            if not hasattr(self, '_orders_task'):
                self._orders_task = None
                self._orders_cache = None
                self._orders_fetch_time = 0
                self.logger().info("  DEBUG: Initialized cache variables")

            current_time = time.time()
            cache_age = current_time - self._orders_fetch_time
            self.logger().info(f"  DEBUG: Cache age: {cache_age:.1f}s, has cache: {self._orders_cache is not None}, task exists: {self._orders_task is not None}")

            # First, check if we have a completed task to cache
            if self._orders_task is not None and self._orders_task.done() and self._orders_cache is None:
                self.logger().info("  DEBUG: Caching completed task result")
                self._orders_cache = self._orders_task.result()
                self.logger().info(f"  DEBUG: Cached {len(self._orders_cache) if self._orders_cache else 0} orders")

            # Refresh every 60 seconds or if no cache
            if self._orders_cache is None or cache_age > 60:
                self.logger().info(f"  DEBUG: Need refresh (cache={'None' if self._orders_cache is None else 'exists'}, age={cache_age:.1f}s)")
                # Create new task if needed
                if self._orders_task is None or (self._orders_task.done() and cache_age > 60):
                    self.logger().info("  DEBUG: Creating new task")
                    self._orders_task = safe_ensure_future(self._fetch_open_orders(weex))
                    self._orders_fetch_time = current_time

                # Check if result is ready
                if not self._orders_task.done():
                    self.logger().info("  Fetching orders from API...")
                    if self._orders_cache:
                        self.logger().info("  (Using cached data below)")
                        orders_data = self._orders_cache
                    else:
                        self.logger().info("  DEBUG: No cache available, returning early")
                        return
                else:
                    # Task just completed, use the result
                    orders_data = self._orders_cache
            else:
                # Use cached data
                self.logger().info(f"  DEBUG: Using cached data ({cache_age:.1f}s old)")
                orders_data = self._orders_cache

            if not orders_data or len(orders_data) == 0:
                self.logger().info("  No open orders")
                return

            self.logger().info(f"  DEBUG: Processing {len(orders_data)} orders")
            self.logger().info(f"  DEBUG: First order sample: {orders_data[0] if orders_data else 'N/A'}")

            buy_orders = [o for o in orders_data if o.get("side") == "buy"]
            sell_orders = [o for o in orders_data if o.get("side") == "sell"]

            self.logger().info(f"  DEBUG: Buy orders found: {len(buy_orders)}, Sell orders found: {len(sell_orders)}")

            self.logger().info(f"  Total Orders: {len(orders_data)} ({len(buy_orders)} BUY, {len(sell_orders)} SELL)")
            self.logger().info("")

            # Display buy orders
            if buy_orders:
                self.logger().info("  BUY ORDERS:")
                for order in sorted(buy_orders, key=lambda x: float(x.get("price", 0)), reverse=True):
                    price = float(order.get("price", 0))
                    quantity = float(order.get("quantity", 0))
                    self.logger().info(
                        f"    {price:.6f} × {quantity:.2f} = {price * quantity:.2f} USDT"
                    )

            # Display sell orders
            if sell_orders:
                self.logger().info("  SELL ORDERS:")
                for order in sorted(sell_orders, key=lambda x: float(x.get("price", 0))):
                    price = float(order.get("price", 0))
                    quantity = float(order.get("quantity", 0))
                    self.logger().info(
                        f"    {price:.6f} × {quantity:.2f} = {price * quantity:.2f} USDT"
                    )

        except Exception as e:
            self.logger().error(f"  ✗ Error fetching open orders: {e}")

    def _display_recent_activity(self, weex):
        """Display recent trading activity"""
        self.logger().info("\n📈 RECENT ACTIVITY (Last 24h)")
        self.logger().info("-" * 70)

        try:
            # Note: This requires the connector to track fills
            # For a pure monitoring script, you would call the API directly

            # Get in-flight orders (completed in current session)
            in_flight = weex.in_flight_orders

            filled_orders = [
                o for o in in_flight.values()
                if o.is_done and o.executed_amount_base > 0
            ]

            if not filled_orders:
                self.logger().info("  No recent fills in current session")
                self.logger().info("  (For full 24h history, use the monitoring API directly)")
                return

            total_volume = Decimal("0")
            buy_volume = Decimal("0")
            sell_volume = Decimal("0")

            for order in filled_orders:
                volume = order.executed_amount_base * order.price
                total_volume += volume

                if order.trade_type == TradeType.BUY:
                    buy_volume += volume
                else:
                    sell_volume += volume

            self.logger().info(f"  Filled Orders: {len(filled_orders)}")
            self.logger().info(f"  Total Volume:  ${total_volume:.2f}")
            self.logger().info(f"    - Buy:       ${buy_volume:.2f}")
            self.logger().info(f"    - Sell:      ${sell_volume:.2f}")

        except Exception as e:
            self.logger().error(f"  ✗ Error fetching activity: {e}")

    def _display_market_status(self, weex):
        """Display current market status"""
        self.logger().info("\n💹 MARKET STATUS")
        self.logger().info("-" * 70)

        try:
            trading_pair = self.config.trading_pair  # VCC-USDT (Hummingbot format)

            # Get current price (use Hummingbot format)
            mid_price = weex.get_mid_price(trading_pair)

            if mid_price:
                self.logger().info(f"  {trading_pair} Mid Price: ${mid_price:.6f}")

            # Get trading rules (use Hummingbot format)
            trading_rule = weex.trading_rules.get(trading_pair)
            if trading_rule:
                self.logger().info(f"  Min Order Size:     {trading_rule.min_order_size:.2f} VCC")
                self.logger().info(f"  Max Order Size:     {trading_rule.max_order_size:.2f} VCC")
                self.logger().info(f"  Min Notional:       ${trading_rule.min_notional_size:.2f}")

            # Get order book info if available (use Hummingbot format)
            try:
                order_book = weex.get_order_book(trading_pair)
                if order_book:
                    self.logger().info(f"  Best Bid:           ${order_book.get_price(False):.6f}")
                    self.logger().info(f"  Best Ask:           ${order_book.get_price(True):.6f}")
                    spread = order_book.get_price(True) - order_book.get_price(False)
                    spread_pct = (spread / order_book.get_price(False)) * 100
                    self.logger().info(f"  Spread:             ${spread:.6f} ({spread_pct:.3f}%)")
            except Exception:
                self.logger().info("  Order book not yet initialized")

        except Exception as e:
            self.logger().error(f"  ✗ Error fetching market status: {e}")

    def format_status(self) -> str:
        """
        Display strategy status (called by 'status' command)
        """
        lines = []
        lines.append("\n  WEEX Account Monitor")
        lines.append("  " + "─" * 50)

        weex = self.connectors.get("weex")
        if weex:
            if weex.ready:
                lines.append("  Status: ✓ Connected (Read-Only)")

                # Show basic info
                try:
                    balances = weex.get_all_balances()
                    vcc_balance = balances.get("VCC", Decimal("0"))
                    usdt_balance = balances.get("USDT", Decimal("0"))

                    lines.append(f"  VCC Balance:  {vcc_balance:,.2f}")
                    lines.append(f"  USDT Balance: ${usdt_balance:,.2f}")

                    open_orders = weex.get_open_orders()
                    lines.append(f"  Open Orders:  {len(open_orders)}")
                except Exception:
                    pass
            else:
                lines.append("  Status: ⚠️  Connecting...")
        else:
            lines.append("  Status: ✗ Not connected")

        if self.config.monitoring_interval_seconds > 0:
            lines.append(f"  Update Interval: {self.config.monitoring_interval_seconds}s")
        else:
            lines.append("  Mode: One-time check")

        return "\n".join(lines)

    async def _fetch_open_orders(self, weex):
        """Async helper to fetch open orders from API"""
        from hummingbot.connector.exchange.weex import weex_constants as CONSTANTS

        try:
            symbol = await weex.exchange_symbol_associated_to_pair(trading_pair=self.config.trading_pair)
            self.logger().info(f"Fetching orders for symbol: {symbol}")

            response = await weex._api_post(
                path_url=CONSTANTS.OPEN_ORDERS_PATH_URL,
                data={"symbol": symbol, "limit": 100, "pageNo": 0},
                is_auth_required=True,
                limit_id=CONSTANTS.OPEN_ORDERS_LIMIT_ID
            )

            self.logger().info(f"API response: {response}")

            if response:
                orders = response.get("data", {}).get("orderInfoResultList", [])
                self.logger().info(f"Extracted {len(orders)} orders from response")
                return orders
            else:
                self.logger().warning("API response was None or empty")
                return []
        except Exception as e:
            self.logger().error(f"Error fetching open orders: {e}", exc_info=True)
            return []

    def _write_health_file(self, healthy: bool, issues: list):
        """Write health status to JSON file for monitoring dashboard"""
        try:
            import time

            from hummingbot.core.utils.async_utils import safe_ensure_future

            weex = self.connectors.get("weex")
            open_orders = []
            balances = {}

            if weex:
                # Fetch open orders directly from API - use task that persists across ticks
                try:
                    # Initialize cache variables
                    if not hasattr(self, '_health_orders_task'):
                        self._health_orders_task = None
                        self._health_orders_cache = None
                        self._health_fetch_time = 0

                    current_time = time.time()
                    cache_age = current_time - self._health_fetch_time

                    # First, check if we have a completed task to cache
                    if self._health_orders_task is not None and self._health_orders_task.done() and self._health_orders_cache is None:
                        self._health_orders_cache = self._health_orders_task.result()

                    # Refresh every 60 seconds or if no cache
                    if self._health_orders_cache is None or cache_age > 60:
                        # Create new task if needed
                        if self._health_orders_task is None or (self._health_orders_task.done() and cache_age > 60):
                            self._health_orders_task = safe_ensure_future(self._fetch_open_orders(weex))
                            self._health_fetch_time = current_time

                    # Use cached data (may be None on first run)
                    if self._health_orders_cache:
                        for order in self._health_orders_cache:
                            open_orders.append({
                                "side": order.get("side", "").upper(),
                                "price": float(order.get("price", 0)),
                                "amount": float(order.get("quantity", 0)),
                                "trading_pair": self.config.trading_pair
                            })
                except Exception as e:
                    self.logger().warning(f"Failed to fetch orders for health file: {e}")

                # Get balances
                if hasattr(weex, 'available_balances'):
                    balances = {k: float(v) for k, v in weex.available_balances.items() if v > 0}

            health_data = {
                "healthy": healthy,
                "last_update": datetime.now().timestamp(),
                "issues": issues,
                "timestamp": datetime.now().isoformat(),
                "open_orders": open_orders,
                "open_orders_count": len(open_orders),
                "balances": balances
            }
            with open(self._health_file, "w", encoding="utf-8") as f:
                json.dump(health_data, f, indent=2)
            self.logger().debug(f"Health file written to {self._health_file} with {len(open_orders)} orders")
        except Exception as e:
            self.logger().error(f"Failed to write health file: {e}")


# For standalone execution (outside Hummingbot)
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║         WEEX Account Monitoring Script                      ║
    ╚══════════════════════════════════════════════════════════════╝

    This script is designed to run within Hummingbot.

    To use:
    1. Start Hummingbot
    2. Connect to WEEX with your MONITORING (read-only) API keys
    3. Run: import weex_monitor
    4. View the monitoring dashboard

    Note: Use your read-only monitoring keys, not trading keys!
    """)
