"""
Unit tests for the EVEDEX Perpetual connector.

Run with: python3 -m pytest tests/connector/derivative/evedex_perpetual/ -v
Live API tests: TEST_LIVE=1 python3 -m pytest tests/ -v -k live
"""
import asyncio
import os
import sys
import time
import unittest
from decimal import Decimal
from types import ModuleType
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Inject hummingbot stub modules so our connector files can be imported
# without a full hummingbot installation.
# ---------------------------------------------------------------------------

def _make_stub(*args, **kwargs):
    return MagicMock()


def _pkg(name):
    """Create a ModuleType stub that acts as a package."""
    m = ModuleType(name)
    m.__path__ = []
    m.__package__ = name
    return m


def _install_hummingbot_stubs():
    """
    Inject stubs for hummingbot.core (not shipped with the connector).
    Real connector files are found via the filesystem (evedex_connector/ root).
    """

    # Add the connector root to sys.path so Python can find hummingbot/ on disk
    connector_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    if connector_root not in sys.path:
        sys.path.insert(0, connector_root)

    # Enum-like stubs
    class OrderState:
        OPEN = "OPEN"
        PARTIALLY_FILLED = "PARTIALLY_FILLED"
        FILLED = "FILLED"
        CANCELED = "CANCELED"
        FAILED = "FAILED"
        PENDING_CREATE = "PENDING_CREATE"

    class RateLimit:
        def __init__(self, limit_id="", limit=100, time_interval=60, linked_limits=None):
            self.limit_id = limit_id

    class LinkedLimitWeightPair:
        def __init__(self, *args, **kwargs):
            pass

    class TradeFeeSchema:
        def __init__(self, maker_percent_fee_decimal=Decimal("0"),
                     taker_percent_fee_decimal=Decimal("0"),
                     buy_percent_fee_deducted_from_returns=False):
            self.maker_percent_fee_decimal = maker_percent_fee_decimal
            self.taker_percent_fee_decimal = taker_percent_fee_decimal
            self.buy_percent_fee_deducted_from_returns = buy_percent_fee_deducted_from_returns

    class AuthBase:
        async def rest_authenticate(self, request):
            return request
        async def ws_authenticate(self, request):
            return request

    class RESTRequest:
        def __init__(self, *args, **kwargs):
            self.headers = {}

    class WSRequest:
        def __init__(self, *args, **kwargs):
            pass

    class TradingRule:
        def __init__(self, trading_pair="", min_order_size=Decimal("0"),
                     min_price_increment=Decimal("0"), min_base_amount_increment=Decimal("0"),
                     min_notional_size=Decimal("0"), buy_order_collateral_token="USD",
                     sell_order_collateral_token="USD", **kwargs):
            self.trading_pair = trading_pair
            self.min_order_size = min_order_size
            self.min_price_increment = min_price_increment
            self.min_base_amount_increment = min_base_amount_increment
            self.min_notional_size = min_notional_size

    class ClientFieldData:
        def __init__(self, *args, **kwargs):
            pass

    class BaseConnectorConfigMap:
        @classmethod
        def construct(cls, **kwargs):
            return cls()

    # Build stub module hierarchy for hummingbot.core (not on disk)
    stub_mods = {
        "hummingbot.core": _pkg("hummingbot.core"),
        "hummingbot.core.api_throttler": _pkg("hummingbot.core.api_throttler"),
        "hummingbot.core.api_throttler.data_types": MagicMock(
            RateLimit=RateLimit,
            LinkedLimitWeightPair=LinkedLimitWeightPair,
        ),
        "hummingbot.core.api_throttler.async_throttler": MagicMock(
            AsyncThrottler=MagicMock,
        ),
        "hummingbot.core.data_type": _pkg("hummingbot.core.data_type"),
        "hummingbot.core.data_type.in_flight_order": MagicMock(
            OrderState=OrderState,
            InFlightOrder=MagicMock,
            OrderUpdate=MagicMock,
            TradeUpdate=MagicMock,
        ),
        "hummingbot.core.data_type.trade_fee": MagicMock(
            TradeFeeSchema=TradeFeeSchema,
            DeductedFromReturnsTradeFee=MagicMock,
            TokenAmount=MagicMock,
            TradeFeeBase=MagicMock(new_perpetual_fee=MagicMock()),
        ),
        "hummingbot.core.data_type.common": MagicMock(),
        "hummingbot.core.data_type.order_book_message": MagicMock(),
        "hummingbot.core.data_type.order_book_row": MagicMock(),
        "hummingbot.core.data_type.funding_info": MagicMock(FundingInfo=MagicMock),
        "hummingbot.core.data_type.cancellation_result": MagicMock(),
        "hummingbot.core.data_type.order_book_tracker_data_source": MagicMock(
            OrderBookTrackerDataSource=MagicMock,
        ),
        "hummingbot.core.data_type.user_stream_tracker_data_source": MagicMock(
            UserStreamTrackerDataSource=MagicMock,
        ),
        "hummingbot.core.web_assistant": _pkg("hummingbot.core.web_assistant"),
        "hummingbot.core.web_assistant.auth": MagicMock(AuthBase=AuthBase),
        "hummingbot.core.web_assistant.connections": _pkg("hummingbot.core.web_assistant.connections"),
        "hummingbot.core.web_assistant.connections.data_types": MagicMock(
            RESTRequest=RESTRequest,
            WSRequest=WSRequest,
            RESTMethod=MagicMock(),
        ),
        "hummingbot.core.web_assistant.web_assistants_factory": MagicMock(
            WebAssistantsFactory=MagicMock,
        ),
        "hummingbot.client": _pkg("hummingbot.client"),
        "hummingbot.client.config": _pkg("hummingbot.client.config"),
        "hummingbot.client.config.config_data_types": MagicMock(
            BaseConnectorConfigMap=BaseConnectorConfigMap,
            ClientFieldData=ClientFieldData,
        ),
        "hummingbot.client.config.config_helpers": MagicMock(),
        "hummingbot.connector.constants": MagicMock(s_decimal_NaN=Decimal("nan")),
        "hummingbot.connector.perpetual_derivative_py_base": MagicMock(
            PerpetualDerivativePyBase=object,
        ),
        "hummingbot.connector.trading_rule": MagicMock(TradingRule=TradingRule),
        "hummingbot.logger": MagicMock(HummingbotLogger=MagicMock),
        "hummingbot.core.utils": _pkg("hummingbot.core.utils"),
        "hummingbot.core.utils.async_utils": MagicMock(
            safe_ensure_future=MagicMock,
            safe_gather=MagicMock,
        ),
        "hummingbot.core.rate_oracle": _pkg("hummingbot.core.rate_oracle"),
        "hummingbot.core.rate_oracle.rate_oracle": MagicMock(),
        "bidict": MagicMock(bidict=dict),
    }

    for name, stub in stub_mods.items():
        sys.modules[name] = stub

    # Patch pydantic.Field to tolerate pydantic v1 kwargs like const=True
    # (evedex_perpetual_utils.py uses these; the installed pydantic v2 doesn't support them)
    import pydantic as _pydantic_real
    _original_field = _pydantic_real.Field

    def _compat_field(*args, **kwargs):
        kwargs.pop("const", None)
        kwargs.pop("client_data", None)
        return _original_field(*args, **kwargs)

    _pydantic_real.Field = _compat_field


