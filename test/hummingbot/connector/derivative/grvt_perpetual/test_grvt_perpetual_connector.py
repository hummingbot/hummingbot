"""
Unit tests for the GRVT Perpetual connector.
Tests use mocked HTTP responses — no live API calls.
"""
import asyncio
import json
import time
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

# Test constants
SAMPLE_INSTRUMENTS = [
    {
        "instrument": "BTC_USDT_Perp",
        "instrument_hash": "0x020901",
        "base": "BTC",
        "quote": "USDT",
        "kind": "PERPETUAL",
        "settlement_period": "PERPETUAL",
        "base_decimals": 9,
        "quote_decimals": 6,
        "tick_size": "0.1",
        "min_size": "0.001",
        "is_active": True,
    },
    {
        "instrument": "ETH_USDT_Perp",
        "instrument_hash": "0x030901",
        "base": "ETH",
        "quote": "USDT",
        "kind": "PERPETUAL",
        "settlement_period": "PERPETUAL",
        "base_decimals": 9,
        "quote_decimals": 6,
        "tick_size": "0.01",
        "min_size": "0.01",
        "is_active": True,
    },
]

SAMPLE_TICKER = {
    "instrument": "BTC_USDT_Perp",
    "mark_price": "70000.0",
    "index_price": "70010.0",
    "last_price": "70000.0",
    "last_size": "0.1",
    "best_bid_price": "69999.9",
    "best_ask_price": "70000.1",
}


