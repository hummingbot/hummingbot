"""
Tests for the Lighter spot connector.

Lighter diverges from the base in one structural way: orders are **signed and
submitted through the Lighter SDK signer client** (``_signer_client.create_order`` /
``cancel_order``) rather than through an HTTP POST that ``aioresponses`` can
intercept. The order-creation and order-cancellation tests are therefore overridden
to drive a mocked signer client. Everything reachable over REST (which Lighter
serves with authenticated GET requests) is left to the base class.
"""

import asyncio
import json
import re
from decimal import Decimal
from types import SimpleNamespace
from typing import Callable, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS, lighter_web_utils as web_utils
from hummingbot.connector.exchange.lighter.lighter_api_utils import LighterMarketInfo
from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import TradeFeeBase


class MockSignerClient:
    """Stand-in for ``lighter.SignerClient`` so tests never touch the real SDK or crypto."""

    ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 0
    ORDER_TIME_IN_FORCE_POST_ONLY = 1
    ORDER_TYPE_LIMIT = 0

    def __init__(self):
        self.create_order = AsyncMock(return_value=(None, {"code": 200}, None))
        self.create_market_order = AsyncMock(return_value=(None, {"code": 200}, None))
        self.cancel_order = AsyncMock(return_value=(None, {"code": 200}, None))

    def create_auth_token_with_expiry(self, deadline, api_key_index):
        return "lighter-auth-token", None


class LighterExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)
        cls.exchange_symbol = f"{cls.base_asset}/{cls.quote_asset}"
        cls.market_id = 1
        cls.account_index = 724450
        cls.l1_address = "0xabc"
        cls.api_key_index = 2
        cls._trading_required = True
        cls.api_private_key = "0xprivate"
        cls._auth_token = "lighter-auth-token"
        cls.client_order_id_prefix = "HBOT"
        cls.exchange_order_id_prefix = "9100"
        cls.maker_fee = Decimal("0.0001")
        cls.taker_fee = Decimal("0.0004")

    def setUp(self) -> None:
        super().setUp()
        self._simulate_markets()

    @staticmethod
    def _regex_url(path_url: str):
        url = web_utils.public_rest_url(path_url)
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

    @property
    def all_symbols_url(self):
        return self._regex_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)

    @property
    def latest_prices_url(self):
        return self._regex_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)

    @property
    def network_status_url(self):
        return self._regex_url(CONSTANTS.PING_PATH_URL)

    @property
    def trading_rules_url(self):
        return self._regex_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)

    @property
    def order_creation_url(self):
        # Lighter submits orders through the SDK signer (not REST); the order-creation
        # tests are overridden below, so this URL is only a placeholder for completeness.
        return web_utils.public_rest_url("/api/v1/sendTx")

    @property
    def balance_url(self):
        return web_utils.public_rest_url(CONSTANTS.BALANCE_PATH_URL)

    @property
    def active_orders_url(self):
        return web_utils.public_rest_url(CONSTANTS.ACCOUNT_ACTIVE_ORDERS_PATH_URL)

    @property
    def inactive_orders_url(self):
        return web_utils.public_rest_url(CONSTANTS.ACCOUNT_INACTIVE_ORDERS_PATH_URL)

    def _market_detail(self, symbol: str, market_id: int, status: str = "active", hidden: bool = False,
                       last_trade_price: str = "9999.9") -> dict:
        return {
            "symbol": symbol,
            "market_id": market_id,
            "status": status,
            "market_config": {"hidden": hidden},
            "min_base_amount": "0.01",
            "min_quote_amount": "10",
            "supported_size_decimals": 6,
            "supported_price_decimals": 4,
            "maker_fee": str(self.maker_fee),
            "taker_fee": str(self.taker_fee),
            "last_trade_price": last_trade_price,
        }

    @property
    def all_symbols_request_mock_response(self):
        return {"spot_order_book_details": [self._market_detail(self.exchange_symbol, self.market_id)]}

    @property
    def latest_prices_request_mock_response(self):
        return {
            "spot_order_book_details": [
                self._market_detail(self.exchange_symbol, self.market_id, last_trade_price=str(self.expected_latest_price))
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        response = {
            "spot_order_book_details": [
                self._market_detail(self.exchange_symbol, self.market_id),
                # Inactive market — filtered out by is_exchange_information_valid.
                self._market_detail("INVALID/PAIR", 9999, status="inactive"),
            ]
        }
        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {"status": "ok"}

    @property
    def trading_rules_request_mock_response(self):
        return {"spot_order_book_details": [self._market_detail(self.exchange_symbol, self.market_id)]}

    @property
    def trading_rules_request_erroneous_mock_response(self):
        # An "active" market that is missing the fields required to build a trading rule.
        return {
            "spot_order_book_details": [
                {
                    "symbol": self.exchange_symbol,
                    "market_id": self.market_id,
                    "status": "active",
                    "market_config": {"hidden": False},
                }
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        # Orders go through the signer client; not used by the overridden creation tests.
        return {"code": 200}

    def _account_balance_response(self, assets: List[dict]) -> dict:
        return {"accounts": [{"index": self.account_index, "assets": assets}]}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return self._account_balance_response(
            [
                {"symbol": self.base_asset, "balance": "15", "locked_balance": "5"},
                {"symbol": self.quote_asset, "balance": "2000", "locked_balance": "0"},
            ]
        )

    @property
    def balance_request_mock_response_only_base(self):
        return self._account_balance_response(
            [{"symbol": self.base_asset, "balance": "15", "locked_balance": "5"}]
        )

    @property
    def balance_event_websocket_update(self):
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_ASSETS_CHANNEL}:{self.account_index}",
            "assets": {
                "1": {"symbol": self.base_asset, "balance": "15", "locked_balance": "5"},
            },
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.01"),
            min_base_amount_increment=Decimal("1e-6"),
            min_price_increment=Decimal("1e-4"),
            min_notional_size=Decimal("10"),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["spot_order_book_details"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "99001"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        # Fills are delivered through the dedicated trade-history poll / websocket trade
        # channel, never bundled into the order-status response.
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10000")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return TradeFeeBase.new_spot_fee(
            fee_schema=self.exchange.trade_fee_schema(),
            trade_type=TradeType.BUY,
            percent=self.taker_fee,
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "30000"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}/{quote_token}"

    # ----------------------------------------------------------------------------------
    # Exchange construction & helpers
    # ----------------------------------------------------------------------------------
    def create_exchange_instance(self):
        with patch.object(LighterExchange, "_create_signer_client", return_value=MockSignerClient()):
            exchange = LighterExchange(
                lighter_l1_address=self.l1_address,
                lighter_account_index=self.account_index,
                lighter_api_key_index=self.api_key_index,
                lighter_api_private_key=self.api_private_key,
                trading_pairs=[self.trading_pair],
            )
        return exchange

    def _market_info(self) -> LighterMarketInfo:
        return LighterMarketInfo(
            market_id=self.market_id,
            exchange_symbol=self.exchange_symbol,
            trading_pair=self.trading_pair,
            base_asset=self.base_asset,
            quote_asset=self.quote_asset,
            market_type="spot",
            min_base_amount=Decimal("0.01"),
            min_quote_amount=Decimal("10"),
            size_decimals=6,
            price_decimals=4,
            maker_fee=self.maker_fee,
            taker_fee=self.taker_fee,
            raw_info={"last_trade_price": "9999.9"},
        )

    def _simulate_markets(self):
        market = self._market_info()
        self.exchange._markets_by_trading_pair = {self.trading_pair: market}
        self.exchange._markets_by_id = {self.market_id: market}
        self.exchange._markets_by_exchange_symbol = {self.exchange_symbol: market}

    def _simulate_trading_rules_initialized(self):
        super()._simulate_trading_rules_initialized()
        self._simulate_markets()

    # ----------------------------------------------------------------------------------
    # Request validators
    # ----------------------------------------------------------------------------------
    def validate_auth_credentials_present(self, request_call: RequestCall):
        params = request_call.kwargs.get("params") or {}
        if params.get("auth") is not None:
            self.assertEqual(self._auth_token, params.get("auth"))

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        # Orders are not created over REST on Lighter; see the overridden creation tests.
        pass

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        params = request_call.kwargs["params"]
        self.assertEqual(self.account_index, params["account_index"])
        self.assertEqual(self.market_id, params["market_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        params = request_call.kwargs["params"]
        self.assertEqual(self.account_index, params["account_index"])
        self.assertEqual(self.market_id, params["market_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        params = request_call.kwargs["params"]
        self.assertEqual(self.account_index, params["account_index"])
        self.assertEqual(self.market_id, params["market_id"])

    # ----------------------------------------------------------------------------------
    # Order status configuration (active/inactive GET endpoints)
    # ----------------------------------------------------------------------------------
    def _order_data(self, order: InFlightOrder, status: str, filled_base_amount: str = "0") -> dict:
        return {
            "client_order_id": order.client_order_id,
            "order_id": order.exchange_order_id or self.expected_exchange_order_id,
            "status": status,
            "filled_base_amount": filled_base_amount,
            "transaction_time": "1640780000000000",
        }

    def _mock_active_orders(self, mock_api, orders, callback=lambda *a, **k: None):
        url = self.active_orders_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps({"orders": orders}), callback=callback)
        return url

    def _mock_inactive_orders(self, mock_api, orders, callback=lambda *a, **k: None):
        url = self.inactive_orders_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps({"orders": orders}), callback=callback)
        return url

    def configure_completely_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        active = self._mock_active_orders(mock_api, [])
        inactive = self._mock_inactive_orders(mock_api, [self._order_data(order, "filled")], callback=callback)
        return [active, inactive]

    def configure_canceled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        active = self._mock_active_orders(mock_api, [])
        inactive = self._mock_inactive_orders(mock_api, [self._order_data(order, "canceled")], callback=callback)
        return [active, inactive]

    def configure_open_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        return self._mock_active_orders(mock_api, [self._order_data(order, "open")], callback=callback)

    def configure_partially_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        return self._mock_active_orders(
            mock_api, [self._order_data(order, "open", filled_base_amount="0.5")], callback=callback)

    def configure_http_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = self.active_orders_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=500, callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        # The order is absent from both active and inactive lists. Advance the clock past the
        # post-creation grace window so the connector treats the absence as a hard "not found".
        self.exchange._set_current_timestamp(
            self.exchange.current_timestamp + CONSTANTS.ORDER_NOT_FOUND_GRACE_PERIOD + 1)
        active = self._mock_active_orders(mock_api, [])
        inactive = self._mock_inactive_orders(mock_api, [], callback=callback)
        return [active, inactive]

    # ----------------------------------------------------------------------------------
    # Trade-history configuration (used by lost-order fill flow)
    # ----------------------------------------------------------------------------------
    def _trade_data(self, order: InFlightOrder) -> dict:
        return {
            "ask_account_id": 1,
            "bid_account_id": self.account_index,
            "bid_client_id_str": order.client_order_id,
            "bid_id_str": order.exchange_order_id or self.expected_exchange_order_id,
            "is_maker_ask": True,
            "market_id": self.market_id,
            "trade_id": self.expected_fill_trade_id,
            "price": str(order.price),
            "size": str(order.amount),
            "transaction_time": "1640780000000000",
        }

    def configure_full_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps({"trades": [self._trade_data(order)]}), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        trade = self._trade_data(order)
        trade["size"] = str(self.expected_partial_fill_amount)
        mock_api.get(regex_url, body=json.dumps({"trades": [trade]}), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    # ----------------------------------------------------------------------------------
    # Cancelation configuration (find via REST GET, cancel via signer)
    # ----------------------------------------------------------------------------------
    def configure_successful_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        self.exchange._signer_client.cancel_order = AsyncMock(return_value=(None, {"code": 200}, None))
        return self._mock_active_orders(mock_api, [self._order_data(order, "open")], callback=callback)

    def configure_erroneous_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        self.exchange._signer_client.cancel_order = AsyncMock(return_value=(None, {"code": 200}, "boom"))
        return self._mock_active_orders(mock_api, [self._order_data(order, "open")], callback=callback)

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        active = self._mock_active_orders(mock_api, [])
        inactive = self._mock_inactive_orders(mock_api, [], callback=callback)
        return [active, inactive]

    def configure_one_successful_one_erroneous_cancel_all_response(
            self, successful_order: InFlightOrder, erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        # Both orders are found through the same active-orders endpoint; the signer mock decides
        # which one fails based on its on-chain order index.
        active = self._mock_active_orders(
            mock_api,
            [self._order_data(successful_order, "open"), self._order_data(erroneous_order, "open")],
        )

        success_index = int(successful_order.exchange_order_id)

        async def cancel_side_effect(market_index, order_index):
            if order_index == success_index:
                return None, {"code": 200}, None
            return None, {"code": 200}, "boom"

        self.exchange._signer_client.cancel_order = AsyncMock(side_effect=cancel_side_effect)
        return [active]

    # ----------------------------------------------------------------------------------
    # Websocket event builders
    # ----------------------------------------------------------------------------------
    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_ORDERS_CHANNEL}:{self.account_index}",
            "orders": {str(self.market_id): [self._order_data(order, "open")]},
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_ORDERS_CHANNEL}:{self.account_index}",
            "orders": {str(self.market_id): [self._order_data(order, "canceled")]},
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_ORDERS_CHANNEL}:{self.account_index}",
            "orders": {str(self.market_id): [self._order_data(order, "filled", filled_base_amount=str(order.amount))]},
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_TRADES_CHANNEL}:{self.account_index}",
            "trades": {str(self.market_id): [self._trade_data(order)]},
        }

    # ----------------------------------------------------------------------------------
    # Overridden tests — order creation through the SDK signer
    # ----------------------------------------------------------------------------------
    async def test_create_buy_limit_order_successfully(self, *_):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        order_id = self.place_buy_order()
        await asyncio.sleep(0.1)

        self.exchange._signer_client.create_order.assert_awaited()
        self.assertIn(order_id, self.exchange.in_flight_orders)

        create_event = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)

    async def test_create_sell_limit_order_successfully(self, *_):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        order_id = self.place_sell_order()
        await asyncio.sleep(0.1)

        self.exchange._signer_client.create_order.assert_awaited()
        self.assertIn(order_id, self.exchange.in_flight_orders)

        create_event = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(order_id, create_event.order_id)

    async def test_create_limit_maker_order_uses_post_only(self, *_):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        self.place_buy_order(order_type=OrderType.LIMIT_MAKER)
        await asyncio.sleep(0.1)

        self.exchange._signer_client.create_order.assert_awaited_once()
        call_kwargs = self.exchange._signer_client.create_order.await_args.kwargs
        self.assertEqual(
            self.exchange._signer_client.ORDER_TIME_IN_FORCE_POST_ONLY, call_kwargs["time_in_force"])

    async def test_create_market_order_uses_signer_market_order(self, *_):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.get_mid_price = MagicMock(return_value=Decimal("10000"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda trading_pair, price: price)

        order_id, _ = await self.exchange._place_order(
            order_id="123",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.SELL,
            order_type=OrderType.MARKET,
            price=Decimal("NaN"),
        )

        self.assertEqual("123", order_id)
        self.exchange._signer_client.create_market_order.assert_awaited_once()
        call_kwargs = self.exchange._signer_client.create_market_order.await_args.kwargs
        self.assertEqual(self.market_id, call_kwargs["market_index"])
        self.assertTrue(call_kwargs["is_ask"])

    async def test_create_order_fails_and_raises_failure_event(self, *_):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._signer_client.create_order = AsyncMock(return_value=(None, {"code": 200}, "boom"))

        order_id = self.place_buy_order()
        await asyncio.sleep(0.1)

        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

    async def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, *_):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        order_id = self.place_buy_order(amount=Decimal("0.0001"), price=Decimal("0.0001"))
        await asyncio.sleep(0.1)

        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.exchange._signer_client.create_order.assert_not_awaited()
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event = self.order_failure_logger.event_log[0]
        self.assertEqual(order_id, failure_event.order_id)

    # ----------------------------------------------------------------------------------
    # Overridden tests — cancelation through the SDK signer
    # ----------------------------------------------------------------------------------
    async def test_cancel_order_successfully(self, *_):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        with aioresponses() as mock_api:
            url = self.configure_successful_cancelation_response(
                order=order, mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())
            self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
            await request_sent_event.wait()
            await asyncio.sleep(0.1)

            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(order=order, request_call=cancel_request)

        self.exchange._signer_client.cancel_order.assert_awaited_once_with(
            market_index=self.market_id, order_index=int(order.exchange_order_id))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        cancel_event = self.order_cancelled_logger.event_log[0]
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}."))

    async def test_cancel_order_raises_failure_event_when_request_fails(self, *_):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        with aioresponses() as mock_api:
            self.configure_erroneous_cancelation_response(
                order=order, mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())
            self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=order.client_order_id)
            await request_sent_event.wait()
            await asyncio.sleep(0.1)

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                for log in self.log_records))

    async def test_cancel_two_orders_with_cancel_all_and_one_fails(self, *_):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )
        order1 = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.exchange.start_tracking_order(
            order_id="12",
            exchange_order_id=self.exchange_order_id_prefix + "2",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )
        order2 = self.exchange.in_flight_orders["12"]

        with aioresponses() as mock_api:
            self.configure_one_successful_one_erroneous_cancel_all_response(
                successful_order=order1, erroneous_order=order2, mock_api=mock_api)
            cancellation_results = await self.exchange.cancel_all(10)

        self.assertEqual(2, len(cancellation_results))
        self.assertIn(CancellationResult(order1.client_order_id, True), cancellation_results)
        self.assertIn(CancellationResult(order2.client_order_id, False), cancellation_results)
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertEqual(order1.client_order_id, self.order_cancelled_logger.event_log[0].order_id)

    async def test_cancel_order_not_found_in_the_exchange(self, *_):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        with aioresponses() as mock_api:
            self.configure_order_not_found_error_cancelation_response(order=order, mock_api=mock_api)
            self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=order.client_order_id)
            await asyncio.sleep(0.1)

        self.exchange._signer_client.cancel_order.assert_not_awaited()
        self.assertFalse(order.is_done)

    # ----------------------------------------------------------------------------------
    # Overridden tests — Lighter-specific behavior
    # ----------------------------------------------------------------------------------
    async def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, *_):
        # On Lighter, fills for a lost order are not bundled into the order-status (or
        # lost-order-status) update — they arrive through the dedicated trade-history poll,
        # which iterates every fillable order (lost orders included).
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            await self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)

        request_sent_event = asyncio.Event()
        with aioresponses() as mock_api:
            trade_url = self.configure_full_fill_trade_response(
                order=order, mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())
            await self.exchange._update_trade_history()
            await request_sent_event.wait()
            await asyncio.sleep(0.1)

            trades_request = self._all_executed_requests(mock_api, trade_url)[0]
            self.validate_auth_credentials_present(trades_request)
            self.validate_trades_request(order=order, request_call=trades_request)

        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertTrue(order.is_failure)

    async def test_user_stream_logs_errors(self, *_):
        self.exchange._set_current_timestamp(1640780000)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = ["Invalid message", asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        with patch(f"{type(self.exchange).__module__}.{type(self.exchange).__qualname__}._sleep"):
            try:
                await self.exchange._user_stream_event_listener()
            except asyncio.CancelledError:
                pass
        await asyncio.sleep(0.1)

        self.assertTrue(self.is_logged("ERROR", "Unexpected error in Lighter user stream listener."))

    def test_extract_tx_code(self):
        self.assertEqual(200, self.exchange._extract_tx_code({"code": "200"}))
        self.assertEqual(500, self.exchange._extract_tx_code(SimpleNamespace(code=500)))
        self.assertIsNone(self.exchange._extract_tx_code({"message": "ok"}))
        self.assertIsNone(self.exchange._extract_tx_code({"code": "bad"}))
        self.assertIsNone(self.exchange._extract_tx_code(None))

    def test_is_tx_response_success(self):
        self.assertTrue(self.exchange._is_tx_response_success({"code": 200}))
        self.assertFalse(self.exchange._is_tx_response_success({"code": 500}))
        self.assertTrue(self.exchange._is_tx_response_success({"status": "ok"}))

    def test_account_lookup_params_defaults_to_l1_address(self):
        self.exchange._account_index = None
        self.exchange._l1_address = "0xabc"
        self.assertEqual(
            {"by": "l1_address", "value": "0xabc", "active_only": "true"},
            self.exchange._account_lookup_params())

    def test_account_lookup_params_uses_index_override(self):
        self.exchange._account_index = 12
        self.assertEqual(
            {"by": "index", "value": 12, "active_only": "true"},
            self.exchange._account_lookup_params())

    def test_effective_market_order_price_uses_mid_price(self):
        self.exchange.get_mid_price = MagicMock(return_value=Decimal("100"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda trading_pair, price: price)

        buy_price = self.exchange._effective_order_price(
            trading_pair=self.trading_pair, trade_type=TradeType.BUY,
            order_type=OrderType.MARKET, price=Decimal("NaN"))
        sell_price = self.exchange._effective_order_price(
            trading_pair=self.trading_pair, trade_type=TradeType.SELL,
            order_type=OrderType.MARKET, price=Decimal("NaN"))
        limit_price = self.exchange._effective_order_price(
            trading_pair=self.trading_pair, trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT, price=Decimal("99"))

        self.assertEqual(Decimal("105"), buy_price)
        self.assertEqual(Decimal("95"), sell_price)
        self.assertEqual(Decimal("99"), limit_price)

    def test_effective_market_order_price_applies_slippage_to_passed_price(self):
        # Regression for #8326: a take-profit MARKET SELL is submitted with a concrete price that
        # sits above the market. It must still be slipped down (used as avg_execution_price), or
        # the exchange rejects the order as unfillable.
        self.exchange.get_mid_price = MagicMock(return_value=Decimal("100"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda trading_pair, price: price)

        sell_price = self.exchange._effective_order_price(
            trading_pair=self.trading_pair, trade_type=TradeType.SELL,
            order_type=OrderType.MARKET, price=Decimal("120"))
        buy_price = self.exchange._effective_order_price(
            trading_pair=self.trading_pair, trade_type=TradeType.BUY,
            order_type=OrderType.MARKET, price=Decimal("80"))

        self.assertEqual(Decimal("114.00"), sell_price)  # 120 * (1 - 0.05), NOT 120
        self.assertEqual(Decimal("84.00"), buy_price)    # 80 * (1 + 0.05), NOT 80

    async def test_get_last_traded_price_lazily_loads_markets(self):
        # A non-trading price-feed connector starts with an empty market map (no trading-rules
        # polling). _get_last_traded_price must lazily load it instead of raising "(none loaded)".
        self.exchange._markets_by_trading_pair = {}
        self.exchange._markets_by_id = {}
        self.exchange._markets_by_exchange_symbol = {}

        async def _load_rules():
            self.exchange._markets_by_trading_pair = {self.trading_pair: self._market_info()}
        self.exchange._update_trading_rules = AsyncMock(side_effect=_load_rules)
        self.exchange._api_get = AsyncMock(return_value={
            "spot_order_book_details": [
                self._market_detail(self.exchange_symbol, self.market_id, last_trade_price="2501")
            ]
        })

        price = await self.exchange._get_last_traded_price(self.trading_pair)

        self.exchange._update_trading_rules.assert_awaited_once()
        self.assertEqual(2501.0, price)

    def test_create_signer_client_validates_required_fields(self):
        self.exchange._account_index = None
        with self.assertRaises(ValueError):
            self.exchange._create_signer_client()

    def test_match_order_by_client_or_exchange_id(self):
        tracked_order = SimpleNamespace(client_order_id="cid", exchange_order_id="999")
        self.assertEqual(
            {"client_order_id": "cid"},
            self.exchange._match_order(tracked_order, [{"client_order_id": "cid"}]))
        self.assertEqual(
            {"order_id": "999"},
            self.exchange._match_order(tracked_order, [{"order_id": "999"}]))
        self.assertIsNone(self.exchange._match_order(tracked_order, [{"order_id": "888"}]))

    def test_process_order_events_filters_invalid_payloads(self):
        tracked_order = SimpleNamespace(trading_pair=self.trading_pair)
        self.exchange._order_tracker = SimpleNamespace(
            all_updatable_orders={"cid": tracked_order},
            process_order_update=MagicMock(),
        )
        self.exchange._process_order_events(
            {
                "bad-group": "not-list",
                "market": [
                    {},
                    {"client_order_id": "unknown", "status": "open"},
                    {"client_order_id": "cid", "order_id": "999", "status": "open",
                     "transaction_time": "1000000"},
                ],
            }
        )
        self.exchange._order_tracker.process_order_update.assert_called_once()

    def test_process_trade_events_accepts_list_and_market_grouped_payloads(self):
        self.exchange._trade_update_from_trade = MagicMock(return_value="trade-update")
        self.exchange._order_tracker = SimpleNamespace(process_trade_update=MagicMock())

        self.exchange._process_trade_events([{"trade_id": 1}])
        self.exchange._process_trade_events({"2048": [{"trade_id": 2}]})

        self.assertEqual(2, self.exchange._order_tracker.process_trade_update.call_count)

    def test_process_balance_events_replaces_balances(self):
        self.exchange._account_balances = {"OLD": Decimal("1")}
        self.exchange._account_available_balances = {"OLD": Decimal("1")}

        self.exchange._process_balance_events(
            {
                "1": {"symbol": "ETH", "balance": "2", "locked_balance": "0.5"},
                "3": {"symbol": "USDC", "balance": "100", "locked_balance": "10"},
            }
        )

        self.assertEqual({"ETH", "USDC"}, set(self.exchange._account_balances.keys()))
        self.assertEqual(Decimal("2"), self.exchange._account_balances["ETH"])
        self.assertEqual(Decimal("1.5"), self.exchange._account_available_balances["ETH"])
        self.assertEqual(Decimal("90"), self.exchange._account_available_balances["USDC"])

    async def test_find_order_checks_active_then_inactive(self):
        tracked_order = SimpleNamespace(
            client_order_id="cid", exchange_order_id=None, trading_pair=self.trading_pair)
        self.exchange._api_get = AsyncMock(
            side_effect=[
                {"orders": []},
                {"orders": [{"client_order_id": "cid", "order_id": "999"}]},
            ]
        )
        order = await self.exchange._find_order(tracked_order, include_inactive=True)
        self.assertEqual("999", order["order_id"])
        self.assertEqual(2, self.exchange._api_get.await_count)

    async def test_ensure_account_ready_resolves_account_and_rebuilds_auth(self):
        self.exchange._account_index = None
        self.exchange._signer_client = None
        # Force the trading-rules bootstrap branch as well.
        self.exchange._markets_by_exchange_symbol = {}
        self.exchange._update_trading_rules = AsyncMock()
        self.exchange._api_get = AsyncMock(
            return_value={"sub_accounts": [{"index": self.account_index, "l1_address": self.l1_address}]})
        self.exchange._create_signer_client = MagicMock(return_value="signer")
        self.exchange._create_web_assistants_factory = MagicMock(return_value="factory")
        self.exchange._create_user_stream_tracker = MagicMock(return_value="tracker")

        await self.exchange._ensure_account_ready()

        self.exchange._update_trading_rules.assert_awaited_once()
        self.assertEqual(self.account_index, self.exchange._account_index)
        self.assertEqual("signer", self.exchange._signer_client)
        self.assertEqual("factory", self.exchange._web_assistants_factory)
        self.assertEqual("tracker", self.exchange._user_stream_tracker)

    async def test_ensure_account_ready_noop_when_not_trading_required(self):
        self.exchange._trading_required = False
        self.exchange._api_get = AsyncMock()
        await self.exchange._ensure_account_ready()
        self.exchange._api_get.assert_not_awaited()
