import asyncio
import functools
import time
from collections import Awaitable

import pandas as pd

import ujson
from decimal import Decimal
from typing import Any, Dict, List, Callable
from unittest import TestCase
from unittest.mock import AsyncMock, PropertyMock, patch

from hummingbot.connector.exchange.mexc.mexc_exchange import MexcExchange
from hummingbot.connector.exchange.mexc.mexc_in_flight_order import (
    MexcInFlightOrder
)
from hummingbot.connector.exchange.mexc.mexc_order_book import MexcOrderBook
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.event.events import (
    OrderCancelledEvent,
    OrderType,
    TradeType, SellOrderCompletedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class MexcExchangeTests(TestCase):
    # the level is required to receive logs from the data source loger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "MX"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()

        self.tracker_task = None
        self.exchange_task = None
        self.log_records = []
        self.resume_test_event = asyncio.Event()
        self._account_name = "hbot"

        self.exchange = MexcExchange(mexc_api_key='testAPIKey',
                                     mexc_secret_key='testSecret',
                                     trading_pairs=[self.trading_pair])

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._account_id = 1

        self.mocking_assistant = NetworkMockingAssistant()
        self.mock_done_event = asyncio.Event()

    def tearDown(self) -> None:
        self.tracker_task and self.tracker_task.cancel()
        self.exchange_task and self.exchange_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    def _simulate_reset_poll_notifier(self):
        self.exchange._poll_notifier.clear()

    def _simulate_ws_message_received(self, timestamp: float):
        self.exchange._user_stream_tracker._data_source._last_recv_time = timestamp

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=4,
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=2,
                min_notional_size=Decimal(str(5))
            )
        }

    @property
    def order_book_data(self):
        _data = {"code": 200, "data": {
            "asks": [{"price": "56454.0", "quantity": "0.799072"}, {"price": "56455.28", "quantity": "0.008663"}],
            "bids": [{"price": "56451.0", "quantity": "0.008663"}, {"price": "56449.99", "quantity": "0.173078"}],
            "version": "547878563"}}
        return _data

    def _simulate_create_order(self,
                               trade_type: TradeType,
                               order_id: str,
                               trading_pair: str,
                               amount: Decimal,
                               price: Decimal = Decimal("0"),
                               order_type: OrderType = OrderType.MARKET):
        future = safe_ensure_future(
            self.exchange.execute_buy(order_id, trading_pair, amount, order_type, price)
        )
        self.exchange.start_tracking_order(
            order_id, None, self.trading_pair, TradeType.BUY, Decimal(10.0), Decimal(1.0), OrderType.LIMIT
        )
        return future

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_user_event_queue_error_is_logged(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_text_message(ws_connect_mock,
                                                          ujson.dumps({'channel': 'push.personal.order'}))
        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        try:
            self.exchange_task.cancel()
            self.async_run_with_timeout(self.exchange_task)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

        self.assertTrue(self._is_logged('ERROR', "Unknown error. Retrying after 1 second. Dummy test error"))

    def test_user_event_queue_notifies_cancellations(self):
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            asyncio.CancelledError())
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.tracker_task)

    def test_exchange_logs_unknown_event_message(self):
        payload = {'channel': 'test'}
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: payload)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream
        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self._is_logged('DEBUG', f"Unknown event received from the connector ({payload})"))

    @property
    def balances_mock_data(self):
        return {
            "code": 200,
            "data": {
                "MX": {
                    "frozen": "30.9863",
                    "available": "450.0137"
                }
            }
        }

    @property
    def user_stream_data(self):
        return {
            'symbol': 'MX_USDT',
            'data': {
                'price': 3.1504,
                'quantity': 2,
                'amount': 6.3008,
                'remainAmount': 6.3008,
                'remainQuantity': 2,
                'remainQ': 2,
                'id': '40728558ead64032a676e6f0a4afc4ca',
                'status': 4,
                'tradeType': 2,
                'createTime': 1638156451000,
                'symbolDisplay': 'MX_USDT',
                'clientOrderId': 'sell-MX-USDT-1638156451005305'},
            'channel': 'push.personal.order', 'symbol_display': 'MX_USDT'}

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_order_event_with_cancel_status_cancels_in_flight_order(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 200, self.balances_mock_data, self.balances_mock_data)

        self.exchange.start_tracking_order(order_id="sell-MX-USDT-1638156451005305",
                                           exchange_order_id="40728558ead64032a676e6f0a4afc4ca",
                                           trading_pair="MX-USDT",
                                           trade_type=TradeType.SELL,
                                           price=Decimal("3.1504"),
                                           amount=Decimal("6.3008"),
                                           order_type=OrderType.LIMIT)

        inflight_order = self.exchange.in_flight_orders["sell-MX-USDT-1638156451005305"]

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: self.user_stream_data)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual("CANCELED", inflight_order.last_state)
        self.assertTrue(inflight_order.is_cancelled)
        self.assertFalse(inflight_order.client_order_id in self.exchange.in_flight_orders)
        self.assertTrue(self._is_logged("INFO", f"Order {inflight_order.client_order_id} "
                                                f"has been cancelled according to order delta websocket API."))
        self.assertEqual(1, len(self.exchange.event_logs))
        cancel_event = self.exchange.event_logs[0]
        self.assertEqual(OrderCancelledEvent, type(cancel_event))
        self.assertEqual(inflight_order.client_order_id, cancel_event.order_id)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_order_event_with_rejected_status_makes_in_flight_order_fail(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 200, self.balances_mock_data)
        self.exchange.start_tracking_order(order_id="sell-MX-USDT-1638156451005305",
                                           exchange_order_id="40728558ead64032a676e6f0a4afc4ca",
                                           trading_pair="MX-USDT",
                                           trade_type=TradeType.SELL,
                                           price=Decimal("3.1504"),
                                           amount=Decimal("6.3008"),
                                           order_type=OrderType.LIMIT)

        inflight_order = self.exchange.in_flight_orders["sell-MX-USDT-1638156451005305"]
        stream_data = self.user_stream_data
        stream_data.get("data")["status"] = 5
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: stream_data)
        self.exchange._user_stream_tracker._user_stream = mock_user_stream
        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual("PARTIALLY_CANCELED", inflight_order.last_state)
        self.assertTrue(inflight_order.is_failure)
        self.assertFalse(inflight_order.client_order_id in self.exchange.in_flight_orders)
        self.assertTrue(self._is_logged("INFO", f"Order {inflight_order.client_order_id} "
                                                f"has been cancelled according to order delta websocket API."))
        self.assertEqual(1, len(self.exchange.event_logs))
        failure_event = self.exchange.event_logs[0]
        self.assertEqual(OrderCancelledEvent, type(failure_event))
        self.assertEqual(inflight_order.client_order_id, failure_event.order_id)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_trade_event_fills_and_completes_buy_in_flight_order(self, mock_api):
        fee_mock_data = {'code': 200, 'data': [{'id': 'c85b7062f69c4bf1b6c153dca5c0318a',
                                                'symbol': 'MX_USDT', 'quantity': '2',
                                                'price': '3.1265', 'amount': '6.253',
                                                'fee': '0.012506', 'trade_type': 'BID',
                                                'order_id': '95c4ce45fdd34cf99bfd1e1378eb38ae',
                                                'is_taker': False, 'fee_currency': 'USDT',
                                                'create_time': 1638177115000}]}
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 200, self.balances_mock_data)
        self.mocking_assistant.add_http_response(mock_api, 200, fee_mock_data)
        self.exchange.start_tracking_order(order_id="sell-MX-USDT-1638156451005305",
                                           exchange_order_id="40728558ead64032a676e6f0a4afc4ca",
                                           trading_pair="MX-USDT",
                                           trade_type=TradeType.SELL,
                                           price=Decimal("3.1504"),
                                           amount=Decimal("6.3008"),
                                           order_type=OrderType.LIMIT)
        inflight_order = self.exchange.in_flight_orders["sell-MX-USDT-1638156451005305"]
        _user_stream = self.user_stream_data
        _user_stream.get("data")["status"] = 2
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: _user_stream)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream
        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual("FILLED", inflight_order.last_state)
        self.assertEqual(Decimal(0), inflight_order.executed_amount_base)
        self.assertEqual(Decimal(0), inflight_order.executed_amount_quote)
        self.assertEqual(1, len(self.exchange.event_logs))
        fill_event = self.exchange.event_logs[0]
        self.assertEqual(SellOrderCompletedEvent, type(fill_event))
        self.assertEqual(inflight_order.client_order_id, fill_event.order_id)
        self.assertEqual(inflight_order.trading_pair, f'{fill_event.base_asset}-{fill_event.quote_asset}')

    def test_tick_initial_tick_successful(self):
        start_ts: float = time.time() * 1e3

        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("time.time")
    def test_tick_subsequent_tick_within_short_poll_interval(self, mock_ts):
        # Assumes user stream tracker has NOT been receiving messages, Hence SHORT_POLL_INTERVAL in use
        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.SHORT_POLL_INTERVAL - 1)

        mock_ts.return_value = start_ts
        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        self._simulate_reset_poll_notifier()

        mock_ts.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("time.time")
    def test_tick_subsequent_tick_exceed_short_poll_interval(self, mock_ts):
        # Assumes user stream tracker has NOT been receiving messages, Hence SHORT_POLL_INTERVAL in use
        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.SHORT_POLL_INTERVAL + 1)

        mock_ts.return_value = start_ts
        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        self._simulate_reset_poll_notifier()

        mock_ts.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_update_balances(self, mock_api):
        self.assertEqual(0, len(self.exchange._account_balances))
        self.assertEqual(0, len(self.exchange._account_available_balances))

        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 200, self.balances_mock_data, "")

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._update_balances()
        )
        self.async_run_with_timeout(self.exchange_task)

        self.assertEqual(Decimal(str(481.0)), self.exchange.get_balance(self.base_asset))

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.current_timestamp", new_callable=PropertyMock)
    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_order_status(self, mock_order_status, mock_trade_history, mock_ts):
        # Simulates order being tracked
        order: MexcInFlightOrder = MexcInFlightOrder(
            "0",
            "2628",
            self.trading_pair,
            OrderType.LIMIT,
            TradeType.SELL,
            Decimal(str(41720.83)),
            Decimal("1"),
            "Working",
        )
        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })
        self.exchange._last_poll_timestamp = 10
        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts
        self.assertTrue(1, len(self.exchange.in_flight_orders))

        # Add FullyExecuted GetOrderStatus API Response
        self.mocking_assistant.configure_http_request_mock(mock_order_status)
        self.mocking_assistant.add_http_response(
            mock_order_status,
            200,
            {
                "Side": "Sell",
                "OrderId": 2628,
                "Price": 41720.830000000000000000000000,
                "Quantity": 0.0000000000000000000000000000,
                "DisplayQuantity": 0.0000000000000000000000000000,
                "Instrument": 5,
                "Account": 528,
                "AccountName": "hbot",
                "OrderType": "Limit",
                "ClientOrderId": 0,
                "OrderState": "FullyExecuted",
                "ReceiveTime": 1627380780887,
                "ReceiveTimeTicks": 637629775808866338,
                "LastUpdatedTime": 1627380783860,
                "LastUpdatedTimeTicks": 637629775838598558,
                "OrigQuantity": 1.0000000000000000000000000000,
                "QuantityExecuted": 1.0000000000000000000000000000,
                "GrossValueExecuted": 41720.830000000000000000000000,
                "ExecutableValue": 0.0000000000000000000000000000,
                "AvgPrice": 41720.830000000000000000000000,
                "CounterPartyId": 0,
                "ChangeReason": "Trade",
                "OrigOrderId": 2628,
                "OrigClOrdId": 0,
                "EnteredBy": 492,
                "UserName": "hbot",
                "IsQuote": False,
                "InsideAsk": 41720.830000000000000000000000,
                "InsideAskSize": 0.9329960000000000000000000000,
                "InsideBid": 41718.340000000000000000000000,
                "InsideBidSize": 0.0632560000000000000000000000,
                "LastTradePrice": 41720.830000000000000000000000,
                "RejectReason": "",
                "IsLockedIn": False,
                "CancelReason": "",
                "OrderFlag": "AddedToBook, RemovedFromBook",
                "UseMargin": False,
                "StopPrice": 0.0000000000000000000000000000,
                "PegPriceType": "Last",
                "PegOffset": 0.0000000000000000000000000000,
                "PegLimitOffset": 0.0000000000000000000000000000,
                "IpAddress": "103.6.151.12",
                "ClientOrderIdUuid": None,
                "OMSId": 1
            },
            "")

        # Add TradeHistory API Response
        self.mocking_assistant.configure_http_request_mock(mock_trade_history)
        self.mocking_assistant.add_http_response(
            mock_trade_history,
            200,
            {
                "code": 200,
                "data": [
                    {
                        "id": "504feca6ba6349e39c82262caf0be3f4",
                        "symbol": "MX_USDT",
                        "price": "3.001",
                        "quantity": "30",
                        "state": "CANCELED",
                        "type": "BID",
                        "deal_quantity": "0",
                        "deal_amount": "0",
                        "create_time": 1573117266000
                    }
                ]
            },
            "")

        self.exchange_task = asyncio.get_event_loop().create_task(self.exchange._update_order_status())
        self.async_run_with_timeout(self.exchange_task)
        self.assertEqual(0, len(self.exchange.in_flight_orders))

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.current_timestamp", new_callable=PropertyMock)
    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_order_status_error_response(self, mock_api, mock_ts):

        # Simulates order being tracked
        order: MexcInFlightOrder = MexcInFlightOrder("0", "2628", self.trading_pair, OrderType.LIMIT, TradeType.SELL,
                                                     Decimal(str(41720.83)), Decimal("1"))
        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })
        self.assertTrue(1, len(self.exchange.in_flight_orders))

        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts
        # Add FullyExecuted GetOrderStatus API Response
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(
            mock_api,
            200,
            {
                "Side": "Sell",
                "OrderId": 2628,
                "Price": 41720.830000000000000000000000,
                "Quantity": 0.0000000000000000000000000000,
                "DisplayQuantity": 0.0000000000000000000000000000,
                "Instrument": 5,
                "Account": 528,
                "AccountName": "hbot",
                "OrderType": "Limit",
                "ClientOrderId": 0,
                "OrderState": "Working",
                "ReceiveTime": 1627380780887,
                "ReceiveTimeTicks": 637629775808866338,
                "LastUpdatedTime": 1627380783860,
                "LastUpdatedTimeTicks": 637629775838598558,
                "OrigQuantity": 1.0000000000000000000000000000,
                "QuantityExecuted": 1.0000000000000000000000000000,
                "GrossValueExecuted": 41720.830000000000000000000000,
                "ExecutableValue": 0.0000000000000000000000000000,
                "AvgPrice": 41720.830000000000000000000000,
                "CounterPartyId": 0,
                "ChangeReason": "Trade",
                "OrigOrderId": 2628,
                "OrigClOrdId": 0,
                "EnteredBy": 492,
                "UserName": "hbot",
                "IsQuote": False,
                "InsideAsk": 41720.830000000000000000000000,
                "InsideAskSize": 0.9329960000000000000000000000,
                "InsideBid": 41718.340000000000000000000000,
                "InsideBidSize": 0.0632560000000000000000000000,
                "LastTradePrice": 41720.830000000000000000000000,
                "RejectReason": "",
                "IsLockedIn": False,
                "CancelReason": "",
                "OrderFlag": "AddedToBook, RemovedFromBook",
                "UseMargin": False,
                "StopPrice": 0.0000000000000000000000000000,
                "PegPriceType": "Last",
                "PegOffset": 0.0000000000000000000000000000,
                "PegLimitOffset": 0.0000000000000000000000000000,
                "IpAddress": "103.6.151.12",
                "ClientOrderIdUuid": None,
                "OMSId": 1
            },
            "")

        # Add TradeHistory API Response
        self.mocking_assistant.add_http_response(
            mock_api,
            200,
            {
                "result": False,
                "errormsg": "Invalid Request",
                "errorcode": 100,
                "detail": None
            }, "")
        self.exchange_task = asyncio.get_event_loop().create_task(self.exchange._update_order_status())
        self.async_run_with_timeout(self.exchange_task)
        self.assertEqual(1, len(self.exchange.in_flight_orders))

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._update_balances", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._update_order_status", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.current_timestamp", new_callable=PropertyMock)
    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._reset_poll_notifier")
    def test_status_polling_loop(self, _, mock_ts, mock_update_order_status, mock_balances):
        mock_balances.return_value = None
        mock_update_order_status.return_value = None

        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts

        with self.assertRaises(asyncio.TimeoutError):
            self.exchange_task = asyncio.get_event_loop().create_task(
                self.exchange._status_polling_loop()
            )
            self.exchange._poll_notifier.set()

            self.async_run_with_timeout(asyncio.wait_for(self.exchange_task, 2.0))

        self.assertEqual(ts, self.exchange._last_poll_timestamp)

    @patch("aiohttp.ClientSession.request")
    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.current_timestamp", new_callable=PropertyMock)
    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._reset_poll_notifier")
    def test_status_polling_loop_cancels(self, _, mock_ts, mock_api):
        mock_api.side_effect = asyncio.CancelledError

        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts

        with self.assertRaises(asyncio.CancelledError):
            self.exchange_task = asyncio.get_event_loop().create_task(
                self.exchange._status_polling_loop()
            )
            self.exchange._poll_notifier.set()

            self.async_run_with_timeout(self.exchange_task)

        self.assertEqual(0, self.exchange._last_poll_timestamp)

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._update_balances", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._update_order_status", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.current_timestamp", new_callable=PropertyMock)
    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._reset_poll_notifier")
    def test_status_polling_loop_exception_raised(self, _, mock_ts, mock_update_order_status, mock_balances):
        mock_balances.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))
        mock_update_order_status.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))

        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._status_polling_loop()
        )

        self.exchange._poll_notifier.set()

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(0, self.exchange._last_poll_timestamp)
        self._is_logged("ERROR", "Unexpected error while in status polling loop. Error: ")

    def test_format_trading_rules_success(self):
        instrument_info: List[Dict[str, Any]] = [{
            "symbol": f"{self.base_asset}_{self.quote_asset}",
            "price_scale": 3,
            "quantity_scale": 3,
            "min_amount": "1",
        }]

        result: List[str, TradingRule] = self.exchange._format_trading_rules(instrument_info)
        self.assertTrue(self.trading_pair == result[0].trading_pair)

    def test_format_trading_rules_failure(self):
        # Simulate invalid API response
        instrument_info: List[Dict[str, Any]] = [{}]

        result: Dict[str, TradingRule] = self.exchange._format_trading_rules(instrument_info)
        self.assertTrue(self.trading_pair not in result)
        self.assertTrue(self._is_logged("ERROR", 'Error parsing the trading pair rule {}. Skipping.'))

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.current_timestamp", new_callable=PropertyMock)
    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_update_trading_rules(self, mock_api, mock_ts):
        mock_response = {
            "code": 200,
            "data": [
                {
                    "symbol": "MX_USDT",
                    "state": "ENABLED",
                    "price_scale": 4,
                    "quantity_scale": 2,
                    "min_amount": "5",
                    "max_amount": "5000000",
                    "maker_fee_rate": "0.002",
                    "taker_fee_rate": "0.002",
                    "limited": False,
                    "etf_mark": 0,
                    "symbol_partition": "MAIN"
                }
            ]
        }
        self.exchange._last_poll_timestamp = 10
        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts

        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response, "")

        task = asyncio.get_event_loop().create_task(
            self.exchange._update_trading_rules()
        )
        self.async_run_with_timeout(task)

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)

        self.exchange.trading_rules[self.trading_pair]

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._update_trading_rules",
           new_callable=AsyncMock)
    def test_trading_rules_polling_loop(self, mock_update):
        # No Side Effects expected
        mock_update.return_value = None
        with self.assertRaises(asyncio.TimeoutError):
            self.exchange_task = asyncio.get_event_loop().create_task(self.exchange._trading_rules_polling_loop())

            self.async_run_with_timeout(
                asyncio.wait_for(self.exchange_task, 1.0)
            )

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._update_trading_rules",
           new_callable=AsyncMock)
    def test_trading_rules_polling_loop_cancels(self, mock_update):
        mock_update.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.exchange_task = asyncio.get_event_loop().create_task(
                self.exchange._trading_rules_polling_loop()
            )

            self.async_run_with_timeout(self.exchange_task)

        self.assertEqual(0, self.exchange._last_poll_timestamp)

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange._update_trading_rules",
           new_callable=AsyncMock)
    def test_trading_rules_polling_loop_exception_raised(self, mock_update):
        mock_update.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._trading_rules_polling_loop()
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self._is_logged("ERROR", "Unexpected error while fetching trading rules. Error: ")

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_check_network_succeeds_when_ping_replies_pong(self, mock_api):
        mock_response = {"code": 200}
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response, "")

        result = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, result)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_check_network_fails_when_ping_does_not_reply_pong(self, mock_api):
        mock_response = {"code": 100}
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response, "")

        result = self.async_run_with_timeout(self.exchange.check_network())
        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

        mock_response = {}
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response, "")

        result = self.async_run_with_timeout(self.exchange.check_network())
        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_check_network_fails_when_ping_returns_error_code(self, mock_api):
        mock_response = {"code": 200}
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 404, mock_response, "")

        result = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    def test_get_order_book_for_valid_trading_pair(self):
        dummy_order_book = MexcOrderBook()
        self.exchange._order_book_tracker.order_books["BTC-USDT"] = dummy_order_book
        self.assertEqual(dummy_order_book, self.exchange.get_order_book("BTC-USDT"))

    def test_get_order_book_for_invalid_trading_pair_raises_error(self):
        self.assertRaisesRegex(ValueError,
                               "No order book exists for 'BTC-USDT'",
                               self.exchange.get_order_book,
                               "BTC-USDT")

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.execute_buy", new_callable=AsyncMock)
    def test_buy(self, mock_create):
        mock_create.side_effect = None
        order_details = [
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        # Note: BUY simply returns immediately with the client order id.
        order_id: str = self.exchange.buy(*order_details)

        # Order ID is simply a timestamp. The assertion below checks if it is created within 1 sec
        self.assertTrue(len(order_id) > 0)

    def test_sell(self):
        order_details = [
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        # Note: SELL simply returns immediately with the client order id.
        order_id: str = self.exchange.buy(*order_details)

        # Order ID is simply a timestamp. The assertion below checks if it is created within 1 sec
        self.assertTrue(len(order_id) > 0)

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.quantize_order_amount")
    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_create_limit_order(self, mock_post, amount_mock):
        amount_mock.return_value = Decimal("1")
        expected_response = {"code": 200, "data": "123"}
        self.mocking_assistant.configure_http_request_mock(mock_post)
        self.mocking_assistant.add_http_response(mock_post, 200, expected_response, "")

        self._simulate_trading_rules_initialized()

        order_details = [
            TradeType.BUY,
            str(1),
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        future = self._simulate_create_order(*order_details)
        self.async_run_with_timeout(future)

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self._is_logged("INFO",
                        f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {123} for {Decimal(1.0)} {self.trading_pair}")

        tracked_order: MexcInFlightOrder = self.exchange.in_flight_orders["1"]
        self.assertEqual(tracked_order.client_order_id, "1")
        self.assertEqual(tracked_order.exchange_order_id, "123")
        self.assertEqual(tracked_order.last_state, "NEW")
        self.assertEqual(tracked_order.trading_pair, self.trading_pair)
        self.assertEqual(tracked_order.price, Decimal(10.0))
        self.assertEqual(tracked_order.amount, Decimal(1.0))
        self.assertEqual(tracked_order.trade_type, TradeType.BUY)

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.quantize_order_amount")
    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_create_market_order(self, mock_post, amount_mock):
        amount_mock.return_value = Decimal("1")
        expected_response = {"code": 200, "data": "123"}
        self.mocking_assistant.configure_http_request_mock(mock_post)
        self.mocking_assistant.add_http_response(mock_post, 200, expected_response, "")

        self._simulate_trading_rules_initialized()

        order_details = [
            TradeType.BUY,
            str(1),
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT_MAKER,
        ]

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        future = self._simulate_create_order(*order_details)
        self.async_run_with_timeout(future)

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self._is_logged("INFO",
                        f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {123} for {Decimal(1.0)} {self.trading_pair}")

        tracked_order: MexcInFlightOrder = self.exchange.in_flight_orders["1"]
        self.assertEqual(tracked_order.client_order_id, "1")
        self.assertEqual(tracked_order.exchange_order_id, "123")
        self.assertEqual(tracked_order.last_state, "NEW")
        self.assertEqual(tracked_order.trading_pair, self.trading_pair)
        self.assertEqual(tracked_order.amount, Decimal(1.0))
        self.assertEqual(tracked_order.trade_type, TradeType.BUY)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_detect_created_order_server_acknowledgement(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.mocking_assistant.add_http_response(mock_api, 200, self.balances_mock_data, self.balances_mock_data)

        self.exchange.start_tracking_order(order_id="sell-MX-USDT-1638156451005305",
                                           exchange_order_id="40728558ead64032a676e6f0a4afc4ca",
                                           trading_pair="MX-USDT",
                                           trade_type=TradeType.SELL,
                                           price=Decimal("3.1504"),
                                           amount=Decimal("6.3008"),
                                           order_type=OrderType.LIMIT)
        _user_data = self.user_stream_data
        _user_data.get("data")["status"] = 2
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: _user_data)
        self.exchange._user_stream_tracker._user_stream = mock_user_stream
        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        tracked_order: MexcInFlightOrder = self.exchange.in_flight_orders["sell-MX-USDT-1638156451005305"]
        self.assertEqual(tracked_order.last_state, "NEW")

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.quantize_order_amount")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_create_order_below_min_order_size_exception_raised(self, mock_main_app, amount_mock):
        amount_mock.return_value = Decimal("1")
        self._simulate_trading_rules_initialized()

        order_details = [
            str(1),
            self.trading_pair,
            Decimal(1.0),
            OrderType.LIMIT_MAKER,
            Decimal(10.0),
        ]

        self.assertEqual(0, len(self.exchange.in_flight_orders))

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange.execute_buy(*order_details)
        )

        self.async_run_with_timeout(self.exchange_task)

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        self._is_logged("NETWORK", "Error submitting buy limit_maker order to Mexc for 1 MX-USDT "
                                   ".10.0000.OSError(\"Error request from https://www.mexc.com/open/api/v2/order/place?"
                                   "api_key=testAPIKey&req_time=1638244964&sign=7c9b991595d647c326685680fef3f26b5b273527"
                                   "bd9180fe92d080d74b917231. Response: {'msg': 'invalid api_key', 'code': 400}.\")")

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_execute_cancel_success(self, mock_cancel):
        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0),
            initial_state="Working",
        )

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        mock_response = {
            "code": 200,
            "data": {"123": "success"}
        }

        self.mocking_assistant.configure_http_request_mock(mock_cancel)
        self.mocking_assistant.add_http_response(mock_cancel, 200, mock_response, "")

        result = self.async_run_with_timeout(
            self.exchange.execute_cancel(self.trading_pair, order.client_order_id)
        )
        self.assertIsNone(result)

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_execute_cancel_all_success(self, mock_post_request):
        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        mock_response = {
            "code": 200,
            "data": {
                "0": "success"
            }
        }
        self.mocking_assistant.configure_http_request_mock(mock_post_request)
        self.mocking_assistant.add_http_response(mock_post_request, 200, mock_response, "")

        cancellation_results = self.async_run_with_timeout(
            self.exchange.cancel_all(10)
        )

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("0", cancellation_results[0].order_id)
        self.assertTrue(cancellation_results[0].success)

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_execute_cancel_fail(self, mock_cancel, mock_main_app):
        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0),
            initial_state="Working",
        )

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })
        mock_response = {
            "code": 100,
            "data": {"123": "success"}
        }

        self.mocking_assistant.configure_http_request_mock(mock_cancel)
        self.mocking_assistant.add_http_response(mock_cancel, 200, mock_response, "")

        self.async_run_with_timeout(
            self.exchange.execute_cancel(self.trading_pair, order.client_order_id)
        )

        self._is_logged("NETWORK", "Failed to cancel order 0 : MexcAPIError('Order could not be canceled')")

    @patch("aiohttp.ClientSession.request", new_callable=AsyncMock)
    def test_execute_cancel_cancels(self, mock_cancel):
        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0),
            initial_state="Working",
        )

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        mock_cancel.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.exchange.execute_cancel(self.trading_pair, order.client_order_id)
            )

    @patch("hummingbot.connector.exchange.mexc.mexc_exchange.MexcExchange.execute_cancel", new_callable=AsyncMock)
    def test_cancel(self, mock_cancel):
        mock_cancel.return_value = None

        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        # Note: BUY simply returns immediately with the client order id.
        return_val: str = self.exchange.cancel(self.trading_pair, order.client_order_id)

        # Order ID is simply a timestamp. The assertion below checks if it is created within 1 sec
        self.assertTrue(order.client_order_id, return_val)

    def test_ready_trading_required_all_ready(self):
        self.exchange._trading_required = True

        # Simulate all components initialized
        self.exchange._account_id = 1
        self.exchange._order_book_tracker._order_books_initialized.set()
        self.exchange._account_balances = {
            self.base_asset: Decimal(str(10.0))
        }
        self._simulate_trading_rules_initialized()
        self.exchange._user_stream_tracker.data_source._last_recv_time = 1

        self.assertTrue(self.exchange.ready)

    def test_ready_trading_required_not_ready(self):
        self.exchange._trading_required = True

        # Simulate all components but account_id not initialized
        self.exchange._account_id = None
        self.exchange._order_book_tracker._order_books_initialized.set()
        self.exchange._account_balances = {}
        self._simulate_trading_rules_initialized()
        self.exchange._user_stream_tracker.data_source._last_recv_time = 0

        self.assertFalse(self.exchange.ready)

    def test_ready_trading_not_required_ready(self):
        self.exchange._trading_required = False

        # Simulate all components but account_id not initialized
        self.exchange._account_id = None
        self.exchange._order_book_tracker._order_books_initialized.set()
        self.exchange._account_balances = {}
        self._simulate_trading_rules_initialized()
        self.exchange._user_stream_tracker.data_source._last_recv_time = 0

        self.assertTrue(self.exchange.ready)

    def test_ready_trading_not_required_not_ready(self):
        self.exchange._trading_required = False
        self.assertFalse(self.exchange.ready)

    def test_limit_orders(self):
        self.assertEqual(0, len(self.exchange.limit_orders))

        # Simulate orders being placed and tracked
        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        self.assertEqual(1, len(self.exchange.limit_orders))

    def test_tracking_states_order_not_done(self):
        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        order_json = order.to_json()

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        self.assertEqual(1, len(self.exchange.tracking_states))
        self.assertEqual(order_json, self.exchange.tracking_states[order.client_order_id])

    def test_tracking_states_order_done(self):
        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0),
            initial_state="FILLED"
        )

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        self.assertEqual(0, len(self.exchange.tracking_states))

    def test_restore_tracking_states(self):
        order: MexcInFlightOrder = MexcInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        order_json = order.to_json()

        self.exchange.restore_tracking_states({order.client_order_id: order_json})

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertEqual(str(self.exchange.in_flight_orders[order.client_order_id]), str(order))
