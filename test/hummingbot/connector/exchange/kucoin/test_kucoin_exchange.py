import asyncio
import json
import re
import unittest
from collections import Awaitable
from decimal import Decimal
from functools import partial
from typing import Any, Dict, Optional
from unittest.mock import patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_web_utils as web_utils,
)
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_exchange import KucoinExchange
from hummingbot.connector.exchange.kucoin.kucoin_in_flight_order import KucoinInFlightOrder
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.time_iterator import TimeIterator


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

    def get_accounts_data_mock(self) -> Dict:
        acc_data = {
            "code": "200000",
            "data": [
                {
                    "id": "someId1",
                    "currency": self.base_asset,
                    "type": "trade",
                    "balance": "81.8446241",
                    "available": "81.8446241",
                    "holds": "0",
                },
                {
                    "id": "someId2",
                    "currency": self.quote_asset,
                    "type": "trade",
                    "balance": "41.3713",
                    "available": "41.3713",
                    "holds": "0",
                },
            ],
        }
        return acc_data

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

    def get_in_flight_order_mock(self, order_id: str, exchange_id: str) -> KucoinInFlightOrder:
        order = KucoinInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10.0"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.0
        )
        return order

    def get_order_response_mock(self, size: float, filled: float) -> Dict[str, Any]:
        order_response = {
            "data": {
                "id": "5c35c02703aa673ceec2a168",
                "symbol": self.trading_pair,
                "opType": "DEAL",
                "type": "limit",
                "side": "buy",
                "price": "10",
                "size": str(size),
                "funds": "0",
                "dealFunds": "0.166",
                "dealSize": str(filled),
                "fee": "0",
                "feeCurrency": "USDT",
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
        return order_response

    @staticmethod
    def get_cancel_response(exchange_id: str) -> Dict:
        cancel_response = {
            "code": "200000",
            "data": {
                "cancelledOrderIds": [exchange_id],
            }
        }
        return cancel_response

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
    def test_update_balances(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.ACCOUNTS_PATH_URL)
        resp = self.get_accounts_data_mock()
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertTrue(self.quote_asset in self.exchange.available_balances)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = web_utils.rest_url(CONSTANTS.SYMBOLS_PATH_URL)
        resp = self.get_exchange_rules_mock()
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)

    @aioresponses()
    def test_get_order_status(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = "someStatus"
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.get_order_status(exchange_order_id="someId"))

        self.assertEqual(resp, ret)

    @aioresponses()
    def test_place_order(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        resp = {
            "code": "200000",
            "data": {
                "orderId": "someId",
            }
        }

        mock_api.post(url, body=json.dumps(resp))
        amount = Decimal("1")
        price = Decimal("10.0")
        ret = self.async_run_with_timeout(
            coroutine=self.exchange.place_order(
                order_id="internalId",
                trading_pair=self.trading_pair,
                amount=amount,
                is_buy=True,
                order_type=OrderType.LIMIT,
                price=price,
            )
        )

        self.assertEqual(ret, resp["data"]["orderId"])

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_data = order_request[1][0].kwargs["data"]
        expected_data = {
            "size": str(amount),
            "clientOid": "internalId",
            "side": "buy",
            "symbol": self.trading_pair,
            "type": "limit",
            "price": str(price),
        }
        self.assertEqual(expected_data, request_data)

    @aioresponses()
    def test_execute_cancel(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        called = asyncio.Event()

        def callback(*args, **kwargs):
            called.set()

        exchange_id = "someId"
        resp = self.get_cancel_response(exchange_id=exchange_id)
        mock_api.delete(regex_url, body=json.dumps(resp), callback=callback)

        order_id = "internalId"
        order = self.get_in_flight_order_mock(order_id, exchange_id=exchange_id)
        order.last_state = "DEAL"
        self.exchange.in_flight_orders[order_id] = order
        self.async_run_with_timeout(coroutine=self.exchange.execute_cancel(self.trading_pair, order_id))

        self.assertTrue(called.is_set())

    @aioresponses()
    def test_cancel_all(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        called1 = asyncio.Event()
        called2 = asyncio.Event()

        def callback(ev, *args, **kwargs):
            ev.set()

        order_id1 = "internalId1"
        order_id2 = "internalId2"
        exchange_id1 = "someId1"
        exchange_id2 = "someId2"
        resp1 = self.get_cancel_response(exchange_id1)
        resp2 = self.get_cancel_response(exchange_id2)
        mock_api.delete(regex_url, body=json.dumps(resp1), callback=partial(callback, called1))
        mock_api.delete(regex_url, body=json.dumps(resp2), callback=partial(callback, called2))

        self.exchange.in_flight_orders[order_id1] = self.get_in_flight_order_mock(order_id1, exchange_id=exchange_id1)
        self.exchange.in_flight_orders[order_id2] = self.get_in_flight_order_mock(order_id2, exchange_id=exchange_id2)
        self.async_run_with_timeout(coroutine=self.exchange.cancel_all(timeout_seconds=1))

        self.assertTrue(called1.is_set())
        self.assertTrue(called2.is_set())

    @aioresponses()
    def test_update_order_status_notifies_on_order_filled(self, mocked_api):
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}")
        resp = self.get_order_response_mock(size=2, filled=2)
        mocked_api.get(regex_url, body=json.dumps(resp))

        clock = Clock(
            ClockMode.BACKTEST,
            start_time=self.exchange.UPDATE_ORDERS_INTERVAL,
            end_time=self.exchange.UPDATE_ORDERS_INTERVAL * 2,
        )
        TimeIterator.start(self.exchange, clock)
        order_id = "someId"
        exchange_id = "someExchangeId"
        self.exchange.in_flight_orders[order_id] = self.get_in_flight_order_mock(order_id, exchange_id)
        order = self.exchange.in_flight_orders[order_id]

        self.async_run_with_timeout(self.exchange._update_order_status())

        orders_filled_events = self.order_filled_logger.event_log
        order_completed_events = self.buy_order_completed_logger.event_log

        self.assertTrue(order.is_done)
        self.assertEqual(1, len(order_completed_events))
        self.assertEqual(1, len(orders_filled_events))
        self.assertEqual(order_id, order_completed_events[0].order_id)
        self.assertEqual(order_id, orders_filled_events[0].order_id)

    @aioresponses()
    def test_update_order_status_skips_if_order_no_longer_tracked(self, mocked_api):
        order_id = "someId"
        exchange_id = "someExchangeId"

        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}")
        resp = self.get_order_response_mock(size=2, filled=2)
        mocked_api.get(
            regex_url,
            body=json.dumps(resp),
            callback=lambda *_, **__: self.exchange.stop_tracking_order(order_id),
        )

        clock = Clock(
            ClockMode.BACKTEST,
            start_time=self.exchange.UPDATE_ORDERS_INTERVAL,
            end_time=self.exchange.UPDATE_ORDERS_INTERVAL * 2,
        )
        TimeIterator.start(self.exchange, clock)
        self.exchange.in_flight_orders[order_id] = self.get_in_flight_order_mock(order_id, exchange_id)

        self.async_run_with_timeout(self.exchange._update_order_status())

        orders_filled_events = self.order_filled_logger.event_log
        order_completed_events = self.buy_order_completed_logger.event_log

        self.assertEqual(0, len(order_completed_events))
        self.assertEqual(0, len(orders_filled_events))

    @aioresponses()
    def test_get_fee_defaults_on_not_found(self, mocked_api):
        url = web_utils.rest_url(CONSTANTS.FEE_PATH_URL)
        regex_url = re.compile(f"^{url}")
        resp = {"data": [{"makerFeeRate": "0.002", "takerFeeRate": "0.002"}]}
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
