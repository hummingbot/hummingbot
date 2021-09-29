import asyncio
import json
import re
import pandas as pd

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils as bybit_utils

from aioresponses import aioresponses
from collections import deque
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch, AsyncMock

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import BybitPerpetualAPIOrderBookDataSource
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BybitPerpetualAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.domain = "bybit_perpetual_testnet"

        self.log_records = []
        self.listening_task = None

        self.data_source = BybitPerpetualAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                                domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._trading_pair_symbol_map = {}

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    @aioresponses()
    def test_get_trading_pair_symbols(self, mock_get):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_SYMBOL_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "name": "EOSUSD",
                    "alias": "EOSUSD",
                    "status": "Closed",
                    "base_currency": "EOS",
                    "quote_currency": "USD",
                    "price_scale": 3,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 50,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.001",
                        "max_price": "1999.999",
                        "tick_size": "0.001"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                },
                {
                    "name": "BTCUSD",
                    "alias": "BTCUSD",
                    "status": "Trading",
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                },
                {
                    "name": "BTCUSDT",
                    "alias": "BTCUSDT",
                    "status": "Trading",
                    "base_currency": "BTC",
                    "quote_currency": "USDT",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 100,
                        "min_trading_qty": 0.001,
                        "qty_step": 0.001
                    }
                },
                {
                    "name": "BTCUSDM21",
                    "alias": "BTCUSD0625",
                    "status": "Trading",
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                }
            ],
            "time_now": "1615801223.589808"
        }
        mock_get.get(regex_url, body=json.dumps(mock_response))

        symbols_map = asyncio.get_event_loop().run_until_complete(self.data_source.trading_pair_symbol_map(domain=self.domain))

        self.assertEqual(1, len(symbols_map))
        self.assertEqual("BTC-USDT", symbols_map["BTCUSDT"])

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_get):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_SYMBOL_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "name": "EOSUSD",
                    "alias": "EOSUSD",
                    "status": "Closed",
                    "base_currency": "EOS",
                    "quote_currency": "USD",
                    "price_scale": 3,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 50,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.001",
                        "max_price": "1999.999",
                        "tick_size": "0.001"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                },
                {
                    "name": "BTCUSD",
                    "alias": "BTCUSD",
                    "status": "Trading",
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                },
                {
                    "name": "BTCUSDT",
                    "alias": "BTCUSDT",
                    "status": "Trading",
                    "base_currency": "BTC",
                    "quote_currency": "USDT",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 100,
                        "min_trading_qty": 0.001,
                        "qty_step": 0.001
                    }
                },
                {
                    "name": "BTCUSDM21",
                    "alias": "BTCUSD0625",
                    "status": "Trading",
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                }
            ],
            "time_now": "1615801223.589808"
        }
        mock_get.get(regex_url, body=json.dumps(mock_response))

        trading_pairs = asyncio.get_event_loop().run_until_complete(self.data_source.fetch_trading_pairs(domain=self.domain))

        self.assertEqual(1, len(trading_pairs))
        self.assertEqual("BTC-USDT", trading_pairs[0])

    @aioresponses()
    def test_get_last_traded_prices_requests_rest_api_price_when_subscription_price_not_available(self, mock_get):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "symbol": "BTCUSDT",
                    "bid_price": "7230",
                    "ask_price": "7230.5",
                    "last_price": "7230.00",
                    "last_tick_direction": "ZeroMinusTick",
                    "prev_price_24h": "7163.00",
                    "price_24h_pcnt": "0.009353",
                    "high_price_24h": "7267.50",
                    "low_price_24h": "7067.00",
                    "prev_price_1h": "7209.50",
                    "price_1h_pcnt": "0.002843",
                    "mark_price": "7230.31",
                    "index_price": "7230.14",
                    "open_interest": 117860186,
                    "open_value": "16157.26",
                    "total_turnover": "3412874.21",
                    "turnover_24h": "10864.63",
                    "total_volume": 28291403954,
                    "volume_24h": 78053288,
                    "funding_rate": "0.0001",
                    "predicted_funding_rate": "0.0001",
                    "next_funding_time": "2019-12-28T00:00:00Z",
                    "countdown_hour": 2,
                    "delivery_fee_rate": "0",
                    "predicted_delivery_price": "0.00",
                    "delivery_time": ""
                }
            ],
            "time_now": "1577484619.817968"
        }
        mock_get.get(regex_url, body=json.dumps(mock_response))

        results = asyncio.get_event_loop().run_until_complete(
            self.data_source.get_last_traded_prices([self.trading_pair], domain=self.domain))

        self.assertEqual(results[self.trading_pair], float(mock_response["result"][0]["last_price"]))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_registers_to_orders_trades_and_instruments(self, ws_connect_mock):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        task = asyncio.get_event_loop().create_task(self.data_source.listen_for_subscriptions())
        # Add message to be processed after subscriptions, to unlock the test
        self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, {"topic": "test_topic.BTCUSDT"})
        # Lock the test to let the async task run
        received_messages_queue = self.data_source._messages_queues["test_topic"]
        asyncio.get_event_loop().run_until_complete(received_messages_queue.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(3, len(sent_messages))
        expected_orders_subscription = {'op': 'subscribe', 'args': ['orderBook_200.100ms.BTCUSDT']}
        expected_trades_subscription = {'op': 'subscribe', 'args': ['trade.BTCUSDT']}
        expected_instruments_subscription = {'op': 'subscribe', 'args': ['instrument_info.100ms.BTCUSDT']}
        self.assertEqual(expected_orders_subscription, sent_messages[0])
        self.assertEqual(expected_trades_subscription, sent_messages[1])
        self.assertEqual(expected_instruments_subscription, sent_messages[2])

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_raises_cancel_exceptions(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = asyncio.get_event_loop().create_task(self.data_source.listen_for_subscriptions())

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task.cancel()
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_raises_cancel_exception_when_canceled_during_ws_connection(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError()

        self.listening_task = asyncio.get_event_loop().create_task(self.data_source.listen_for_subscriptions())

        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_ws_connection_exception_details_are_logged(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception()

        self.listening_task = asyncio.get_event_loop().create_task(self.data_source.listen_for_subscriptions())
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occurred during bybit_perpetual WebSocket Connection ()"))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exceptions_details(self, ws_connect_mock):
        sync_queue = asyncio.Queue()

        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}
        websocket_mock = self.mocking_assistant.create_websocket_mock()
        websocket_mock.receive_json.side_effect = Exception()
        websocket_mock.close.side_effect = lambda: sync_queue.put_nowait(1)
        ws_connect_mock.return_value = websocket_mock

        self.listening_task = asyncio.get_event_loop().create_task(self.data_source.listen_for_subscriptions())
        # Block the test until the subscription function advances
        asyncio.get_event_loop().run_until_complete(sync_queue.get())

        try:
            self.listening_task.cancel()
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(
            self._is_logged("NETWORK",
                            "Unexpected error with WebSocket connection on wss://stream-testnet.bybit.com/realtime_public ()"))

    def test_listen_for_trades(self, ):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}

        trades_queue = asyncio.Queue()

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_TRADES_TOPIC]
        data_source_queue.put_nowait({'topic': 'trade.BTCUSDT',
                                      'data': [{'trade_time_ms': 1628618168965,
                                                'timestamp': '2021-08-10T17:56:08.000Z',
                                                'symbol': 'BTCUSDT',
                                                'side': 'Buy',
                                                'size': 5,
                                                'price': 45011,
                                                'tick_direction': 'PlusTick',
                                                'trade_id': '6b78ccb1-b967-5b55-b237-025f8ce38f3f',
                                                'cross_seq': 8926514939},
                                               {'trade_time_ms': 1628618168987,
                                                'timestamp': '2021-08-10T17:56:08.000Z',
                                                'symbol': 'BTCUSDT',
                                                'side': 'Sell',
                                                'size': 1,
                                                'price': 45010.5,
                                                'tick_direction': 'MinusTick',
                                                'trade_id': '1cab862b-1682-597d-96fc-d31cbbe28981',
                                                'cross_seq': 8926514939}
                                               ]})

        # Lock the test to let the async task run
        first_trade = asyncio.get_event_loop().run_until_complete(trades_queue.get())
        second_trade = asyncio.get_event_loop().run_until_complete(trades_queue.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(trades_queue.empty())
        self.assertEqual("6b78ccb1-b967-5b55-b237-025f8ce38f3f", first_trade.trade_id)
        self.assertEqual("1cab862b-1682-597d-96fc-d31cbbe28981", second_trade.trade_id)

    def test_listen_for_trades_raises_cancel_exceptions(self):
        trades_queue = asyncio.Queue()
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

    def test_listen_for_trades_logs_exception_details(self, ):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}

        trades_queue = asyncio.Queue()

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_TRADES_TOPIC]
        # Add an invalid message to trigger the excepton, and a valid one to unlock the test process.
        data_source_queue.put_nowait({})
        data_source_queue.put_nowait({'topic': 'trade.BTCUSDT',
                                      'data': [{'trade_time_ms': 1628618168965,
                                                'timestamp': '2021-08-10T17:56:08.000Z',
                                                'symbol': 'BTCUSDT',
                                                'side': 'Buy',
                                                'size': 5,
                                                'price': 45011,
                                                'tick_direction': 'PlusTick',
                                                'trade_id': '6b78ccb1-b967-5b55-b237-025f8ce38f3f',
                                                'cross_seq': 8926514939}]})

        asyncio.get_event_loop().run_until_complete(trades_queue.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(self._is_logged("ERROR", "Unexpected error ('data')"))

    def test_listen_for_order_book_snapshot_event(self, ):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSD": "BTC-USD"}}

        order_book_messages = asyncio.Queue()

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=order_book_messages))

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC]
        data_source_queue.put_nowait({'topic': 'orderBook_200.100ms.BTCUSD',
                                      'type': 'snapshot',
                                      'data': [
                                          {'price': '46272.00',
                                           'symbol': 'BTCUSD',
                                           'id': 462720000,
                                           'side': 'Buy',
                                           'size': 2},
                                          {'price': '46380.00',
                                           'symbol': 'BTCUSD',
                                           'id': 463800000,
                                           'side': 'Sell',
                                           'size': 89041}],
                                      'cross_seq': 8945092523,
                                      'timestamp_e6': "1628703196211205"})

        # Lock the test to let the async task run
        order_book_message = asyncio.get_event_loop().run_until_complete(order_book_messages.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(order_book_messages.empty())
        self.assertEqual(1628703196211205, order_book_message.update_id)
        self.assertEqual(1628703196211205 * 1e-6, order_book_message.timestamp)
        self.assertEqual(46272.00, order_book_message.bids[0].price)
        self.assertEqual(46380.0, order_book_message.asks[0].price)

    def test_listen_for_order_book_diff_event(self, ):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSD": "BTC-USD"}}

        order_book_messages = asyncio.Queue()

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=order_book_messages))

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC]
        data_source_queue.put_nowait({'topic': 'orderBook_200.100ms.BTCUSD',
                                      'type': 'delta',
                                      'data':
                                          {
                                              'delete': [
                                                  {'price': '46331.00',
                                                   'symbol': 'BTCUSD',
                                                   'id': 463310000,
                                                   'side': 'Sell'}],
                                              'update': [
                                                  {'price': '46181.00',
                                                   'symbol': 'BTCUSD',
                                                   'id': 461810000,
                                                   'side': 'Buy',
                                                   'size': 2928}],
                                              'insert': [
                                                  {'price': '46332.50',
                                                   'symbol': 'BTCUSD',
                                                   'id': 463325000,
                                                   'side': 'Sell',
                                                   'size': 153}],
                                              'transactTimeE6': 0},
                                      'cross_seq': 8946119966,
                                      'timestamp_e6': 1628709816411166})

        # Lock the test to let the async task run
        order_book_message = asyncio.get_event_loop().run_until_complete(order_book_messages.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(order_book_messages.empty())
        self.assertEqual(1628709816411166, order_book_message.update_id)
        self.assertEqual(1628709816411166 * 1e-6, order_book_message.timestamp)
        self.assertEqual(46181.0, order_book_message.bids[0].price)
        self.assertEqual(46331.0, order_book_message.asks[0].price)
        self.assertEqual(46332.5, order_book_message.asks[1].price)

    def test_listen_for_order_book_diff_raises_cancel_exceptions(self):
        trades_queue = asyncio.Queue()
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

    def test_listen_for_order_book_diff_logs_exception_details(self, ):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSD": "BTC-USD"}}

        order_book_messages = asyncio.Queue()

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=order_book_messages))

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC]
        # Add an invalid message to trigger the excepton, and a valid one to unlock the test process.
        data_source_queue.put_nowait({})
        data_source_queue.put_nowait({'topic': 'orderBook_200.100ms.BTCUSD',
                                      'type': 'snapshot',
                                      'data': [
                                          {'price': '46272.00',
                                           'symbol': 'BTCUSD',
                                           'id': 462720000,
                                           'side': 'Buy',
                                           'size': 2}],
                                      'cross_seq': 8945092523,
                                      'timestamp_e6': 1628703196211205})

        asyncio.get_event_loop().run_until_complete(order_book_messages.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(self._is_logged("ERROR", "Unexpected error ('topic')"))

    def test_listen_for_instruments_info_snapshot_event_trading_info_does_not_exist(self):
        BybitPerpetualAPIOrderBookDataSource._last_traded_prices = {self.domain: {"BTC-USDT": 0.0}}

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_instruments_info())

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC]
        data_source_queue.put_nowait({'topic': 'instrument_info.100ms.BTCUSDT',
                                      'type': 'snapshot',
                                      'data': {
                                          'id': 1,
                                          'symbol': 'BTCUSDT',
                                          'last_price_e4': 463550000,
                                          'last_price': '46355.00',
                                          'bid1_price_e4': 463545000,
                                          'bid1_price': '46354.50',
                                          'ask1_price_e4': 463550000,
                                          'ask1_price': '46355.00',
                                          'mark_price': 50147.03,
                                          'index_price': 50147.08,
                                          'predicted_funding_rate_e6': -15,
                                          'next_funding_time': '2021-08-23T08:00:00Z',
                                      },
                                      'cross_seq': 8946315343,
                                      'timestamp_e6': 1628711274147854})

        # Lock the test to let the async task run
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
        last_traded_prices = asyncio.get_event_loop().run_until_complete(
            BybitPerpetualAPIOrderBookDataSource.get_last_traded_prices(["BTC-USDT"], domain=self.domain))
        funding_info = asyncio.get_event_loop().run_until_complete(
            self.data_source.get_funding_info("BTC-USDT"))

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertEqual(46355.0, last_traded_prices["BTC-USDT"])
        self.assertEqual(Decimal('50147.03'), funding_info.mark_price)
        self.assertEqual(Decimal('50147.08'), funding_info.index_price)
        self.assertEqual((Decimal('-15') * Decimal(1e-6)), funding_info.rate)
        self.assertEqual(int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()), funding_info.next_funding_utc_timestamp)

    def test_listen_for_instruments_info_delta_event(self):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSD": "BTC-USD"}}
        BybitPerpetualAPIOrderBookDataSource._last_traded_prices = {self.domain: {"BTC-USD": 0.0}}
        self.data_source._funding_info = {
            "BTC-USD": FundingInfo(
                trading_pair="BTC-USD",
                index_price=Decimal("50000"),
                mark_price=Decimal("50000"),
                next_funding_utc_timestamp=int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()),
                rate=(Decimal('-15') * Decimal(1e-6)),
            )
        }

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_instruments_info())

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC]
        # Add an instrument info message without las traded price that should be ignored
        data_source_queue.put_nowait({'topic': 'instrument_info.100ms.BTCUSD',
                                      'type': 'delta',
                                      'data': {
                                          'delete': [],
                                          'update': [{
                                              'id': 1,
                                              'symbol': 'BTCUSD',
                                              'last_tick_direction': 'MinusTick'}],
                                          'insert': []},
                                      'cross_seq': 8946315837,
                                      'timestamp_e6': 1628711277742874})
        # And one with last traded price that should be processed
        data_source_queue.put_nowait({'topic': 'instrument_info.100ms.BTCUSD',
                                      'type': 'delta',
                                      'data': {
                                          'delete': [],
                                          'update': [{
                                              'id': 1,
                                              'symbol': 'BTCUSD',
                                              'last_price_e4': 463545000,
                                              'last_price': '46354.50',
                                              'last_tick_direction': 'MinusTick'}],
                                          'insert': []},
                                      'cross_seq': 8946315838,
                                      'timestamp_e6': 1628711277743874})
        # Update message with updated predicted_funding_rate
        data_source_queue.put_nowait({'topic': 'instrument_info.100ms.BTCUSD',
                                      'type': 'delta',
                                      'data': {
                                          'update': [
                                              {
                                                  'id': 1,
                                                  'symbol': 'BTCUSD',
                                                  'predicted_funding_rate_e6': '-347',
                                                  'cross_seq': '7085522375',
                                                  'created_at': '1970-01-01T00:00:00.000Z',
                                                  'updated_at': '2021-08-23T07:58:07.000Z'
                                              }
                                          ]
                                      },
                                      'cross_seq': '7085522444',
                                      'timestamp_e6': '1629705487804991'
                                      }
                                     )
        # Update message with updated index and mark price
        data_source_queue.put_nowait({'topic': 'instrument_info.100ms.BTCUSD',
                                      'type': 'delta',
                                      'data': {
                                          'update': [
                                              {
                                                  'id': 1,
                                                  'symbol': 'BTCUSD',
                                                  'mark_price_e4': '501353600',
                                                  'mark_price': '50135.36',
                                                  'index_price_e4': '501303500',
                                                  'index_price': '50130.35',
                                                  'cross_seq': '7085530086',
                                                  'created_at': '1970-01-01T00:00:00.000Z',
                                                  'updated_at': '2021-08-23T07:59:58.000Z'
                                              }
                                          ]
                                      },
                                      'cross_seq': '7085530240',
                                      'timestamp_e6': '1629705601304084'
                                      })
        # Update message with updated index and next_funding_timestamp
        data_source_queue.put_nowait({'topic': 'instrument_info.100ms.BTCUSD',
                                      'type': 'delta',
                                      'data': {
                                          'update': [
                                              {
                                                  'id': 1,
                                                  'symbol': 'BTCUSD',
                                                  'index_price_e4': '501313400',
                                                  'index_price': '50131.34',
                                                  'total_turnover_e8': '-8861738985507851616',
                                                  'turnover_24h_e8': '277455604387899960',
                                                  'total_volume_e8': '1458835785899924',
                                                  'volume_24h_e8': '5640266599999',
                                                  'cross_seq': '7085530253',
                                                  'created_at': '1970-01-01T00:00:00.000Z',
                                                  'updated_at': '2021-08-23T08:00:01.000Z',
                                                  'next_funding_time': '2021-08-23T16:00:00Z',
                                                  'count_down_hour': '8'
                                              }
                                          ]
                                      },
                                      'cross_seq': '7085530254',
                                      'timestamp_e6': '1629705602003689'
                                      })

        # Lock the test to let the async task run
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
        last_traded_prices = asyncio.get_event_loop().run_until_complete(
            BybitPerpetualAPIOrderBookDataSource.get_last_traded_prices(["BTC-USD"], domain=self.domain))
        funding_info = asyncio.get_event_loop().run_until_complete(
            self.data_source.get_funding_info("BTC-USD"))
        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertEqual(0, data_source_queue.qsize())
        self.assertEqual(46354.5, last_traded_prices["BTC-USD"])
        self.assertEqual(Decimal('50135.36'), funding_info.mark_price)
        self.assertEqual(Decimal('50131.34'), funding_info.index_price)
        self.assertEqual((Decimal('-347') * Decimal(1e-6)), funding_info.rate)
        self.assertEqual(int(pd.Timestamp('2021-08-23T16:00:00Z', tz="UTC").timestamp()), funding_info.next_funding_utc_timestamp)

    @aioresponses()
    def test_listen_for_instruments_info_delta_event_trading_info_does_not_exist(self, mock_get):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}

        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                # Truncated Response
                {
                    "symbol": "BTCUSDT",
                    "mark_price": "50000",
                    "index_price": "50000",
                    "funding_rate": "-15",
                    "predicted_funding_rate": "-15",
                    "next_funding_time": "2021-08-23T08:00:00Z",
                }
            ],
            "time_now": "1577484619.817968"
        }
        mock_get.get(regex_url, body=json.dumps(mock_response))

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_instruments_info())

        # Add message queue to be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC]

        # Update message with updated predicted_funding_rate
        data_source_queue.put_nowait({'topic': 'instrument_info.100ms.BTCUSDT',
                                      'type': 'delta',
                                      'data': {
                                          'update': [
                                              {
                                                  'id': 1,
                                                  'symbol': 'BTCUSDT',
                                                  'predicted_funding_rate_e6': '-347',
                                                  'cross_seq': '7085522375',
                                                  'created_at': '1970-01-01T00:00:00.000Z',
                                                  'updated_at': '2021-08-23T07:58:07.000Z'
                                              }
                                          ]
                                      },
                                      'cross_seq': '7085522444',
                                      'timestamp_e6': '1629705487804991'
                                      }
                                     )

        # Lock the test to let the async task run
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
        funding_info = asyncio.get_event_loop().run_until_complete(
            self.data_source.get_funding_info("BTC-USDT"))
        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertEqual(Decimal('50000'), funding_info.mark_price)
        self.assertEqual(Decimal('50000'), funding_info.index_price)
        # Note: Only funding rate is updated.
        self.assertEqual((Decimal('-347') * Decimal(1e-6)), funding_info.rate)
        self.assertEqual(int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()), funding_info.next_funding_utc_timestamp)

    def test_listen_for_instruments_info_raises_cancel_exceptions(self):
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_instruments_info())

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

    def test_listen_for_instruments_info_logs_exception_details(self, ):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_instruments_info())

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC]
        # Add an invalid message to trigger the excepton
        data_source_queue.put_nowait({})

        asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(self._is_logged("ERROR", "Unexpected error ('topic')"))

    @aioresponses()
    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source.BybitPerpetualAPIOrderBookDataSource._sleep",
           new_callable=AsyncMock)
    def test_listen_for_snapshots_successful(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)
        sync_queue.append(2)

        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSD": "BTC-USDT"}}

        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.ORDER_BOOK_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "symbol": "BTCUSDT",
                    "price": "9487",
                    "size": 336241,
                    "side": "Buy"
                },
                {
                    "symbol": "BTCUSDT",
                    "price": "9487.5",
                    "size": 522147,
                    "side": "Sell"
                }
            ],
            "time_now": "1567108756.834357"
        }
        mock_get.get(regex_url, body=json.dumps(mock_response))

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_order_book_snapshots(asyncio.get_event_loop(), msg_queue))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

        self.assertEqual(1, msg_queue.qsize())

        snapshot_msg: OrderBookMessage = msg_queue.get_nowait()
        self.assertEqual(1567108756834357, snapshot_msg.update_id)
        self.assertEqual(self.trading_pair, snapshot_msg.trading_pair)
        self.assertEqual(9487, snapshot_msg.bids[0].price)
        self.assertEqual(9487.5, snapshot_msg.asks[0].price)

    @aioresponses()
    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source.BybitPerpetualAPIOrderBookDataSource._sleep",
           new_callable=AsyncMock)
    def test_listen_for_snapshots_for_unknown_pair_fails(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)
        sync_queue.append(2)

        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"UNKNOWN": "UNK-NOWN"}}

        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.ORDER_BOOK_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        mock_get.get(regex_url)

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_order_book_snapshots(asyncio.get_event_loop(), msg_queue))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

        self.assertEqual(0, msg_queue.qsize())

        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error occurred listening for orderbook snapshots."
                                        " Retrying in 5 secs. (There is no symbol mapping for trading pair BTC-USDT)"))

    @aioresponses()
    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source.BybitPerpetualAPIOrderBookDataSource._sleep",
           new_callable=AsyncMock)
    def test_listen_for_snapshots_fails_when_api_request_fails(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)
        sync_queue.append(2)

        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}

        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.ORDER_BOOK_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        mock_get.get(regex_url, status=405, body=json.dumps({}))

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_order_book_snapshots(asyncio.get_event_loop(), msg_queue))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

        self.assertEqual(0, msg_queue.qsize())

        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error occurred listening for orderbook snapshots."
                                        f" Retrying in 5 secs. (Error fetching OrderBook for {self.trading_pair} "
                                        "at https://api-testnet.bybit.com/v2/public/orderBook/L2. "
                                        f"HTTP 405. Response: {dict()})"))

    def test_listen_for_snapshots_raises_cancel_exceptions(self):
        trades_queue = asyncio.Queue()
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

    @aioresponses()
    def test_get_new_order_book(self, mock_get):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSD": "BTC-USDT"}}

        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.ORDER_BOOK_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "symbol": "BTCUSDT",
                    "price": "9487",
                    "size": 336241,
                    "side": "Buy"
                },
                {
                    "symbol": "BTCUSDT",
                    "price": "9487.5",
                    "size": 522147,
                    "side": "Sell"
                }
            ],
            "time_now": "1567108756.834357"
        }
        mock_get.get(regex_url, body=json.dumps(mock_response))

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.get_new_order_book(self.trading_pair))
        order_book = asyncio.get_event_loop().run_until_complete(self.listening_task)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())

        self.assertEqual(1, len(bids))
        self.assertEqual(9487.0, bids[0].price)
        self.assertEqual(336241, bids[0].amount)
        self.assertEqual(1567108756834357, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(9487.5, asks[0].price)
        self.assertEqual(522147, asks[0].amount)
        self.assertEqual(1567108756834357, asks[0].update_id)

    def test_get_funding_info_trading_pair_exist(self):
        self.data_source._funding_info = {
            "BTC-USD": FundingInfo(
                trading_pair="BTC-USD",
                index_price=Decimal("50000"),
                mark_price=Decimal("50000"),
                next_funding_utc_timestamp=int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()),
                rate=(Decimal('-15') * Decimal(1e-6)),
            )
        }
        task = asyncio.get_event_loop().create_task(
            self.data_source.get_funding_info("BTC-USD"))

        funding_info = asyncio.get_event_loop().run_until_complete(task)

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertEqual(Decimal('50000'), funding_info.mark_price)
        self.assertEqual(Decimal('50000'), funding_info.index_price)
        self.assertEqual((Decimal('-15') * Decimal(1e-6)), funding_info.rate)
        self.assertEqual(int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()), funding_info.next_funding_utc_timestamp)

    @aioresponses()
    def test_get_funding_info_trading_pair_does_not_exist(self, mock_get):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {self.domain: {"BTCUSDT": "BTC-USDT"}}
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                # Truncated Response
                {
                    "symbol": "BTCUSDT",
                    "mark_price": "50000",
                    "index_price": "50000",
                    "funding_rate": "-15",
                    "predicted_funding_rate": "-15",
                    "next_funding_time": "2021-08-23T08:00:00Z",
                }
            ],
            "time_now": "1577484619.817968"
        }
        mock_get.get(regex_url, body=json.dumps(mock_response))

        funding_info = asyncio.get_event_loop().run_until_complete(
            self.data_source.get_funding_info("BTC-USDT")
        )

        self.assertEqual(Decimal('50000'), funding_info.mark_price)
        self.assertEqual(Decimal('50000'), funding_info.index_price)
        self.assertEqual(Decimal('-15'), funding_info.rate)
        self.assertEqual(int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()), funding_info.next_funding_utc_timestamp)

    def test_funding_info_property(self):
        self.assertEqual(0, len(self.data_source.funding_info))

        expected_funding_info: FundingInfo = FundingInfo(
            trading_pair="BTC-USD",
            index_price=Decimal("50000"),
            mark_price=Decimal("50000"),
            next_funding_utc_timestamp=int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()),
            rate=(Decimal('-15') * Decimal(1e-6)),
        )

        self.data_source._funding_info = {
            "BTC-USD": expected_funding_info
        }

        self.assertEqual(1, len(self.data_source.funding_info))
        self.assertEqual(expected_funding_info.trading_pair, self.data_source.funding_info["BTC-USD"].trading_pair)
        self.assertEqual(expected_funding_info.index_price, self.data_source.funding_info["BTC-USD"].index_price)
        self.assertEqual(expected_funding_info.mark_price, self.data_source.funding_info["BTC-USD"].mark_price)
        self.assertEqual(expected_funding_info.next_funding_utc_timestamp, self.data_source.funding_info["BTC-USD"].next_funding_utc_timestamp)
        self.assertEqual(expected_funding_info.rate, self.data_source.funding_info["BTC-USD"].rate)