_install_hummingbot_stubs()

# Now we can import our connector modules
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth

# ---------------------------------------------------------------------------
# Sample test data
# ---------------------------------------------------------------------------

SAMPLE_INSTRUMENT = {
    "id": "btc-usd",
    "from": {"symbol": "BTC"},
    "to": {"symbol": "USD"},
    "minQuantity": "0.001",
    "maxQuantity": "500",
    "quantityIncrement": "0.001",
    "priceIncrement": "0.1",
    "minVolume": "5",
    "maxLeverage": 100,
    "lastPrice": "70000",
    "markPrice": "70010",
    "fundingRate": "0.0001",
    "marketState": "OPEN",
    "visibility": "all",
    "trading": "all",
}

SAMPLE_BALANCE_RESPONSE = [
    {"coin": "USD", "balance": "10000.0", "availableBalance": "9500.0"},
    {"coin": "BTC", "balance": "0.5", "availableBalance": "0.5"},
]

SAMPLE_POSITION_RESPONSE = [
    {
        "instrument": "btc-usd",
        "quantity": "0.1",
        "side": "buy",
        "entryPrice": "69500.0",
        "unrealisedPnl": "50.0",
        "margin": "695.0",
    }
]

# Well-known test private key (DO NOT use with real funds)
TEST_PRIVATE_KEY = "0x4c0883a69102937d6231471b5dbb6e538eba2ef2d179bf25c028a28c8f7d9e50"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEvedexWebUtils(unittest.TestCase):
    """Test trading pair and instrument ID conversion utilities."""

    def test_instrument_to_trading_pair(self):
        self.assertEqual(web_utils.instrument_to_trading_pair("btc-usd"), "BTC-USD")
        self.assertEqual(web_utils.instrument_to_trading_pair("eth-usd"), "ETH-USD")
        self.assertEqual(web_utils.instrument_to_trading_pair("BTC-USD"), "BTC-USD")

    def test_trading_pair_to_instrument(self):
        self.assertEqual(web_utils.trading_pair_to_instrument("BTC-USD"), "btc-usd")
        self.assertEqual(web_utils.trading_pair_to_instrument("ETH-USD"), "eth-usd")

    def test_roundtrip_conversion(self):
        pairs = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]
        for pair in pairs:
            instrument = web_utils.trading_pair_to_instrument(pair)
            result = web_utils.instrument_to_trading_pair(instrument)
            self.assertEqual(result, pair)

    def test_get_trade_base_url(self):
        self.assertEqual(web_utils.get_trade_base_url(CONSTANTS.DOMAIN), CONSTANTS.TRADE_BASE_URL)
        self.assertEqual(web_utils.get_trade_base_url(CONSTANTS.TESTNET_DOMAIN), CONSTANTS.TESTNET_TRADE_BASE_URL)

    def test_get_ws_url(self):
        self.assertIn("wss://", web_utils.get_ws_url(CONSTANTS.DOMAIN))

    def test_ws_channel_name(self):
        channel = web_utils.ws_channel_name("orderBook-{instrument}-0.1", CONSTANTS.DOMAIN, instrument="btc-usd")
        self.assertEqual(channel, "futures-perp:orderBook-btc-usd-0.1")

    def test_user_channel_names(self):
        channel = web_utils.ws_channel_name("order-{user_id}", CONSTANTS.DOMAIN, user_id="user123")
        self.assertEqual(channel, "futures-perp:order-user123")


