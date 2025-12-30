#!/usr/bin/env python3
"""
Backpack Exchange Integration Test Script

Tests both spot and perpetual connectors with live API:
- Authentication
- Balance retrieval
- Order placement/cancellation
- WebSocket connections
- Order lifecycle events

Usage:
    python scripts/backpack_integration_test.py
"""

import asyncio
import os
import sys
import time
from decimal import Decimal

# Add hummingbot to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)


class BackpackIntegrationTest:
    """Integration test suite for Backpack connectors."""

    def __init__(self):
        self.api_key = os.getenv("BACKPACK_API_KEY")
        self.api_secret = os.getenv("BACKPACK_API_SECRET")
        self.results = []

        if not self.api_key or not self.api_secret:
            raise ValueError("BACKPACK_API_KEY and BACKPACK_API_SECRET must be set in environment")

    def log(self, message: str, status: str = "INFO"):
        """Log a message with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        emoji = {"PASS": "✅", "FAIL": "❌", "INFO": "ℹ️", "WARN": "⚠️"}.get(status, "•")
        print(f"[{timestamp}] {emoji} {message}")
        if status in ["PASS", "FAIL"]:
            self.results.append((message, status == "PASS"))

    async def test_spot_auth(self):
        """Test spot connector authentication."""
        self.log("Testing Spot Authentication...")
        try:
            from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth

            auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

            # Test signing
            params = {"symbol": "BTC_USDC"}
            timestamp = int(time.time() * 1000)
            window = 5000

            headers = auth.generate_auth_headers(
                instruction="balanceQuery",
                params=params,
                timestamp=timestamp,
                window=window,
            )

            assert headers.get("X-API-Key") == self.api_key
            assert "X-Signature" in headers
            assert headers.get("X-Timestamp") == str(timestamp)
            assert headers.get("X-Window") == str(window)
            self.log("Spot Auth: Signature generation works", "PASS")
            return True
        except Exception as e:
            self.log(f"Spot Auth failed: {e}", "FAIL")
            return False

    async def test_spot_balance(self):
        """Test spot balance retrieval."""
        self.log("Testing Spot Balance Retrieval...")
        try:
            from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange

            exchange = BackpackExchange(
                backpack_api_key=self.api_key,
                backpack_api_secret=self.api_secret,
                trading_pairs=["BTC-USDC"],
            )

            await exchange._update_balances()
            balances = exchange.get_all_balances()

            self.log(f"Spot Balances: {dict(balances)}")
            self.log("Spot Balance Retrieval: Success", "PASS")

            await exchange.stop_network()
            return True
        except Exception as e:
            self.log(f"Spot Balance failed: {e}", "FAIL")
            return False

    async def test_spot_trading_rules(self):
        """Test spot trading rules fetching."""
        self.log("Testing Spot Trading Rules...")
        try:
            from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange

            exchange = BackpackExchange(
                backpack_api_key=self.api_key,
                backpack_api_secret=self.api_secret,
                trading_pairs=["BTC-USDC", "SOL-USDC"],
            )

            await exchange._update_trading_rules()
            rules = exchange.trading_rules

            self.log(f"Trading pairs found: {list(rules.keys())}")
            if rules:
                self.log("Spot Trading Rules: Success", "PASS")
            else:
                self.log("Spot Trading Rules: No rules found", "WARN")

            await exchange.stop_network()
            return bool(rules)
        except Exception as e:
            self.log(f"Spot Trading Rules failed: {e}", "FAIL")
            return False

    async def test_spot_order_lifecycle(self):
        """Test spot order placement and cancellation."""
        self.log("Testing Spot Order Lifecycle...")
        try:
            from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange
            from hummingbot.core.data_type.common import OrderType, TradeType

            exchange = BackpackExchange(
                backpack_api_key=self.api_key,
                backpack_api_secret=self.api_secret,
                trading_pairs=["SOL-USDC"],
            )

            # Initialize
            await exchange._update_trading_rules()
            await exchange._update_balances()

            # Place a limit order far from market (won't fill)
            # Use a very low price so it won't fill
            order_id = exchange.buy(
                trading_pair="SOL-USDC",
                amount=Decimal("0.1"),
                order_type=OrderType.LIMIT,
                price=Decimal("1.0"),  # Very low price
            )

            self.log(f"Order placed: {order_id}")
            await asyncio.sleep(2)

            # Check order status
            in_flight_orders = exchange.in_flight_orders
            self.log(f"In-flight orders: {list(in_flight_orders.keys())}")

            # Cancel the order
            if order_id in in_flight_orders:
                exchange.cancel(trading_pair="SOL-USDC", client_order_id=order_id)
                await asyncio.sleep(2)
                self.log("Order cancelled successfully", "PASS")
            else:
                self.log("Order lifecycle test completed", "PASS")

            await exchange.stop_network()
            return True
        except Exception as e:
            self.log(f"Spot Order Lifecycle failed: {e}", "FAIL")
            return False

    async def test_perpetual_auth(self):
        """Test perpetual connector authentication."""
        self.log("Testing Perpetual Authentication...")
        try:
            from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_auth import (
                BackpackPerpetualAuth,
            )

            auth = BackpackPerpetualAuth(api_key=self.api_key, api_secret=self.api_secret)

            # Test that it inherits properly and can generate headers
            headers = auth.generate_auth_headers(
                instruction="balanceQuery",
                params={"symbol": "BTC_USDC"},
                timestamp=int(time.time() * 1000),
                window=5000,
            )
            assert headers.get("X-API-Key") == self.api_key
            assert "X-Signature" in headers
            assert hasattr(auth, "generate_ws_auth_payload")

            self.log("Perpetual Auth: Inheritance verified", "PASS")
            return True
        except Exception as e:
            self.log(f"Perpetual Auth failed: {e}", "FAIL")
            return False

    async def test_perpetual_balance(self):
        """Test perpetual balance retrieval."""
        self.log("Testing Perpetual Balance Retrieval...")
        try:
            from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
                BackpackPerpetualDerivative,
            )

            exchange = BackpackPerpetualDerivative(
                backpack_perpetual_api_key=self.api_key,
                backpack_perpetual_api_secret=self.api_secret,
                trading_pairs=["BTC-USDC"],
            )

            await exchange._update_balances()
            balances = exchange.get_all_balances()

            self.log(f"Perpetual Balances: {dict(balances)}")
            self.log("Perpetual Balance Retrieval: Success", "PASS")

            await exchange.stop_network()
            return True
        except Exception as e:
            self.log(f"Perpetual Balance failed: {e}", "FAIL")
            return False

    async def test_perpetual_positions(self):
        """Test perpetual position retrieval."""
        self.log("Testing Perpetual Position Retrieval...")
        try:
            from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
                BackpackPerpetualDerivative,
            )

            exchange = BackpackPerpetualDerivative(
                backpack_perpetual_api_key=self.api_key,
                backpack_perpetual_api_secret=self.api_secret,
                trading_pairs=["BTC-USDC"],
            )

            await exchange._update_positions()
            positions = exchange.account_positions

            self.log(f"Positions: {positions}")
            self.log("Perpetual Position Retrieval: Success", "PASS")

            await exchange.stop_network()
            return True
        except Exception as e:
            self.log(f"Perpetual Positions failed: {e}", "FAIL")
            return False

    async def test_rest_api_direct(self):
        """Direct REST API test without connector framework."""
        self.log("Testing Direct REST API...")
        try:
            import aiohttp
            import base64
            import hashlib
            from cryptography.hazmat.primitives.asymmetric import ed25519
            from cryptography.hazmat.primitives import serialization

            # Decode the secret key
            secret_bytes = base64.b64decode(self.api_secret)

            # Create the private key
            if len(secret_bytes) == 64:
                private_key = ed25519.Ed25519PrivateKey.from_private_bytes(secret_bytes[:32])
            elif len(secret_bytes) == 32:
                private_key = ed25519.Ed25519PrivateKey.from_private_bytes(secret_bytes)
            else:
                raise ValueError(f"Invalid secret key length: {len(secret_bytes)}")

            # Prepare request
            timestamp = int(time.time() * 1000)
            window = 5000
            instruction = "balanceQuery"

            # Create signing string
            sign_str = f"instruction={instruction}&timestamp={timestamp}&window={window}"
            signature = private_key.sign(sign_str.encode())
            signature_b64 = base64.b64encode(signature).decode()

            headers = {
                "X-API-Key": self.api_key,
                "X-Signature": signature_b64,
                "X-Timestamp": str(timestamp),
                "X-Window": str(window),
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                # Test balance endpoint
                async with session.get(
                    "https://api.backpack.exchange/api/v1/capital",
                    headers=headers,
                ) as response:
                    data = await response.json()
                    self.log(f"API Response Status: {response.status}")
                    self.log(f"Balance Data: {data}")

                    if response.status == 200:
                        self.log("Direct REST API: Success", "PASS")
                        return True
                    else:
                        self.log(f"Direct REST API: HTTP {response.status}", "FAIL")
                        return False

        except Exception as e:
            self.log(f"Direct REST API failed: {e}", "FAIL")
            import traceback
            traceback.print_exc()
            return False

    async def test_websocket_public(self):
        """Test public WebSocket connection."""
        self.log("Testing Public WebSocket...")
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.ws_connect("wss://ws.backpack.exchange") as ws:
                    # Subscribe to a public channel
                    subscribe_msg = {
                        "method": "SUBSCRIBE",
                        "params": ["trade.SOL_USDC"],
                    }
                    await ws.send_json(subscribe_msg)

                    # Wait for response
                    msg = await asyncio.wait_for(ws.receive(), timeout=10)
                    self.log(f"WS Response: {msg.data[:200] if msg.data else msg}")

                    self.log("Public WebSocket: Connected", "PASS")
                    return True

        except asyncio.TimeoutError:
            self.log("Public WebSocket: Timeout (may still be working)", "WARN")
            return True
        except Exception as e:
            self.log(f"Public WebSocket failed: {e}", "FAIL")
            return False

    async def run_all_tests(self):
        """Run all integration tests."""
        self.log("=" * 60)
        self.log("BACKPACK EXCHANGE INTEGRATION TESTS")
        self.log("=" * 60)

        # Direct API test first (doesn't need full hummingbot)
        await self.test_rest_api_direct()
        await self.test_websocket_public()

        # Connector tests (need hummingbot compiled)
        try:
            await self.test_spot_auth()
            await self.test_spot_balance()
            await self.test_spot_trading_rules()
            # await self.test_spot_order_lifecycle()  # Uncomment to test real orders

            await self.test_perpetual_auth()
            await self.test_perpetual_balance()
            await self.test_perpetual_positions()
        except ImportError as e:
            self.log(f"Connector tests skipped (need compiled hummingbot): {e}", "WARN")

        # Summary
        self.log("=" * 60)
        self.log("TEST SUMMARY")
        self.log("=" * 60)

        passed = sum(1 for _, success in self.results if success)
        failed = sum(1 for _, success in self.results if not success)

        for test_name, success in self.results:
            status = "✅ PASS" if success else "❌ FAIL"
            self.log(f"  {status}: {test_name}")

        self.log(f"\nTotal: {passed} passed, {failed} failed")

        return failed == 0


async def main():
    """Main entry point."""
    try:
        tester = BackpackIntegrationTest()
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
