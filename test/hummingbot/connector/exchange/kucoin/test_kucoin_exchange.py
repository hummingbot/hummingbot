import asyncio
import json
import re
import unittest
from collections.abc import Awaitable
from decimal import Decimal
from typing import Dict, NamedTuple, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS, kucoin_web_utils as web_utils
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_exchange import KucoinExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus


class TestKucoinExchange(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair = cls.trading_pair
        cls.api_key = "someKey"
        cls.api_passphrase = "somePassPhrase"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None

        self.exchange = KucoinExchange(
            self.api_key, self.api_passphrase, self.api_secret_key, trading_pairs=[self.trading_pair]
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._time_synchronizer.logger().setLevel(1)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        KucoinAPIOrderBookDataSource._trading_pair_symbol_map = {
            CONSTANTS.DEFAULT_DOMAIN: bidict(
                {self.trading_pair: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        KucoinAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_exchange_rules_mock(self) -> Dict:
        exchange_rules = {
            "code": "200000",
            "data": [
                {
                    "symbol": self.trading_pair,
                    "name": self.trading_pair,
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "feeCurrency": self.quote_asset,
                    "market": "ALTS",
                    "baseMinSize": "1",
                    "quoteMinSize": "0.1",
                    "baseMaxSize": "10000000000",
                    "quoteMaxSize": "99999999",
                    "baseIncrement": "0.1",
                    "quoteIncrement": "0.01",
                    "priceIncrement": "0.01",
                    "priceLimitRate": "0.1",
                    "isMarginEnabled": False,
                    "enableTrading": True,
                },
            ],
        }
        return exchange_rules

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def _validate_auth_credentials_present(self, request_call_tuple: NamedTuple):
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("KC-API-PARTNER", request_headers)
        self.assertEqual(CONSTANTS.HB_PARTNER_ID, request_headers["KC-API-PARTNER"])
        self.assertIn("KC-API-PARTNER-SIGN", request_headers)
        self.assertIn("KC-API-KEY", request_headers)
        self.assertEqual(self.api_key, request_headers["KC-API-KEY"])
        self.assertIn("KC-API-TIMESTAMP", request_headers)
        self.assertIn("KC-API-KEY-VERSION", request_headers)
        self.assertEqual("2", request_headers["KC-API-KEY-VERSION"])
        self.assertIn("KC-API-SIGN", request_headers)
        self.assertIn("KC-API-PASSPHRASE", request_headers)

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.MARKET, supported_types)
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.LIMIT_MAKER, supported_types)

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        resp = {
            "code": "200000",
            "msg": "success",
            "data": 1640001112223
        }
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, ret)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        mock_api.get(url, status=500)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)

        mock_api.get(url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = web_utils.rest_url(CONSTANTS.SYMBOLS_PATH_URL)
        resp = self.get_exchange_rules_mock()
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange._trading_rules)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = web_utils.rest_url(CONSTANTS.SYMBOLS_PATH_URL)
        resp = {
            "code": "200000",
            "data": [
                {
                    "symbol": self.trading_pair,
                    "name": self.trading_pair,
                    "enableTrading": True,
                },
            ],
        }
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange._trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {resp['data'][0]}. Skipping.")
        )

    @aioresponses()
    def test_get_fee_returns_fee_from_exchange_if_available_and_default_if_not(self, mocked_api):
        url = web_utils.rest_url(CONSTANTS.FEE_PATH_URL)
        regex_url = re.compile(f"^{url}")
        resp = {"data": [
            {"symbol": self.trading_pair,
             "makerFeeRate": "0.002",
             "takerFeeRate": "0.002"}]}
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_trading_fees())

        fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.002"), fee.percent)

        fee = self.exchange.get_fee(
            base_currency="SOME",
            quote_currency="OTHER",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.001"), fee.percent)  # default fee

    @patch("hummingbot.connector.utils.get_tracking_nonce_low_res")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 9

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True, trading_pair=self.trading_pair
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False, trading_pair=self.trading_pair
        )

        self.assertEqual(result, expected_client_order_id)

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="EOID2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.CANCELED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="EOID4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)

    @aioresponses()
    def test_create_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        creation_response = {
            "data": {
                "orderId": "5bd6e9286d99522a52e458de"
            }}

        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(TradeType.BUY.name.lower(), request_data["side"])
        self.assertEqual("limit", request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["size"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual("OID1", request_data["clientOid"])

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual(creation_response["data"]["orderId"], create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT BUY order OID1 for {Decimal('100.000000')} {self.trading_pair}."
            )
        )

    @aioresponses()
    def test_create_limit_maker_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        creation_response = {
            "data": {
                "orderId": "5bd6e9286d99522a52e458de"
            }}

        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT_MAKER,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(TradeType.BUY.name.lower(), request_data["side"])
        self.assertEqual("limit", request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["size"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual("OID1", request_data["clientOid"])
        self.assertTrue(request_data["postOnly"])

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT_MAKER, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual(creation_response["data"]["orderId"], create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT_MAKER BUY order OID1 for {Decimal('100.000000')} {self.trading_pair}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.exchange.kucoin.kucoin_exchange.KucoinExchange.get_price")
    def test_create_market_order_successfully(self, mock_api, get_price_mock):
        get_price_mock.return_value = Decimal(1000)
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        creation_response = {
            "data": {
                "orderId": "5bd6e9286d99522a52e458de"
            }}

        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.SELL,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.MARKET))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(TradeType.SELL.name.lower(), request_data["side"])
        self.assertEqual("market", request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["size"]))
        self.assertEqual("OID1", request_data["clientOid"])
        self.assertNotIn("price", request_data)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.MARKET, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertIsNone(create_event.price)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual(creation_response["data"]["orderId"], create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created MARKET SELL order OID1 for {Decimal('100.000000')} {self.trading_pair}."
            )
        )

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='OID1', exchange_order_id=None)"
            )
        )

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("0.0001"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("0.0000001")))
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID2",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "WARNING",
                "Buy order amount 0 is lower than the minimum order size 0.01. The order will not be created."
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                "client_order_id='OID1', exchange_order_id=None)"
            )
        )

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.rest_url(f"{CONSTANTS.ORDERS_PATH_URL}/{order.exchange_order_id}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "data": {"cancelledOrderIds": [order.exchange_order_id]}
        }

        mock_api.delete(regex_url,
                        body=json.dumps(response),
                        callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(cancel_request[1][0])
        request_params = cancel_request[1][0].kwargs["params"]
        self.assertIsNone(request_params)

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully canceled order {order.client_order_id}."
            )
        )

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.rest_url(f"{CONSTANTS.ORDERS_PATH_URL}/{order.exchange_order_id}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.delete(regex_url,
                        status=400,
                        callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(cancel_request[1][0])

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Failed to cancel order {order.client_order_id}"
            )
        )

    def test_cancel_order_without_exchange_order_id_marks_order_as_fail_after_retries(self):
        update_event = MagicMock()
        update_event.wait.side_effect = asyncio.TimeoutError

        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]
        order.exchange_order_id_update_event = update_event

        self.async_run_with_timeout(self.exchange._execute_cancel(
            trading_pair=order.trading_pair,
            order_id=order.client_order_id,
        ))

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "WARNING",
                f"Failed to cancel the order {order.client_order_id} because it does not have an exchange order id yet"
            )
        )

        # After the fourth time not finding the exchange order id the order should be marked as failed
        for i in range(ClientOrderTracker.ORDER_NOT_FOUND_COUNT_LIMIT + 1):
            self.async_run_with_timeout(self.exchange._execute_cancel(
                trading_pair=order.trading_pair,
                order_id=order.client_order_id,
            ))

        self.assertTrue(order.is_failure)

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders["OID1"]

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="5",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID2", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["OID2"]

        url = web_utils.rest_url(f"{CONSTANTS.ORDERS_PATH_URL}/{order1.exchange_order_id}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "data": {"cancelledOrderIds": [order1.exchange_order_id]}
        }

        mock_api.delete(regex_url, body=json.dumps(response))

        url = web_utils.rest_url(f"{CONSTANTS.ORDERS_PATH_URL}/{order2.exchange_order_id}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.delete(regex_url, status=400)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        self.assertEqual(2, len(cancellation_results))
        self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
        self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order1.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully canceled order {order1.client_order_id}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        seconds_counter_mock.side_effect = [0, 0, 0]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "code": "200000",
            "msg": "success",
            "data": 1640000003000
        }

        mock_api.get(regex_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response["data"] * 1e-3, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "code": "-1",
            "msg": "error"
        }

        mock_api.get(regex_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self._is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.ACCOUNTS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "code": "200000",
            "data": [
                {
                    "id": "5bd6e9286d99522a52e458de",
                    "currency": "BTC",
                    "type": "trade",
                    "balance": "15.0",
                    "available": "10.0",
                    "holds": "0"
                },
                {
                    "id": "5bd6e9216d99522a52e458d6",
                    "currency": "LTC",
                    "type": "trade",
                    "balance": "2000",
                    "available": "2000",
                    "holds": "0"
                }]
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("2000"), available_balances["LTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])
        self.assertEqual(Decimal("2000"), total_balances["LTC"])

        response = {
            "code": "200000",
            "data": [
                {
                    "id": "5bd6e9286d99522a52e458de",
                    "currency": "BTC",
                    "type": "trade",
                    "balance": "15.0",
                    "available": "10.0",
                    "holds": "0"
                }]
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn("LTC", available_balances)
        self.assertNotIn("LTC", total_balances)
        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        url = web_utils.rest_url(f"{CONSTANTS.ORDERS_PATH_URL}/{order.exchange_order_id}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "code": "200000",
            "data": {
                "id": order.exchange_order_id,
                "symbol": self.trading_pair,
                "opType": "DEAL",
                "type": "limit",
                "side": order.trade_type.name.lower(),
                "price": "10000",
                "size": "1",
                "funds": "0",
                "dealFunds": "0.166",
                "dealSize": "1",
                "fee": "0",
                "feeCurrency": self.quote_asset,
                "stp": "",
                "stop": "",
                "stopTriggered": False,
                "stopPrice": "0",
                "timeInForce": "GTC",
                "postOnly": False,
                "hidden": False,
                "iceberg": False,
                "visibleSize": "0",
                "cancelAfter": 0,
                "channel": "IOS",
                "clientOid": "",
                "remark": "",
                "tags": "",
                "isActive": False,
                "cancelExist": False,
                "createdAt": 1547026471000,
                "tradeType": "TRADE"
            }
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        # Simulate the order has been filled with a TradeUpdate
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.async_run_with_timeout(order.wait_until_completely_filled())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertIsNone(request_params)
        self._validate_auth_credentials_present(order_request[1][0])

        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(Decimal(0), buy_event.base_asset_amount)
        self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    def test_update_order_status_when_cancelled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.rest_url(f"{CONSTANTS.ORDERS_PATH_URL}/{order.exchange_order_id}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "code": "200000",
            "data": {
                "id": order.exchange_order_id,
                "symbol": self.trading_pair,
                "opType": "CANCEL",
                "type": "limit",
                "side": order.trade_type.name.lower(),
                "price": "10000",
                "size": "1",
                "funds": "0",
                "dealFunds": "0.166",
                "dealSize": "1",
                "fee": "0",
                "feeCurrency": self.quote_asset,
                "stp": "",
                "stop": "",
                "stopTriggered": False,
                "stopPrice": "0",
                "timeInForce": "GTC",
                "postOnly": False,
                "hidden": False,
                "iceberg": False,
                "visibleSize": "0",
                "cancelAfter": 0,
                "channel": "IOS",
                "clientOid": "",
                "remark": "",
                "tags": "",
                "isActive": False,
                "cancelExist": True,
                "createdAt": 1547026471000,
                "tradeType": "TRADE"
            }
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertIsNone(request_params)
        self._validate_auth_credentials_present(order_request[1][0])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        url = web_utils.rest_url(f"{CONSTANTS.ORDERS_PATH_URL}/{order.exchange_order_id}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "code": "200000",
            "data": {
                "id": order.exchange_order_id,
                "symbol": self.trading_pair,
                "opType": "DEAL",
                "type": "limit",
                "side": order.trade_type.name.lower(),
                "price": "10000",
                "size": "1",
                "funds": "0",
                "dealFunds": "0.166",
                "dealSize": "1",
                "fee": "0",
                "feeCurrency": self.quote_asset,
                "stp": "",
                "stop": "",
                "stopTriggered": False,
                "stopPrice": "0",
                "timeInForce": "GTC",
                "postOnly": False,
                "hidden": False,
                "iceberg": False,
                "visibleSize": "0",
                "cancelAfter": 0,
                "channel": "IOS",
                "clientOid": "",
                "remark": "",
                "tags": "",
                "isActive": True,
                "cancelExist": False,
                "createdAt": 1547026471000,
                "tradeType": "TRADE"
            }
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertIsNone(request_params)
        self._validate_auth_credentials_present(order_request[1][0])

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

    @aioresponses()
    def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        url = web_utils.rest_url(f"{CONSTANTS.ORDERS_PATH_URL}/{order.exchange_order_id}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=404)

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertIsNone(request_params)
        self._validate_auth_credentials_present(order_request[1][0])

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    def test_update_order_status_marks_order_with_no_exchange_id_as_not_found(self):
        update_event = MagicMock()
        update_event.wait.side_effect = asyncio.TimeoutError

        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]
        order.exchange_order_id_update_event = update_event

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    def test_user_stream_update_for_new_order_does_not_update_status(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "type": "message",
            "topic": "/spotMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {
                "symbol": order.trading_pair,
                "orderType": "limit",
                "side": order.trade_type.name.lower(),
                "orderId": order.exchange_order_id,
                "type": "open",
                "orderTime": 1593487481683297666,
                "size": "1",
                "filledSize": "0",
                "price": "10000.0",
                "clientOid": order.client_order_id,
                "remainSize": "1",
                "status": "open",
                "ts": 1593487481683297666
            }
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertEqual(order.price, event.price)
        self.assertEqual(order.client_order_id, event.order_id)
        self.assertEqual(order.exchange_order_id, event.exchange_order_id)
        self.assertTrue(order.is_open)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created {order.order_type.name.upper()} {order.trade_type.name.upper()} order "
                f"{order.client_order_id} for {order.amount} {order.trading_pair}."
            )
        )

    def test_user_stream_update_for_cancelled_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "type": "message",
            "topic": "/spotMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {
                "symbol": order.trading_pair,
                "orderType": "limit",
                "side": order.trade_type.name.lower(),
                "orderId": order.exchange_order_id,
                "type": "canceled",
                "orderTime": 1593487481683297666,
                "size": "1.0",
                "filledSize": "0",
                "price": "10000.0",
                "clientOid": order.client_order_id,
                "remainSize": "0",
                "status": "done",
                "ts": 1593487481893140844
            }
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    def test_user_stream_update_for_order_partial_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "type": "message",
            "topic": "/spotMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {
                "symbol": order.trading_pair,
                "orderType": "limit",
                "side": order.trade_type.name.lower(),
                "orderId": order.exchange_order_id,
                "liquidity": "taker",
                "type": "match",
                "orderTime": 1593487482038606180,
                "size": "1",
                "filledSize": "0.1",
                "price": "10000",
                "matchPrice": "10010.5",
                "matchSize": "0.1",
                "tradeId": "5efab07a4ee4c7000a82d6d9",
                "clientOid": order.client_order_id,
                "remainSize": "0.9",
                "status": "match",
                "ts": 1593487482038606180
            }
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(event_message["data"]["matchPrice"]), fill_event.price)
        self.assertEqual(Decimal(event_message["data"]["matchSize"]), fill_event.amount)
        expected_fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=order.order_type,
            order_side=order.trade_type,
            amount=Decimal(event_message["data"]["matchSize"]),
            price=Decimal(event_message["data"]["matchPrice"]),
            is_maker=False,
        )
        self.assertEqual(expected_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        self.assertTrue(
            self._is_logged("INFO", f"The {order.trade_type.name} order {order.client_order_id} amounting to "
                                    f"0.1/{order.amount} {order.base_asset} has been filled.")
        )

    def test_user_stream_update_for_order_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        match_event = {
            "type": "message",
            "topic": "/spotMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {
                "symbol": order.trading_pair,
                "orderType": "limit",
                "side": order.trade_type.name.lower(),
                "orderId": order.exchange_order_id,
                "liquidity": "taker",
                "type": "match",
                "orderTime": 1593487482038606180,
                "size": "1",
                "filledSize": "1",
                "price": "10000",
                "matchPrice": "10010.5",
                "matchSize": "1",
                "tradeId": "5efab07a4ee4c7000a82d6d9",
                "clientOid": order.client_order_id,
                "remainSize": "0",
                "status": "match",
                "ts": 1593487482038606180
            }
        }

        filled_event = {
            "type": "message",
            "topic": "/spotMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {

                "symbol": order.trading_pair,
                "orderType": "limit",
                "side": order.trade_type.name.lower(),
                "orderId": order.exchange_order_id,
                "type": "filled",
                "orderTime": 1593487482038606180,
                "size": "1",
                "filledSize": "1",
                "price": "10000",
                "clientOid": order.client_order_id,
                "remainSize": "0",
                "status": "done",
                "ts": 1593487482038606180
            }
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [match_event, filled_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        match_price = Decimal(match_event["data"]["matchPrice"])
        match_size = Decimal(match_event["data"]["matchSize"])
        self.assertEqual(match_price, fill_event.price)
        self.assertEqual(match_size, fill_event.amount)
        expected_fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=order.order_type,
            order_side=order.trade_type,
            amount=match_size,
            price=match_price,
            is_maker=False,
        )
        self.assertEqual(expected_fee, fill_event.trade_fee)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * match_price, buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_user_stream_balance_update(self):
        self.exchange._set_current_timestamp(1640780000)

        event_message = {
            "type": "message",
            "topic": "/account/balance",
            "subject": "account.balance",
            "channelType": "private",
            "data": {
                "total": "10500",
                "available": "10000",
                "availableChange": "0",
                "currency": self.base_asset,
                "hold": "0",
                "holdChange": "0",
                "relationEvent": "trade.setted",
                "relationEventId": "5c21e80303aa677bd09d7dff",
                "relationContext": {
                    "symbol": self.trading_pair,
                    "tradeId": "5e6a5dca9e16882a7d83b7a4",
                    "orderId": "5ea10479415e2f0009949d54"
                },
                "time": "1545743136994"
            }
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10000"), self.exchange.available_balances["COINALPHA"])
        self.assertEqual(Decimal("10500"), self.exchange.get_balance("COINALPHA"))

    def test_user_stream_raises_cancel_exception(self):
        self.exchange._set_current_timestamp(1640780000)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.exchange._user_stream_tracker._user_stream = mock_queue

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout,
            self.exchange._user_stream_event_listener())

    @patch("hummingbot.connector.exchange.kucoin.kucoin_exchange.KucoinExchange._sleep")
    def test_user_stream_logs_errors(self, sleep_mock):
        self.exchange._set_current_timestamp(1640780000)

        incomplete_event = {
            "type": "message",
            "topic": "/spotMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error in user stream listener loop."
            )
        )

    def test_initial_status_dict(self):
        KucoinAPIOrderBookDataSource._trading_pair_symbol_map = {}

        status_dict = self.exchange.status_dict

        expected_initial_dict = {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": False,
            "trading_rule_initialized": False,
            "user_stream_initialized": False,
        }

        self.assertEqual(expected_initial_dict, status_dict)
        self.assertFalse(self.exchange.ready)
