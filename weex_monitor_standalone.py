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
    - WEEX_MONITOR_CONSOLE_LEVEL (e.g., INFO, WARNING, ERROR)
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from decimal import Decimal
from logging.handlers import RotatingFileHandler

import requests

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Set the lowest level for the logger

# File Handler (logs everything at INFO level and above)
log_file = "/home/hummingbot/logs/weex_monitor.log"
file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console Handler (level is configurable via environment variable)
console_level_str = os.getenv("WEEX_MONITOR_CONSOLE_LEVEL", "INFO").upper()
console_level = getattr(logging, console_level_str, logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(console_level)
console_formatter = logging.Formatter('%(message)s')  # Keep console output clean
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

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

    def _serialize_body(self, body):
        if not body:
            return ""
        return json.dumps(body, separators=(",", ":"), sort_keys=True)

    def _get_headers(self, method, path, params=None, body=None):
        """Generate authentication headers"""
        timestamp = self._timestamp_ms()

        # Build query string
        query = ""
        if params:
            if isinstance(params, (list, tuple)):
                query = "?" + "&".join([f"{k}={v}" for k, v in params])
            else:
                query = "?" + "&".join([f"{k}={v}" for k, v in sorted(params.items())])

        # Build body string
        body_str = self._serialize_body(body)

        # Create signature payload
        payload = f"{timestamp}{method.upper()}{path}{query}{body_str}"
        signature = self._sign(payload)

        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-SIGN": signature,
            "Content-Type": "application/json",
            "ACCESS-CHANNEL": "self",
        }

        if self.passphrase:
            headers["ACCESS-PASSPHRASE"] = self.passphrase

        return headers, payload, timestamp, body_str

    def _mask_value(self, value, show_start=4, show_end=2):
        if not value:
            return ""
        if len(value) <= show_start + show_end:
            return value[:1] + "***"
        return f"{value[:show_start]}***{value[-show_end:]}"

    def _log_request_error(self, method, path, params, body, payload, timestamp, response):
        status = getattr(response, "status_code", None)
        try:
            response_text = response.text
        except Exception:
            response_text = "<unreadable>"

        logger.error("  Auth error for %s %s", method, path)
        logger.error("  Status: %s", status)
        logger.error("  Timestamp: %s", timestamp)
        logger.error("  Payload: %s", payload)
        logger.error("  Params: %s", params)
        logger.error("  Body: %s", body)
        logger.error("  Response: %s", response_text)
        logger.error(
            "  Key: %s Passphrase: %s",
            self._mask_value(self.api_key),
            self._mask_value(self.passphrase),
        )

    def _request(self, method, path, params=None, body=None):
        params_items = None
        if params:
            params_items = sorted(params.items()) if isinstance(params, dict) else params

        headers, payload, timestamp, body_str = self._get_headers(
            method, path, params=params_items, body=body
        )

        try:
            if method.upper() == "GET":
                response = requests.get(
                    f"{self.base_url}{path}",
                    params=params_items,
                    headers=headers,
                )
            else:
                response = requests.post(
                    f"{self.base_url}{path}",
                    data=body_str,
                    headers=headers,
                )
        except requests.RequestException as exc:
            logger.error("  Request error for %s %s: %s", method, path, exc)
            return {"code": "request_error", "msg": str(exc)}

        try:
            data = response.json()
        except Exception:
            data = {"code": "parse_error", "msg": response.text}

        if data.get("code") != "00000":
            self._log_request_error(method, path, params, body, payload, timestamp, response)

        return data

    def get_account_balance(self):
        """Get account balances"""
        path = "/api/v2/account/assets"
        return self._request("GET", path)

    def get_ticker(self, symbol):
        """Get ticker information (public endpoint)"""
        path = "/api/v2/market/ticker"
        params = {"symbol": symbol}
        return self._request("GET", path, params=params)

    def get_open_orders(self, symbol, limit=100, page_no=0):
        """Get open/unfinished orders"""
        path = "/api/v2/trade/open-orders"
        body = {
            "symbol": symbol,
            "limit": int(limit),
            "pageNo": int(page_no),
        }
        return self._request("POST", path, body=body)

    def get_fills(self, symbol, limit=20, page_no=0):
        """Get recent fills/trades"""
        path = "/api/v2/trade/fills"
        body = {
            "symbol": symbol,
            "limit": int(limit),
            "pageNo": int(page_no),
        }
        return self._request("POST", path, body=body)