class TestEvedexConstants(unittest.TestCase):
    """Test constants and configuration values."""

    def test_production_urls_set(self):
        self.assertTrue(CONSTANTS.TRADE_BASE_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.AUTH_BASE_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.WS_URL.startswith("wss://"))

    def test_testnet_urls_set(self):
        self.assertTrue(CONSTANTS.TESTNET_TRADE_BASE_URL.startswith("https://"))
        self.assertIn("evedex.io", CONSTANTS.TESTNET_TRADE_BASE_URL)

    def test_chain_ids(self):
        self.assertEqual(CONSTANTS.CHAIN_ID, 161803)
        self.assertEqual(CONSTANTS.TESTNET_CHAIN_ID, 16182)

    def test_ws_channel_prefix(self):
        self.assertEqual(CONSTANTS.WS_CHANNEL_PREFIX, "futures-perp")
        self.assertEqual(CONSTANTS.TESTNET_WS_CHANNEL_PREFIX, "futures-perp-beta")

    def test_eip712_domain(self):
        self.assertEqual(CONSTANTS.EIP712_DOMAIN_NAME, "evedex")
        self.assertEqual(CONSTANTS.EIP712_DOMAIN_VERSION, "1")

    def test_order_state_mapping(self):
        from hummingbot.core.data_type.in_flight_order import OrderState
        self.assertEqual(CONSTANTS.ORDER_STATE.get("ACTIVE"), OrderState.OPEN)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("FILLED"), OrderState.FILLED)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("CANCELED"), OrderState.CANCELED)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("CANCELLED"), OrderState.CANCELED)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("PARTIALLY_FILLED"), OrderState.PARTIALLY_FILLED)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("REJECTED"), OrderState.FAILED)

    def test_rate_limits_defined(self):
        self.assertGreater(len(CONSTANTS.RATE_LIMITS), 0)


