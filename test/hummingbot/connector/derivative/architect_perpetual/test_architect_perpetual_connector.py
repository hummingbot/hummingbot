"""
Unit tests for the Architect Perpetual connector.

Run: python3 -m pytest tests/ -v
Live API tests: TEST_LIVE=1 python3 -m pytest tests/ -v -k live
"""
import os
import sys
import time
import unittest
from decimal import Decimal
from types import ModuleType
from unittest.mock import MagicMock, AsyncMock


def _pkg(name):
    m = ModuleType(name)
    m.__path__ = []
    m.__package__ = name
    return m


def _install_stubs():
    connector_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    if connector_root not in sys.path:
        sys.path.insert(0, connector_root)

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

    class TradingRule:
        def __init__(self, trading_pair="", min_order_size=Decimal("0"),
                     min_price_increment=Decimal("0"), min_base_amount_increment=Decimal("0"),
                     min_notional_size=Decimal("0"), buy_order_collateral_token="USDT",
                     sell_order_collateral_token="USDT", **kwargs):
            self.trading_pair = trading_pair
            self.min_order_size = min_order_size
            self.min_price_increment = min_price_increment

    class ClientFieldData:
        def __init__(self, *args, **kwargs):
            pass

    class BaseConnectorConfigMap:
        @classmethod
        def construct(cls, **kwargs):
            return cls()

    stubs = {
        "hummingbot.core": _pkg("hummingbot.core"),
        "hummingbot.core.api_throttler": _pkg("hummingbot.core.api_throttler"),
        "hummingbot.core.api_throttler.data_types": MagicMock(
            RateLimit=RateLimit, LinkedLimitWeightPair=LinkedLimitWeightPair),
        "hummingbot.core.api_throttler.async_throttler": MagicMock(),
        "hummingbot.core.data_type": _pkg("hummingbot.core.data_type"),
        "hummingbot.core.data_type.in_flight_order": MagicMock(
            OrderState=OrderState, InFlightOrder=MagicMock,
            OrderUpdate=MagicMock, TradeUpdate=MagicMock),
        "hummingbot.core.data_type.trade_fee": MagicMock(
            TradeFeeSchema=TradeFeeSchema, DeductedFromReturnsTradeFee=MagicMock,
            TokenAmount=MagicMock, TradeFeeBase=MagicMock(new_perpetual_fee=MagicMock())),
        "hummingbot.core.data_type.common": MagicMock(),
        "hummingbot.core.data_type.order_book_message": MagicMock(),
        "hummingbot.core.data_type.order_book_row": MagicMock(),
        "hummingbot.core.data_type.funding_info": MagicMock(FundingInfo=MagicMock),
        "hummingbot.core.data_type.cancellation_result": MagicMock(),
        "hummingbot.core.data_type.order_book_tracker_data_source": MagicMock(
            OrderBookTrackerDataSource=MagicMock),
        "hummingbot.core.data_type.user_stream_tracker_data_source": MagicMock(
            UserStreamTrackerDataSource=MagicMock),
        "hummingbot.core.web_assistant": _pkg("hummingbot.core.web_assistant"),
        "hummingbot.core.web_assistant.auth": MagicMock(),
        "hummingbot.core.web_assistant.connections": _pkg("hummingbot.core.web_assistant.connections"),
        "hummingbot.core.web_assistant.connections.data_types": MagicMock(),
        "hummingbot.core.web_assistant.web_assistants_factory": MagicMock(
            WebAssistantsFactory=MagicMock),
        "hummingbot.client": _pkg("hummingbot.client"),
        "hummingbot.client.config": _pkg("hummingbot.client.config"),
        "hummingbot.client.config.config_data_types": MagicMock(
            BaseConnectorConfigMap=BaseConnectorConfigMap, ClientFieldData=ClientFieldData),
        "hummingbot.client.config.config_helpers": MagicMock(),
        "hummingbot.connector.constants": MagicMock(s_decimal_NaN=Decimal("nan")),
        "hummingbot.connector.perpetual_derivative_py_base": MagicMock(
            PerpetualDerivativePyBase=object),
        "hummingbot.connector.trading_rule": MagicMock(TradingRule=TradingRule),
        "hummingbot.logger": MagicMock(HummingbotLogger=MagicMock),
        "hummingbot.core.utils": _pkg("hummingbot.core.utils"),
        "hummingbot.core.utils.async_utils": MagicMock(
            safe_ensure_future=MagicMock, safe_gather=MagicMock),
        "hummingbot.core.rate_oracle": _pkg("hummingbot.core.rate_oracle"),
        "hummingbot.core.rate_oracle.rate_oracle": MagicMock(),
        "bidict": MagicMock(bidict=dict),
    }
    for name, stub in stubs.items():
        sys.modules[name] = stub

    # Patch pydantic.Field for pydantic v1 compat (const=True, client_data=...)
    import pydantic as _pd
    _orig_field = _pd.Field
    def _compat_field(*a, **kw):
        kw.pop("const", None)
        kw.pop("client_data", None)
        return _orig_field(*a, **kw)
    _pd.Field = _compat_field