# ============================================================================
# DASHBOARD DISPLAY
# ============================================================================

def display_account_dashboard(account_name, client):
    """Display monitoring dashboard for one account"""
    logger.info("\n" + "=" * 80)
    logger.info(f"  {account_name.upper()} ACCOUNT")
    logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    # 1. Account Balances
    logger.info("\n📊 ACCOUNT BALANCES")
    logger.info("-" * 80)
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
                        logger.info(f"  {coin:10s}  Available: {available:>20.8f}  Frozen: {frozen:>15.8f}")

                        # Estimate USD value
                        if coin == "USDT":
                            total_usd += total
            else:
                logger.info("  No balances")
        else:
            logger.error(f"  Error fetching balances: {balance_response.get('msg', 'Unknown error')}")
    except Exception as e:
        logger.error(f"  ✗ Error fetching balances: {e}")

    # 2. Current Price
    logger.info("\n💹 MARKET PRICE")
    logger.info("-" * 80)
    try:
        ticker_response = client.get_ticker(TRADING_PAIR)
        if ticker_response.get("code") == "00000":
            ticker = ticker_response.get("data", {})
            if ticker:
                last_price = ticker.get("close", "N/A")
                bid = ticker.get("bid", "N/A")
                ask = ticker.get("ask", "N/A")
                volume_24h = ticker.get("volume", "N/A")

                logger.info(f"  Last Price:  ${last_price}")
                logger.info(f"  Best Bid:    ${bid}")
                logger.info(f"  Best Ask:    ${ask}")
                logger.info(f"  24h Volume:  {volume_24h}")

                if bid != "N/A" and ask != "N/A":
                    spread = Decimal(ask) - Decimal(bid)
                    spread_pct = (spread / Decimal(bid)) * 100
                    logger.info(f"  Spread:      ${spread:.6f} ({spread_pct:.3f}%)")
        else:
            logger.error(f"  Error fetching ticker: {ticker_response.get('msg', 'Unknown error')}")
    except Exception as e:
        logger.error(f"  ✗ Error fetching ticker: {e}")

    # 3. Open Orders
    logger.info("\n📝 OPEN ORDERS")
    logger.info("-" * 80)
    try:
        orders_response = client.get_open_orders(TRADING_PAIR)
        if orders_response.get("code") == "00000":
            data = orders_response.get("data", [])
            if isinstance(data, dict):
                orders = (
                    data.get("orderInfoResultList")
                    or data.get("orderInfoList")
                    or data.get("list")
                    or data.get("orders")
                    or []
                )
            else:
                orders = data or []

            if orders:
                for order in orders:
                    side = order.get("side", "")
                    order["_side_norm"] = str(side).upper()

                buy_orders = [o for o in orders if o.get("_side_norm") == "BUY"]
                sell_orders = [o for o in orders if o.get("_side_norm") == "SELL"]

                logger.info(
                    "  Total: %s orders (%s BUY, %s SELL)",
                    len(orders),
                    len(buy_orders),
                    len(sell_orders),
                )

                sample_symbol = orders[0].get("symbol")
                if sample_symbol and sample_symbol.upper() != TRADING_PAIR.upper():
                    logger.warning(
                        "  NOTE: orders are for %s (monitoring %s)",
                        sample_symbol,
                        TRADING_PAIR,
                    )

                if buy_orders:
                    logger.info("\n  BUY ORDERS:")
                    for order in sorted(
                        buy_orders,
                        key=lambda x: Decimal(x.get("price", "0")),
                        reverse=True,
                    )[:5]:
                        price = order.get("price")
                        qty = order.get("quantity")
                        filled = order.get("executedQty", order.get("fillQuantity", "0"))
                        symbol = order.get("symbol", TRADING_PAIR)
                        logger.info("    %s $%s × %s (filled: %s)", symbol, price, qty, filled)

                if sell_orders:
                    logger.info("\n  SELL ORDERS:")
                    for order in sorted(
                        sell_orders,
                        key=lambda x: Decimal(x.get("price", "0")),
                    )[:5]:
                        price = order.get("price")
                        qty = order.get("quantity")
                        filled = order.get("executedQty", order.get("fillQuantity", "0"))
                        symbol = order.get("symbol", TRADING_PAIR)
                        logger.info("    %s $%s × %s (filled: %s)", symbol, price, qty, filled)
            else:
                logger.info("  No open orders")
        else:
            logger.error("  Error fetching orders: %s", orders_response.get("msg", "Unknown error"))
    except Exception as e:
        logger.error(f"  ✗ Error fetching orders: {e}")

    # 4. Recent Fills
    logger.info("\n📈 RECENT FILLS (Last 10)")
    logger.info("-" * 80)
    try:
        fills_response = client.get_fills(TRADING_PAIR, limit=10)
        if fills_response.get("code") == "00000":
            data = fills_response.get("data", [])
            if isinstance(data, dict):
                fills = (
                    data.get("fillsOrderResultList")
                    or data.get("fillList")
                    or data.get("fillInfoList")
                    or data.get("list")
                    or data.get("fills")
                    or []
                )
            else:
                fills = data or []

            if fills:
                total_volume = Decimal("0")
                for fill in fills:
                    side = str(fill.get("side", "")).upper()
                    price = fill.get("price", "0")
                    qty = fill.get("quantity", "0")
                    fee = fill.get("fee", "0")
                    timestamp = fill.get("createdAt", "")
                    symbol = fill.get("symbol", TRADING_PAIR)

                    volume = Decimal(price) * Decimal(qty)
                    total_volume += volume

                    try:
                        dt = datetime.fromtimestamp(int(timestamp) / 1000)
                        time_str = dt.strftime("%H:%M:%S")
                    except Exception:
                        time_str = timestamp

                    logger.info(
                        "  %s %s %s %s @ $%s  (fee: %s)",
                        time_str,
                        symbol,
                        side,
                        qty,
                        price,
                        fee,
                    )

                logger.info("\n  Total Volume: $%.2f", total_volume)
            else:
                logger.info("  No recent fills")
        else:
            logger.error("  Error fetching fills: %s", fills_response.get("msg", "Unknown error"))
    except Exception as e:
        logger.error(f"  ✗ Error fetching fills: {e}")


def main():
    """Main monitoring loop"""
    logger.info("\n" + "=" * 80)
    logger.info("  WEEX DUAL ACCOUNT MONITORING DASHBOARD")
    logger.info("=" * 80)

    # Check if credentials are configured
    if not MM_ACCOUNT["api_key"] or not VOL_ACCOUNT["api_key"]:
        logger.critical("\nCRITICAL: API credentials not configured!")
        logger.critical("Please set environment variables:")
        logger.critical("  - WEEX_MM_API_KEY, WEEX_MM_API_SECRET, WEEX_MM_PASSPHRASE")
        logger.critical("  - WEEX_VOL_API_KEY, WEEX_VOL_API_SECRET, WEEX_VOL_PASSPHRASE")
        logger.critical("\nOr edit the credentials section in this script.")
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

            logger.info("\n" + "=" * 80)
            logger.info("  Monitoring complete!")
            logger.info("=" * 80 + "\n")
            time.sleep(max(interval_seconds, 5))
    except KeyboardInterrupt:
        logger.info("\nExiting monitor.")


if __name__ == "__main__":
    main()
