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
            if hasattr(self, '_ready_wait_logged'):
                return  # Already logged, just wait silently
            self.logger().info("⏳ Waiting for WEEX connector to initialize...")
            self.logger().info(f"   Status: {weex.status_dict}")
            self._ready_wait_logged = True
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
            return

        # Display header
        self.logger().info("\n" + "=" * 70)
        self.logger().info("  WEEX ACCOUNT MONITORING DASHBOARD")
        self.logger().info("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.logger().info(f"  Connector ready: {weex.ready}")
        self.logger().info("=" * 70)

        # 1. Check balances
        self._display_balances(weex)

        # 2. Check open orders
        self._display_open_orders(weex)

        # 3. Check recent activity
        self._display_recent_activity(weex)

        # 4. Check market status
        self._display_market_status(weex)

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
            # Get in-flight orders (open orders)
            open_orders = list(weex.in_flight_orders.values()) if hasattr(weex, 'in_flight_orders') else []

            if not open_orders:
                self.logger().info("  No open orders")
                return

            buy_orders = [o for o in open_orders if o.trade_type == TradeType.BUY]
            sell_orders = [o for o in open_orders if o.trade_type == TradeType.SELL]

            self.logger().info(f"  Total Orders: {len(open_orders)} ({len(buy_orders)} BUY, {len(sell_orders)} SELL)")
            self.logger().info("")

            # Display buy orders
            if buy_orders:
                self.logger().info("  BUY ORDERS:")
                for order in sorted(buy_orders, key=lambda x: x.price, reverse=True):
                    self.logger().info(
                        f"    {order.price:.6f} × {order.quantity:.2f} = {order.price * order.quantity:.2f} USDT"
                    )

            # Display sell orders
            if sell_orders:
                self.logger().info("  SELL ORDERS:")
                for order in sorted(sell_orders, key=lambda x: x.price):
                    self.logger().info(
                        f"    {order.price:.6f} × {order.quantity:.2f} = {order.price * order.quantity:.2f} USDT"
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
            trading_pair = self.config.trading_pair
            weex_symbol = to_weex_symbol(trading_pair)

            # Get current price
            mid_price = weex.get_mid_price(weex_symbol)

            if mid_price:
                self.logger().info(f"  {trading_pair} Mid Price: ${mid_price:.6f}")

            # Get trading rules
            trading_rule = weex.trading_rules.get(weex_symbol)
            if trading_rule:
                self.logger().info(f"  Min Order Size:     {trading_rule.min_order_size:.2f} VCC")
                self.logger().info(f"  Max Order Size:     {trading_rule.max_order_size:.2f} VCC")
                self.logger().info(f"  Min Notional:       ${trading_rule.min_notional_size:.2f}")

            # Get order book info if available
            try:
                order_book = weex.get_order_book(weex_symbol)
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