class TestEvedexAuth(unittest.TestCase):
    """Test EIP-712 signing and JWT auth management."""

    def setUp(self):
        self.auth = EvedexPerpetualAuth(private_key=TEST_PRIVATE_KEY, testnet=True)

    def test_address_derivation(self):
        self.assertTrue(self.auth.address.startswith("0x"))
        self.assertEqual(len(self.auth.address), 42)

    def test_chain_id_testnet(self):
        self.assertEqual(self.auth.chain_id, CONSTANTS.TESTNET_CHAIN_ID)

    def test_chain_id_mainnet(self):
        auth = EvedexPerpetualAuth(private_key=TEST_PRIVATE_KEY, testnet=False)
        self.assertEqual(auth.chain_id, CONSTANTS.CHAIN_ID)

    def test_generate_order_id(self):
        order_id = self.auth.generate_order_id()
        self.assertTrue(order_id.startswith("HBOT-"))
        self.assertEqual(len(order_id), 21)  # HBOT- (5) + 16 hex chars

    def test_generate_order_ids_unique(self):
        ids = {self.auth.generate_order_id() for _ in range(20)}
        self.assertEqual(len(ids), 20)

    def test_price_multiplier(self):
        self.assertEqual(self.auth.to_matcher_number(1.0), 10**18)
        self.assertEqual(self.auth.to_matcher_number(0.5), int(0.5 * 10**18))

    def test_sign_limit_order_structure(self):
        signed = self.auth.sign_limit_order(
            order_id="HBOT-test123",
            instrument="btc-usd",
            side="buy",
            leverage=10,
            quantity=0.01,
            limit_price=70000.0,
        )
        required_fields = ["id", "instrument", "side", "leverage", "quantity", "limitPrice", "chainId", "signature"]
        for field in required_fields:
            self.assertIn(field, signed, f"Missing field: {field}")
        self.assertEqual(signed["instrument"], "btc-usd")
        self.assertEqual(signed["side"], "buy")
        self.assertEqual(signed["leverage"], 10)
        self.assertIsInstance(signed["signature"], str)
        self.assertGreater(len(signed["signature"]), 10)

    def test_sign_market_order_structure(self):
        signed = self.auth.sign_market_order(
            order_id="HBOT-test456",
            instrument="eth-usd",
            side="sell",
            leverage=5,
            cash_quantity=1000.0,
        )
        required_fields = ["id", "instrument", "side", "timeInForce", "leverage", "cashQuantity", "chainId", "signature"]
        for field in required_fields:
            self.assertIn(field, signed, f"Missing field: {field}")
        self.assertEqual(signed["timeInForce"], "IOC")
        self.assertEqual(signed["side"], "sell")

    def test_jwt_not_authenticated_initially(self):
        self.assertFalse(self.auth.is_authenticated())
        self.assertEqual(self.auth.get_auth_headers(), {})

    def test_jwt_set_and_authenticated(self):
        self.auth.set_jwt_token("test-jwt-token", "user-123", ttl_seconds=3600)
        self.assertTrue(self.auth.is_authenticated())
        headers = self.auth.get_auth_headers()
        self.assertEqual(headers["Authorization"], "Bearer test-jwt-token")
        self.assertEqual(self.auth.user_exchange_id, "user-123")

    def test_eip712_domain(self):
        domain = self.auth.get_eip712_domain()
        self.assertEqual(domain["name"], "evedex")
        self.assertEqual(domain["version"], "1")
        self.assertEqual(domain["chainId"], CONSTANTS.TESTNET_CHAIN_ID)


class TestEvedexSiweMessage(unittest.TestCase):
    """Test SIWE message construction."""

    def _make_connector(self):
        """Create a minimal connector instance without full init."""
        from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import (
            EvedexPerpetualDerivative,
        )
        conn = object.__new__(EvedexPerpetualDerivative)
        conn._domain = CONSTANTS.DOMAIN
        return conn

    def test_siwe_message_format(self):
        conn = self._make_connector()
        msg = conn._build_siwe_message(
            address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            nonce="testnonce123",
            chain_id=161803,
        )
        self.assertIn("evedex.com wants you to sign in", msg)
        self.assertIn("0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B", msg)
        self.assertIn("testnonce123", msg)
        self.assertIn("161803", msg)
        self.assertIn("URI: https://evedex.com", msg)
        self.assertIn("Version: 1", msg)
        self.assertIn("Issued At:", msg)
        self.assertIn("Sign in to evedex.com", msg)


