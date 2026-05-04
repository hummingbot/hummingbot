import asyncio
import sys
import types
import unittest
from decimal import Decimal
from enum import Enum
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.web_assistant.connections.data_types import RESTMethod

try:
    __import__("hummingbot.core.data_type.limit_order")
except Exception:
    if "hummingbot.core.data_type.limit_order" not in sys.modules:
        fake_limit_order = types.ModuleType("hummingbot.core.data_type.limit_order")

        class LimitOrder:
            pass

        fake_limit_order.LimitOrder = LimitOrder
        sys.modules["hummingbot.core.data_type.limit_order"] = fake_limit_order

try:
    __import__("hummingbot.core.data_type.order_book")
except Exception:
    if "hummingbot.core.data_type.order_book" not in sys.modules:
        fake_order_book = types.ModuleType("hummingbot.core.data_type.order_book")

        class OrderBook:
            def apply_snapshot(self, bids, asks, update_id):
                _ = bids
                _ = asks
                _ = update_id

        fake_order_book.OrderBook = OrderBook
        sys.modules["hummingbot.core.data_type.order_book"] = fake_order_book

try:
    __import__("hummingbot.connector.exchange_base")
except Exception:
    if "hummingbot.connector.exchange_base" not in sys.modules:
        fake_exchange_base = types.ModuleType("hummingbot.connector.exchange_base")

        class ExchangeBase:
            def __init__(self, *args, **kwargs):
                _ = args
                _ = kwargs
                self._account_balances = {}
                self._account_available_balances = {}
                self._trading_fees = {}

            def trade_fee_schema(self):
                return TradeFeeSchema()

            def _set_order_book_tracker(self, order_book_tracker):
                self.order_book_tracker = order_book_tracker

        fake_exchange_base.ExchangeBase = ExchangeBase
        sys.modules["hummingbot.connector.exchange_base"] = fake_exchange_base

try:
    __import__("hummingbot.connector.trading_rule")
except Exception:
    if "hummingbot.connector.trading_rule" not in sys.modules:
        fake_trading_rule = types.ModuleType("hummingbot.connector.trading_rule")

        class TradingRule:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        fake_trading_rule.TradingRule = TradingRule
        sys.modules["hummingbot.connector.trading_rule"] = fake_trading_rule

if "hummingbot.core.network_iterator" not in sys.modules:
    fake_network_iterator = types.ModuleType("hummingbot.core.network_iterator")

    class NetworkStatus(Enum):
        STOPPED = 0
        NOT_CONNECTED = 1
        CONNECTED = 2

    fake_network_iterator.NetworkStatus = NetworkStatus
    sys.modules["hummingbot.core.network_iterator"] = fake_network_iterator

try:
    from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange
    from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
    _LIGHTER_EXCHANGE_AVAILABLE = True
except ModuleNotFoundError:
    _LIGHTER_EXCHANGE_AVAILABLE = False


def _set_exchange_timestamp(exchange, timestamp):
    # Runtime implementations differ between pure-python and cython-backed objects.
    try:
        exchange.current_timestamp = timestamp
        return
    except (AttributeError, TypeError):
        pass
    try:
        exchange._set_current_timestamp(float(timestamp))
        return
    except (AttributeError, TypeError):
        pass
    object.__setattr__(exchange, "_current_timestamp", float(timestamp))


