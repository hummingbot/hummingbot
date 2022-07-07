import asyncio
import contextlib
import functools
import json
import re
import time
from decimal import Decimal
from typing import Awaitable, Callable, NamedTuple, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, PropertyMock, patch

from aioresponses import aioresponses
from async_timeout import timeout
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.coinflex import coinflex_constants as CONSTANTS, coinflex_web_utils
from hummingbot.connector.exchange.coinflex.coinflex_api_order_book_data_source import CoinflexAPIOrderBookDataSource
from hummingbot.connector.exchange.coinflex.coinflex_exchange import CoinflexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.time_iterator import TimeIterator


class CoinflexExchangeTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = CoinflexExchange(
            client_config_map=self.client_config_map,
            coinflex_api_key="testAPIKey",
            coinflex_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self._initialize_event_loggers()

        CoinflexAPIOrderBookDataSource._trading_pair_symbol_map = {
            "coinflex": bidict(
                {f"{self.base_asset}-{self.quote_asset}": self.trading_pair})
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        CoinflexAPIOrderBookDataSource._trading_pair_symbol_map = {}
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

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def _validate_auth_credentials_for_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="params"
        )

    def _validate_auth_credentials_for_post_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="data"
        )

    def _validate_auth_credentials_taking_parameters_from_argument(self, request_call_tuple: NamedTuple,
                                                                   params_key: str):
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("Timestamp", request_headers)
        self.assertIn("Signature", request_headers)
        self.assertIn("Nonce", request_headers)
        self.assertIn("AccessKey", request_headers)
        self.assertEqual("testAPIKey", request_headers["AccessKey"])

    def _get_regex_url(self,
                       endpoint,
                       return_url=False,
                       endpoint_api_version=None,
                       public=False):
        prv_or_pub = coinflex_web_utils.public_rest_url if public else coinflex_web_utils.private_rest_url
        url = prv_or_pub(endpoint, domain=self.domain, endpoint_api_version=endpoint_api_version)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        if return_url:
            return url, regex_url
        return regex_url

    def _get_mock_order_data(self,
                             order,
                             status="OrderMatched",
                             price="10000.0",
                             amount="1.0",
                             is_matched=True):
        order_data = {
            "status": status,
            "orderId": int(order.exchange_order_id),
            "clientOrderId": order.client_order_id,
            "marketCode": self.exchange_trading_pair,
            "side": "BUY",
            "orderType": "LIMIT",
            "price": price,
            "quantity": amount,
            "remainQuantity": "0.0",
            "timeInForce": "GTC",
            "orderOpenedTimestamp": "1499827319559",
            "orderClosedTimestamp": "1499827319559",
        }
        if is_matched:
            order_data["matchIds"] = [
                {
                    "448528458527567630": {
                        "matchQuantity": "1.0",
                        "matchPrice": "10000.0",
                        "timestamp": "1499827319559",
                        "orderMatchType": "TAKER",
                    },
                },
            ]
            order_data["fees"] = {
                f"{self.quote_asset}": "-0.00440786"
            }

        return {
            "data": [order_data]
        }

    def _get_mock_user_stream_order_data(self,
                                         order=None,
                                         trade_id=-1,
                                         client_order_id=None,
                                         status="OPEN",
                                         side="BUY",
                                         price="1000.00000000",
                                         amount="1.00000000",
                                         is_matched=False,
                                         fill_base_amount="0.00000000",
                                         fill_price="0.00000000",
                                         fee_asset=None,
                                         fee_paid="0"):

        order_data = {
            "clientOrderId": client_order_id or order.client_order_id,
            "orderId": int(order.exchange_order_id if order and order.exchange_order_id else 1),
            "timestamp": 1499405658658,
            "status": status,
            "side": side,
            "price": price,
            "quantity": amount,
        }
        if is_matched:
            order_data["matchId"] = trade_id
            order_data["matchQuantity"] = fill_base_amount
            order_data["matchPrice"] = fill_price
            order_data["fees"] = fee_paid
            order_data["feeInstrumentId"] = fee_asset

        return {
            "table": "order",
            "data": [order_data]
        }

    def _get_mock_trading_rule_data(self,
                                    invalid=False):

        trading_rule = {
            "marketId": "2001000000000",
            "marketCode": self.exchange_trading_pair,
            "name": f"{self.base_asset}/{self.quote_asset}",
            "referencePair": f"{self.base_asset}/{self.quote_asset}",
            "base": f"{self.base_asset}",
            "counter": f"{self.quote_asset}",
            "type": "SPOT",
            "tickSize": "1",
            "qtyIncrement": "0.001",
            "marginCurrency": f"{self.quote_asset}",
            "contractValCurrency": f"{self.base_asset}",
            "upperPriceBound": "41580",
            "lowerPriceBound": "38380",
            "marketPrice": "39980",
            "markPrice": None,
            "listingDate": 1593316800000,
            "endDate": 0,
            "marketPriceLastUpdated": 1645265706110,
            "markPriceLastUpdated": 0
        }

        if invalid:
            trading_rule = {"type": "SPOT"}

        return {
            "event": "markets",
            "timestamp": 1565246363776,
            "data": [trading_rule]
        }

    def _get_mock_balance_data(self,
                               asset="BTC",
                               free="10.0",
                               total="15.0",
                               with_second=False):
        balances = [
            {
                "instrumentId": asset,
                "available": free,
                "total": total
            }
        ]

        if with_second:
            balances.append({
                "instrumentId": "LTC",
                "available": "2000",
                "total": "2000"
            })
        return {
            "table": "balance",
            "data": balances
        }

    def _get_snapshot_response(self, update_id=1027024):
        resp = {
            "event": "depthL1000",
            "timestamp": update_id,
            "data": [{
                "bids": [
                    [
                        "4.00000000",
                        "431.00000000"
                    ]
                ],
                "asks": [
                    [
                        "4.00000200",
                        "12.00000000"
                    ]
                ],
                "marketCode": self.exchange_trading_pair,
                "timestamp": update_id,
            }]
        }
        return resp

    def _get_mock_login_message(self):
        resp = {
            "tag": "1234567890",
            "event": "login",
            "success": True,
            "timestamp": "1234567890"
        }
        return resp

    def _get_mock_ticker_data(self):
        return [{
            "last": "100.0",
            "open24h": "38719",
            "high24h": "38840",
            "low24h": "36377",
            "volume24h": "3622970.9407847790",
            "currencyVolume24h": "96.986",
            "openInterest": "0",
            "marketCode": "COINALPHA-HBOT",
            "timestamp": "1645546950025",
            "lastQty": "0.086",
            "markPrice": "37645",
            "lastMarkPrice": "37628",
        }]

    async def _wait_til_ready(self, clock: Clock):
        async with timeout(20):
            while True:
                now = time.time()
                next_iteration = now // 1.0 + 1
                if self.exchange.ready:
                    break
                else:
                    await clock.run_til(next_iteration)
                await asyncio.sleep(1.0)

    async def _wait_til_stopped(self, clock: Clock):
        async with timeout(20):
            while True:
                now = time.time()
                next_iteration = now // 1.0 + 1
                if not self.exchange.ready:
                    break
                else:
                    await clock.run_til(next_iteration)
                await asyncio.sleep(1.0)

    def _start_exchange_iterator(self):
        clock = Clock(
            ClockMode.BACKTEST,
            start_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL,
            end_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2,
        )
        clock.add_iterator(self.exchange)
        clock = self.stack.enter_context(clock)
        TimeIterator.start(self.exchange, clock)
        return clock

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.LIMIT_MAKER, supported_types)

    @aioresponses()
    def test_check_network_successful(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.PING_PATH_URL, public=True)

        mock_api.get(regex_url, body=json.dumps({"success": "true"}))

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, status)

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_check_network_unsuccessful(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        regex_url = self._get_regex_url(CONSTANTS.PING_PATH_URL, public=True)

        mock_api.get(regex_url, status=404)

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.PING_PATH_URL, public=True)

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    def test_connector_not_ready(self):
        self.assertEqual(False, self.exchange.ready)
        self.assertEqual(False, self.exchange.status_dict['order_books_initialized'])

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_api_user_stream_data_source.CoinflexAPIUserStreamDataSource.listen_for_user_stream")
    @patch("hummingbot.connector.exchange.coinflex.coinflex_api_user_stream_data_source.CoinflexAPIUserStreamDataSource.last_recv_time", new_callable=PropertyMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_connector_start_iterator(self, mock_api, ws_connect_mock, last_recv_mock, user_stream_mock):
        mock_repetitions = 20
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # User stream
        user_stream_mock.return_value = True
        last_recv_mock.return_value = int(1)

        # Network check events
        check_url = self._get_regex_url(CONSTANTS.PING_PATH_URL, public=True)
        for x in range(mock_repetitions):
            mock_api.get(check_url, body=json.dumps({"success": "true"}))

        # Balance check events
        bal_url = self._get_regex_url(CONSTANTS.ACCOUNTS_PATH_URL)
        for x in range(mock_repetitions):
            mock_api.get(bal_url, body=json.dumps(self._get_mock_balance_data(with_second=True)))

        # Snapshots
        snap_url = self._get_regex_url(CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair, 1000))
        for x in range(mock_repetitions):
            mock_api.get(snap_url, body=json.dumps(self._get_snapshot_response()))

        # Pub WS
        for x in range(mock_repetitions):
            self.mocking_assistant.add_websocket_aiohttp_message(
                websocket_mock=ws_connect_mock.return_value,
                message=json.dumps(self._get_mock_login_message()))

        # Mock Trading rules
        rule_url = self._get_regex_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        for x in range(mock_repetitions):
            mock_api.get(rule_url, body=json.dumps(self._get_mock_trading_rule_data()))

        # Mock Ticker
        ticker_url = self._get_regex_url(CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        mock_api.get(ticker_url, body=json.dumps(self._get_mock_ticker_data()))

        # Start connector
        clock = self._start_exchange_iterator()
        self.async_run_with_timeout(self._wait_til_ready(clock), timeout=10)
        self.assertTrue(self.exchange.ready)
        self.async_run_with_timeout(asyncio.sleep(1), timeout=10)
        TimeIterator.stop(self.exchange, clock)
        self.async_run_with_timeout(self._wait_til_stopped(clock), timeout=10)
        self.assertFalse(self.exchange.ready)

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_exchange.CoinflexExchange.current_timestamp")
    def test_status_polling_loop(self, mock_api, current_ts_mock):
        # Order Balance Updates
        balances_called_event = asyncio.Event()
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNTS_PATH_URL)
        response = self._get_mock_balance_data(with_second=True)
        mock_api.get(regex_url, body=json.dumps(response), callback=lambda *args, **kwargs: balances_called_event.set())

        current_ts_mock.return_value = time.time()

        self.ev_loop.create_task(self.exchange._status_polling_loop())
        self.exchange._poll_notifier.set()
        self.async_run_with_timeout(balances_called_event.wait())

        self.assertEqual(self.exchange.available_balances["BTC"], Decimal("10.0"))

    @patch("hummingbot.connector.exchange.coinflex.coinflex_exchange.CoinflexExchange._update_balances")
    def test_status_polling_loop_raises_on_asyncio_cancelled_error(self, update_balances_mock: AsyncMock):
        update_balances_mock.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            exception=asyncio.CancelledError
        )

        self.exchange._poll_notifier.set()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._status_polling_loop())

    @patch("hummingbot.connector.exchange.coinflex.coinflex_exchange.CoinflexExchange._api_request")
    @patch("hummingbot.connector.exchange.coinflex.coinflex_exchange.CoinflexExchange._update_order_status")
    def test_status_polling_loop_logs_other_exceptions(self, order_status_mock: AsyncMock, api_request_mock: AsyncMock):
        api_request_mock.side_effect = lambda *args, **kwargs: self._create_exception_and_unlock_test_with_event(
            exception=Exception("Dummy test error")
        )
        order_status_mock.side_effect = lambda *args, **kwargs: self._create_exception_and_unlock_test_with_event(
            exception=Exception("Dummy test error")
        )

        self.exchange._poll_notifier.set()

        self.test_task = self.ev_loop.create_task(self.exchange._status_polling_loop())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("ERROR", "Error getting account balances from server"))
        self.assertTrue(
            self._is_logged("NETWORK", "Unexpected error while fetching account updates.")
        )

    @aioresponses()
    def test_create_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_CREATE_PATH_URL, return_url=True)

        creation_response = {
            "data": [{
                "marketCode": self.exchange_trading_pair,
                "orderId": 28,
                "orderListId": -1,
                "clientOrderId": "OID1",
                "timestamp": 1507725176595
            }]
        }

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
        self._validate_auth_credentials_for_post_request(order_request[1][0])
        request_data = order_request[1][0].kwargs["data"]
        order_data = json.loads(request_data)["orders"][0]
        self.assertEqual(self.exchange_trading_pair, order_data["marketCode"])
        self.assertEqual(CONSTANTS.SIDE_BUY, order_data["side"])
        self.assertEqual(CoinflexExchange.coinflex_order_type(OrderType.LIMIT), order_data["orderType"])
        self.assertEqual(Decimal("100"), Decimal(order_data["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(order_data["price"]))
        self.assertEqual("OID1", order_data["clientOrderId"])

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual("28", create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT BUY order OID1 for {Decimal('100.000000')} {self.trading_pair}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_create_order_fails_and_raises_failure_event(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_CREATE_PATH_URL, return_url=True)

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
        self._validate_auth_credentials_for_post_request(order_request[1][0])

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                "client_order_id='OID1', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_CREATE_PATH_URL, return_url=True)

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
        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
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
                "client_order_id='OID1', exchange_order_id=None, misc_updates=None)"
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

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_CANCEL_PATH_URL, return_url=True)

        response = {
            "data": [{
                "marketCode": self.exchange_trading_pair,
                "clientOrderId": "OID1",
                "orderId": 4,
                "orderListId": -1,
                "price": str(order.price),
                "origQty": str(order.amount),
                "executedQty": str(Decimal("0")),
                "cummulativeQuoteQty": str(Decimal("0")),
                "status": "CANCELED",
                "timeInForce": "GTC",
                "orderType": "LIMIT",
                "side": "BUY"
            }]
        }

        mock_api.delete(regex_url,
                        body=json.dumps(response),
                        callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])
        request_params = json.loads(cancel_request[1][0].kwargs["data"])["orders"][0]
        self.assertEqual(self.exchange_trading_pair, request_params["marketCode"])
        self.assertEqual(order.client_order_id, request_params["clientOrderId"])

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
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
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

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_CANCEL_PATH_URL, return_url=True)

        for i in range(CONSTANTS.API_MAX_RETRIES):
            mock_api.delete(regex_url,
                            status=400,
                            callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"There was an error when requesting cancelation of order {order.client_order_id}"
            )
        )
        expected_error = {"errors": None, "status": None}

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unhandled error canceling order: {order.client_order_id}. Error: {expected_error}"
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_cancel_order_succeeds_after_max_failures(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
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

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_CANCEL_PATH_URL, return_url=True)

        response = {
            "data": [{
                "clientOrderId": "OID1",
                "success": "false",
                "message": "Open order not found with clientOrderId or orderId",
            }]
        }

        for i in range(CONSTANTS.API_MAX_RETRIES):
            mock_api.delete(regex_url,
                            body=json.dumps(response),
                            callback=lambda *args, **kwargs: request_sent_event.set())

        for i in range(self.exchange.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
            self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")

        self.async_run_with_timeout(request_sent_event.wait())
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"There was an error when requesting cancelation of order {order.client_order_id}"
            )
        )
        expected_error = (
            f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
            f" update_timestamp={'1640780000.0'}, new_state={repr(OrderState.FAILED)}, "
            f"client_order_id='{order.client_order_id}', exchange_order_id=None, misc_updates=None)")

        self.assertTrue(self._is_logged("INFO", expected_error))

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
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

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_CANCEL_PATH_URL, return_url=True)

        response = {
            "data": [{
                "marketCode": self.exchange_trading_pair,
                "clientOrderId": "OID1",
                "orderId": 4,
                "price": str(order1.price),
                "quantity": str(order1.amount),
                "status": "CANCELED_BY_USER",
                "timeInForce": "GTC",
                "orderType": "LIMIT",
                "side": "BUY"
            }]
        }

        mock_api.delete(regex_url, body=json.dumps(response))
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
    def test_update_balances(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNTS_PATH_URL)

        response = self._get_mock_balance_data(with_second=True)

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("2000"), available_balances["LTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])
        self.assertEqual(Decimal("2000"), total_balances["LTC"])

        response = self._get_mock_balance_data()

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn("LTC", available_balances)
        self.assertNotIn("LTC", total_balances)
        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_update_balances_logs_errors(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNTS_PATH_URL)

        mock_api.get(regex_url, status=401)
        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertTrue(
            self._is_logged("ERROR", "Error getting account balances from server")
        )

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_PATH_URL, return_url=True, endpoint_api_version="v2.1")

        order_status = self._get_mock_order_data(order, is_matched=True)

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        # Simulate the order has been filled with a TradeUpdate
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.async_run_with_timeout(order.wait_until_completely_filled())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["marketCode"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(Decimal("1"), buy_event.base_asset_amount)
        self.assertEqual(Decimal("10000"), buy_event.quote_asset_amount)
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
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

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

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_PATH_URL, return_url=True, endpoint_api_version="v2.1")

        order_status = self._get_mock_order_data(order, status="OrderClosed", is_matched=False)

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["marketCode"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

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

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_PATH_URL, return_url=True, endpoint_api_version="v2.1")

        order_status = self._get_mock_order_data(order, status="REJECT_CANCEL_ORDER_ID_NOT_FOUND", is_matched=False)

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["marketCode"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={int(order_status['data'][0]['orderClosedTimestamp']) * 1e-3}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}', "
                "misc_updates=None)")
        )

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_constants.API_MAX_RETRIES", new=int(1))
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_update_order_status_when_unauthorised(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

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

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_PATH_URL, return_url=True, endpoint_api_version="v2.1")

        for i in range(2):
            mock_api.get(regex_url, status=401)

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["marketCode"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        expected_error = {"errors": "Unauthorized", "status": 401}
        self.assertTrue(
            self._is_logged(
                "NETWORK",
                f"Error fetching status update for the order {order.client_order_id}: {expected_error}.")
        )

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_constants.API_MAX_RETRIES", new=int(2))
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_update_order_status_marks_order_as_failure_after_three_not_found(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

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

        url, regex_url = self._get_regex_url(CONSTANTS.ORDER_PATH_URL, return_url=True, endpoint_api_version="v2.1")

        order_status = {"data": [{
            "success": "false",
            "message": CONSTANTS.ORDER_NOT_FOUND_ERRORS[0]
        }]}

        for i in range(2 * self.exchange.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
            mock_api.get(regex_url, body=json.dumps(order_status))

        for i in range(self.exchange.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
            self.async_run_with_timeout(self.exchange._update_order_status())

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        expected_error = {
            **order_status,
            "errors": CONSTANTS.ORDER_NOT_FOUND_ERRORS[0]
        }
        self.assertTrue(
            self._is_logged(
                "NETWORK",
                f"Error fetching status update for the order {order.client_order_id}, marking as not found: {expected_error}.")
        )

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)

        trading_rules_response = self._get_mock_trading_rule_data()

        mock_response = trading_rules_response
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        trading_rule = self.exchange.trading_rules[self.trading_pair]
        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(Decimal(trading_rules_response["data"][0]["qtyIncrement"]),
                         trading_rule.min_order_size)
        self.assertEqual(Decimal(trading_rules_response["data"][0]["tickSize"]),
                         trading_rule.min_price_increment)
        self.assertEqual(Decimal(trading_rules_response["data"][0]["qtyIncrement"]),
                         trading_rule.min_base_amount_increment)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)

        trading_rules_response = self._get_mock_trading_rule_data(invalid=True)

        mock_response = trading_rules_response
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange.trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {trading_rules_response['data'][0]}. Skipping.")
        )

    def test_user_stream_update_for_new_order(self):
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

        event_message = self._get_mock_user_stream_order_data(order)

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
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = self._get_mock_user_stream_order_data(order,
                                                              status="CANCELED_BY_USER")

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

    def test_user_stream_update_for_order_fill(self):
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

        event_message = self._get_mock_user_stream_order_data(order,
                                                              trade_id=1,
                                                              status="FILLED",
                                                              is_matched=True,
                                                              fill_base_amount="1.00000000",
                                                              fill_price="10050.00000000",
                                                              fee_asset="HBOT",
                                                              fee_paid="50")
        sent_order_data = event_message["data"][0]

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
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
        self.assertEqual(Decimal(sent_order_data["matchPrice"]), fill_event.price)
        self.assertEqual(Decimal(sent_order_data["matchQuantity"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(sent_order_data["feeInstrumentId"], Decimal(sent_order_data["fees"]))],
            fill_event.trade_fee.flat_fees)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        exec_amt_quote = Decimal(sent_order_data["matchQuantity"]) * Decimal(sent_order_data["matchPrice"])
        self.assertEqual(exec_amt_quote, buy_event.quote_asset_amount)
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

    def test_user_stream_update_for_order_failure(self):
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

        event_message = self._get_mock_user_stream_order_data(order,
                                                              trade_id=1,
                                                              status="REJECT_CANCEL_ORDER_ID_NOT_FOUND")

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_failure)
        self.assertTrue(order.is_done)

    def test_user_stream_balance_update(self):
        self.exchange._set_current_timestamp(1640780000)

        event_message = self._get_mock_balance_data(asset="COINALPHA", free="10000.000000", total="10500.000000")

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10000"), self.exchange.available_balances["COINALPHA"])
        self.assertEqual(Decimal("10500"), self.exchange.get_balance("COINALPHA"))

    def test_user_stream_event_listener_raises_cancelled_error(self):
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = asyncio.CancelledError

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.test_task)

    def test_user_stream_event_queue_error_is_logged(self):
        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error")
        )
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertTrue(self._is_logged("NETWORK", "Unknown error. Retrying after 1 seconds."))

    @patch("hummingbot.core.data_type.in_flight_order.GET_EX_ORDER_ID_TIMEOUT", 0.0)
    def test_user_stream_event_order_not_created_error(self):
        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        self.exchange.start_tracking_order(
            exchange_order_id=None,
            order_id="OID1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = self._get_mock_user_stream_order_data(order=order)

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                              lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertTrue(self._is_logged("ERROR", f"Failed to get exchange order id for order: {order.client_order_id}"))
        self.assertTrue(self._is_logged("ERROR", "Unexpected error in user stream listener loop."))

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