_install_stubs()

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils


class TestArchitectWebUtils(unittest.TestCase):

    def test_trading_pair_to_symbol(self):
        sym = web_utils.trading_pair_to_architect_symbol("BTC-USDT", "BINANCE")
        self.assertEqual(sym, "BTC-USDT BINANCE Perpetual")

    def test_symbol_to_trading_pair(self):
        pair = web_utils.architect_symbol_to_trading_pair("BTC-USDT BINANCE Perpetual")
        self.assertEqual(pair, "BTC-USDT")

    def test_roundtrip(self):
        pairs = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT"]
        for pair in pairs:
            sym = web_utils.trading_pair_to_architect_symbol(pair, "BINANCE")
            result = web_utils.architect_symbol_to_trading_pair(sym)
            self.assertEqual(result, pair)

    def test_is_perpetual_symbol(self):
        self.assertTrue(web_utils.is_perpetual_symbol("BTC-USDT BINANCE Perpetual"))
        self.assertFalse(web_utils.is_perpetual_symbol("BTC-USDT BINANCE Future"))
        self.assertFalse(web_utils.is_perpetual_symbol("BTC-USDT"))

    def test_is_paper_trading(self):
        self.assertFalse(web_utils.is_paper_trading(CONSTANTS.DOMAIN))
        self.assertTrue(web_utils.is_paper_trading(CONSTANTS.PAPER_DOMAIN))


class TestArchitectConstants(unittest.TestCase):

    def test_domain_values(self):
        self.assertEqual(CONSTANTS.DOMAIN, "architect_perpetual")
        self.assertEqual(CONSTANTS.PAPER_DOMAIN, "architect_perpetual_paper")

    def test_grpc_endpoint(self):
        self.assertEqual(CONSTANTS.GRPC_ENDPOINT, "app.architect.co")

    def test_order_state_mapping(self):
        from hummingbot.core.data_type.in_flight_order import OrderState
        self.assertEqual(CONSTANTS.ORDER_STATE.get("Open"), OrderState.OPEN)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("Out"), OrderState.FILLED)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("Canceled"), OrderState.CANCELED)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("Rejected"), OrderState.FAILED)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("Pending"), OrderState.PENDING_CREATE)
        self.assertEqual(CONSTANTS.ORDER_STATE.get("ReconciledOut"), OrderState.FILLED)

    def test_rate_limits_defined(self):
        self.assertGreater(len(CONSTANTS.RATE_LIMITS), 0)

    def test_default_execution_venue(self):
        self.assertEqual(CONSTANTS.DEFAULT_EXECUTION_VENUE, "BINANCE")


class TestArchitectUtils(unittest.TestCase):

    def test_default_fees(self):
        from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_utils import DEFAULT_FEES
        self.assertEqual(DEFAULT_FEES.maker_percent_fee_decimal, Decimal("0.0002"))
        self.assertEqual(DEFAULT_FEES.taker_percent_fee_decimal, Decimal("0.0005"))

    def test_order_status_to_hummingbot(self):
        from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_utils import order_status_to_hummingbot
        from hummingbot.core.data_type.in_flight_order import OrderState
        self.assertEqual(order_status_to_hummingbot("Open"), OrderState.OPEN)
        self.assertEqual(order_status_to_hummingbot("Canceled"), OrderState.CANCELED)
        self.assertEqual(order_status_to_hummingbot("Out"), OrderState.FILLED)
        self.assertEqual(order_status_to_hummingbot("Rejected"), OrderState.FAILED)