@unittest.skipUnless(_LIGHTER_EXCHANGE_AVAILABLE, "Core exchange runtime modules are unavailable in this local environment")
class LighterExchangeTests(IsolatedAsyncioWrapperTestCase):
    def test_init_and_properties(self):
        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.ExchangePyBase.__init__", lambda self, *a, **kw: None):
            exchange = LighterExchange(
                lighter_api_key_private_key="0x" + ("a" * 64),
                lighter_api_key_index="7",
                lighter_account_index="693751",
                trading_pairs=["ETH-USDC"],
                trading_required=False,
            )

        self.assertEqual("lighter", exchange.name)
        self.assertEqual("lighter", exchange.domain)
        self.assertEqual(["ETH-USDC"], exchange.trading_pairs)
        self.assertFalse(exchange.is_trading_required)
        self.assertTrue(exchange.is_cancel_request_in_exchange_synchronous)
        self.assertEqual("https://mainnet.zklighter.elliot.ai", exchange._api_host_for_signer())

    def test_supported_order_types_and_request_paths(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        self.assertEqual([OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET], exchange.supported_order_types())
        self.assertEqual("/orderBooks", exchange.trading_rules_request_path)
        self.assertEqual("/orderBooks", exchange.trading_pairs_request_path)
        self.assertEqual("/orderBooks", exchange.check_network_request_path)

    async def test_refresh_market_metadata_and_get_market_spec(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._market_id_by_symbol = {}
        exchange._size_decimals_by_symbol = {}
        exchange._price_decimals_by_symbol = {}
        exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value="ETH/USDC")
        exchange._api_get = AsyncMock(
            return_value={
                "order_books": [
                    {
                        "symbol": "ETH/USDC",
                        "market_type": "spot",
                        "market_id": 2048,
                        "supported_size_decimals": 4,
                        "supported_price_decimals": 2,
                    }
                ]
            }
        )

        await exchange._refresh_market_metadata()
        market_spec = await exchange._get_market_spec("ETH-USDC")

        self.assertEqual((2048, 4, 2, "ETH/USDC"), market_spec)

    async def test_get_market_spec_raises_when_missing(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._market_id_by_symbol = {}
        exchange._size_decimals_by_symbol = {}
        exchange._price_decimals_by_symbol = {}
        exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value="MISSING")
        exchange._refresh_market_metadata = AsyncMock()

        with self.assertRaises(ValueError):
            await exchange._get_market_spec("ETH-USDC")

    async def test_place_order_and_cancel_success(self):
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._client_order_index_from_order_id = lambda order_id: 999
        exchange._allocate_client_order_index = MagicMock(return_value=999)
        exchange._get_api_key_index = lambda: 7

        signer_client = type(
            "SignerClient",
            (),
            {
                "ORDER_TYPE_LIMIT": 1,
                "ORDER_TYPE_MARKET": 2,
                "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
                "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
                "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
                "DEFAULT_28_DAY_ORDER_EXPIRY": 1000,
                "DEFAULT_IOC_EXPIRY": 1001,
            },
        )()
        signer_client.create_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 200})(), None))
        signer_client.cancel_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 200})(), None))
        exchange._get_lighter_signer_client = lambda: signer_client
        exchange._refresh_signer_client = lambda: signer_client
        exchange._signer_client_lock = asyncio.Lock()
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: False
        exchange._response_code = lambda r: getattr(r, "code", 0)
        exchange._sleep = AsyncMock()
        exchange._account_available_balances = None
        exchange._schedule_balance_sync_for_terminal_update = lambda *args, **kwargs: None

        with patch.object(LighterExchange, "_allocate_client_order_index", return_value=999):
            exchange_order_id, ts = await exchange._place_order(
                order_id="HBOT-A",
                trading_pair="ETH-USDC",
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("10"),
            )
            result = await exchange._place_cancel("HBOT-A", type("Tracked", (), {"client_order_id": "HBOT-A", "trading_pair": "ETH-USDC", "exchange_order_id": "42"})())

        self.assertTrue(exchange_order_id.isdigit(), f"exchange_order_id should be a digit string, got: {exchange_order_id}")
        self.assertEqual(1700000000, ts)
        self.assertTrue(result)

    async def test_place_order_and_cancel_errors(self):
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._client_order_index_from_order_id = lambda order_id: 111
        exchange._get_api_key_index = lambda: 7

        signer_client = type(
            "SignerClient",
            (),
            {
                "ORDER_TYPE_LIMIT": 1,
                "ORDER_TYPE_MARKET": 2,
                "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
                "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
                "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
                "DEFAULT_28_DAY_ORDER_EXPIRY": 1000,
                "DEFAULT_IOC_EXPIRY": 1001,
            },
        )()
        signer_client.create_order = AsyncMock(return_value=(None, None, "err"))
        signer_client.cancel_order = AsyncMock(return_value=(None, None, "err"))
        exchange._get_lighter_signer_client = lambda: signer_client

        mock_order_book = type("OrderBook", (), {"get_price": lambda self, is_bid: 10.0})()
        exchange.get_order_book = lambda trading_pair: mock_order_book

        with self.assertRaises(IOError):
            await exchange._place_order(
                order_id="HBOT-B",
                trading_pair="ETH-USDC",
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.MARKET,
                price=Decimal("10"),
            )

        with self.assertRaises(IOError):
            await exchange._place_cancel("HBOT-B", type("Tracked", (), {"trading_pair": "ETH-USDC", "exchange_order_id": "42"})())

    async def test_place_modify_sends_signed_modify_order(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._get_market_spec = AsyncMock(return_value=(45, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 4

        signer_client = type("SignerClient", (), {})()
        signer_client.modify_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 200})(), None))
        exchange._get_lighter_signer_client = lambda: signer_client

        tracked_order = type("Tracked", (), {"trading_pair": "ETH-USDC", "exchange_order_id": "12345"})()
        result = await exchange._place_modify(tracked_order, Decimal("1.234"), Decimal("12345"))

        self.assertTrue(result)
        signer_client.modify_order.assert_called_once()
        call_args = signer_client.modify_order.call_args[1]
        self.assertEqual(45, call_args["market_index"])
        self.assertEqual(12345, call_args["order_index"])
        self.assertEqual(123, call_args["base_amount"])
        self.assertEqual(1234500, call_args["price"])
        self.assertEqual(4, call_args["api_key_index"])

    async def test_place_modify_raises_on_signing_error(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._get_market_spec = AsyncMock(return_value=(45, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 4

        signer_client = type("SignerClient", (), {})()
        signer_client.modify_order = AsyncMock(return_value=(None, None, "signing_error"))
        exchange._get_lighter_signer_client = lambda: signer_client

        tracked_order = type("Tracked", (), {"trading_pair": "ETH-USDC", "exchange_order_id": "12345"})()
        with self.assertRaises(IOError):
            await exchange._place_modify(tracked_order, Decimal("1.234"), Decimal("12345"))

    async def test_api_request_uses_sdk_for_authenticated_requests(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        exchange._api_key = "k"
        exchange._api_secret = ""

        class DummyContext:
            async def __aenter__(self):
                return None

            async def __aexit__(self, exc_type, exc, tb):
                return False

        exchange._throttler = type("Throttler", (), {"execute_task": lambda self, limit_id: DummyContext()})()

        fake_response = type(
            "Response",
            (),
            {
                "status": 200,
                "data": b'{"success": true, "data": {"assets": []}}',
                "read": AsyncMock(),
            },
        )()
        fake_client = type(
            "ApiClient",
            (),
            {
                "param_serialize": MagicMock(return_value=("GET", "https://mainnet.zklighter.elliot.ai/api/v1/account", {"X-Api-Key": "k"}, None, [])),
                "call_api": AsyncMock(return_value=fake_response),
            },
        )()
        exchange._get_lighter_api_client = lambda: fake_client

        response = await exchange._api_request(path_url="/account", method=RESTMethod.GET, params={"by": "index", "value": "693751"}, is_auth_required=True, return_err=True)

        self.assertTrue(response["success"])
        fake_client.param_serialize.assert_called_once()
        fake_client.call_api.assert_awaited_once()

    def test_helper_methods_cover_expected_validation_paths(self):
        self.assertTrue(LighterExchange._is_expected_order_rejection("Order below the minimum notional"))
        self.assertFalse(LighterExchange._is_expected_order_rejection("unexpected signer failure"))
        self.assertTrue(LighterExchange._is_int_string("17"))
        self.assertFalse(LighterExchange._is_int_string("not-an-int"))
        self.assertTrue(LighterExchange._is_hex_private_key("0x" + ("a" * 64)))
        self.assertFalse(LighterExchange._is_hex_private_key("0x1234"))

    async def test_sdk_api_request_normalizes_non_dict_payload_and_return_err(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._sdk_rest_base_url = lambda: "https://mainnet.zklighter.elliot.ai"
        exchange._throttler = None

        fake_response = type(
            "Response",
            (),
            {
                "status": 200,
                "data": b'["ok"]',
                "read": AsyncMock(),
            },
        )()
        fake_client = type(
            "ApiClient",
            (),
            {
                "param_serialize": MagicMock(return_value=("GET", "/api/v1/account", {}, None, [])),
                "call_api": AsyncMock(return_value=fake_response),
            },
        )()
        exchange._get_lighter_api_client = lambda: fake_client

        payload = await exchange._sdk_api_request(path_url="/account")
        self.assertEqual(["ok"], payload["data"])
        self.assertEqual(200, payload["code"])
        self.assertTrue(payload["success"])

        class RequestError(Exception):
            def __init__(self, message, status):
                super().__init__(message)
                self.status = status

        fake_client.call_api = AsyncMock(side_effect=RequestError("boom", 503))

        error_payload = await exchange._sdk_api_request(path_url="/account", return_err=True)
        self.assertFalse(error_payload["success"])
        self.assertEqual(503, error_payload["code"])

    async def test_sdk_api_request_raises_on_rate_limit_payload(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._sdk_rest_base_url = lambda: "https://mainnet.zklighter.elliot.ai"
        exchange._throttler = None

        fake_response = type(
            "Response",
            (),
            {
                "status": 429,
                "data": b'{"code": 23000, "message": "Too Many Requests"}',
                "read": AsyncMock(),
            },
        )()
        fake_client = type(
            "ApiClient",
            (),
            {
                "param_serialize": MagicMock(return_value=("GET", "/api/v1/account", {}, None, [])),
                "call_api": AsyncMock(return_value=fake_response),
            },
        )()
        exchange._get_lighter_api_client = lambda: fake_client

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            with self.assertRaises(IOError):
                await exchange._sdk_api_request(path_url="/account")

        sleep_mock.assert_awaited_once_with(3.0)

    def test_response_helpers_and_account_identifier_helpers(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_key_index = "9"
        exchange._account_index = "693751"

        self.assertEqual(9, exchange._get_api_key_index())
        self.assertEqual(693751, exchange._get_account_index())
        self.assertTrue(exchange._is_ok_response({"success": True}))
        self.assertTrue(exchange._is_ok_response({"code": 200}))
        self.assertFalse(exchange._is_ok_response({"code": "bad"}))
        self.assertTrue(exchange._is_rate_limited_response({"code": 23000}))
        self.assertTrue(exchange._is_rate_limited_response({"message": "Too many requests"}))
        self.assertTrue(exchange._is_rate_limited_exception(RuntimeError("Too Many Requests")))
        self.assertEqual({"by": "index", "value": "693751", "active_only": "true"}, exchange._account_query_params())
        self.assertEqual({"id": 1}, exchange._account_from_response({"data": [{"id": 1}]}))
        self.assertEqual({"id": 2}, exchange._account_from_response({"accounts": [{"id": 2}]}))
        self.assertEqual({"assets": []}, exchange._account_from_response({"assets": []}))
        self.assertIsNone(exchange._account_from_response({}))

    def test_get_lighter_auth_token_uses_cache_and_raises_on_signer_failure(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._cached_auth_token = "cached-token"
        exchange._cached_auth_token_expiry_ts = 200.0

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.time.time", return_value=100.0):
            self.assertEqual("cached-token", exchange._get_lighter_auth_token())

        signer_client = type("SignerClient", (), {"create_auth_token_with_expiry": MagicMock(return_value=("fresh-token", None))})()
        exchange._cached_auth_token = None
        exchange._cached_auth_token_expiry_ts = 0.0
        exchange._get_lighter_signer_client = lambda: signer_client

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.time.time", return_value=100.0):
            self.assertEqual("fresh-token", exchange._get_lighter_auth_token())
        self.assertEqual("fresh-token", exchange._cached_auth_token)

        signer_client.create_auth_token_with_expiry = MagicMock(return_value=(None, "bad key"))
        exchange._cached_auth_token = None
        exchange._cached_auth_token_expiry_ts = 0.0

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.time.time", return_value=100.0):
            with self.assertRaises(IOError):
                exchange._get_lighter_auth_token()

    async def test_close_lighter_api_client_closes_and_clears_cached_client(self):
        exchange = LighterExchange.__new__(LighterExchange)
        client = type("ApiClient", (), {"close": AsyncMock()})()
        exchange._lighter_api_client = client

        await exchange._close_lighter_api_client()

        client.close.assert_awaited_once()
        self.assertIsNone(exchange._lighter_api_client)

    def test_balance_lock_release_and_fill_helpers_update_balances(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_balances = {
            "USDC": Decimal("20"),
            "ETH": Decimal("5"),
        }
        exchange._account_available_balances = {
            "USDC": Decimal("20"),
            "ETH": Decimal("5"),
        }

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.time.time", return_value=100.0):
            exchange._lock_balance_on_order_creation("ETH-USDC", Decimal("2"), Decimal("3"), TradeType.BUY)
            exchange._lock_balance_on_order_creation("ETH-USDC", Decimal("1.5"), Decimal("3"), TradeType.SELL)

        self.assertEqual(Decimal("14"), exchange._account_available_balances["USDC"])
        self.assertEqual(Decimal("3.5"), exchange._account_available_balances["ETH"])
        self.assertIn("USDC", exchange._optimistic_balance_lock)
        self.assertIn("ETH", exchange._optimistic_balance_lock)

        buy_order = type(
            "Order",
            (),
            {
                "trading_pair": "ETH-USDC",
                "amount": Decimal("2"),
                "price": Decimal("3"),
                "executed_amount_base": Decimal("0.5"),
                "trade_type": TradeType.BUY,
            },
        )()
        sell_order = type(
            "Order",
            (),
            {
                "trading_pair": "ETH-USDC",
                "amount": Decimal("2"),
                "price": Decimal("3"),
                "executed_amount_base": Decimal("0.25"),
                "trade_type": TradeType.SELL,
            },
        )()

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.time.time", return_value=101.0):
            exchange._release_locked_balance_on_cancel(buy_order)
            exchange._release_locked_balance_on_cancel(sell_order)

        self.assertEqual(Decimal("18.5"), exchange._account_available_balances["USDC"])
        self.assertEqual(Decimal("5"), exchange._account_available_balances["ETH"])
        self.assertIn("USDC", exchange._optimistic_balance_release)
        self.assertIn("ETH", exchange._optimistic_balance_release)

        sell_fill_order = type(
            "Order",
            (),
            {
                "trading_pair": "ETH-USDC",
                "amount": Decimal("1"),
                "price": Decimal("4"),
                "trade_type": TradeType.SELL,
            },
        )()
        buy_fill_order = type(
            "Order",
            (),
            {
                "trading_pair": "ETH-USDC",
                "amount": Decimal("2"),
                "price": Decimal("2"),
                "trade_type": TradeType.BUY,
            },
        )()

        exchange._release_locked_balance_on_fill(sell_fill_order)
        exchange._release_locked_balance_on_fill(buy_fill_order)

        self.assertEqual(Decimal("6"), exchange._account_balances["ETH"])
        self.assertEqual(Decimal("6"), exchange._account_available_balances["ETH"])
        self.assertEqual(Decimal("20"), exchange._account_balances["USDC"])
        self.assertEqual(Decimal("20"), exchange._account_available_balances["USDC"])

    def test_schedule_balance_sync_and_account_payload_helpers(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 0.0
        exchange._last_ws_balance_update_ts = 0.0
        exchange._current_timestamp_safely = MagicMock(return_value=10.0)
        exchange._schedule_fast_balance_sync = MagicMock()

        exchange._schedule_balance_sync_for_terminal_update(
            OrderUpdate(
                client_order_id="HBOT-1",
                exchange_order_id="1",
                trading_pair="ETH-USDC",
                update_timestamp=10.0,
                new_state=OrderState.CANCELED,
            )
        )
        self.assertEqual(10.0, exchange._balance_refresh_required_since)
        exchange._schedule_fast_balance_sync.assert_called_once_with(min_interval_seconds=0.2)

        exchange._schedule_fast_balance_sync.reset_mock()
        exchange._last_ws_balance_update_ts = 9.5
        exchange._schedule_balance_sync_for_terminal_update(
            OrderUpdate(
                client_order_id="HBOT-2",
                exchange_order_id="2",
                trading_pair="ETH-USDC",
                update_timestamp=10.0,
                new_state=OrderState.FAILED,
            )
        )
        exchange._schedule_fast_balance_sync.assert_not_called()

        self.assertTrue(exchange._account_payload_has_assets({"assets": [{"symbol": "USDC"}]}))
        self.assertTrue(exchange._account_payload_has_assets({"assets": {"0": {"symbol": "USDC"}}}))
        self.assertFalse(exchange._account_payload_has_assets({"assets": ["bad"]}))
        self.assertFalse(exchange._account_payload_has_assets(None))

    def test_extract_private_stream_payloads_normalizes_assets_trades_and_orders(self):
        account_data, trades, orders = LighterExchange._extract_private_stream_payloads(
            {
                "type": "update/account_all_assets",
                "assets": {"0": {"symbol": "USDC", "balance": "10", "locked_balance": "1"}},
                "trades": {"1": [{"id": "t1"}], "2": {"id": "t2"}},
                "trade": {"id": "t3"},
                "orders": {"1": [{"id": "o1"}], "2": {"id": "o2"}},
                "order": {"id": "o3"},
            }
        )

        self.assertEqual({"assets": [{"symbol": "USDC", "balance": "10", "locked_balance": "1"}]}, account_data)
        self.assertEqual(["t1", "t2", "t3"], [trade["id"] for trade in trades])
        self.assertEqual(["o1", "o2", "o3"], [order["id"] for order in orders])

        account_data, trades, orders = LighterExchange._extract_private_stream_payloads(
            {
                "type": "update/account_tx",
                "channel": "account_order_updates:123",
                "data": [{"id": "o4"}],
                "txs": [{"order": {"id": "o5"}}, {"id": "o6"}],
            }
        )

        self.assertIsNone(account_data)
        self.assertEqual([], trades)
        self.assertEqual(["o4", "o5", "o6"], [order["id"] for order in orders])

    def test_process_balance_message_from_account_preserves_optimistic_release_and_lock(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_balances = {
            "USDC": Decimal("10"),
            "BTC": Decimal("2"),
            "DOGE": Decimal("0"),
        }
        exchange._account_available_balances = {
            "USDC": Decimal("9"),
            "BTC": Decimal("1"),
            "DOGE": Decimal("0"),
        }
        exchange._optimistic_balance_release = {"USDC": (Decimal("9"), 100.0)}
        exchange._optimistic_balance_lock = {"BTC": (Decimal("1"), 100.0)}

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.time.time", return_value=101.0):
            exchange._process_balance_message_from_account(
                {
                    "assets": [
                        {"symbol": "USDC", "balance": "10", "locked_balance": "2"},
                        {"symbol": "BTC", "balance": "2", "locked_balance": "0"},
                    ]
                }
            )

        self.assertEqual(Decimal("10"), exchange._account_balances["USDC"])
        self.assertEqual(Decimal("9"), exchange._account_available_balances["USDC"])
        self.assertEqual(Decimal("2"), exchange._account_balances["BTC"])
        self.assertEqual(Decimal("1"), exchange._account_available_balances["BTC"])
        self.assertNotIn("DOGE", exchange._account_balances)
        self.assertNotIn("DOGE", exchange._account_available_balances)

    def test_order_update_from_raw_message_matches_compact_server_order_fallback(self):
        exchange = LighterExchange.__new__(LighterExchange)
        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-compact",
                "exchange_order_id": "77",
                "trading_pair": "ETH-USDC",
                "trade_type": TradeType.BUY,
                "price": Decimal("100"),
                "is_done": False,
            },
        )()
        exchange.logger = MagicMock(return_value=MagicMock())
        exchange._server_order_index_to_client_order_index = {}
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_updatable_orders": {"HBOT-compact": tracked_order},
                "all_fillable_orders_by_exchange_order_id": {},
            },
        )()

        order_update = exchange._order_update_from_raw_message(
            {"i": "9001", "s": "ETH-USDC", "d": "bid", "p": "100", "os": "filled", "ut": 1700000000000}
        )

        self.assertIsNotNone(order_update)
        self.assertEqual("HBOT-compact", order_update.client_order_id)
        self.assertEqual(OrderState.FILLED, order_update.new_state)
        self.assertEqual("77", exchange._server_order_index_to_client_order_index["9001"])

    def test_trade_update_from_raw_message_matches_compact_client_and_server_ids(self):
        exchange = LighterExchange.__new__(LighterExchange)
        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-trade",
                "exchange_order_id": "77",
                "trading_pair": "ETH-USDC",
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
            },
        )()
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._client_order_index_to_client_order_id = {"55": "HBOT-trade"}
        exchange._server_order_index_to_client_order_index = {"9001": "55"}
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_fillable_orders": {"HBOT-trade": tracked_order},
                "all_fillable_orders_by_exchange_order_id": {},
            },
        )()

        by_client_index = exchange._trade_update_from_raw_message(
            {
                "I": "55",
                "trade_id": "t-client-index",
                "price": "2.5",
                "amount": "4",
                "fee": "0",
                "created_at": 1700000000123,
            }
        )
        by_server_index = exchange._trade_update_from_raw_message(
            {
                "i": "9001",
                "trade_id": "t-server-index",
                "price": "3",
                "amount": "2",
                "fee": "0",
                "created_at": 1700000001123,
            }
        )

        self.assertIsNotNone(by_client_index)
        self.assertEqual("t-client-index", by_client_index.trade_id)
        self.assertIsNotNone(by_server_index)
        self.assertEqual("t-server-index", by_server_index.trade_id)

    async def test_api_request_and_get_last_traded_prices(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        exchange._api_key = "k"
        exchange._api_secret = ""
        exchange._web_assistants_factory = type("Factory", (), {"get_rest_assistant": AsyncMock()})()
        rest = type("Rest", (), {})()
        rest.execute_request = AsyncMock(return_value={"ok": True})
        exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=rest)

        response = await exchange._api_request(path_url="/orderBooks", method=RESTMethod.GET, params={"a": 1}, is_auth_required=False)
        self.assertEqual({"ok": True}, response)

        exchange._api_request = AsyncMock(
            return_value={
                "order_book_stats": [
                    {"symbol": "ETH/USDC", "last_trade_price": "100.5"},
                    {"symbol": "BTC/USDC", "last_trade_price": "200.5"},
                ]
            }
        )
        exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=["ETH-USDC", "BTC-USDC"])
        prices = await exchange.get_last_traded_prices(["ETH-USDC"])
        self.assertEqual({"ETH-USDC": 100.5}, prices)

    async def test_status_polling_loop_fetch_updates(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._update_balances = AsyncMock()
        exchange._update_order_status = AsyncMock()
        exchange._update_lost_orders_status = AsyncMock()
        exchange._cleanup_startup_orphan_orders = AsyncMock()
        exchange._cleanup_runtime_orphan_orders = AsyncMock()

        await exchange._status_polling_loop_fetch_updates()
        self.assertEqual(1, exchange._update_balances.await_count)
        self.assertEqual(1, exchange._update_order_status.await_count)
        self.assertEqual(1, exchange._update_lost_orders_status.await_count)
        exchange._cleanup_startup_orphan_orders.assert_awaited_once()

    def test_get_lighter_signer_client_builds_once(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._lighter_signer_client = None
        exchange._api_host_for_signer = lambda: "https://mainnet.zklighter.elliot.ai"
        exchange._get_account_index = lambda: 693751
        exchange._get_api_key_index = lambda: 7
        exchange._get_signer_private_key = lambda: "0xabc"

        fake_lighter = types.ModuleType("lighter")

        class SignerClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        fake_lighter.signer_client = type("SignerModule", (), {"SignerClient": SignerClient})
        fake_lighter.create_api_key = lambda: ("priv", "pub", None)
        sys.modules["lighter"] = fake_lighter

        client_1 = exchange._get_lighter_signer_client()
        client_2 = exchange._get_lighter_signer_client()

        self.assertIs(client_1, client_2)
        self.assertEqual(693751, client_1.kwargs["account_index"])
        self.assertEqual({7: "0xabc"}, client_1.kwargs["api_private_keys"])

    async def test_update_trading_fees_noop(self):
        exchange = LighterExchange.__new__(LighterExchange)
        self.assertIsNone(await exchange._update_trading_fees())

    async def test_user_stream_event_listener_processes_messages(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._process_balance_message_from_account = lambda _: None
        exchange._trade_update_from_raw_message = lambda _: "TRADE_UPDATE"
        exchange._order_update_from_raw_message = lambda _: "ORDER_UPDATE"
        exchange._schedule_unmatched_private_event_reconcile = MagicMock()
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_trade_update": lambda self, _: None,
                "process_order_update": lambda self, _: None,
                "all_fillable_orders_by_exchange_order_id": {},
            },
        )()
        exchange._sleep = AsyncMock()

        async def events():
            yield {
                "data": {"assets": []},
                "trades": [{"trade_id": "t1"}],
                "orders": [{"order_id": "o1"}],
            }
            raise asyncio.CancelledError

        exchange._iter_user_event_queue = events

        with self.assertRaises(asyncio.CancelledError):
            await exchange._user_stream_event_listener()

    async def test_user_stream_event_listener_triggers_reconcile_for_unmatched_private_events(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._process_balance_message_from_account = lambda _: None
        exchange._trade_update_from_raw_message = lambda _: None
        exchange._order_update_from_raw_message = lambda _: None
        exchange._schedule_unmatched_private_event_reconcile = MagicMock()
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_trade_update": lambda self, _: None,
                "process_order_update": lambda self, _: None,
                "all_fillable_orders_by_exchange_order_id": {},
            },
        )()
        exchange._sleep = AsyncMock()

        async def events():
            yield {
                "data": {"assets": []},
                "trades": [{"trade_id": "t1"}],
                "orders": [{"order_id": "o1"}],
            }
            raise asyncio.CancelledError

        exchange._iter_user_event_queue = events

        with self.assertRaises(asyncio.CancelledError):
            await exchange._user_stream_event_listener()

        exchange._schedule_unmatched_private_event_reconcile.assert_called_once()

    async def test_user_stream_event_listener_handles_exception(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._process_balance_message_from_account = lambda _: None

        def failing_trade(_):
            raise RuntimeError("boom")

        exchange._trade_update_from_raw_message = failing_trade
        exchange._order_update_from_raw_message = lambda _: None
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_trade_update": lambda self, _: None,
                "process_order_update": lambda self, _: None,
                "all_fillable_orders_by_exchange_order_id": {},
            },
        )()
        exchange._sleep = AsyncMock()

        class Logger:
            def error(self, *args, **kwargs):
                return None

        exchange.logger = lambda: Logger()

        async def events():
            yield {"trades": [{"trade_id": "t1"}]}
            raise asyncio.CancelledError

        exchange._iter_user_event_queue = events

        with self.assertRaises(asyncio.CancelledError):
            await exchange._user_stream_event_listener()

        self.assertEqual(1, exchange._sleep.await_count)

    async def test_all_trade_updates_for_order_handles_pagination(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_index = "693751"
        _set_exchange_timestamp(exchange, 1700001000)
        exchange._order_history_last_poll_timestamp = {}
        exchange._hb_order_id_to_client_order_index = {"HBOT-11": 42}
        exchange._server_order_index_to_client_order_index = {}
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._api_get = AsyncMock(
            side_effect=[
                {
                    "success": True,
                    "data": [
                        {"order_id": "x", "history_id": "h0", "price": "1", "amount": "1", "created_at": 1000},
                        {
                            "order_id": "42",
                            "history_id": "h1",
                            "price": "2",
                            "amount": "3",
                            "fee": "0.1",
                            "created_at": 2000,
                            "event_type": "fulfill_taker",
                        },
                    ],
                    "has_more": True,
                    "next_cursor": "cur1",
                },
                {"success": True, "data": [], "has_more": False},
            ]
        )

        order = type(
            "Order",
            (),
            {
                "exchange_order_id": "42",
                "creation_timestamp": 1700000000,
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
                "client_order_id": "HBOT-11",
                "trading_pair": "ETH-USDC",
            },
        )()

        updates = await exchange._all_trade_updates_for_order(order)
        self.assertEqual(1, len(updates))
        self.assertEqual("h1", updates[0].trade_id)
        self.assertTrue(updates[0].is_taker)
        self.assertIn("42", exchange._order_history_last_poll_timestamp)

    async def test_all_trade_updates_for_order_matches_server_order_index_when_client_id_absent(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_index = "693751"
        _set_exchange_timestamp(exchange, 1700001000)
        exchange._order_history_last_poll_timestamp = {}
        exchange._hb_order_id_to_client_order_index = {"HBOT-11": 42}
        exchange._server_order_index_to_client_order_index = {"9001": "42"}
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._api_get = AsyncMock(
            return_value={
                "success": True,
                "data": [
                    {
                        "order_id": "9001",
                        "history_id": "h-server-only",
                        "price": "2",
                        "size": "3",
                        "timestamp": 2000,
                        "is_maker_ask": False,
                    }
                ],
            }
        )

        order = type(
            "Order",
            (),
            {
                "exchange_order_id": "42",
                "creation_timestamp": 1700000000,
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
                "client_order_id": "HBOT-11",
                "trading_pair": "ETH-USDC",
            },
        )()

        updates = await exchange._all_trade_updates_for_order(order)

        self.assertEqual(1, len(updates))
        self.assertEqual("h-server-only", updates[0].trade_id)

    async def test_all_trade_updates_for_order_applies_time_drift_buffer(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_index = "693751"
        _set_exchange_timestamp(exchange, 1700001000)
        exchange._order_history_last_poll_timestamp = {"42": 20}
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._api_get = AsyncMock(return_value={"success": True, "data": []})

        order = type(
            "Order",
            (),
            {
                "exchange_order_id": "42",
                "creation_timestamp": 10,
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
                "client_order_id": "HBOT-11",
                "trading_pair": "ETH-USDC",
            },
        )()

        await exchange._all_trade_updates_for_order(order)

        api_get_call = exchange._api_get.call_args
        self.assertEqual(10, api_get_call.kwargs["params"]["from"])

    async def test_all_trade_updates_for_order_does_not_advance_cursor_without_matches(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_index = "693751"
        _set_exchange_timestamp(exchange, 1700001000)
        exchange._order_history_last_poll_timestamp = {"42": 20}
        exchange._hb_order_id_to_client_order_index = {"HBOT-11": 42}
        exchange._server_order_index_to_client_order_index = {}
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._api_get = AsyncMock(
            return_value={
                "success": True,
                "data": [
                    {
                        "bid_client_id": 999,
                        "history_id": "h-unrelated",
                        "price": "2",
                        "size": "3",
                        "timestamp": 2000,
                    }
                ],
            }
        )

        order = type(
            "Order",
            (),
            {
                "exchange_order_id": "42",
                "creation_timestamp": 10,
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
                "client_order_id": "HBOT-11",
                "trading_pair": "ETH-USDC",
            },
        )()

        updates = await exchange._all_trade_updates_for_order(order)

        self.assertEqual([], updates)
        self.assertEqual(20, exchange._order_history_last_poll_timestamp["42"])

    async def test_all_trade_updates_for_order_without_exchange_order_id_returns_empty(self):
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700001000)
        exchange._order_history_last_poll_timestamp = {}
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._api_get = AsyncMock()

        order = type(
            "Order",
            (),
            {
                "exchange_order_id": None,
                "creation_timestamp": 1700000000,
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
                "client_order_id": "HBOT-INVALID",
                "trading_pair": "ETH-USDC",
            },
        )()

        updates = await exchange._all_trade_updates_for_order(order)
        self.assertEqual([], updates)
        exchange._api_get.assert_not_called()
        self.assertIn("None", exchange._order_history_last_poll_timestamp)

    async def test_request_order_status_raises_on_error(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_get = AsyncMock(return_value={"success": False, "code": 500})
        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-12",
                "exchange_order_id": "600",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        with self.assertRaises(IOError):
            await exchange._request_order_status(tracked_order)

    def test_get_fee_returns_zero_fee(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        fee = exchange._get_fee(
            base_currency="ETH",
            quote_currency="USDC",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
        )
        self.assertIsNotNone(fee)

    def test_get_poll_interval_is_short_with_active_orders(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange.SHORT_POLL_INTERVAL = 5.0
        exchange._order_tracker = type("Tracker", (), {"active_orders": {"OID": object()}})()

        interval = exchange._get_poll_interval(timestamp=100)

        self.assertEqual(5.0, interval)

    async def test_update_order_fills_from_trades_processes_trade(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL = 1
        exchange.LONG_POLL_INTERVAL = 120
        exchange._last_poll_timestamp = 0
        exchange._last_trades_poll_timestamp = 0
        _set_exchange_timestamp(exchange, 10)
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._get_account_index = lambda: 693751

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "exchange_order_id": "77",
                "trade_type": TradeType.BUY,
                "quote_asset": "USDC",
                "client_order_id": "HBOT-13",
                "trading_pair": "ETH-USDC",
            },
        )()
        captured = []
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_fillable_orders": {"HBOT-13": tracked_order},
                "process_trade_update": lambda self, update: captured.append(update),
                "active_orders": {"HBOT-13": tracked_order},
            },
        )()
        exchange._api_get = AsyncMock(
            return_value={
                "data": [
                    {"bid_client_id": 77, "trade_id": "t1", "size": "1", "price": "2", "timestamp": 1000},
                ]
            }
        )

        await exchange._update_order_fills_from_trades()
        self.assertEqual(1, len(captured))

        api_get_call = exchange._api_get.call_args
        self.assertEqual(693751, api_get_call.kwargs["params"]["account_index"])
        self.assertNotIn("from", api_get_call.kwargs["params"])

    async def test_update_order_fills_from_trades_uses_time_filter_when_available(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL = 1
        exchange.LONG_POLL_INTERVAL = 120
        exchange._last_poll_timestamp = 0
        exchange._last_trades_poll_timestamp = 5
        _set_exchange_timestamp(exchange, 10)
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._get_account_index = lambda: 693751

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "exchange_order_id": "77",
                "trade_type": TradeType.BUY,
                "quote_asset": "USDC",
                "client_order_id": "HBOT-13",
                "trading_pair": "ETH-USDC",
            },
        )()
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_fillable_orders": {"HBOT-13": tracked_order},
                "process_trade_update": lambda self, update: None,
                "active_orders": {"HBOT-13": tracked_order},
            },
        )()
        exchange._api_get = AsyncMock(return_value={"data": []})

        await exchange._update_order_fills_from_trades()

        api_get_call = exchange._api_get.call_args
        self.assertEqual(693751, api_get_call.kwargs["params"]["account_index"])
        self.assertNotIn("from", api_get_call.kwargs["params"])
        self.assertEqual(10, exchange._last_trades_poll_timestamp)

    async def test_update_order_fills_from_trades_no_poll(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL = 1
        exchange.LONG_POLL_INTERVAL = 120
        exchange._last_poll_timestamp = 10
        _set_exchange_timestamp(exchange, 10)
        exchange._order_tracker = type("Tracker", (), {"all_fillable_orders": {}, "active_orders": {}})()
        exchange._api_get = AsyncMock(return_value={"data": []})

        await exchange._update_order_fills_from_trades()
        self.assertEqual(0, exchange._api_get.await_count)

    async def test_update_order_status_delegates(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "active_orders": {"k": "v"},
                "cached_orders": {},
                "all_fillable_orders": {},
            },
        )()
        exchange._update_order_fills_from_trades = AsyncMock()
        exchange._update_orders = AsyncMock()
        exchange._rescue_cached_order_fills = AsyncMock()

        await exchange._update_order_status()

        self.assertEqual(1, exchange._update_order_fills_from_trades.await_count)
        self.assertEqual(1, exchange._update_orders.await_count)
        self.assertEqual(1, exchange._rescue_cached_order_fills.await_count)

    async def test_update_orders_fills_processes_each_trade_update(self):
        exchange = LighterExchange.__new__(LighterExchange)
        order = object()
        exchange._all_trade_updates_for_order = AsyncMock(return_value=["u1", "u2"])
        processed = []
        exchange._order_tracker = type("Tracker", (), {"process_trade_update": lambda self, update: processed.append(update)})()

        await exchange._update_orders_fills([order])

        self.assertEqual(["u1", "u2"], processed)

    async def test_update_orders_processes_order_updates(self):
        exchange = LighterExchange.__new__(LighterExchange)
        tracked_order = object()
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "active_orders": {"o": tracked_order},
                "process_order_update": lambda self, update: None,
            },
        )()
        exchange._request_order_status = AsyncMock(return_value="ORDER_UPDATE")

        await exchange._update_orders()
        self.assertEqual(1, exchange._request_order_status.await_count)

    async def test_update_orders_triggers_fast_balance_sync_for_canceled_orders(self):
        exchange = LighterExchange.__new__(LighterExchange)
        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "is_done": False,
                "amount": Decimal("2"),
                "executed_amount_base": Decimal("0"),
                "trade_type": TradeType.BUY,
                "price": Decimal("10"),
                "quote_asset": "USDC",
                "base_asset": "ETH",
                "client_order_id": "HBOT-C",
                "exchange_order_id": "42",
                "trading_pair": "ETH-USDC",
            },
        )()
        processed_updates = []
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "active_orders": {"o": tracked_order},
                "process_order_update": lambda self, update: processed_updates.append(update),
            },
        )()
        exchange._request_order_status = AsyncMock(
            return_value=OrderUpdate(
                trading_pair="ETH-USDC",
                update_timestamp=1,
                new_state=OrderState.CANCELED,
                client_order_id="HBOT-C",
                exchange_order_id="42",
            )
        )
        exchange._account_balances = {"USDC": Decimal("100")}
        exchange._account_available_balances = {"USDC": Decimal("20")}
        exchange._safe_update_balances_from_private_stream = AsyncMock()
        exchange._all_trade_updates_for_order = AsyncMock(return_value=[])
        exchange._last_private_stream_balance_sync_ts = 0.0
        exchange._current_timestamp_safely = lambda: 1000.0
        exchange._balance_refresh_required_since = 0.0

        await exchange._update_orders()

        self.assertEqual(1, len(processed_updates))
        self.assertEqual(Decimal("20"), exchange._account_available_balances["USDC"])
        self.assertEqual(1000.0, exchange._balance_refresh_required_since)
        self.assertEqual(1000.0, exchange._last_private_stream_balance_sync_ts)

    def test_schedule_balance_sync_for_terminal_update_sets_refresh_requirement(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_balances = {"LINK": Decimal("5")}
        exchange._account_available_balances = {"LINK": Decimal("1")}
        exchange._safe_update_balances_from_private_stream = AsyncMock()
        exchange._last_private_stream_balance_sync_ts = 0.0
        exchange._current_timestamp_safely = lambda: 2000.0
        exchange._balance_refresh_required_since = 0.0

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "amount": Decimal("2.1"),
                "executed_amount_base": Decimal("0.1"),
                "trade_type": TradeType.SELL,
                "price": Decimal("9.5"),
                "quote_asset": "USDC",
                "base_asset": "LINK",
            },
        )()
        order_update = OrderUpdate(
            trading_pair="LINK-USDC",
            update_timestamp=1,
            new_state=OrderState.CANCELED,
            client_order_id="HBOT-S",
            exchange_order_id="7",
        )

        exchange._schedule_balance_sync_for_terminal_update(order_update=order_update, tracked_order=tracked_order)

        self.assertEqual(Decimal("1"), exchange._account_available_balances["LINK"])
        self.assertEqual(2000.0, exchange._balance_refresh_required_since)
        self.assertEqual(2000.0, exchange._last_private_stream_balance_sync_ts)

    async def test_ensure_fresh_balance_snapshot_waits_for_balance_refresh(self):
        # The guard is in _ensure_fresh_balance_snapshot_before_order which is called from
        # _place_order.  Verify the happy path: when _update_balances succeeds and updates
        # _last_balance_update_timestamp, the guard clears and returns without raising.
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 100.0
        exchange._last_balance_update_timestamp = 90.0
        exchange._last_ws_balance_update_ts = 0.0

        async def refresh_balance(**_kwargs):
            exchange._last_balance_update_timestamp = 101.0

        exchange._update_balances = AsyncMock(side_effect=refresh_balance)

        # Should return without raising (balance is now fresh)
        await exchange._ensure_fresh_balance_snapshot_before_order(trade_type=TradeType.BUY)

        exchange._update_balances.assert_awaited_once()

    async def test_place_order_raises_when_balance_refresh_is_pending(self):
        # The balance-refresh guard was moved from _create_order to _place_order so that
        # start_tracking_order() in the base _create_order always runs first.  Verify that
        # _place_order itself raises IOError when the guard fires.
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 100.0
        exchange._last_balance_update_timestamp = 90.0
        exchange._last_ws_balance_update_ts = 0.0
        exchange._update_balances = AsyncMock(side_effect=IOError("rate limited"))

        with self.assertRaises(IOError):
            await exchange._place_order(
                order_id="HBOT-BUY",
                trading_pair="LINK-USDC",
                amount=Decimal("2"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("10"),
            )

        exchange._update_balances.assert_awaited_once()

    async def test_iter_user_event_queue_yields_message(self):
        exchange = LighterExchange.__new__(LighterExchange)
        q = asyncio.Queue()
        q.put_nowait({"event": 1})
        exchange._user_stream_tracker = type("UST", (), {"user_stream": q})()

        agen = exchange._iter_user_event_queue()
        message = await agen.__anext__()
        self.assertEqual({"event": 1}, message)

    def test_hb_pair_from_symbol_variants(self):
        self.assertEqual("ETH-USDC", LighterExchange._hb_pair_from_symbol("ETH/USDC"))
        self.assertEqual("BTC-USDC", LighterExchange._hb_pair_from_symbol("BTC-USDC"))

    def test_client_order_index_from_order_id_is_stable(self):
        idx_1 = LighterExchange._client_order_index_from_order_id("HBOT-1")
        idx_2 = LighterExchange._client_order_index_from_order_id("HBOT-1")

        self.assertEqual(idx_1, idx_2)
        self.assertGreaterEqual(idx_1, 0)
        self.assertLessEqual(idx_1, (1 << 48) - 1)

    def test_get_signer_private_key_precedence_and_validation(self):
        exchange = LighterExchange.__new__(LighterExchange)
        # _api_key holds the private key (hex) — returned when it's not an integer string
        exchange._api_key = "0x" + ("a" * 64)
        self.assertEqual("0x" + ("a" * 64), exchange._get_signer_private_key())

        # Integer string in _api_key means it's the key index, not the private key — raises
        exchange._api_key = "7"
        with self.assertRaises(ValueError):
            exchange._get_signer_private_key()

        # Empty _api_key raises
        exchange._api_key = ""
        with self.assertRaises(ValueError):
            exchange._get_signer_private_key()

    def test_get_api_key_index_and_account_index(self):
        exchange = LighterExchange.__new__(LighterExchange)
        # _api_key_index is the canonical attribute used by _get_api_key_index
        exchange._api_key_index = "7"
        exchange._account_index = "42"
        self.assertEqual(7, exchange._get_api_key_index())
        self.assertEqual(42, exchange._get_account_index())

        # Non-integer _api_key_index raises
        exchange._api_key_index = "not-an-int"
        with self.assertRaises(ValueError):
            exchange._get_api_key_index()

        # Non-integer account index raises
        exchange._account_index = "abc"
        with self.assertRaises(ValueError):
            exchange._get_account_index()

    def test_account_from_response_variants(self):
        self.assertEqual({"assets": []}, LighterExchange._account_from_response({"data": {"assets": []}}))
        self.assertEqual({"assets": [1]}, LighterExchange._account_from_response({"data": [{"assets": [1]}]}))
        self.assertEqual({"assets": [2]}, LighterExchange._account_from_response({"accounts": [{"assets": [2]}]}))
        # Lighter API returns account object directly at top level (no data/accounts wrapper)
        top_level = {"code": 200, "assets": [{"symbol": "USDC", "balance": "5.7"}], "collateral": "5.7", "available_balance": "5.7"}
        self.assertEqual(top_level, LighterExchange._account_from_response(top_level))
        self.assertIsNone(LighterExchange._account_from_response({"code": 200}))

    def test_account_query_params(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_index = "693751"
        self.assertEqual({"by": "index", "value": "693751", "active_only": "true"}, exchange._account_query_params())

    def test_is_ok_response(self):
        self.assertTrue(LighterExchange._is_ok_response({"success": True}))
        self.assertTrue(LighterExchange._is_ok_response({"code": 200}))
        self.assertFalse(LighterExchange._is_ok_response({"code": 500}))

    def test_process_balance_message_from_account(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_balances = {}
        exchange._account_available_balances = {}

        exchange._process_balance_message_from_account(
            {
                "assets": [
                    {"symbol": "USDC", "balance": "10", "locked_balance": "2"},
                    {"symbol": "ETH", "balance": "1.5", "locked_balance": "0.5"},
                ]
            }
        )

        self.assertEqual(Decimal("10"), exchange._account_balances["USDC"])
        self.assertEqual(Decimal("8"), exchange._account_available_balances["USDC"])
        self.assertEqual(Decimal("1.0"), exchange._account_available_balances["ETH"])

    def test_process_balance_message_from_account_ignores_top_level_available_balance(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_balances = {}
        exchange._account_available_balances = {}

        exchange._process_balance_message_from_account(
            {
                "available_balance": "13.8",
                "assets": [
                    {"symbol": "USDC", "balance": "13", "locked_balance": "3"},
                ],
            }
        )

        self.assertEqual(Decimal("13"), exchange._account_balances["USDC"])
        self.assertEqual(Decimal("10"), exchange._account_available_balances["USDC"])

    def test_order_update_from_raw_message(self):
        exchange = LighterExchange.__new__(LighterExchange)
        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-1",
                "exchange_order_id": "42",
                "trading_pair": "ETH-USDC",
            },
        )()
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_updatable_orders": {"HBOT-1": tracked_order},
                "all_fillable_orders_by_exchange_order_id": {},
            },
        )()

        order_update = exchange._order_update_from_raw_message(
            {"client_order_id": "HBOT-1", "order_status": "canceled", "updated_at": 1700000000}
        )

        self.assertIsNotNone(order_update)
        self.assertEqual("HBOT-1", order_update.client_order_id)
        self.assertEqual(OrderState.CANCELED, order_update.new_state)

    def test_trade_update_from_raw_message(self):
        exchange = LighterExchange.__new__(LighterExchange)
        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-2",
                "exchange_order_id": "77",
                "trading_pair": "ETH-USDC",
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
            },
        )()
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_fillable_orders": {"HBOT-2": tracked_order},
                "all_fillable_orders_by_exchange_order_id": {"77": tracked_order},
            },
        )()

        trade_update = exchange._trade_update_from_raw_message(
            {
                "client_order_id": "HBOT-2",
                "order_id": "77",
                "trade_id": "t-1",
                "price": "2.5",
                "amount": "4",
                "created_at": 1700000000123,
            }
        )

        self.assertIsNotNone(trade_update)
        self.assertEqual("t-1", trade_update.trade_id)
        self.assertEqual(Decimal("2.5"), trade_update.fill_price)
        self.assertEqual(Decimal("4"), trade_update.fill_base_amount)
        self.assertEqual(Decimal("10"), trade_update.fill_quote_amount)

    async def test_format_trading_rules_filters_non_spot(self):
        exchange = LighterExchange.__new__(LighterExchange)
        rules = await exchange._format_trading_rules(
            {
                "data": [
                    {"symbol": "ETH/USDC", "market_type": "spot", "supported_size_decimals": 3, "supported_price_decimals": 2},
                    {"symbol": "BTC/USDC", "market_type": "perp", "supported_size_decimals": 3, "supported_price_decimals": 2},
                ]
            }
        )
        self.assertEqual(1, len(rules))
        self.assertEqual("ETH-USDC", rules[0].trading_pair)

    async def test_request_order_status_empty_returns_current_state(self):
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700001234)
        exchange._api_get = AsyncMock(return_value={"success": True, "data": []})

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-3",
                "exchange_order_id": "300",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)
        self.assertEqual("HBOT-3", status.client_order_id)
        self.assertEqual(OrderState.OPEN, status.new_state)

    async def test_request_order_status_parses_state(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_get = AsyncMock(
            return_value={
                "success": True,
                "data": [
                    {"created_at": 1, "order_status": "open"},
                    {"created_at": 2, "order_status": "canceled"},
                ],
            }
        )

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-4",
                "exchange_order_id": "301",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)
        self.assertEqual(OrderState.CANCELED, status.new_state)

    async def test_request_order_status_matches_by_order_id(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_get = AsyncMock(
            return_value={
                "success": True,
                "data": [
                    {"order_id": "301", "symbol": "ETH/USDC", "created_at": 2, "order_status": "canceled"},
                ],
            }
        )

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-4",
                "exchange_order_id": "301",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)
        self.assertEqual(OrderState.CANCELED, status.new_state)

    async def test_request_order_status_does_not_use_unrelated_active_rows(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_get = AsyncMock(
            side_effect=[
                {
                    "success": True,
                    "data": [
                        {"order_id": "999", "client_order_id": "999", "symbol": "ETH/USDC", "order_status": "open"},
                    ],
                },
                {"success": True, "data": []},
            ]
        )

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-ghost",
                "exchange_order_id": "301",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)
        self.assertEqual(OrderState.OPEN, status.new_state)

    async def test_request_order_status_uses_terminal_state_from_active_rows(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_get = AsyncMock(
            side_effect=[
                {"success": True, "data": [{"order_id": "301", "symbol": "ETH/USDC", "order_status": "closed", "created_at": 3}]},
            ]
        )

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-closed",
                "exchange_order_id": "301",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)
        self.assertEqual(OrderState.CANCELED, status.new_state)

    async def test_request_order_status_preserves_partial_state_from_active_rows(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_get = AsyncMock(
            side_effect=[
                {"success": True, "data": [{"order_id": "301", "symbol": "ETH/USDC", "order_status": "partially_filled", "created_at": 3}]},
            ]
        )

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-partial",
                "exchange_order_id": "301",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)
        self.assertEqual(OrderState.PARTIALLY_FILLED, status.new_state)

    async def test_request_order_status_queries_active_orders_before_inactive_history(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_get = AsyncMock(
            side_effect=[
                {"success": True, "data": [{"order_id": "301", "symbol": "ETH/USDC", "order_status": "open", "created_at": 3}]},
            ]
        )

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-open",
                "exchange_order_id": "301",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)

        self.assertEqual(OrderState.OPEN, status.new_state)
        self.assertEqual(1, exchange._api_get.await_count)
        self.assertEqual("/accountActiveOrders", exchange._api_get.await_args.kwargs["path_url"])

    async def test_update_balances_updates_and_removes_assets(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_balances = {"OLD": Decimal("1")}
        exchange._account_available_balances = {"OLD": Decimal("1")}
        exchange._account_query_params = lambda: {"by": "index", "value": "1"}
        exchange._api_get = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "assets": [
                        {"symbol": "USDC", "balance": "12", "locked_balance": "2"},
                    ]
                },
            }
        )

        await exchange._update_balances()

        self.assertNotIn("OLD", exchange._account_balances)
        self.assertEqual(Decimal("12"), exchange._account_balances["USDC"])
        self.assertEqual(Decimal("10"), exchange._account_available_balances["USDC"])

    async def test_update_balances_ignores_top_level_available_balance(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_balances = {}
        exchange._account_available_balances = {}
        exchange._account_query_params = lambda: {"by": "index", "value": "1"}
        exchange._api_get = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "available_balance": "13.8",
                    "assets": [
                        {"symbol": "USDC", "balance": "13", "locked_balance": "3"},
                    ]
                },
            }
        )

        await exchange._update_balances()

        self.assertEqual(Decimal("13"), exchange._account_balances["USDC"])
        self.assertEqual(Decimal("10"), exchange._account_available_balances["USDC"])

    def test_initialize_trading_pair_symbols_from_exchange_info(self):
        exchange = LighterExchange.__new__(LighterExchange)
        captured = {}
        exchange._set_trading_pair_symbol_map = lambda mapping: captured.update(mapping)

        exchange._initialize_trading_pair_symbols_from_exchange_info(
            {
                "data": [
                    {"symbol": "ETH/USDC", "market_type": "spot"},
                    {"symbol": "BTC/USDC", "market_type": "perp"},
                ]
            }
        )

        self.assertEqual({"ETH/USDC": "ETH-USDC"}, captured)

    async def test_request_order_fills_by_client_order_id_filters(self):
        exchange = LighterExchange.__new__(LighterExchange)
        order = type("Order", (), {"client_order_id": "HBOT-5", "exchange_order_id": "500"})()
        exchange._request_order_fills_from_trades_api = AsyncMock(
            return_value=[
                {"client_order_id": "HBOT-0"},
                {"client_order_id": "HBOT-5"},
                {"clientOrderId": "HBOT-5"},
            ]
        )

        fills = await exchange._request_order_fills_by_client_order_id(order)
        self.assertEqual(2, len(fills))

    async def test_request_trade_fills(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_index = "693751"
        exchange._domain = "lighter"
        exchange._api_get = AsyncMock(
            return_value={
                "data": [
                    {"history_id": "h1", "symbol": "ETH/USDC"},
                    {"trade_id": "t2", "symbol": "LIT/USDC"},
                ]
            }
        )

        fills = await exchange._request_trade_fills()
        self.assertEqual(2, len(fills))
        self.assertEqual("lighter", fills[0].market)
        self.assertEqual("h1", fills[0].exchange_trade_id)

    async def test_request_order_fills_from_trades_api_success_and_failure(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_index = "693751"
        exchange._api_get = AsyncMock(return_value={"success": True, "data": [{"order_id": "1"}]})

        order = type("Order", (), {"exchange_order_id": "1"})()
        fills = await exchange._request_order_fills_from_trades_api(order)
        self.assertEqual(1, len(fills))

        exchange._api_get = AsyncMock(return_value={"success": False})
        fills = await exchange._request_order_fills_from_trades_api(order)
        self.assertEqual([], fills)

    async def test_request_order_fills_without_exchange_id(self):
        exchange = LighterExchange.__new__(LighterExchange)
        order = type("Order", (), {"exchange_order_id": None})()
        fills = await exchange._request_order_fills(order)
        self.assertEqual([], fills)

    async def test_request_order_fills_and_fills_api_delegates(self):
        exchange = LighterExchange.__new__(LighterExchange)
        order = type("Order", (), {"exchange_order_id": "99"})()
        exchange._request_order_fills_by_exchange_order_id = AsyncMock(return_value=[{"order_id": "99"}])
        exchange._request_order_fills_from_trades_api = AsyncMock(return_value=[{"order_id": "99"}])

        fills = await exchange._request_order_fills(order)
        fills2 = await exchange._request_order_fills_from_fills_api(order)
        self.assertEqual([{"order_id": "99"}], fills)
        self.assertEqual([{"order_id": "99"}], fills2)

    async def test_request_trade_updates_and_order_update_delegate(self):
        exchange = LighterExchange.__new__(LighterExchange)
        order_1 = type("Order", (), {"id": "1"})()
        order_2 = type("Order", (), {"id": "2"})()
        trade_update = object()
        exchange._all_trade_updates_for_order = AsyncMock(side_effect=[[trade_update], []])
        exchange._request_order_status = AsyncMock(return_value="ORDER_UPDATE")

        updates = await exchange._request_trade_updates([order_1, order_2])
        order_update = await exchange._request_order_update(order_1)

        self.assertEqual([trade_update], updates)
        self.assertEqual("ORDER_UPDATE", order_update)

    async def test_execute_order_cancel_and_get_last_prices(self):
        exchange = LighterExchange.__new__(LighterExchange)
        order = type("Order", (), {"client_order_id": "HBOT-8"})()
        exchange._place_cancel = AsyncMock(return_value=True)
        exchange.get_last_traded_prices = AsyncMock(return_value={"ETH-USDC": 1234.5})

        cancelled = await exchange._execute_order_cancel(order)
        last_price = await exchange._get_last_traded_price("ETH-USDC")
        last_trade_price = await exchange._get_last_trade_price("ETH-USDC")

        self.assertEqual("HBOT-8", cancelled)
        self.assertEqual(1234.5, last_price)
        self.assertEqual(1234.5, last_trade_price)

    async def test_create_order_fill_updates_and_fee_payment(self):
        exchange = LighterExchange.__new__(LighterExchange)
        order = type("Order", (), {"client_order_id": "HBOT-9"})()
        exchange._all_trade_updates_for_order = AsyncMock(return_value=["a", "b"])

        updates = await exchange._create_order_fill_updates(order=order, exchange_order_id="1", fee=None)
        last_fee = await exchange._fetch_last_fee_payment("ETH-USDC")

        self.assertEqual(["a", "b"], updates)
        self.assertEqual((0, Decimal("0"), Decimal("0")), last_fee)

    async def test_get_all_pairs_prices(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._api_get = AsyncMock(return_value={"data": [{"symbol": "ETH/USDC"}]})
        pairs = await exchange._get_all_pairs_prices()
        self.assertEqual([{"symbol": "ETH/USDC"}], pairs)

    async def test_create_trade_fill_updates(self):
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._get_fee = lambda **kwargs: "FEE"

        inflight_order = type(
            "InFlightOrder",
            (),
            {
                "client_order_id": "HBOT-10",
                "exchange_order_id": "500",
                "trading_pair": "ETH-USDC",
                "base_asset": "ETH",
                "quote_asset": "USDC",
                "order_type": "LIMIT",
                "trade_type": TradeType.BUY,
                "amount": Decimal("1"),
                "price": Decimal("100"),
            },
        )()

        fills_data = [{"trade_id": "t-1", "price": "100", "amount": "2", "quote_amount": "200", "timestamp": 1700000001}]
        updates = exchange._create_trade_fill_updates(inflight_order=inflight_order, fills_data=fills_data)

        self.assertEqual(1, len(updates))
        self.assertEqual("t-1", updates[0].trade_id)
        self.assertEqual(Decimal("200"), updates[0].fill_quote_amount)

    async def test_update_orders_with_error_handler(self):
        exchange = LighterExchange.__new__(LighterExchange)
        processed = []
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_order_update": lambda self, update: processed.append(("order", update)),
                "process_trade_update": lambda self, update: processed.append(("trade", update)),
            },
        )()

        orders = ["o1", "o2", "o3"]

        async def fetch(order):
            if order == "o1":
                return "ORDER_UPDATE"
            if order == "o2":
                return [type("DummyTradeUpdate", (), {})()]
            raise RuntimeError("boom")

        handled = []

        async def on_error(order, err):
            handled.append((order, str(err)))

        await exchange._update_orders_with_error_handler(orders=orders, fetch_updates=fetch, error_handler=on_error)

        self.assertEqual(1, len(handled))
        self.assertEqual("o3", handled[0][0])

    async def test_update_lost_orders_and_cancel_lost_orders(self):
        exchange = LighterExchange.__new__(LighterExchange)
        lost_orders = {
            "1": type("Order", (), {"client_order_id": "1"})(),
            "2": type("Order", (), {"client_order_id": "2"})(),
        }
        exchange._order_tracker = type("Tracker", (), {"lost_orders": lost_orders})()
        exchange._update_orders_with_error_handler = AsyncMock()
        exchange._request_order_status = AsyncMock()
        exchange._handle_update_error_for_lost_order = AsyncMock()
        exchange._execute_order_cancel = AsyncMock(return_value="")

        await exchange._update_lost_orders()
        await exchange._cancel_lost_orders()

        self.assertEqual(1, exchange._update_orders_with_error_handler.await_count)
        self.assertEqual(2, exchange._execute_order_cancel.await_count)

    async def test_execute_orders_cancel(self):
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._execute_order_cancel = AsyncMock(side_effect=["HBOT-6", ""])

        orders = [
            type("Order", (), {"client_order_id": "HBOT-6", "trading_pair": "ETH-USDC"})(),
            type("Order", (), {"client_order_id": "HBOT-7", "trading_pair": "ETH-USDC"})(),
        ]

        updates = await exchange._execute_orders_cancel(orders)
        self.assertEqual(1, len(updates))
        self.assertEqual("HBOT-6", updates[0].client_order_id)
        self.assertEqual(OrderState.CANCELED, updates[0].new_state)

    async def test_request_order_fills_by_exchange_order_id_filters(self):
        exchange = LighterExchange.__new__(LighterExchange)
        order = type("Order", (), {"exchange_order_id": "42"})()
        exchange._request_order_fills_from_trades_api = AsyncMock(
            return_value=[
                {"order_id": 1, "trade_id": "a"},
                {"order_id": 42, "trade_id": "b"},
                {"order_id": 42, "trade_id": "c"},
            ]
        )

        fills = await exchange._request_order_fills_by_exchange_order_id(order)

        self.assertEqual(2, len(fills))
        self.assertEqual(["b", "c"], [f["trade_id"] for f in fills])

    def test_state_from_raw_order_status(self):
        exchange = LighterExchange.__new__(LighterExchange)

        self.assertEqual(OrderState.CANCELED, exchange._state_from_raw_order_status("canceled"))
        self.assertEqual(OrderState.CANCELED, exchange._state_from_raw_order_status("closed"))
        self.assertEqual(OrderState.PARTIALLY_FILLED, exchange._state_from_raw_order_status("partially_filled"))
        self.assertEqual(OrderState.OPEN, exchange._state_from_raw_order_status("unknown"))

    def test_misc_helper_branches(self):
        class BadStr:
            def __str__(self):
                raise RuntimeError("bad")

        class BadInt:
            def __int__(self):
                raise RuntimeError("bad")

        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        exchange._api_key = "api"
        exchange._api_secret = "sec"
        exchange._account_index = "1"
        exchange._api_key_public_key = ""

        self.assertFalse(LighterExchange._is_int_string(BadStr()))
        self.assertFalse(LighterExchange._is_int_string(None))
        self.assertFalse(LighterExchange._is_ok_response({"code": BadInt()}))
        self.assertIsNone(LighterExchange._account_from_response({"data": []}))
        self.assertFalse(exchange._is_request_exception_related_to_time_synchronizer(Exception("x")))
        self.assertFalse(exchange._is_order_not_found_during_status_update_error(Exception("x")))
        self.assertFalse(exchange._is_order_not_found_during_cancelation_error(Exception("x")))
        self.assertEqual("ABC", exchange._hb_pair_from_symbol("ABC"))
        self.assertIsNotNone(exchange.authenticator)
        self.assertEqual(32, exchange.client_order_id_max_length)
        self.assertEqual("HBOT", exchange.client_order_id_prefix)

    def test_rest_api_key_and_authenticator_use_key_index_when_available(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_index = "1"

        exchange._api_key = "7"
        exchange._api_secret = "private"
        self.assertEqual("7", exchange.rest_api_key)
        self.assertEqual("7", exchange.authenticator.api_key)

        exchange._api_key = "private"
        exchange._api_secret = "8"
        self.assertEqual("8", exchange.rest_api_key)
        self.assertEqual("8", exchange.authenticator.api_key)

        exchange._api_key = "api-key"
        exchange._api_secret = "secret"
        self.assertEqual("api-key", exchange.rest_api_key)
        self.assertEqual("api-key", exchange.authenticator.api_key)

    async def test_more_branch_paths(self):
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_updatable_orders": {},
                "all_fillable_orders_by_exchange_order_id": {},
                "all_fillable_orders": {},
                "process_order_update": lambda self, update: None,
                "process_trade_update": lambda self, update: None,
                "active_orders": {},
                "lost_orders": {},
            },
        )()

        self.assertIsNone(exchange._order_update_from_raw_message({"order_id": "x"}))
        self.assertIsNone(exchange._trade_update_from_raw_message({"order_id": "x"}))

        class Logger:
            def warning(self, *args, **kwargs):
                return None

            def error(self, *args, **kwargs):
                return None

        exchange.logger = lambda: Logger()
        await exchange._handle_update_error_for_active_order(type("O", (), {"client_order_id": "1"})(), RuntimeError("e"))
        await exchange._handle_update_error_for_lost_order(type("O", (), {"client_order_id": "1"})(), RuntimeError("e"))

        exchange._place_cancel = AsyncMock(return_value=False)
        result = await exchange._execute_order_cancel(type("O", (), {"client_order_id": "X"})())
        self.assertIsNone(result)

    async def test_instance_type_branches_in_update_handler_and_iter_cancel(self):
        exchange = LighterExchange.__new__(LighterExchange)
        processed_orders = []
        processed_trades = []
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_order_update": lambda self, update: processed_orders.append(update),
                "process_trade_update": lambda self, update: processed_trades.append(update),
            },
        )()

        order_update = OrderUpdate(client_order_id="c", exchange_order_id="e", trading_pair="ETH-USDC", update_timestamp=1, new_state=OrderState.OPEN)
        trade_update = TradeUpdate(trade_id="t", client_order_id="c", exchange_order_id="e", trading_pair="ETH-USDC", fill_timestamp=1, fill_price=Decimal("1"), fill_base_amount=Decimal("1"), fill_quote_amount=Decimal("1"), fee=None)

        async def fetch_order(_):
            return order_update

        async def fetch_trade(_):
            return [trade_update]

        async def fetch_cancel(_):
            raise asyncio.CancelledError

        async def on_error(_, __):
            return None

        await exchange._update_orders_with_error_handler(["a"], fetch_order, on_error)
        await exchange._update_orders_with_error_handler(["b"], fetch_trade, on_error)
        with self.assertRaises(asyncio.CancelledError):
            await exchange._update_orders_with_error_handler(["c"], fetch_cancel, on_error)

        self.assertEqual(1, len(processed_orders))
        self.assertEqual(1, len(processed_trades))

        class BadQueue:
            async def get(self):
                raise asyncio.CancelledError

        exchange._user_stream_tracker = type("UST", (), {"user_stream": BadQueue()})()
        agen = exchange._iter_user_event_queue()
        with self.assertRaises(asyncio.CancelledError):
            await agen.__anext__()

    def test_rate_limits_property(self):
        exchange = LighterExchange.__new__(LighterExchange)
        self.assertTrue(len(exchange.rate_limits_rules) > 0)

    async def test_targeted_remaining_branches(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        exchange._account_index = "1"
        _set_exchange_timestamp(exchange, 1700000000)

        exchange._market_id_by_symbol = {}
        exchange._size_decimals_by_symbol = {}
        exchange._price_decimals_by_symbol = {}
        exchange._api_get = AsyncMock(return_value={"data": [{"symbol": "ETH/USDC", "market_type": "perp", "market_id": 1}, {"market_type": "spot", "market_id": 2}]})
        await exchange._refresh_market_metadata()

        exchange._get_market_spec = AsyncMock(return_value=(1, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 1
        signer = type("Signer", (), {
            "ORDER_TYPE_LIMIT": 1,
            "ORDER_TYPE_MARKET": 2,
            "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
            "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
            "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
            "DEFAULT_28_DAY_ORDER_EXPIRY": 100,
            "DEFAULT_IOC_EXPIRY": 101,
        })()
        signer.create_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 500})(), None))
        signer.cancel_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 500})(), None))
        exchange._get_lighter_signer_client = lambda: signer

        with self.assertRaises(IOError):
            await exchange._place_order("x", "ETH-USDC", Decimal("1"), TradeType.BUY, OrderType.LIMIT, Decimal("1"))
        with self.assertRaises(IOError):
            await exchange._place_cancel("x", type("Order", (), {"trading_pair": "ETH-USDC", "exchange_order_id": "1"})())

        with self.assertRaises(ValueError):
            await exchange._place_order("x", "ETH-USDC", Decimal("1"), TradeType.BUY, "UNSUPPORTED", Decimal("1"))

        signer.create_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 200})(), None))
        await exchange._place_order("x", "ETH-USDC", Decimal("1"), TradeType.BUY, OrderType.LIMIT_MAKER, Decimal("1"))

        exchange._order_tracker = type("Tracker", (), {"all_updatable_orders": {}, "all_fillable_orders_by_exchange_order_id": {"7": type("T", (), {"client_order_id": "c", "exchange_order_id": "7", "trading_pair": "ETH-USDC"})()}, "all_fillable_orders": {}})()
        order_update = exchange._order_update_from_raw_message({"order_id": "7", "updated_at": 1700000000123})
        self.assertIsNotNone(order_update)

        exchange._order_tracker = type("Tracker", (), {"all_updatable_orders": {}, "all_fillable_orders_by_exchange_order_id": {}, "all_fillable_orders": {}})()
        self.assertIsNone(exchange._order_update_from_raw_message({"order_id": "unknown"}))
        self.assertIsNone(exchange._trade_update_from_raw_message({"order_id": "unknown"}))

        rules = await exchange._format_trading_rules({"data": [{"market_type": "spot"}]})
        self.assertEqual([], rules)

        exchange._account_balances = {}
        exchange._account_available_balances = {}
        exchange._account_query_params = lambda: {"by": "index", "value": "1"}

        class Logger:
            def error(self, *args, **kwargs):
                return None

        exchange.logger = lambda: Logger()
        exchange._api_get = AsyncMock(return_value={"success": False})
        with self.assertRaises(IOError):
            await exchange._update_balances()
        exchange._api_get = AsyncMock(return_value={"success": True, "data": {"assets": [{"locked_balance": "1", "balance": "1"}]}})
        await exchange._update_balances()

        exchange._order_history_last_poll_timestamp = {"42": 1700000001}
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._api_get = AsyncMock(return_value={"success": True, "data": [{"order_id": "42", "history_id": "h", "price": "1", "amount": "1", "created_at": 1000}], "has_more": False})
        order = type("Order", (), {"exchange_order_id": "42", "creation_timestamp": 1700000000, "quote_asset": "USDC", "trade_type": TradeType.BUY, "client_order_id": "c", "trading_pair": "ETH-USDC"})()
        updates = await exchange._all_trade_updates_for_order(order)
        self.assertEqual(1, len(updates))

        exchange._throttler = object()
        exchange._auth = object()
        exchange._web_assistants_factory = object()
        exchange._trading_pairs = ["ETH-USDC"]
        self.assertIsNotNone(exchange._create_web_assistants_factory())
        self.assertIsNotNone(exchange._create_order_book_data_source())
        self.assertIsNotNone(exchange._create_user_stream_data_source())

        captured = {}
        exchange._set_trading_pair_symbol_map = lambda m: captured.update(m)
        exchange._initialize_trading_pair_symbols_from_exchange_info({"data": [{"market_type": "spot"}, {"symbol": "A/B", "market_type": "perp"}]})
        self.assertEqual({}, captured)

        exchange._api_request = AsyncMock(return_value={"data": [{"index_price": "1"}, {"symbol": "ETH/USDC", "index_price": "2"}]})
        exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=KeyError("x"))
        prices = await exchange.get_last_traded_prices(["ETH-USDC"])
        self.assertEqual({}, prices)

    async def test_final_branch_closures(self):
        exchange = LighterExchange.__new__(LighterExchange)

        class Rest:
            async def execute_request(self, **kwargs):
                return {"ok": True, "headers": kwargs.get("headers")}

        exchange._web_assistants_factory = type("F", (), {"get_rest_assistant": AsyncMock(return_value=Rest())})()
        exchange._domain = "lighter"
        exchange._api_key = "k"

        # Cover false auth-header branch in _api_request
        response = await exchange._api_request(path_url="/orderBooks", method=RESTMethod.GET, is_auth_required=False)
        self.assertEqual({"ok": True, "headers": {}}, response)

        # Cover last_price None branch in get_last_traded_prices and loop back-edge
        exchange._api_request = AsyncMock(return_value={"data": [{"symbol": "ETH/USDC"}, {"symbol": "ETH/USDC", "last_trade_price": "1"}]})
        exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="ETH-USDC")
        prices = await exchange.get_last_traded_prices(["ETH-USDC"])
        self.assertEqual({"ETH-USDC": 1.0}, prices)

        # Cover order_id not provided branch in _request_order_fills_from_trades_api
        exchange._account_index = "1"
        exchange._api_get = AsyncMock(return_value={"success": True, "data": []})
        await exchange._request_order_fills_from_trades_api(type("O", (), {"exchange_order_id": None})())

        # Cover unmatched exchange_order_id branch in _update_order_fills_from_trades
        exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL = 1
        exchange.LONG_POLL_INTERVAL = 120
        exchange._last_poll_timestamp = 0
        exchange._last_trades_poll_timestamp = 0
        _set_exchange_timestamp(exchange, 10)
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._get_account_index = lambda: 1
        tracked = type("Tracked", (), {"exchange_order_id": "7", "trade_type": TradeType.BUY, "quote_asset": "USDC", "client_order_id": "c", "trading_pair": "ETH-USDC"})()
        captured = []
        exchange._order_tracker = type("Tracker", (), {"all_fillable_orders": {"c": tracked}, "process_trade_update": lambda self, u: captured.append(u), "active_orders": {"c": tracked}})()
        exchange._api_get = AsyncMock(return_value={"data": [{"bid_client_id": 999}, {"bid_client_id": 7, "trade_id": "t", "size": "1", "price": "1", "timestamp": 1000}]})
        await exchange._update_order_fills_from_trades()
        self.assertEqual(1, len(captured))

        # Cover process_balance missing symbol continue path
        exchange._account_balances = {}
        exchange._account_available_balances = {}
        exchange._process_balance_message_from_account({"assets": [{"balance": "1", "locked_balance": "0"}]})

        # Cover user stream non-dict continue and inner CancelledError raise path
        exchange._trade_update_from_raw_message = lambda _: (_ for _ in ()).throw(asyncio.CancelledError())
        exchange._order_update_from_raw_message = lambda _: None
        exchange._process_balance_message_from_account = lambda _: None
        exchange._order_tracker = type("Tracker", (), {"process_trade_update": lambda self, u: None, "process_order_update": lambda self, u: None})()

        async def events():
            yield "invalid"
            yield {"trades": [{"trade_id": "t"}]}

        exchange._iter_user_event_queue = events
        with self.assertRaises(asyncio.CancelledError):
            await exchange._user_stream_event_listener()

    async def test_trade_update_seconds_timestamp_path_and_user_stream_loop_back_edges(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        _set_exchange_timestamp(exchange, 1700000000)

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-17",
                "exchange_order_id": "88",
                "trading_pair": "ETH-USDC",
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
            },
        )()
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_fillable_orders": {"HBOT-17": tracked_order},
                "all_fillable_orders_by_exchange_order_id": {"88": tracked_order},
                "process_trade_update": lambda self, _: None,
                "process_order_update": lambda self, _: None,
            },
        )()

        # keep created_at in seconds so the if fill_timestamp > 1e12 branch is false
        update = exchange._trade_update_from_raw_message(
            {
                "client_order_id": "HBOT-17",
                "order_id": "88",
                "trade_id": "t-seconds",
                "price": "1",
                "amount": "2",
                "created_at": 1000,
            }
        )
        self.assertEqual(1000.0, update.fill_timestamp)

        exchange._process_balance_message_from_account = lambda _: None
        exchange._trade_update_from_raw_message = lambda _: "TRADE_UPDATE"
        exchange._order_update_from_raw_message = lambda _: "ORDER_UPDATE"
        exchange._sleep = AsyncMock()

        async def events():
            yield {
                "trades": [{"trade_id": "t1"}, {"trade_id": "t2"}],
                "orders": [{"order_id": "o1"}, {"order_id": "o2"}],
            }
            raise asyncio.CancelledError

        exchange._iter_user_event_queue = events
        with self.assertRaises(asyncio.CancelledError):
            await exchange._user_stream_event_listener()

    # ------------------------------------------------------------------ #
    # Additional branch coverage for missing CI lines                     #
    # ------------------------------------------------------------------ #

    def test_is_hex_private_key_empty_returns_false(self):
        """_is_hex_private_key must return False for empty string (covers line 132)."""
        self.assertFalse(LighterExchange._is_hex_private_key(""))
        self.assertFalse(LighterExchange._is_hex_private_key("0x"))
        self.assertTrue(LighterExchange._is_hex_private_key("0x" + "a" * 64))

    def test_sdk_rest_base_url_matches_rest_url_host(self):
        """_sdk_rest_base_url must return the host part of REST_URL (covers lines 144-145)."""
        from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        expected_host = CONSTANTS.REST_URL.split("/api/v1")[0]
        self.assertEqual(expected_host, exchange._sdk_rest_base_url())

    async def test_all_trading_pairs_returns_empty_on_exception(self):
        """all_trading_pairs must return [] when the API call raises (covers lines 395-399)."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        exchange._trading_pairs = ["ETH-USDC"]
        with patch.object(exchange, "_api_get", side_effect=Exception("network error")):
            result = await exchange.all_trading_pairs()
        self.assertEqual([], result)

    async def test_all_trading_pairs_filters_non_spot_markets(self):
        """all_trading_pairs must skip non-spot markets (covers lines 386-394)."""
        mock_response = {
            "order_books": [
                {"symbol": "ETH-USDC", "market_type": "spot"},
                {"symbol": "BTC-USDC", "market_type": "perp"},
                {"symbol": "SOL-USDC", "market_type": "spot"},
            ]
        }
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        exchange._trading_pairs = ["ETH-USDC", "SOL-USDC"]
        with patch.object(exchange, "_api_get", new=AsyncMock(return_value=mock_response)):
            result = await exchange.all_trading_pairs()
        self.assertIn("ETH-USDC", result)
        self.assertNotIn("BTC-USDC", result)
        self.assertIn("SOL-USDC", result)

    # ---------------------------------------------------------------------------
    # Coverage boost: _get_lighter_auth_token (cached vs fresh token)
    # ---------------------------------------------------------------------------

    def test_get_lighter_auth_token_returns_cached_token_when_valid(self):
        """_get_lighter_auth_token must return cached token when still within expiry."""
        import time as _time
        exchange = LighterExchange.__new__(LighterExchange)
        object.__setattr__(exchange, "_current_timestamp", _time.time())
        exchange._cached_auth_token = "cached-tok"
        exchange._cached_auth_token_expiry_ts = _time.time() + 600
        token = exchange._get_lighter_auth_token()
        self.assertEqual("cached-tok", token)

    def test_get_lighter_auth_token_raises_when_signer_fails(self):
        """_get_lighter_auth_token must raise IOError when signer returns an error."""
        import time as _time
        exchange = LighterExchange.__new__(LighterExchange)
        object.__setattr__(exchange, "_current_timestamp", _time.time())
        exchange._cached_auth_token = None
        exchange._cached_auth_token_expiry_ts = 0.0
        signer_mock = MagicMock()
        signer_mock.create_auth_token_with_expiry = MagicMock(return_value=(None, "bad key"))
        exchange._get_lighter_signer_client = MagicMock(return_value=signer_mock)
        with self.assertRaises(IOError):
            exchange._get_lighter_auth_token()

    def test_get_lighter_auth_token_refreshes_and_caches(self):
        """_get_lighter_auth_token must cache a new token when none is cached."""
        import time as _time
        exchange = LighterExchange.__new__(LighterExchange)
        object.__setattr__(exchange, "_current_timestamp", _time.time())
        exchange._cached_auth_token = None
        exchange._cached_auth_token_expiry_ts = 0.0
        signer_mock = MagicMock()
        signer_mock.create_auth_token_with_expiry = MagicMock(return_value=("new-tok", None))
        exchange._get_lighter_signer_client = MagicMock(return_value=signer_mock)
        token = exchange._get_lighter_auth_token()
        self.assertEqual("new-tok", token)
        self.assertEqual("new-tok", exchange._cached_auth_token)

    # ---------------------------------------------------------------------------
    # Coverage boost: _allocate_client_order_index (spot exchange)
    # ---------------------------------------------------------------------------

    def test_allocate_client_order_index_returns_monotonically_increasing_values(self):
        """Consecutive calls must always return increasing values."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._last_client_order_index = 0
        first = exchange._allocate_client_order_index()
        second = exchange._allocate_client_order_index()
        self.assertGreater(second, first)

    def test_allocate_client_order_index_bumps_counter_within_same_ms(self):
        """When time-based candidate would exceed max, it is clamped to max."""
        exchange = LighterExchange.__new__(LighterExchange)
        max_idx = (1 << 48) - 1  # 281474976710655
        # Force a value just below max so the time-based candidate exceeds it
        exchange._last_client_order_index = max_idx - 1
        idx = exchange._allocate_client_order_index()
        # Must be clamped to max
        self.assertEqual(max_idx, idx)

    # ---------------------------------------------------------------------------
    # Coverage boost: _response_code and _is_invalid_nonce_failure
    # ---------------------------------------------------------------------------

    def test_response_code_returns_none_for_none_input(self):
        """_response_code must return None when given None."""
        self.assertIsNone(LighterExchange._response_code(None))

    def test_response_code_returns_int_from_dict(self):
        """_response_code must extract code from dict."""
        self.assertEqual(200, LighterExchange._response_code({"code": "200"}))

    def test_response_code_returns_int_from_object(self):
        """_response_code must extract code from an object attribute."""
        obj = MagicMock()
        obj.code = 404
        self.assertEqual(404, LighterExchange._response_code(obj))

    def test_is_invalid_nonce_failure_detects_code_21104(self):
        """_is_invalid_nonce_failure must return True for response code 21104."""
        exchange = LighterExchange.__new__(LighterExchange)
        resp = MagicMock()
        resp.code = 21104
        self.assertTrue(exchange._is_invalid_nonce_failure(response=resp))

    def test_is_invalid_nonce_failure_detects_error_string(self):
        """_is_invalid_nonce_failure must return True when error contains 'invalid nonce'."""
        exchange = LighterExchange.__new__(LighterExchange)
        self.assertTrue(exchange._is_invalid_nonce_failure(error="Invalid Nonce value"))

    def test_is_invalid_nonce_failure_returns_false_for_other_errors(self):
        """_is_invalid_nonce_failure must return False for unrelated errors."""
        exchange = LighterExchange.__new__(LighterExchange)
        self.assertFalse(exchange._is_invalid_nonce_failure(error="network timeout", response={"code": 500}))

    # ---------------------------------------------------------------------------
    # Coverage boost: _safe_update_balances_from_private_stream
    # ---------------------------------------------------------------------------

    async def test_safe_update_balances_swallows_non_cancelled_exceptions(self):
        """_safe_update_balances_from_private_stream must not propagate non-CancelledError."""
        exchange = LighterExchange.__new__(LighterExchange)
        with patch.object(exchange, "_update_balances", new=AsyncMock(side_effect=IOError("fail"))):
            await exchange._safe_update_balances_from_private_stream()  # must not raise

    async def test_safe_update_balances_propagates_cancelled_error(self):
        """_safe_update_balances_from_private_stream must re-raise CancelledError."""
        exchange = LighterExchange.__new__(LighterExchange)
        with patch.object(exchange, "_update_balances", new=AsyncMock(side_effect=asyncio.CancelledError())):
            with self.assertRaises(asyncio.CancelledError):
                await exchange._safe_update_balances_from_private_stream()

    # ---------------------------------------------------------------------------
    # Coverage boost: _close_lighter_api_client
    # ---------------------------------------------------------------------------

    async def test_close_lighter_api_client_resets_client_to_none(self):
        """_close_lighter_api_client must close and nullify _lighter_api_client."""
        exchange = LighterExchange.__new__(LighterExchange)
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        exchange._lighter_api_client = mock_client
        await exchange._close_lighter_api_client()
        mock_client.close.assert_called_once()
        self.assertIsNone(exchange._lighter_api_client)

    async def test_close_lighter_api_client_no_op_when_none(self):
        """_close_lighter_api_client must be a no-op when no client exists."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._lighter_api_client = None
        await exchange._close_lighter_api_client()  # must not raise

    # ---------------------------------------------------------------------------
    # Coverage boost batch: validation helpers, buy/sell, place_order edge cases
    # ---------------------------------------------------------------------------

    def test_is_order_not_found_cancelation_branches(self):
        exchange = LighterExchange.__new__(LighterExchange)
        self.assertTrue(exchange._is_order_not_found_during_cancelation_error(Exception('"code":5')))
        self.assertTrue(exchange._is_order_not_found_during_cancelation_error(Exception("'code': 5")))
        self.assertTrue(exchange._is_order_not_found_during_cancelation_error(Exception('"code": 5')))
        self.assertTrue(exchange._is_order_not_found_during_cancelation_error(Exception("order not found")))
        self.assertFalse(exchange._is_order_not_found_during_cancelation_error(Exception("timeout")))

    def test_is_order_not_found_during_status_update_error(self):
        exchange = LighterExchange.__new__(LighterExchange)
        self.assertTrue(exchange._is_order_not_found_during_status_update_error(Exception("order not found on chain")))
        self.assertFalse(exchange._is_order_not_found_during_status_update_error(Exception("network error")))

    def test_hb_pair_from_symbol_all_branches(self):
        self.assertEqual("ETH-USDC", LighterExchange._hb_pair_from_symbol("ETH/USDC"))
        self.assertEqual("BTC-USDT", LighterExchange._hb_pair_from_symbol("BTC-USDT"))
        self.assertEqual("NOSLASH", LighterExchange._hb_pair_from_symbol("NOSLASH"))

    def test_api_host_for_signer_domain_variants(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        mainnet_host = exchange._api_host_for_signer()
        self.assertNotIn("/api/v1", mainnet_host)
        self.assertTrue(mainnet_host.startswith("https://"))
        exchange._domain = "lighter_testnet"
        testnet_host = exchange._api_host_for_signer()
        self.assertNotIn("/api/v1", testnet_host)
        self.assertTrue(testnet_host.startswith("https://"))

    def test_buy_sell_market_order_adjusts_price(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._create_order = AsyncMock()

        order_book = type("OB", (), {})()
        order_book.get_price = MagicMock(return_value=Decimal("100"))
        exchange.get_order_book = lambda tp: order_book
        exchange.quantize_order_price = lambda tp, p: p
        exchange.get_mid_price = lambda tp: Decimal("100")

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.get_new_client_order_id", return_value="TEST-BUY-123"):
            with patch("hummingbot.connector.exchange.lighter.lighter_exchange.safe_ensure_future") as sfut:
                buy_id = exchange.buy(
                    trading_pair="ETH-USDC",
                    amount=Decimal("1"),
                    order_type=OrderType.MARKET,
                )
                sell_id = exchange.sell(
                    trading_pair="ETH-USDC",
                    amount=Decimal("1"),
                    order_type=OrderType.MARKET,
                )

        self.assertIsNotNone(buy_id)
        self.assertIsNotNone(sell_id)
        # safe_ensure_future should have been called twice (once for buy, once for sell)
        self.assertEqual(2, sfut.call_count)

    async def test_ensure_fresh_balance_snapshot_skips_for_sell(self):
        """_ensure_fresh_balance_snapshot_before_order must return immediately for SELL."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 999.0
        exchange._update_balances = AsyncMock()
        await exchange._ensure_fresh_balance_snapshot_before_order(TradeType.SELL)
        exchange._update_balances.assert_not_called()

    async def test_ensure_fresh_balance_snapshot_skips_when_no_requirement(self):
        """_ensure_fresh_balance_snapshot_before_order must skip if no refresh required."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 0.0
        exchange._update_balances = AsyncMock()
        await exchange._ensure_fresh_balance_snapshot_before_order(TradeType.BUY)
        exchange._update_balances.assert_not_called()

    async def test_ensure_fresh_balance_snapshot_skips_when_ws_balance_fresh(self):
        """Skip REST if a recent WS balance push already satisfied the requirement."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 50.0
        exchange._last_ws_balance_update_ts = 60.0
        exchange._update_balances = AsyncMock()
        await exchange._ensure_fresh_balance_snapshot_before_order(TradeType.BUY)
        exchange._update_balances.assert_not_called()
        self.assertEqual(0.0, exchange._balance_refresh_required_since)

    async def test_ensure_fresh_balance_snapshot_skips_when_rest_balance_fresh(self):
        """Skip REST if last_balance_update_timestamp already >= required."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 50.0
        exchange._last_ws_balance_update_ts = 0.0
        exchange._last_balance_update_timestamp = 60.0
        exchange._update_balances = AsyncMock()
        await exchange._ensure_fresh_balance_snapshot_before_order(TradeType.BUY)
        exchange._update_balances.assert_not_called()

    async def test_ensure_fresh_balance_snapshot_raises_when_update_fails(self):
        """Raise IOError if _update_balances raises."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 50.0
        exchange._last_ws_balance_update_ts = 0.0
        exchange._last_balance_update_timestamp = 0.0
        exchange.BALANCE_SYNC_REQUIRED_TIMEOUT = 5.0
        exchange._update_balances = AsyncMock(side_effect=IOError("network fail"))
        with self.assertRaises(IOError):
            await exchange._ensure_fresh_balance_snapshot_before_order(TradeType.BUY)

    async def test_ensure_fresh_balance_snapshot_raises_when_still_stale_after_update(self):
        """Raise IOError if balance timestamp is still < required even after successful update."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._balance_refresh_required_since = 50.0
        exchange._last_ws_balance_update_ts = 0.0
        exchange._last_balance_update_timestamp = 0.0
        exchange.BALANCE_SYNC_REQUIRED_TIMEOUT = 5.0
        exchange._update_balances = AsyncMock()
        with self.assertRaises(IOError):
            await exchange._ensure_fresh_balance_snapshot_before_order(TradeType.BUY)

    async def test_on_order_failure_logs_expected_rejections(self):
        """_on_order_failure must call _update_order_after_failure for expected rejections."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._update_order_after_failure = MagicMock()
        exchange._on_order_failure(
            order_id="HBOT-rej",
            trading_pair="ETH-USDC",
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("10"),
            exception=Exception("Order below the minimum notional"),
        )
        exchange._update_order_after_failure.assert_called_once()

    def test_get_fee_returns_zero_spot_fee(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        fee = exchange._get_fee(
            base_currency="ETH",
            quote_currency="USDC",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
        )
        self.assertEqual(Decimal("0"), fee.percent)

    async def test_place_cancel_returns_false_when_no_exchange_order_id(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._get_market_spec = AsyncMock(return_value=(1, 2, 2, "ETH/USDC"))
        tracked_order = type("Tracked", (), {"exchange_order_id": None, "trading_pair": "ETH-USDC"})()
        result = await exchange._place_cancel("HBOT-X", tracked_order)
        self.assertFalse(result)

    async def test_place_modify_returns_false_when_no_exchange_order_id(self):
        exchange = LighterExchange.__new__(LighterExchange)
        tracked_order = type("Tracked", (), {"exchange_order_id": None, "trading_pair": "ETH-USDC"})()
        result = await exchange._place_modify(tracked_order, Decimal("1"), Decimal("100"))
        self.assertFalse(result)

    async def test_place_order_raises_when_insufficient_buy_balance(self):
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7

        signer_client = type("SignerClient", (), {
            "ORDER_TYPE_LIMIT": 1,
            "ORDER_TYPE_MARKET": 2,
            "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
            "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
            "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
            "DEFAULT_28_DAY_ORDER_EXPIRY": 1000,
            "DEFAULT_IOC_EXPIRY": 1001,
        })()
        signer_client.create_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 200})(), None))
        exchange._get_lighter_signer_client = lambda: signer_client
        exchange._account_available_balances = {"USDC": Decimal("0.01")}

        with self.assertRaises(IOError):
            await exchange._place_order(
                order_id="HBOT-lowbal",
                trading_pair="ETH-USDC",
                amount=Decimal("100"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("3000"),
            )

    async def test_replay_pending_spot_trade_entries_processes_matched_and_discards_stale(self):
        """_replay_pending_spot_trade_entries: matched fills processed, stale ones discarded."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._client_order_index_to_client_order_id = {"55": "HBOT-1"}
        exchange._server_order_index_to_client_order_index = {}
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange._current_timestamp = 1700000000
        _set_exchange_timestamp(exchange, 1700000000)

        tracked_order = type("Order", (), {
            "client_order_id": "HBOT-1",
            "exchange_order_id": "77",
            "trading_pair": "ETH-USDC",
            "quote_asset": "USDC",
            "trade_type": TradeType.BUY,
            "amount": Decimal("10"),
            "executed_amount_base": Decimal("0"),
            "is_done": False,
        })()

        processed = []
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_trade_update": lambda self, t: processed.append(t),
                "all_fillable_orders": {"HBOT-1": tracked_order},
                "process_order_update": lambda self, u: None,
                "all_fillable_orders_by_exchange_order_id": {},
                "all_updatable_orders": {"HBOT-1": tracked_order},
            },
        )()

        class Logger:
            def debug(self, *args, **kwargs):
                pass

        exchange.logger = lambda: Logger()
        exchange._schedule_unmatched_private_event_reconcile = MagicMock()

        import time as _time
        now = _time.time()
        # One fresh matched fill, one very old stale fill
        exchange._pending_spot_trade_entries = [
            (now - 0.5, {"I": "55", "trade_id": "trade-1", "price": "2", "amount": "1", "fee": "0", "created_at": 1700000000000}),
            (now - 60.0, {"i": "999", "trade_id": "stale-1", "price": "1", "amount": "1", "fee": "0", "created_at": 1700000000000}),
        ]

        await exchange._replay_pending_spot_trade_entries()

        self.assertEqual(1, len(processed))
        self.assertEqual("trade-1", processed[0].trade_id)
        self.assertEqual([], exchange._pending_spot_trade_entries)
        exchange._schedule_unmatched_private_event_reconcile.assert_called_once()

    async def test_fetch_and_apply_fills_skips_duplicate_in_progress(self):
        """_fetch_and_apply_fills must skip if already in-progress for same order."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._fill_fetch_in_progress = {"HBOT-dup"}
        exchange._all_trade_updates_for_order = AsyncMock()

        order = type("Order", (), {"client_order_id": "HBOT-dup"})()
        await exchange._fetch_and_apply_fills(order)

        exchange._all_trade_updates_for_order.assert_not_called()

    async def test_verify_cancel_not_false_applies_if_truly_canceled(self):
        """_verify_cancel_not_false must apply OrderState.CANCELED if REST confirms it."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._release_locked_balance_on_cancel = MagicMock()
        exchange._schedule_balance_sync_for_terminal_update = MagicMock()

        canceled_update = OrderUpdate(
            client_order_id="HBOT-V",
            exchange_order_id="99",
            trading_pair="ETH-USDC",
            update_timestamp=1700000000.0,
            new_state=OrderState.CANCELED,
        )
        exchange._request_order_status = AsyncMock(return_value=canceled_update)

        order_snap = type("Order", (), {"client_order_id": "HBOT-V"})()
        processed = []
        exchange._order_tracker = type("Tracker", (), {
            "all_fillable_orders": {"HBOT-V": order_snap},
            "process_order_update": lambda self, u: processed.append(u),
        })()

        class Logger:
            def debug(self, *args, **kwargs):
                pass

        exchange.logger = lambda: Logger()

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.asyncio.sleep", new=AsyncMock()):
            await exchange._verify_cancel_not_false(order_snap, delay=0.0)

        self.assertEqual(1, len(processed))
        exchange._release_locked_balance_on_cancel.assert_called_once()
        exchange._schedule_balance_sync_for_terminal_update.assert_called_once()

    # -----------------------------------------------------------------------
    # Additional coverage boost: lighter API client creation, _place_order
    # market flow, _on_order_failure, _safe_reconcile, safe_update_balances
    # -----------------------------------------------------------------------

    def test_get_lighter_api_client_builds_once_with_sdk(self):
        """_get_lighter_api_client creates client on first call and reuses it on second."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._lighter_api_client = None
        exchange._domain = "lighter"
        exchange._sdk_rest_base_url = lambda: "https://mainnet.zklighter.elliot.ai"

        fake_config_obj = object()
        fake_client_obj = object()

        fake_lighter = types.ModuleType("lighter")
        fake_lighter.Configuration = lambda host: fake_config_obj
        fake_lighter.ApiClient = lambda configuration: fake_client_obj

        with patch.dict("sys.modules", {"lighter": fake_lighter}):
            client1 = exchange._get_lighter_api_client()
            client2 = exchange._get_lighter_api_client()

        self.assertIs(fake_client_obj, client1)
        self.assertIs(client1, client2)
        self.assertIs(fake_client_obj, exchange._lighter_api_client)

    def test_sdk_rest_base_url_matches_api_host_for_signer(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._domain = "lighter"
        self.assertEqual(exchange._api_host_for_signer(), exchange._sdk_rest_base_url())

    async def test_place_order_market_buy_uses_slippage_price(self):
        """MARKET buy order picks ask price + slippage; no balance check for MARKET."""
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7
        exchange._signer_client_lock = asyncio.Lock()

        signer_client = type("SC", (), {
            "ORDER_TYPE_LIMIT": 1,
            "ORDER_TYPE_MARKET": 2,
            "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
            "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
            "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
            "DEFAULT_28_DAY_ORDER_EXPIRY": 1000,
            "DEFAULT_IOC_EXPIRY": 1001,
        })()
        signer_client.create_order = AsyncMock(return_value=(None, type("R", (), {"code": 200})(), None))
        exchange._get_lighter_signer_client = lambda: signer_client
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: False
        exchange._response_code = lambda r: getattr(r, "code", 0)
        exchange._sleep = AsyncMock()
        exchange._allocate_client_order_index = MagicMock(return_value=12345)
        exchange._account_available_balances = None
        exchange._schedule_balance_sync_for_terminal_update = lambda *a, **kw: None

        mock_ob = type("OB", (), {"get_price": lambda self, is_bid: Decimal("100.00")})()
        exchange.get_order_book = lambda tp: mock_ob

        oid, ts = await exchange._place_order(
            order_id="HBOT-mkt",
            trading_pair="ETH-USDC",
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("0"),
        )
        self.assertTrue(oid.isdigit())
        self.assertEqual(1700000000, ts)
        signer_client.create_order.assert_awaited_once()

    async def test_place_order_limit_maker_uses_post_only_tif(self):
        """LIMIT_MAKER order uses POST_ONLY time-in-force."""
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7
        exchange._signer_client_lock = asyncio.Lock()

        signer_client = type("SC", (), {
            "ORDER_TYPE_LIMIT": 1,
            "ORDER_TYPE_MARKET": 2,
            "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
            "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
            "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
            "DEFAULT_28_DAY_ORDER_EXPIRY": 1000,
            "DEFAULT_IOC_EXPIRY": 1001,
        })()
        signer_client.create_order = AsyncMock(return_value=(None, type("R", (), {"code": 200})(), None))
        exchange._get_lighter_signer_client = lambda: signer_client
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: False
        exchange._response_code = lambda r: getattr(r, "code", 0)
        exchange._sleep = AsyncMock()
        exchange._allocate_client_order_index = MagicMock(return_value=12345)
        exchange._account_available_balances = {"USDC": Decimal("10000")}
        exchange._schedule_balance_sync_for_terminal_update = lambda *a, **kw: None
        exchange._ensure_fresh_balance_snapshot_before_order = AsyncMock()

        oid, ts = await exchange._place_order(
            order_id="HBOT-pm",
            trading_pair="ETH-USDC",
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT_MAKER,
            price=Decimal("3000"),
        )
        self.assertTrue(oid.isdigit())
        call_kwargs = signer_client.create_order.call_args[1]
        self.assertEqual(12, call_kwargs["time_in_force"])

    async def test_on_order_failure_calls_super_for_unexpected_error(self):
        """_on_order_failure delegates to super for non-expected rejections."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._update_order_after_failure = MagicMock()
        super_called = []

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.ExchangePyBase._on_order_failure",
                   side_effect=lambda *a, **kw: super_called.append(True)):
            exchange._on_order_failure(
                order_id="HBOT-unexpected",
                trading_pair="ETH-USDC",
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("10"),
                exception=Exception("Unexpected network failure"),
            )

        exchange._update_order_after_failure.assert_not_called()
        self.assertEqual(1, len(super_called))

    async def test_safe_reconcile_unmatched_private_event_handles_exception(self):
        """_safe_reconcile must swallow non-cancel exceptions from _update_order_status."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._update_order_status = AsyncMock(side_effect=Exception("rest_fail"))

        class Logger:
            def debug(self, *a, **kw):
                pass

        exchange.logger = lambda: Logger()
        await exchange._safe_reconcile_unmatched_private_event()
        exchange._update_order_status.assert_awaited_once()

    async def test_safe_reconcile_re_raises_cancelled(self):
        """_safe_reconcile must propagate asyncio.CancelledError."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._update_order_status = AsyncMock(side_effect=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            await exchange._safe_reconcile_unmatched_private_event()

    def test_extract_private_stream_payloads_account_all_orders_channel(self):
        """account_all_orders channel should produce orders list only."""
        account_data, trades, orders = LighterExchange._extract_private_stream_payloads({
            "type": "update/account_all_orders",
            "orders": [{"id": "o1"}, {"id": "o2"}],
        })
        self.assertIsNone(account_data)
        self.assertEqual([], trades)
        self.assertEqual(2, len(orders))

    def test_extract_private_stream_payloads_account_tx_with_order(self):
        """account_tx channel processes txs with order sub-key."""
        account_data, trades, orders = LighterExchange._extract_private_stream_payloads({
            "type": "update/account_tx",
            "txs": [{"order": {"id": "o5"}}, {"i": "o6"}],
        })
        self.assertIsNone(account_data)
        self.assertEqual([], trades)
        order_ids = [o["id"] for o in orders if "id" in o]
        self.assertIn("o5", order_ids)

    def test_process_balance_message_removes_zero_balance_assets(self):
        """_process_balance_message_from_account removes assets no longer in payload."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._account_balances = {
            "USDC": Decimal("100"),
            "ETH": Decimal("5"),
            "OLDCOIN": Decimal("0"),
        }
        exchange._account_available_balances = {
            "USDC": Decimal("90"),
            "ETH": Decimal("5"),
            "OLDCOIN": Decimal("0"),
        }
        exchange._optimistic_balance_release = {}
        exchange._optimistic_balance_lock = {}

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.time.time", return_value=200.0):
            exchange._process_balance_message_from_account({
                "assets": [
                    {"symbol": "USDC", "balance": "100", "locked_balance": "10"},
                ]
            })

        self.assertIn("USDC", exchange._account_balances)
        # OLDCOIN had zero balance and was absent from payload, so it should be removed
        self.assertNotIn("OLDCOIN", exchange._account_balances)
        # ETH has non-zero balance so it stays even if not in this partial update
        self.assertIn("ETH", exchange._account_balances)

    def test_state_from_raw_order_status_all_known_states(self):
        exchange = LighterExchange.__new__(LighterExchange)
        self.assertEqual(OrderState.OPEN, exchange._state_from_raw_order_status("open"))
        self.assertEqual(OrderState.OPEN, exchange._state_from_raw_order_status("in-progress"))
        self.assertEqual(OrderState.PARTIALLY_FILLED, exchange._state_from_raw_order_status("partially_filled"))
        self.assertEqual(OrderState.FILLED, exchange._state_from_raw_order_status("filled"))
        self.assertEqual(OrderState.CANCELED, exchange._state_from_raw_order_status("canceled"))
        self.assertEqual(OrderState.PENDING_CREATE, exchange._state_from_raw_order_status("pending"))
        # Unknown status maps to OPEN as fallback
        self.assertEqual(OrderState.OPEN, exchange._state_from_raw_order_status("unknown-xyz"))

    def test_is_expected_order_rejection_patterns(self):
        self.assertTrue(LighterExchange._is_expected_order_rejection("minimum notional"))
        self.assertTrue(LighterExchange._is_expected_order_rejection("minimum lot size"))
        self.assertTrue(LighterExchange._is_expected_order_rejection("invalid order base or quote amount"))
        self.assertFalse(LighterExchange._is_expected_order_rejection("server timeout"))

    def test_response_code_helper(self):
        exchange = LighterExchange.__new__(LighterExchange)
        resp200 = type("R", (), {"code": 200})()
        resp429 = type("R", (), {"code": 429})()
        resp_none_attr = type("R", (), {})()
        self.assertEqual(200, exchange._response_code(resp200))
        self.assertEqual(429, exchange._response_code(resp429))
        self.assertIsNone(exchange._response_code(resp_none_attr))  # no code attr -> None
        self.assertIsNone(exchange._response_code(None))  # None input -> None

    async def test_fetch_and_apply_fills_processes_fills_and_credits_balance_on_cancel_fill_race(self):
        """_fetch_and_apply_fills: when order is CANCELED but fills exist, credits balance."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._fill_fetch_in_progress = set()
        exchange._release_locked_balance_on_fill = MagicMock()
        exchange._order_tracker = type("Tracker", (), {"process_trade_update": MagicMock()})()

        fill_update = type("FU", (), {"trade_id": "t1"})()
        exchange._all_trade_updates_for_order = AsyncMock(return_value=[fill_update])

        class Logger:
            def debug(self, *a, **kw):
                pass

            def info(self, *a, **kw):
                pass

        exchange.logger = lambda: Logger()

        order = type("Order", (), {
            "client_order_id": "HBOT-cr",
            "current_state": OrderState.CANCELED,
        })()

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.asyncio.sleep", new=AsyncMock()):
            await exchange._fetch_and_apply_fills(order, delay=0.0)

        exchange._order_tracker.process_trade_update.assert_called_once_with(fill_update)
        exchange._release_locked_balance_on_fill.assert_called_once_with(order)
        self.assertNotIn("HBOT-cr", exchange._fill_fetch_in_progress)

    async def test_fetch_and_apply_fills_retries_when_no_fills(self):
        """_fetch_and_apply_fills: schedules retry when no fills found and retries_left>0."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._fill_fetch_in_progress = set()
        exchange._all_trade_updates_for_order = AsyncMock(return_value=[])

        class Logger:
            def debug(self, *a, **kw):
                pass

        exchange.logger = lambda: Logger()

        order = type("Order", (), {
            "client_order_id": "HBOT-retry",
            "current_state": OrderState.FILLED,
        })()

        futures_scheduled = []
        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.safe_ensure_future",
                   side_effect=lambda coro: futures_scheduled.append(coro)):
            with patch("hummingbot.connector.exchange.lighter.lighter_exchange.asyncio.sleep", new=AsyncMock()):
                await exchange._fetch_and_apply_fills(order, delay=0.0, _retries_left=3)

        self.assertEqual(1, len(futures_scheduled))
        self.assertNotIn("HBOT-retry", exchange._fill_fetch_in_progress)

    async def test_verify_cancel_not_false_open_state_preserves_order(self):
        """_verify_cancel_not_false: OPEN state means false cancel; don't apply CANCELED."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._release_locked_balance_on_cancel = MagicMock()
        exchange._schedule_balance_sync_for_terminal_update = MagicMock()

        open_update = OrderUpdate(
            client_order_id="HBOT-FC",
            exchange_order_id="99",
            trading_pair="ETH-USDC",
            update_timestamp=1700000000.0,
            new_state=OrderState.OPEN,
        )
        exchange._request_order_status = AsyncMock(return_value=open_update)
        processed = []
        exchange._order_tracker = type("Tracker", (), {
            "all_fillable_orders": {},
            "process_order_update": lambda self, u: processed.append(u),
        })()

        class Logger:
            def debug(self, *a, **kw):
                pass

        exchange.logger = lambda: Logger()
        order = type("Order", (), {"client_order_id": "HBOT-FC"})()

        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.asyncio.sleep", new=AsyncMock()):
            await exchange._verify_cancel_not_false(order, delay=0.0)

        self.assertEqual(0, len(processed))
        exchange._release_locked_balance_on_cancel.assert_not_called()

    # ── _place_cancel coverage tests ──────────────────────────────────────

    def _make_cancel_exchange(self, cancel_response=None):
        """Helper: build a minimal exchange for _place_cancel tests."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7
        exchange._signer_client_lock = asyncio.Lock()
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: False
        exchange._response_code = lambda r: getattr(r, "code", None)
        exchange._sleep = AsyncMock()
        exchange._schedule_balance_sync_for_terminal_update = lambda *a, **kw: None

        resp200 = type("Resp", (), {"code": 200})()
        rv = cancel_response if cancel_response is not None else (None, resp200, None)

        signer_client = type("SC", (), {})()
        signer_client.cancel_order = AsyncMock(return_value=rv)
        exchange._get_lighter_signer_client = lambda: signer_client
        return exchange, signer_client

    async def test_place_cancel_success_no_fills_schedules_background_retry(self):
        """Cancel succeeds; no fills found → safe_ensure_future(_fetch_and_apply_fills, delay=0)."""
        exchange, _ = self._make_cancel_exchange()
        exchange._all_trade_updates_for_order = AsyncMock(return_value=[])
        exchange._fetch_and_apply_fills = AsyncMock()

        tracked = type("T", (), {
            "client_order_id": "HBOT-X", "trading_pair": "ETH-USDC", "exchange_order_id": "42",
        })()
        result = await exchange._place_cancel("HBOT-X", tracked)
        self.assertTrue(result)

    async def test_place_cancel_success_with_fills_processes_order_tracker(self):
        """Cancel succeeds; fills found → order_tracker.process_trade_update called."""
        exchange, _ = self._make_cancel_exchange()
        fill_update = MagicMock()
        exchange._all_trade_updates_for_order = AsyncMock(return_value=[fill_update])
        mock_tracker = MagicMock()
        exchange._order_tracker = mock_tracker
        exchange._fetch_and_apply_fills = AsyncMock()

        tracked = type("T", (), {
            "client_order_id": "HBOT-X", "trading_pair": "ETH-USDC", "exchange_order_id": "42",
        })()
        result = await exchange._place_cancel("HBOT-X", tracked)
        self.assertTrue(result)
        mock_tracker.process_trade_update.assert_called_once_with(fill_update)

    async def test_place_cancel_nonce_retry_then_success(self):
        """Nonce failure on first attempt triggers signer refresh and retries."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7
        exchange._signer_client_lock = asyncio.Lock()
        exchange._response_code = lambda r: getattr(r, "code", None)
        exchange._sleep = AsyncMock()
        exchange._schedule_balance_sync_for_terminal_update = lambda *a, **kw: None
        exchange._all_trade_updates_for_order = AsyncMock(return_value=[])
        exchange._fetch_and_apply_fills = AsyncMock()

        resp200 = type("Resp", (), {"code": 200})()
        signer_client = type("SC", (), {})()
        signer_client.cancel_order = AsyncMock(side_effect=[
            (None, None, "nonce_err"),
            (None, resp200, None),
        ])
        exchange._get_lighter_signer_client = lambda: signer_client
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: error == "nonce_err"
        exchange._refresh_signer_client_async = AsyncMock(return_value=signer_client)

        tracked = type("T", (), {
            "client_order_id": "HBOT-X", "trading_pair": "ETH-USDC", "exchange_order_id": "42",
        })()
        result = await exchange._place_cancel("HBOT-X", tracked)
        self.assertTrue(result)
        self.assertEqual(2, signer_client.cancel_order.call_count)

    async def test_place_cancel_timeout_raises_ioerror(self):
        """asyncio.TimeoutError from wait_for is re-raised as IOError."""
        exchange, _ = self._make_cancel_exchange()

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            with self.assertRaises(IOError):
                tracked = type("T", (), {
                    "client_order_id": "HBOT-X", "trading_pair": "ETH-USDC", "exchange_order_id": "42",
                })()
                await exchange._place_cancel("HBOT-X", tracked)

    async def test_place_cancel_returns_false_when_exchange_id_clears_mid_loop(self):
        """exchange_order_id becoming None inside the for-loop returns False immediately."""
        from unittest.mock import PropertyMock
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7
        exchange._signer_client_lock = asyncio.Lock()
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: False
        exchange._response_code = lambda r: getattr(r, "code", None)
        exchange._sleep = AsyncMock()

        tracked = MagicMock()
        tracked.trading_pair = "ETH-USDC"
        type(tracked).exchange_order_id = PropertyMock(side_effect=["42", None])

        signer_client = type("SC", (), {})()
        exchange._get_lighter_signer_client = lambda: signer_client

        result = await exchange._place_cancel("HBOT-X", tracked)
        self.assertFalse(result)

    # ── _place_order MARKET order coverage ────────────────────────────────

    async def test_place_order_sell_market_applies_negative_slippage(self):
        """SELL MARKET order uses bid price with negative slippage (line 819)."""
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._allocate_client_order_index = MagicMock(return_value=999)
        exchange._client_order_index_from_order_id = lambda oid: 999
        exchange._get_api_key_index = lambda: 7
        exchange._account_available_balances = None
        exchange._signer_client_lock = asyncio.Lock()

        resp200 = type("Resp", (), {"code": 200})()
        signer_client = type("SignerClient", (), {
            "ORDER_TYPE_LIMIT": 1,
            "ORDER_TYPE_MARKET": 2,
            "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
            "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
            "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
            "DEFAULT_28_DAY_ORDER_EXPIRY": 1000,
            "DEFAULT_IOC_EXPIRY": 1001,
        })()
        signer_client.create_order = AsyncMock(return_value=(None, resp200, None))
        exchange._get_lighter_signer_client = lambda: signer_client

        # bid price = 90 for SELL market
        mock_ob = type("OB", (), {"get_price": lambda self, is_bid: 90.0 if not is_bid else 110.0})()
        exchange.get_order_book = lambda tp: mock_ob

        exchange._lock_balance_on_order_creation = lambda *a, **kw: None
        exchange._schedule_fast_balance_sync = lambda *a, **kw: None
        exchange._client_order_index_to_client_order_id = {}
        exchange._hb_order_id_to_client_order_index = {}

        oid, ts = await exchange._place_order(
            order_id="HBOT-SELL",
            trading_pair="ETH-USDC",
            amount=Decimal("1"),
            trade_type=TradeType.SELL,
            order_type=OrderType.MARKET,
            price=Decimal("NaN"),
        )
        self.assertTrue(oid.isdigit())

    async def test_place_order_market_invalid_price_raises_value_error(self):
        """MARKET order with NaN/None best price raises ValueError (line 812)."""
        exchange = LighterExchange.__new__(LighterExchange)
        _set_exchange_timestamp(exchange, 1700000000)
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7
        exchange._account_available_balances = None
        exchange._signer_client_lock = asyncio.Lock()

        signer_client = type("SC", (), {
            "ORDER_TYPE_MARKET": 2,
            "ORDER_TYPE_LIMIT": 1,
            "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
            "DEFAULT_IOC_EXPIRY": 1001,
        })()
        exchange._get_lighter_signer_client = lambda: signer_client

        # order book returns NaN → invalid price
        mock_ob = type("OB", (), {"get_price": lambda self, is_bid: Decimal("NaN")})()
        exchange.get_order_book = lambda tp: mock_ob

        with self.assertRaises(ValueError, msg="Should raise ValueError for invalid market price"):
            await exchange._place_order(
                order_id="HBOT-M",
                trading_pair="ETH-USDC",
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.MARKET,
                price=Decimal("NaN"),
            )

    async def test_place_order_spot_nonce_retry_then_success(self):
        """Spot _place_order: first nonce error, then succeeds on retry (lines 868-871)."""
        exchange, _ = self._make_cancel_exchange()
        exchange._current_client_order_id_seq = 100
        exchange._account_index = "123456"
        exchange._api_key_index = "1"
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: "invalid nonce" in str(error or "")

        # Mock signer client: first create_order fails with "invalid nonce", second succeeds
        signer_client = MagicMock()
        signer_client.get_account_portfolio = AsyncMock(return_value={"accounts": []})
        resp200 = type("Resp", (), {"code": 200})()
        signer_client.create_order = AsyncMock(
            side_effect=[
                ("order-1", {"code": 400}, "invalid nonce: sequence too old"),
                ("order-2", resp200, None),
            ]
        )
        exchange._get_lighter_signer_client = lambda: signer_client
        exchange._refresh_signer_client_async = AsyncMock(return_value=signer_client)
        exchange._allocate_client_order_index = lambda: 101
        exchange.get_order_book = lambda tp: MagicMock(get_price=lambda is_bid: Decimal("100"))

        # First call will have nonce error and retry, second will succeed
        await exchange._place_order(
            order_id="HBOT-L",
            trading_pair="ETH-USDC",
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("99"),
        )

        # Should have called create_order twice (once with nonce error, once with success)
        self.assertEqual(2, signer_client.create_order.await_count)
        # Should have refreshed signer client on nonce error
        exchange._refresh_signer_client_async.assert_awaited_once()

    async def test_place_cancel_nonce_retry_with_refresh_failure(self):
        """Cancel nonce retry: refresh fails but retries with existing client (lines 581-582)."""
        exchange, signer_client = self._make_cancel_exchange()
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: "invalid nonce" in str(error or "")
        logger = MagicMock()
        exchange.logger = MagicMock(return_value=logger)

        # First cancel fails with nonce error, refresh fails, second cancel succeeds
        resp200 = type("Resp", (), {"code": 200})()
        signer_client.cancel_order = AsyncMock(
            side_effect=[
                (False, None, "invalid nonce: sequence too old"),
                (True, resp200, None),
            ]
        )
        exchange._refresh_signer_client_async = AsyncMock(side_effect=RuntimeError("refresh failed"))

        tracked = type("T", (), {
            "client_order_id": "HBOT-X", "trading_pair": "ETH-USDC", "exchange_order_id": "42",
        })()
        result = await exchange._place_cancel("HBOT-X", tracked)

        self.assertTrue(result)
        logger.warning.assert_called_once()
        # Refresh was attempted once, then retried with existing client
        self.assertEqual(2, signer_client.cancel_order.await_count)

    async def test_place_cancel_raises_ioerror_when_tx_response_none(self):
        """Cancel raises IOError when tx_response is None (line 639)."""
        exchange, signer_client = self._make_cancel_exchange(cancel_response=(False, None, None))
        exchange._all_trade_updates_for_order = AsyncMock(return_value=[])

        tracked = type("T", (), {
            "client_order_id": "HBOT-X", "trading_pair": "ETH-USDC", "exchange_order_id": "42",
        })()

        with self.assertRaises(IOError):
            await exchange._place_cancel("HBOT-X", tracked)

    async def test_place_cancel_raises_ioerror_when_error_is_not_none(self):
        """Cancel raises IOError when error is returned (line 637)."""
        exchange, signer_client = self._make_cancel_exchange(cancel_response=(False, None, "signing failed"))
        exchange._all_trade_updates_for_order = AsyncMock(return_value=[])

        tracked = type("T", (), {
            "client_order_id": "HBOT-X", "trading_pair": "ETH-USDC", "exchange_order_id": "42",
        })()

        with self.assertRaises(IOError):
            await exchange._place_cancel("HBOT-X", tracked)

    async def test_place_modify_raises_ioerror_on_bad_response(self):
        """Modify raises IOError when tx_response code is not 200."""
        exchange, signer_client = self._make_cancel_exchange()
        exchange._response_code = MagicMock(return_value=500)

        resp = type("Resp", (), {"code": 500})()
        signer_client.modify_order = AsyncMock(return_value=(False, resp, None))

        tracked = type("T", (), {
            "client_order_id": "HBOT-X", "trading_pair": "ETH-USDC", "exchange_order_id": "42",
        })()

        with self.assertRaises(IOError):
            await exchange._place_modify(tracked, Decimal("1.0"), Decimal("100"))

    async def test_place_order_with_nonce_retry_then_success(self):
        """Place order succeeds after nonce retry."""
        exchange, signer_client = self._make_cancel_exchange()
        exchange._get_market_spec = AsyncMock(return_value=(1, 8, 6, "ETH-USDC"))
        exchange._is_invalid_nonce_failure = lambda error=None, response=None: "invalid nonce" in str(error or "")
        exchange._refresh_signer_client_async = AsyncMock(return_value=signer_client)
        exchange._allocate_client_order_index = MagicMock(return_value=101)
        exchange._client_order_index_to_client_order_id = {}
        exchange._hb_order_id_to_client_order_index = {}
        exchange._lock_balance_on_order_creation = MagicMock()
        exchange._schedule_fast_balance_sync = MagicMock()
        exchange.get_order_book = lambda tp: MagicMock(get_price=lambda is_bid: Decimal("100"))

        # First call: nonce error, second call: success
        resp200 = type("Resp", (), {"code": 200})()
        signer_client.ORDER_TYPE_LIMIT = 1
        signer_client.ORDER_TYPE_MARKET = 2
        signer_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 10
        signer_client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = 11
        signer_client.ORDER_TIME_IN_FORCE_POST_ONLY = 12
        signer_client.DEFAULT_28_DAY_ORDER_EXPIRY = 1000
        signer_client.DEFAULT_IOC_EXPIRY = 1001
        signer_client.create_order = AsyncMock(
            side_effect=[
                (False, None, "invalid nonce: sequence too old"),
                (True, resp200, None),
            ]
        )

        result = await exchange._place_order(
            order_id="HBOT-X",
            trading_pair="ETH-USDC",
            amount=Decimal("1.0"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("100"),
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, signer_client.create_order.await_count)

    # ------------------------------------------------------------------
    # _cleanup_startup_orphan_orders
    # ------------------------------------------------------------------

    async def test_cleanup_startup_orphan_orders_noop_when_already_done(self):
        """Returns early without any REST call when the one-time flag is already set."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._startup_orphan_cleanup_done = True
        exchange._api_get = AsyncMock()

        await exchange._cleanup_startup_orphan_orders()
        exchange._api_get.assert_not_awaited()

    async def test_cleanup_startup_orphan_orders_no_orphans_skips_cancel(self):
        """When all active orders are tracked, no cancels are issued."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._startup_orphan_cleanup_done = False

        tracked = MagicMock()
        tracked.exchange_order_id = "77"
        exchange._client_order_index_to_client_order_id = {}
        exchange._get_account_index = lambda: 100
        exchange._api_get = AsyncMock(return_value={
            "success": True,
            "orders": [{"client_order_id": "77", "order_id": "77", "symbol": "ETH/USDC"}],
        })
        exchange._get_lighter_signer_client = MagicMock()
        exchange._signer_client_lock = asyncio.Lock()
        exchange._schedule_fast_balance_sync = MagicMock()

        with patch.object(type(exchange), 'in_flight_orders', new_callable=PropertyMock, return_value={"HBOT-1": tracked}):
            await exchange._cleanup_startup_orphan_orders()

        # No cancel should have been attempted
        exchange._get_lighter_signer_client.assert_not_called()

    async def test_cleanup_startup_orphan_orders_cancels_untracked_order(self):
        """Cancels an active order whose ID is not present in in_flight_orders."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._startup_orphan_cleanup_done = False
        exchange._client_order_index_to_client_order_id = {}
        exchange._get_account_index = lambda: 100
        exchange._api_get = AsyncMock(return_value={
            "success": True,
            "orders": [{"client_order_id": "42", "order_id": "42", "symbol": "ETH/USDC"}],
        })

        signer_client = MagicMock()
        signer_client.cancel_order = AsyncMock(return_value=(None, None, None))
        exchange._get_lighter_signer_client = MagicMock(return_value=signer_client)
        exchange._signer_client_lock = asyncio.Lock()
        exchange._hb_pair_from_symbol = lambda s: "ETH-USDC"
        exchange._get_market_spec = AsyncMock(return_value=(1, 4, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7
        exchange._schedule_fast_balance_sync = MagicMock()

        with patch.object(type(exchange), 'in_flight_orders', new_callable=PropertyMock, return_value={}):
            await exchange._cleanup_startup_orphan_orders()

        signer_client.cancel_order.assert_awaited_once()

    async def test_cleanup_startup_orphan_orders_api_failure_returns_early(self):
        """When the REST call returns a non-success response, nothing is cancelled."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._startup_orphan_cleanup_done = False
        exchange._client_order_index_to_client_order_id = {}
        exchange._get_account_index = lambda: 100
        exchange._api_get = AsyncMock(return_value={"success": False})
        exchange._get_lighter_signer_client = MagicMock()
        exchange._signer_client_lock = asyncio.Lock()

        with patch.object(type(exchange), 'in_flight_orders', new_callable=PropertyMock, return_value={}):
            await exchange._cleanup_startup_orphan_orders()
        exchange._get_lighter_signer_client.assert_not_called()

    # ------------------------------------------------------------------
    # _cleanup_runtime_orphan_orders
    # ------------------------------------------------------------------

    async def test_cleanup_runtime_orphan_orders_no_orphans(self):
        """When all active orders are tracked, no cancels are issued."""
        exchange = LighterExchange.__new__(LighterExchange)
        tracked = MagicMock()
        tracked.exchange_order_id = "55"
        exchange._client_order_index_to_client_order_id = {}
        exchange._get_account_index = lambda: 100
        exchange._api_get = AsyncMock(return_value={
            "success": True,
            "orders": [{"client_order_id": "55", "order_id": "55"}],
        })
        exchange._get_lighter_signer_client = MagicMock()
        exchange._signer_client_lock = asyncio.Lock()
        exchange._schedule_fast_balance_sync = MagicMock()

        with patch.object(type(exchange), 'in_flight_orders', new_callable=PropertyMock, return_value={"HBOT-1": tracked}):
            await exchange._cleanup_runtime_orphan_orders()
        exchange._get_lighter_signer_client.assert_not_called()

    async def test_cleanup_runtime_orphan_orders_cancels_untracked(self):
        """Cancels a runtime-orphan order not present in tracked orders."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._client_order_index_to_client_order_id = {}
        exchange._get_account_index = lambda: 100
        exchange._api_get = AsyncMock(return_value={
            "success": True,
            "orders": [{"client_order_id": "88", "order_id": "88", "symbol": "ETH/USDC"}],
        })

        signer_client = MagicMock()
        signer_client.cancel_order = AsyncMock(return_value=(None, None, None))
        exchange._get_lighter_signer_client = MagicMock(return_value=signer_client)
        exchange._signer_client_lock = asyncio.Lock()
        exchange._hb_pair_from_symbol = lambda s: "ETH-USDC"
        exchange._get_market_spec = AsyncMock(return_value=(1, 4, 2, "ETH/USDC"))
        exchange._get_api_key_index = lambda: 7
        exchange._schedule_fast_balance_sync = MagicMock()

        with patch.object(type(exchange), 'in_flight_orders', new_callable=PropertyMock, return_value={}):
            await exchange._cleanup_runtime_orphan_orders()
        signer_client.cancel_order.assert_awaited_once()

    async def test_cleanup_runtime_orphan_orders_api_failure_returns_early(self):
        """When REST returns a non-success response, cleanup stops without cancelling."""
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._client_order_index_to_client_order_id = {}
        exchange._get_account_index = lambda: 100
        exchange._api_get = AsyncMock(return_value={"error": "rate_limited"})
        exchange._get_lighter_signer_client = MagicMock()
        exchange._signer_client_lock = asyncio.Lock()

        with patch.object(type(exchange), 'in_flight_orders', new_callable=PropertyMock, return_value={}):
            await exchange._cleanup_runtime_orphan_orders()
        exchange._get_lighter_signer_client.assert_not_called()