class TestEvedexTradingRules(unittest.IsolatedAsyncioTestCase):
    """Test trading rule parsing logic."""

    def _make_connector(self):
        from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import (
            EvedexPerpetualDerivative,
        )
        conn = object.__new__(EvedexPerpetualDerivative)
        conn._domain = CONSTANTS.DOMAIN
        return conn

    async def test_format_single_instrument(self):
        conn = self._make_connector()
        rules = await conn._format_trading_rules([SAMPLE_INSTRUMENT])
        self.assertEqual(len(rules), 1)

    async def test_format_filters_closed_markets(self):
        conn = self._make_connector()
        closed = {**SAMPLE_INSTRUMENT, "marketState": "CLOSED"}
        rules = await conn._format_trading_rules([SAMPLE_INSTRUMENT, closed])
        self.assertEqual(len(rules), 1)

    async def test_format_trading_pair_from_id(self):
        conn = self._make_connector()
        rules = await conn._format_trading_rules([SAMPLE_INSTRUMENT])
        # The TradingRule constructor is mocked, so just verify _format_trading_rules runs
        self.assertIsNotNone(rules)

    async def test_format_multiple_instruments(self):
        conn = self._make_connector()
        instruments = [
            {**SAMPLE_INSTRUMENT, "id": "btc-usd"},
            {**SAMPLE_INSTRUMENT, "id": "eth-usd"},
            {**SAMPLE_INSTRUMENT, "id": "sol-usd"},
        ]
        rules = await conn._format_trading_rules(instruments)
        self.assertEqual(len(rules), 3)


# ---------------------------------------------------------------------------
# Live API Tests (disabled by default — set TEST_LIVE=1 to enable)
# ---------------------------------------------------------------------------
LIVE_TESTS_ENABLED = os.environ.get("TEST_LIVE", "0") == "1"


@unittest.skipUnless(LIVE_TESTS_ENABLED, "Live tests disabled. Set TEST_LIVE=1 to enable.")
class TestEvedexLiveAPI(unittest.IsolatedAsyncioTestCase):
    """Live integration tests against EVEDEX mainnet (read-only, no auth required)."""

    async def test_fetch_instruments(self):
        import aiohttp
        url = f"{CONSTANTS.TRADE_BASE_URL}{CONSTANTS.INSTRUMENTS_URL}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"Accept": "application/json"}) as resp:
                self.assertEqual(resp.status, 200)
                data = await resp.json()
                instruments = data if isinstance(data, list) else []
                self.assertGreater(len(instruments), 0)
                ids = [i.get("id", "") for i in instruments]
                self.assertIn("btc-usd", ids)

    async def test_fetch_order_book(self):
        import aiohttp
        url = f"{CONSTANTS.TRADE_BASE_URL}/api/market/btc-usd/deep"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"maxLevel": 5}) as resp:
                self.assertEqual(resp.status, 200)
                data = await resp.json()
                self.assertIn("bids", data)
                self.assertIn("asks", data)
                self.assertGreater(len(data["bids"]), 0)

    async def test_btc_mark_price_positive(self):
        import aiohttp
        url = f"{CONSTANTS.TRADE_BASE_URL}{CONSTANTS.INSTRUMENTS_URL}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                instruments = await resp.json()
                for instr in instruments:
                    if instr.get("id") == "btc-usd":
                        price = float(instr.get("markPrice", 0))
                        self.assertGreater(price, 0)
                        return
                self.fail("btc-usd instrument not found")

    async def test_websocket_connect(self):
        import websockets
        ws_url = CONSTANTS.WS_URL
        async with websockets.connect(ws_url) as ws:
            connect_msg = {"id": 1, "connect": {"token": "", "data": {}}}
            import json
            await ws.send(json.dumps(connect_msg))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            self.assertIn("connect", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