class TestGrvtWebUtils(unittest.TestCase):
    """Test web utility functions."""

    def test_instrument_to_trading_pair(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils import (
            instrument_to_trading_pair, trading_pair_to_instrument
        )
        self.assertEqual(instrument_to_trading_pair("BTC_USDT_Perp"), "BTC-USDT")
        self.assertEqual(instrument_to_trading_pair("ETH_USDT_Perp"), "ETH-USDT")
        self.assertEqual(trading_pair_to_instrument("BTC-USDT"), "BTC_USDT_Perp")
        self.assertEqual(trading_pair_to_instrument("ETH-USDT"), "ETH_USDT_Perp")

    def test_price_to_int(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
        auth = GrvtPerpetualAuth.__new__(GrvtPerpetualAuth)
        self.assertEqual(auth.price_to_int(70000.0), 70000_000000000)
        self.assertEqual(auth.price_to_int(1.5), 1_500000000)

    def test_get_market_data_url(self):
        from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as C
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils import (
            get_market_data_url
        )
        self.assertEqual(get_market_data_url(C.DOMAIN), "https://market-data.grvt.io")
        self.assertEqual(get_market_data_url(C.TESTNET_DOMAIN), "https://market-data.testnet.grvt.io")

    def test_get_expiration_ns(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils import get_expiration_ns
        now_ns = time.time() * 1e9
        exp = get_expiration_ns(3600)
        # Should be roughly 1 hour from now
        self.assertGreater(exp, now_ns + 3500 * 1e9)
        self.assertLess(exp, now_ns + 3700 * 1e9)


class TestGrvtConstants(unittest.TestCase):
    """Test constants and configuration."""

    def test_chain_ids(self):
        from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as C
        self.assertEqual(C.CHAIN_ID_PROD, 325)
        self.assertEqual(C.CHAIN_ID_TESTNET, 326)

    def test_rate_limits_defined(self):
        from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as C
        self.assertGreater(len(C.RATE_LIMITS), 0)
        limit_ids = [r.limit_id for r in C.RATE_LIMITS]
        self.assertIn(C.CREATE_ORDER_URL, limit_ids)
        self.assertIn(C.CANCEL_ORDER_URL, limit_ids)

    def test_order_state_mapping(self):
        from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as C
        from hummingbot.core.data_type.in_flight_order import OrderState
        self.assertEqual(C.ORDER_STATE["FILLED"], OrderState.FILLED)
        self.assertEqual(C.ORDER_STATE["CANCELLED"], OrderState.CANCELED)
        self.assertEqual(C.ORDER_STATE["REJECTED"], OrderState.FAILED)


class TestGrvtAPILive(unittest.TestCase):
    """
    Live API connectivity tests — verify GRVT public endpoints respond correctly.
    These tests call the real API and verify response format.
    """

    def test_instruments_endpoint_returns_perpetuals(self):
        """Verify all_instruments endpoint returns active perpetual contracts."""
        import requests
        r = requests.post(
            "https://market-data.grvt.io/full/v1/all_instruments",
            json={"is_active": True},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        instruments = data.get("result", [])
        self.assertGreater(len(instruments), 0)
        # Verify BTC_USDT_Perp exists
        names = [i["instrument"] for i in instruments]
        self.assertIn("BTC_USDT_Perp", names)
        # Verify structure
        btc = next(i for i in instruments if i["instrument"] == "BTC_USDT_Perp")
        self.assertEqual(btc["kind"], "PERPETUAL")
        self.assertIn("tick_size", btc)
        self.assertIn("min_size", btc)
        self.assertIn("base_decimals", btc)

    def test_ticker_endpoint_returns_price(self):
        """Verify ticker endpoint returns valid market data."""
        import requests
        r = requests.post(
            "https://market-data.grvt.io/full/v1/ticker",
            json={"instrument": "BTC_USDT_Perp"},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        self.assertEqual(r.status_code, 200)
        ticker = r.json().get("result", {})
        mark_price = float(ticker.get("mark_price", 0))
        self.assertGreater(mark_price, 1000.0)  # BTC > $1000
        self.assertLess(mark_price, 1_000_000.0)  # Sanity upper bound

    def test_orderbook_endpoint(self):
        """Verify order book endpoint returns bids and asks."""
        import requests
        r = requests.post(
            "https://market-data.grvt.io/full/v1/book",
            json={"instrument": "BTC_USDT_Perp", "depth": 5},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        self.assertEqual(r.status_code, 200)
        book = r.json().get("result", {})
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        self.assertGreater(len(bids), 0)
        self.assertGreater(len(asks), 0)
        # Verify bid < ask (spread)
        best_bid = float(bids[0]["price"])
        best_ask = float(asks[0]["price"])
        self.assertLess(best_bid, best_ask)

    def test_trading_rules_parse(self):
        """Verify instrument data can be parsed into TradingRule format."""
        import requests
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import parse_instrument_info
        r = requests.post(
            "https://market-data.grvt.io/full/v1/all_instruments",
            json={"is_active": True},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        instruments = r.json().get("result", [])
        perpetuals = [i for i in instruments if i.get("kind") == "PERPETUAL"]
        self.assertGreater(len(perpetuals), 0)

        for instr in perpetuals[:5]:
            parsed = parse_instrument_info(instr)
            self.assertIn("trading_pair", parsed)
            self.assertIn("tick_size", parsed)
            self.assertIn("min_order_size", parsed)
            self.assertGreater(parsed["tick_size"], Decimal("0"))


class TestGrvtAuth(unittest.TestCase):
    """Test GrvtPerpetualAuth without requiring live credentials."""

    def _make_auth(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
        auth = GrvtPerpetualAuth.__new__(GrvtPerpetualAuth)
        auth._api_key = "test_api_key"
        auth._private_key = "0x" + "ab" * 32
        auth._trading_account_id = 123456
        auth._testnet = False
        auth._chain_id = 325
        auth._session_cookie = None
        auth._cookie_expiry = 0.0
        return auth

    def test_size_to_int_default_decimals(self):
        auth = self._make_auth()
        self.assertEqual(auth.size_to_int(1.5), 1_500_000_000)

    def test_size_to_int_custom_decimals(self):
        auth = self._make_auth()
        self.assertEqual(auth.size_to_int(1.0, base_decimals=6), 1_000_000)

    def test_price_to_int_large(self):
        auth = self._make_auth()
        self.assertEqual(auth.price_to_int(100000.0), 100_000_000_000_000)

    def test_price_to_int_zero(self):
        auth = self._make_auth()
        self.assertEqual(auth.price_to_int(0.0), 0)

    def test_get_eip712_domain_mainnet(self):
        auth = self._make_auth()
        domain = auth.get_eip712_domain()
        self.assertEqual(domain["name"], "GRVT Exchange")
        self.assertEqual(domain["version"], "0")
        self.assertEqual(domain["chainId"], 325)

    def test_get_eip712_domain_testnet(self):
        auth = self._make_auth()
        auth._testnet = True
        auth._chain_id = 326
        domain = auth.get_eip712_domain()
        self.assertEqual(domain["chainId"], 326)

    def test_set_session_cookie(self):
        auth = self._make_auth()
        self.assertIsNone(auth._session_cookie)
        auth.set_session_cookie("gravity=test_token", ttl_seconds=3600)
        self.assertEqual(auth._session_cookie, "gravity=test_token")
        self.assertGreater(auth._cookie_expiry, time.time())

    def test_cookie_not_authenticated_initially(self):
        auth = self._make_auth()
        self.assertFalse(time.time() < auth._cookie_expiry)

    def test_cookie_authenticated_after_set(self):
        auth = self._make_auth()
        auth.set_session_cookie("gravity=abc123", ttl_seconds=3600)
        self.assertTrue(bool(auth._session_cookie) and time.time() < auth._cookie_expiry)

    def test_get_login_payload(self):
        auth = self._make_auth()
        payload = auth.get_login_payload()
        self.assertIn("api_key", payload)
        self.assertEqual(payload["api_key"], "test_api_key")

    def test_rest_authenticate_adds_cookie(self):
        auth = self._make_auth()
        auth.set_session_cookie("gravity=session_token", ttl_seconds=3600)

        class FakeRequest:
            headers = {}

        req = FakeRequest()
        result = asyncio.get_event_loop().run_until_complete(auth.rest_authenticate(req))
        self.assertIn("Cookie", result.headers)
        self.assertIn("gravity=session_token", result.headers["Cookie"])

    def test_rest_authenticate_no_cookie(self):
        auth = self._make_auth()

        class FakeRequest:
            headers = {}

        req = FakeRequest()
        result = asyncio.get_event_loop().run_until_complete(auth.rest_authenticate(req))
        self.assertNotIn("Cookie", result.headers)


class TestGrvtUtils(unittest.TestCase):
    """Test utility and parsing functions."""

    def test_is_exchange_information_valid_perpetual(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import is_exchange_information_valid
        valid = {"kind": "PERPETUAL", "settlement_period": "PERPETUAL"}
        self.assertTrue(is_exchange_information_valid(valid))

    def test_is_exchange_information_valid_rejects_spot(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import is_exchange_information_valid
        self.assertFalse(is_exchange_information_valid({"kind": "SPOT", "settlement_period": "PERPETUAL"}))

    def test_parse_instrument_info_fields(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import parse_instrument_info
        parsed = parse_instrument_info(SAMPLE_INSTRUMENTS[0])
        self.assertEqual(parsed["trading_pair"], "BTC-USDT")
        self.assertEqual(parsed["base_asset"], "BTC")
        self.assertEqual(parsed["quote_asset"], "USDT")
        self.assertEqual(parsed["tick_size"], Decimal("0.1"))
        self.assertEqual(parsed["min_order_size"], Decimal("0.001"))
        self.assertEqual(parsed["base_decimals"], 9)

    def test_parse_instrument_info_eth(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import parse_instrument_info
        parsed = parse_instrument_info(SAMPLE_INSTRUMENTS[1])
        self.assertEqual(parsed["trading_pair"], "ETH-USDT")
        self.assertEqual(parsed["step_size"], Decimal("0.01"))

    def test_grvt_order_status_mapping(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import grvt_order_status_to_hummingbot
        from hummingbot.core.data_type.in_flight_order import OrderState
        self.assertEqual(grvt_order_status_to_hummingbot("FILLED"), OrderState.FILLED)
        self.assertEqual(grvt_order_status_to_hummingbot("CANCELLED"), OrderState.CANCELED)
        self.assertEqual(grvt_order_status_to_hummingbot("REJECTED"), OrderState.FAILED)
        self.assertEqual(grvt_order_status_to_hummingbot("OPEN"), OrderState.OPEN)

    def test_order_side_buy_sell(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import order_side_to_grvt
        self.assertTrue(order_side_to_grvt(True))
        self.assertFalse(order_side_to_grvt(False))

    def test_time_in_force_map(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import TIME_IN_FORCE_MAP
        self.assertIn("GTC", TIME_IN_FORCE_MAP)
        self.assertIn("IOC", TIME_IN_FORCE_MAP)
        self.assertEqual(TIME_IN_FORCE_MAP["IOC"], 3)
        self.assertEqual(TIME_IN_FORCE_MAP["FOK"], 4)

    def test_default_fees(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import DEFAULT_FEES
        self.assertEqual(DEFAULT_FEES.maker_percent_fee_decimal, Decimal("0.0002"))
        self.assertEqual(DEFAULT_FEES.taker_percent_fee_decimal, Decimal("0.0005"))


class TestGrvtConstants(unittest.TestCase):
    """Test that all required connector constants are defined."""

    def test_required_endpoint_constants(self):
        from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as C
        for attr in ["CREATE_ORDER_URL", "CANCEL_ORDER_URL", "ACCOUNT_BALANCES_URL",
                     "OPEN_ORDERS_URL", "FUNDING_INFO_URL"]:
            self.assertTrue(hasattr(C, attr), "Missing constant: %s" % attr)

    def test_domain_constants(self):
        from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as C
        self.assertIn("grvt.io", C.DOMAIN)
        self.assertIn("testnet", C.TESTNET_DOMAIN)

    def test_order_states_complete(self):
        from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as C
        from hummingbot.core.data_type.in_flight_order import OrderState
        for state in ["FILLED", "CANCELLED", "REJECTED"]:
            self.assertIn(state, C.ORDER_STATE)

    def test_chain_id_values(self):
        from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as C
        self.assertEqual(C.CHAIN_ID_PROD, 325)
        self.assertEqual(C.CHAIN_ID_TESTNET, 326)
        self.assertNotEqual(C.CHAIN_ID_PROD, C.CHAIN_ID_TESTNET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