class TestArchitectConnectorHelpers(unittest.TestCase):

    def _make_connector(self):
        from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
            ArchitectPerpetualDerivative,
        )
        conn = object.__new__(ArchitectPerpetualDerivative)
        conn._domain = CONSTANTS.DOMAIN
        conn._execution_venue = "BINANCE"
        conn._trading_account = None
        conn._client = None
        return conn

    def test_get_buy_collateral_token(self):
        conn = self._make_connector()
        self.assertEqual(conn.get_buy_collateral_token("BTC-USDT"), "USDT")
        self.assertEqual(conn.get_buy_collateral_token("ETH-USDC"), "USDC")

    def test_get_sell_collateral_token(self):
        conn = self._make_connector()
        self.assertEqual(conn.get_sell_collateral_token("BTC-USDT"), "USDT")

    def test_generate_order_tag_max_10_chars(self):
        conn = self._make_connector()
        import uuid
        order_id = f"HBOT{uuid.uuid4().hex[:6]}"
        tag = conn._generate_order_tag(order_id)
        self.assertLessEqual(len(tag), 10)
        self.assertTrue(tag.isascii())

    def test_client_order_id_prefix(self):
        conn = self._make_connector()
        self.assertEqual(conn.client_order_id_prefix, "HBOT")

    def test_client_order_id_max_length(self):
        conn = self._make_connector()
        self.assertEqual(conn.client_order_id_max_length, 10)

    def test_supported_order_types(self):
        from hummingbot.core.data_type.common import OrderType
        conn = self._make_connector()
        types = conn.supported_order_types()
        self.assertIn(OrderType.LIMIT, types)
        self.assertIn(OrderType.MARKET, types)

    def test_supported_position_modes(self):
        from hummingbot.core.data_type.common import PositionMode
        conn = self._make_connector()
        modes = conn.supported_position_modes()
        self.assertIn(PositionMode.ONEWAY, modes)


class TestArchitectConnectorFormatRules(unittest.IsolatedAsyncioTestCase):

    def _make_connector(self):
        from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
            ArchitectPerpetualDerivative,
        )
        conn = object.__new__(ArchitectPerpetualDerivative)
        conn._domain = CONSTANTS.DOMAIN
        conn._execution_venue = "BINANCE"
        conn._client = None
        return conn

    async def test_format_rules_no_client_returns_empty(self):
        conn = self._make_connector()
        rules = await conn._format_trading_rules(["BTC-USDT BINANCE Perpetual"])
        # Without client, _format_trading_rules returns empty
        self.assertEqual(rules, [])

    async def test_format_rules_with_mock_client(self):
        conn = self._make_connector()
        # Mock the client
        mock_exec_info = MagicMock()
        mock_exec_info.min_order_quantity = "0.001"
        mock_exec_info.step_size = "0.001"
        mock_exec_info.tick_size = "0.01"

        mock_client = AsyncMock()
        mock_client.get_execution_info = AsyncMock(return_value=mock_exec_info)
        conn._client = mock_client

        rules = await conn._format_trading_rules(["BTC-USDT BINANCE Perpetual"])
        self.assertEqual(len(rules), 1)


# ---------------------------------------------------------------------------
# Live API Tests
# ---------------------------------------------------------------------------
LIVE_TESTS_ENABLED = os.environ.get("TEST_LIVE", "0") == "1"
LIVE_API_KEY = os.environ.get("ARCHITECT_API_KEY", "")
LIVE_API_SECRET = os.environ.get("ARCHITECT_API_SECRET", "")


@unittest.skipUnless(LIVE_TESTS_ENABLED and LIVE_API_KEY, "Live tests: set TEST_LIVE=1 ARCHITECT_API_KEY=... ARCHITECT_API_SECRET=...")
class TestArchitectLiveAPI(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        from architect_py import AsyncClient
        self.client = await AsyncClient.connect(
            endpoint="app.architect.co",
            api_key=LIVE_API_KEY,
            api_secret=LIVE_API_SECRET,
            paper_trading=True,  # Use paper trading for live tests
        )

    async def asyncTearDown(self):
        if self.client:
            await self.client.close()

    async def test_list_symbols_returns_perpetuals(self):
        symbols = await self.client.list_symbols()
        perps = [s for s in symbols if "Perpetual" in s and "BINANCE" in s]
        self.assertGreater(len(perps), 0)

    async def test_get_l2_snapshot(self):
        snapshot = await self.client.get_l2_book_snapshot(
            symbol="BTC-USDT BINANCE Perpetual",
            venue="BINANCE",
        )
        self.assertTrue(len(snapshot.b) > 0 or len(snapshot.a) > 0)

    async def test_list_accounts(self):
        accounts = await self.client.list_accounts()
        self.assertIsInstance(accounts, list)

    async def test_get_ticker(self):
        ticker = await self.client.get_ticker(
            symbol="BTC-USDT BINANCE Perpetual",
            venue="BINANCE",
        )
        price = float(ticker.p or ticker.mp or 0)
        self.assertGreater(price, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
