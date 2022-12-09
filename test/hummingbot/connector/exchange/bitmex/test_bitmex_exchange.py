import asyncio
import functools
import json
import re
import time
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.bitmex.bitmex_utils as utils
import hummingbot.connector.exchange.bitmex.bitmex_web_utils as web_utils
import hummingbot.connector.exchange.bitmex.constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bitmex.bitmex_api_order_book_data_source import BitmexAPIOrderBookDataSource
from hummingbot.connector.exchange.bitmex.bitmex_exchange import BitmexExchange
from hummingbot.connector.exchange.bitmex.bitmex_order_status import BitmexOrderStatus
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent


class BitmexExchangeUnitTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}_{cls.quote_asset}"
        cls.domain = CONSTANTS.TESTNET_DOMAIN
        cls.listen_key = "TEST_LISTEN_KEY"
        cls.ev_loop = asyncio.get_event_loop()
        utils.TRADING_PAIR_MULTIPLIERS["COINALPHA_HBOT"] = utils.TRADING_PAIR_MULTIPLIERS_TUPLE(1000000000, 1000000)
        utils.TRADING_PAIR_MULTIPLIERS["XBT_USDT"] = utils.TRADING_PAIR_MULTIPLIERS_TUPLE(100000000, 1000000)

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = BitmexExchange(
            client_config_map=self.client_config_map,
            bitmex_api_key="testAPIKey",
            bitmex_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )
        BitmexAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.symbol: self.trading_pair,
            "XBT_USDT": "XBT-USDT"
        }
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._client_order_tracker.logger().setLevel(1)
        self.exchange._client_order_tracker.logger().addHandler(self)
        self.exchange._trading_pair_to_multipliers["COINALPHA-HBOT"] = utils.TRADING_PAIR_MULTIPLIERS_TUPLE(1000000000, 1000000)
        self.exchange._trading_pair_to_multipliers["XBT-USDT"] = utils.TRADING_PAIR_MULTIPLIERS_TUPLE(1000000000, 1000000)
        self.mocking_assistant = NetworkMockingAssistant()
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()
        BitmexAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict(
                {
                    self.symbol: self.trading_pair,
                    "XBT_USDT": "XBT-USDT"
                }
            )
        }

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        BitmexAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def _get_income_history_dict(self) -> List:
        income_history = [{
            "income": 1,
            "symbol": self.symbol,
            "time": self.start_timestamp,
        }]
        return income_history

    def _get_trading_pair_symbol_map(self) -> Dict[str, str]:
        trading_pair_symbol_map = {self.symbol: f"{self.base_asset}-{self.quote_asset}"}
        return trading_pair_symbol_map

    def _get_exchange_info_mock_response(
            self,
            margin_asset: str = "HBOT",
            min_order_size: float = 1,
            min_price_increment: float = 2,
            min_notional_size: float = 4,
            max_order_size: float = 1000
    ) -> Dict[str, Any]:
        mocked_exchange_info = [
            {
                "symbol": self.symbol,
                "typ": "FFWCSX",
                "rootSymbol": self.base_asset,
                "quoteCurrency": self.quote_asset,
                "maxOrderQty": max_order_size,
                "lotSize": min_order_size,  # this gets divided by the multiplier, which is set to 1
                "settlCurrency": margin_asset,
                "tickSize": min_price_increment
            },
            {
                "symbol": "XBT_USDT",
                "typ": "FFWCSX",
                "rootSymbol": "XBT",
                "quoteCurrency": "USDT",
                "lotSize": 100,
                "tickSize": 0.5,
                "settlCurrency": "XBt",
                "maxOrderQty": 10000000
            },
        ]
        return mocked_exchange_info

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._trading_pairs.append("XBT-USDT")
        url = web_utils.rest_url(
            CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = [
            {
                "symbol": "COINALPHA_HBOT",
                "rootSymbol": "COINALPHA",
                "quoteCurrency": "HBOT",
                "settlCurrency": "HBOT",
                "lotSize": 1.0,
                "tickSize": 0.0001,
                "minProvideSize": 0.001,
                "maxOrderQty": 1000000
            },
            {
                "symbol": "XBT_USDT",
                "rootSymbol": "XBT",
                "quoteCurrency": "USDT",
                "lotSize": 100,
                "tickSize": 0.5,
                "settlCurrency": "XBt",
                "maxOrderQty": 10000000
            },
        ]
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        url_2 = web_utils.rest_url(
            CONSTANTS.TICKER_PRICE_URL, domain=self.domain
        )
        regex_url_2 = re.compile(f"^{url_2}".replace(".", r"\.").replace("?", r"\?"))
        mock_response_2: List[Dict[str, Any]] = [
            {
                "symbol": "COINALPHA_HBOT",
                "lastPrice": 1000.0
            }
        ]
        mock_api.get(regex_url_2, body=json.dumps(mock_response_2))
        url_3 = web_utils.rest_url(
            CONSTANTS.TICKER_PRICE_URL, domain=self.domain
        )
        regex_url_3 = re.compile(f"^{url_3}".replace(".", r"\.").replace("?", r"\?"))
        mock_response_3: List[Dict[str, Any]] = [
            {
                "symbol": "XBT_USDT",
                "lastPrice": 1000.0
            }
        ]
        mock_api.get(regex_url_3, body=json.dumps(mock_response_3))
        self.async_run_with_timeout(self.exchange._update_trading_rules())
        self.assertTrue(len(self.exchange._trading_rules) > 0)
        quant_amount = self.exchange.quantize_order_amount('XBT-USDT', Decimal('0.00001'), Decimal('10000'))
        self.assertEqual(quant_amount, Decimal('0.000010'))
        quant_price = self.exchange.quantize_order_price('COINALPHA-HBOT', Decimal('1'))
        self.assertEqual(quant_price, Decimal('1.0'))
        quant_amount = self.exchange.quantize_order_amount('COINALPHA-HBOT', Decimal('0.00001'), Decimal('10000'))
        self.assertEqual(quant_amount, Decimal('0.000010'))
        self.exchange._trading_pairs.remove("XBT-USDT")

    def test_format_trading_rules(self):
        min_order_size = Decimal('1E-9')
        min_price_increment = 2
        min_base_amount_increment = Decimal('1E-9')
        mocked_response = self._get_exchange_info_mock_response()

        task = self.ev_loop.create_task(self.exchange._format_trading_rules(mocked_response))
        trading_rules = self.async_run_with_timeout(task)

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]

        self.assertEqual(min_order_size, trading_rule.min_order_size)
        self.assertEqual(min_price_increment, trading_rule.min_price_increment)
        self.assertEqual(min_base_amount_increment, trading_rule.min_base_amount_increment)

    def test_buy_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_side=TradeType.BUY,
            client_order_id="OID1",
            order_type=OrderType.LIMIT,
            created_at=time.time(),
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1")
        )

        partial_fill = {
            "table": "execution",
            "data": [
                {
                    "clOrdID": "OID1",
                    "leavesQty": 0.5,
                    "ordStatus": "PartiallyFilled",
                    "avgPx": 9999,
                }
            ]
        }
        logger_len = len(self.order_filled_logger.event_log)

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(logger_len + 1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0.0002"), fill_event.trade_fee.percent)

        complete_fill = {
            "table": "execution",
            "data": [
                {
                    "clOrdID": "OID1",
                    "leavesQty": 0.0,
                    "ordStatus": "Filled",
                    "avgPx": 9999,
                }
            ]
        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(logger_len + 2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0.0002"), fill_event.trade_fee.percent)

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_sell_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_side=TradeType.SELL,
            client_order_id="OID1",
            order_type=OrderType.LIMIT,
            created_at=time.time(),
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        partial_fill = {
            "table": "execution",
            "data": [
                {
                    "clOrdID": "OID1",
                    "leavesQty": 0.5,
                    "ordStatus": "PartiallyFilled",
                    "avgPx": 10001,
                }
            ]
        }
        logger_len = len(self.order_filled_logger.event_log)
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())
        self.assertEqual(logger_len + 1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0.0002"), fill_event.trade_fee.percent)

        complete_fill = {
            "table": "execution",
            "data": [
                {
                    "clOrdID": "OID1",
                    "leavesQty": 0.0,
                    "ordStatus": "Filled",
                    "avgPx": 10001,
                }
            ]
        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(logger_len + 2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0.0002"), fill_event.trade_fee.percent)

        self.assertEqual(1, len(self.sell_order_completed_logger.event_log))

    def test_order_event_with_cancelled_status_marks_order_as_cancelled(self):
        self.exchange.start_tracking_order(
            order_side=TradeType.SELL,
            client_order_id="OID1",
            order_type=OrderType.LIMIT,
            created_at=time.time(),
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1")
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "table": "execution",
            "data": [
                {
                    "clOrdID": "OID1",
                    "ordStatus": "Canceled",
                    "leavesQty": 1
                }
            ]
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

        event = self.order_cancelled_logger.event_log[0]

        self.assertEqual(event.order_id, order.client_order_id)

    def test_user_stream_event_listener_raises_cancelled_error(self):
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = asyncio.CancelledError

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.test_task)

    @aioresponses()
    @patch("hummingbot.connector.exchange.bitmex.bitmex_exchange."
           "BitmexExchange.current_timestamp")
    def test_update_order_status_successful(self, req_mock, mock_timestamp):
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_side=TradeType.SELL,
            client_order_id="OID1",
            order_type=OrderType.LIMIT,
            created_at=time.time(),
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1")
        )

        order = [
            {
                "clOrdID": "OID1",
                "leavesQty": 500000000,
                "ordStatus": "PartiallyFilled",
                "avgPx": 10001,
            }
        ]

        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(order))

        self.async_run_with_timeout(self.exchange._update_order_status())

        in_flight_orders = self.exchange._in_flight_orders

        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(1, in_flight_orders["OID1"].amount)
        self.assertEqual(BitmexOrderStatus.PartiallyFilled, in_flight_orders["OID1"].state)
        # Processing an order update should not impact trade fill information
        self.assertEqual(Decimal("0.5"), in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(Decimal("5000.5"), in_flight_orders["OID1"].executed_amount_quote)

    @aioresponses()
    @patch("hummingbot.connector.exchange.bitmex.bitmex_exchange."
           "BitmexExchange.current_timestamp")
    def test_update_order_status_failure_old_order(self, req_mock, mock_timestamp):
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_side=TradeType.SELL,
            client_order_id="OID1",
            order_type=OrderType.LIMIT,
            created_at=0,
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1")
        )

        order = [
            {
                "clOrdID": "OID2",
                "leavesQty": 0.5,
                "ordStatus": "PartiallyFilled",
                "avgPx": 10001,
            }
        ]

        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(order))

        self.async_run_with_timeout(self.exchange._update_order_status())
        self.assertEqual(len(self.exchange.in_flight_orders), 0)

    @aioresponses()
    @patch("hummingbot.connector.exchange.bitmex.bitmex_exchange."
           "LatchingEventResponder.wait_for_completion")
    def test_cancel_all_successful(self, mocked_api, mock_wait):
        mock_wait.return_value = True
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"code": 200, "msg": "success"}
        mocked_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_side=TradeType.BUY,
            client_order_id="OID1",
            order_type=OrderType.LIMIT,
            created_at=time.time(),
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1")
        )

        self.exchange.start_tracking_order(
            order_side=TradeType.SELL,
            client_order_id="OID2",
            order_type=OrderType.LIMIT,
            created_at=time.time(),
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1")
        )

        self.assertTrue("OID1" in self.exchange._in_flight_orders)
        self.assertTrue("OID2" in self.exchange._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(0, len(order_cancelled_events))
        self.assertEqual(2, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)
        self.assertEqual("OID2", cancellation_results[1].order_id)

    @aioresponses()
    def test_cancel_unknown_new_order(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"error": {"message": "order not found", "name": "Not Found"}}
        req_mock.delete(regex_url, status=400, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_side=TradeType.BUY,
            client_order_id="OID1",
            order_type=OrderType.LIMIT,
            created_at=time.time(),
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1")
        )

        tracked_order = self.exchange.in_flight_orders.get("OID1")
        tracked_order.state = BitmexOrderStatus.New

        self.assertTrue("OID1" in self.exchange._in_flight_orders)

        try:
            self.async_run_with_timeout(self.exchange.cancel_order("OID1"))
        except Exception as e:
            self.assertEqual(str(e), f"order {tracked_order.client_order_id} does not yet exist on the exchange and could not be cancelled.")

    @aioresponses()
    def test_cancel_unknown_old_order(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"error": {"message": "order not found", "name": "Not Found"}}
        req_mock.delete(regex_url, status=400, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_side=TradeType.BUY,
            client_order_id="OID1",
            order_type=OrderType.LIMIT,
            created_at=0.0,
            hash="8886774",
            trading_pair=self.trading_pair,
            price=Decimal("10000"),
            amount=Decimal("1")
        )

        tracked_order = self.exchange.in_flight_orders.get("OID1")
        tracked_order.state = BitmexOrderStatus.New

        self.assertTrue("OID1" in self.exchange._in_flight_orders)
        try:
            cancellation_result = self.async_run_with_timeout(self.exchange.cancel_order("OID1"))
        except Exception:
            pass

        self.assertFalse(cancellation_result)

        self.assertTrue("OID1" not in self.exchange._in_flight_orders)

    @aioresponses()
    def test_create_order_successful(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        create_response = {"updateTime": int(self.start_timestamp),
                           "ordStatus": "New",
                           "orderID": "8886774"}
        req_mock.post(regex_url, body=json.dumps(create_response))

        margin_asset = self.quote_asset
        mocked_response = self._get_exchange_info_mock_response(margin_asset)
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]

        self.async_run_with_timeout(self.exchange.execute_buy(order_id="OID1",
                                                              trading_pair=self.trading_pair,
                                                              amount=Decimal("100"),
                                                              order_type=OrderType.LIMIT,
                                                              price=Decimal("10000")))

        self.assertTrue("OID1" in self.exchange._in_flight_orders)

    @aioresponses()
    def test_create_order_exception(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        create_response = {"updateTime": int(self.start_timestamp),
                           "ordStatus": "Canceled",
                           "orderID": "8886774"}

        req_mock.post(regex_url, body=json.dumps(create_response))

        margin_asset = self.quote_asset
        mocked_response = self._get_exchange_info_mock_response(margin_asset)
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]

        self.async_run_with_timeout(self.exchange.execute_sell(order_id="OID1",
                                                               trading_pair=self.trading_pair,
                                                               amount=Decimal("10000"),
                                                               order_type=OrderType.LIMIT,
                                                               price=Decimal("1010")))

        self.assertTrue("OID1" not in self.exchange._in_flight_orders)

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
            initial_state=BitmexOrderStatus.Canceled
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
            initial_state=BitmexOrderStatus.Filled
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
            initial_state=BitmexOrderStatus.FAILURE
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 4

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action="OPEN",
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action="OPEN",
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.ACCOUNT_INFO_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = [
            {
                "currency": "USDT",
                "amount": 100000000,
                "pendingCredit": 2000000,
                "pendingDebit": 0
            },
            {
                "currency": "XBT",
                "amount": 1000000000,
                "pendingCredit": 20000000,
                "pendingDebit": 0
            }
        ]

        mock_api.get(regex_url, body=json.dumps(response))

        url_2 = web_utils.rest_url(CONSTANTS.TOKEN_INFO_URL, domain=self.domain)
        regex_url_2 = re.compile(f"^{url_2}".replace(".", r"\.").replace("?", r"\?"))

        response_2 = [
            {
                "asset": "USDT",
                "scale": 6
            },
            {
                "asset": "XBT",
                "scale": 8,
            }
        ]

        mock_api.get(regex_url_2, body=json.dumps(response_2))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("98"), available_balances["USDT"])
        self.assertEqual(Decimal("9.8"), available_balances["XBT"])
        self.assertEqual(Decimal("100"), total_balances["USDT"])
        self.assertEqual(Decimal("10"), total_balances["XBT"])

    def test_adjust_quote_based_amounts(self):
        self.exchange._trading_pairs.append("XBT-USDT")
        mocked_response = self._get_exchange_info_mock_response()

        task = self.ev_loop.create_task(self.exchange._format_trading_rules(mocked_response))
        trading_rules = self.async_run_with_timeout(task)
        self.exchange._trading_rules["XBT-USDT"] = trading_rules[1]
        base, quote = self.exchange.adjust_quote_based_amounts("XBT-USDT", Decimal('1000'), Decimal('10'))
        self.exchange._trading_pairs.remove("XBT-USDT")
