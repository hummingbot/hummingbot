#!/usr/bin/env python3
"""
WEEX Account Monitoring Dashboard (Standalone)
================================================
Monitors WEEX accounts using read-only monitoring API keys.

Usage:
    python3 weex_monitor_standalone.py

Configuration:
    Set environment variables or edit the credentials section below:
    - WEEX_MM_API_KEY, WEEX_MM_API_SECRET, WEEX_MM_PASSPHRASE
    - WEEX_VOL_API_KEY, WEEX_VOL_API_SECRET, WEEX_VOL_PASSPHRASE
"""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from decimal import Decimal

import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = "https://api-spot.weex.com"
TRADING_PAIR = os.getenv("WEEX_MONITOR_SYMBOL", "VCCUSDT_SPBL")

# Market Making Account (read-only monitoring keys)
MM_ACCOUNT = {
    "name": "Market Making",
    "api_key": os.getenv("WEEX_MM_API_KEY", ""),
    "api_secret": os.getenv("WEEX_MM_API_SECRET", ""),
    "passphrase": os.getenv("WEEX_MM_PASSPHRASE", ""),
}

# Volume Generation Account (read-only monitoring keys)
VOL_ACCOUNT = {
    "name": "Volume Generation",
    "api_key": os.getenv("WEEX_VOL_API_KEY", ""),
    "api_secret": os.getenv("WEEX_VOL_API_SECRET", ""),
    "passphrase": os.getenv("WEEX_VOL_PASSPHRASE", ""),
}

# ============================================================================
# WEEX API CLIENT
# ============================================================================


class WeexMonitorClient:
    def __init__(self, api_key, api_secret, passphrase):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = BASE_URL

    def _timestamp_ms(self):
        """Get current timestamp in milliseconds"""
        return str(int(time.time() * 1000))

    def _sign(self, message):
        """Generate HMAC SHA256 signature"""
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(mac).decode('utf-8')

    def _get_headers(self, method, path, params=None, body=None):
        """Generate authentication headers"""
        timestamp = self._timestamp_ms()

        # Build query string
        query = ""
        if params:
            query = "?" + "&".join([f"{k}={v}" for k, v in sorted(params.items())])

        # Build body string
        body_str = ""
        if body:
            body_str = json.dumps(body, separators=(',', ':'))

        # Create signature payload
        payload = f"{timestamp}{method.upper()}{path}{query}{body_str}"
        signature = self._sign(payload)

        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-SIGN": signature,
            "Content-Type": "application/json",
        }

        if self.passphrase:
            headers["ACCESS-PASSPHRASE"] = self.passphrase

        return headers

    def get_account_balance(self):
        """Get account balances"""
        path = "/api/v2/account/assets"
        headers = self._get_headers("GET", path)

        response = requests.get(
            f"{self.base_url}{path}",
            headers=headers
        )
        return response.json()

    def get_ticker(self, symbol):
        """Get ticker information (public endpoint)"""
        path = "/api/v2/market/ticker"
        params = {"symbol": symbol}

        response = requests.get(
            f"{self.base_url}{path}",
            params=params
        )
        return response.json()

    def get_open_orders(self, symbol):
        """Get open/unfinished orders"""
        path = "/api/v2/trade/open-orders"
        body = {"symbol": symbol}
        headers = self._get_headers("POST", path, body=body)

        response = requests.post(
            f"{self.base_url}{path}",
            json=body,
            headers=headers
        )
        return response.json()

    def get_fills(self, symbol, limit=20):
        """Get recent fills/trades"""
        path = "/api/v2/trade/fills"
        body = {"symbol": symbol, "limit": limit}
        headers = self._get_headers("POST", path, body=body)

        response = requests.post(
            f"{self.base_url}{path}",
            json=body,
            headers=headers
        )
        return response.json()


# ============================================================================
# DASHBOARD DISPLAY
# ============================================================================

def display_account_dashboard(account_name, client):
    """Display monitoring dashboard for one account"""
    print("\n" + "=" * 80)
    print(f"  {account_name.upper()} ACCOUNT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 1. Account Balances
    print("\n📊 ACCOUNT BALANCES")
    print("-" * 80)
    try:
        balance_response = client.get_account_balance()
        if balance_response.get("code") == "00000":
            balances = balance_response.get("data", [])
            if balances:
                total_usd = Decimal("0")
                for asset_data in balances:
                    coin = asset_data.get("currency", "")
                    available = Decimal(asset_data.get("available", "0"))
                    frozen = Decimal(asset_data.get("frozen", "0"))
                    total = available + frozen

                    if total > 0:
                        print(f"  {coin:10s}  Available: {available:>20.8f}  Frozen: {frozen:>15.8f}")

                        # Estimate USD value
                        if coin == "USDT":
                            total_usd += total
            else:
                print("  No balances")
        else:
            print(f"  Error: {balance_response.get('msg', 'Unknown error')}")
    except Exception as e:
        print(f"  ✗ Error fetching balances: {e}")

    # 2. Current Price
    print("\n💹 MARKET PRICE")
    print("-" * 80)
    try:
        ticker_response = client.get_ticker(TRADING_PAIR)
        if ticker_response.get("code") == "00000":
            ticker = ticker_response.get("data", {})
            if ticker:
                last_price = ticker.get("close", "N/A")
                bid = ticker.get("bid", "N/A")
                ask = ticker.get("ask", "N/A")
                volume_24h = ticker.get("volume", "N/A")

                print(f"  Last Price:  ${last_price}")
                print(f"  Best Bid:    ${bid}")
                print(f"  Best Ask:    ${ask}")
                print(f"  24h Volume:  {volume_24h}")

                if bid != "N/A" and ask != "N/A":
                    spread = Decimal(ask) - Decimal(bid)
                    spread_pct = (spread / Decimal(bid)) * 100
                    print(f"  Spread:      ${spread:.6f} ({spread_pct:.3f}%)")
        else:
            print(f"  Error: {ticker_response.get('msg', 'Unknown error')}")
    except Exception as e:
        print(f"  ✗ Error fetching ticker: {e}")

    # 3. Open Orders
    print("\n📝 OPEN ORDERS")
    print("-" * 80)
    try:
        orders_response = client.get_open_orders(TRADING_PAIR)
        if orders_response.get("code") == "00000":
            orders = orders_response.get("data", [])
            if orders:
                buy_orders = [o for o in orders if o.get("side") == "BUY"]
                sell_orders = [o for o in orders if o.get("side") == "SELL"]

                print(f"  Total: {len(orders)} orders ({len(buy_orders)} BUY, {len(sell_orders)} SELL)")

                if buy_orders:
                    print("\n  BUY ORDERS:")
                    for order in sorted(buy_orders, key=lambda x: Decimal(x.get("price", "0")), reverse=True)[:5]:
                        price = order.get("price")
                        qty = order.get("quantity")
                        filled = order.get("executedQty", "0")
                        print(f"    ${price} × {qty} (filled: {filled})")

                if sell_orders:
                    print("\n  SELL ORDERS:")
                    for order in sorted(sell_orders, key=lambda x: Decimal(x.get("price", "0")))[:5]:
                        price = order.get("price")
                        qty = order.get("quantity")
                        filled = order.get("executedQty", "0")
                        print(f"    ${price} × {qty} (filled: {filled})")
            else:
                print("  No open orders")
        else:
            print(f"  Error: {orders_response.get('msg', 'Unknown error')}")
    except Exception as e:
        print(f"  ✗ Error fetching orders: {e}")

    # 4. Recent Fills
    print("\n📈 RECENT FILLS (Last 10)")
    print("-" * 80)
    try:
        fills_response = client.get_fills(TRADING_PAIR, limit=10)
        if fills_response.get("code") == "00000":
            fills = fills_response.get("data", [])
            if fills:
                total_volume = Decimal("0")
                for fill in fills:
                    side = fill.get("side", "")
                    price = fill.get("price", "0")
                    qty = fill.get("quantity", "0")
                    fee = fill.get("fee", "0")
                    timestamp = fill.get("createdAt", "")

                    volume = Decimal(price) * Decimal(qty)
                    total_volume += volume

                    # Format timestamp
                    try:
                        dt = datetime.fromtimestamp(int(timestamp) / 1000)
                        time_str = dt.strftime("%H:%M:%S")
                    except Exception:
                        time_str = timestamp

                    print(f"  {time_str} {side:4s} {qty:>12s} @ ${price:>10s}  (fee: {fee})")

                print(f"\n  Total Volume: ${total_volume:.2f}")
            else:
                print("  No recent fills")
        else:
            print(f"  Error: {fills_response.get('msg', 'Unknown error')}")
    except Exception as e:
        print(f"  ✗ Error fetching fills: {e}")


def main():
    """Main monitoring loop"""
    print("\n" + "=" * 80)
    print("  WEEX DUAL ACCOUNT MONITORING DASHBOARD")
    print("=" * 80)

    # Check if credentials are configured
    if not MM_ACCOUNT["api_key"] or not VOL_ACCOUNT["api_key"]:
        print("\nWARNING: API credentials not configured!")
        print("\nPlease set environment variables:")
        print("  - WEEX_MM_API_KEY, WEEX_MM_API_SECRET, WEEX_MM_PASSPHRASE")
        print("  - WEEX_VOL_API_KEY, WEEX_VOL_API_SECRET, WEEX_VOL_PASSPHRASE")
        print("\nOr edit the credentials section in this script.")
        return

    # Create clients
    mm_client = WeexMonitorClient(
        MM_ACCOUNT["api_key"],
        MM_ACCOUNT["api_secret"],
        MM_ACCOUNT["passphrase"]
    )

    vol_client = WeexMonitorClient(
        VOL_ACCOUNT["api_key"],
        VOL_ACCOUNT["api_secret"],
        VOL_ACCOUNT["passphrase"]
    )

    interval_seconds = int(os.getenv("WEEX_MONITOR_INTERVAL", "20"))

    try:
        while True:
            # Display dashboards
            display_account_dashboard(MM_ACCOUNT["name"], mm_client)
            display_account_dashboard(VOL_ACCOUNT["name"], vol_client)

            print("\n" + "=" * 80)
            print("  Monitoring complete!")
            print("=" * 80 + "\n")
            time.sleep(max(interval_seconds, 5))
    except KeyboardInterrupt:
        print("\nExiting monitor.")


if __name__ == "__main__":
    main()
