import asyncio
from collections import deque
from unittest import TestCase
from unittest.mock import patch, AsyncMock, PropertyMock

from hummingbot.connector.exchange.bybit import bybit_constants as CONSTANTS
from hummingbot.connector.exchange.bybit.bybit_api_order_book_data_source import BybitAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class AsyncContextMock(AsyncMock):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return


class BybitAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"

        self.api_responses_json: asyncio.Queue = asyncio.Queue()
        self.api_responses_status = deque()
        self.log_records = []
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.listening_task = None

        self.data_source = BybitAPIOrderBookDataSource([self.trading_pair])
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._trading_pair_symbol_map = {}

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _get_next_api_response_status(self):
        status = self.api_responses_status.popleft()
        return status

    async def _get_next_api_response_json(self):
        json = await self.api_responses_json.get()
        return json

    def _configure_mock_api(self, mock_api: AsyncMock):
        response = AsyncMock()
        type(response).status = PropertyMock(side_effect=self._get_next_api_response_status)
        response.json.side_effect = self._get_next_api_response_json
        mock_api.return_value.__aenter__.return_value = response

    async def _get_next_received_message(self, timeout):
        return await self.ws_incoming_messages.get()

    def _create_ws_mock(self):
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: self.ws_sent_messages.append(sent_message)
        ws.receive_json.side_effect = self._get_next_received_message
        return ws

    @patch("aiohttp.ClientSession.get")
    def test_get_trading_pair_symbols(self, mock_get):
        self._configure_mock_api(mock_get)
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
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait(mock_response)

        symbols_map = asyncio.get_event_loop().run_until_complete(self.data_source.trading_pair_symbol_map())

        self.assertEqual(1, len(symbols_map))
        self.assertEqual("BTC-USDT", symbols_map["BTCUSDT"])

    @patch("aiohttp.ClientSession.get")
    def test_fetch_trading_pairs(self, mock_get):
        self._configure_mock_api(mock_get)
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
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
                }
            ],
            "time_now": "1615801223.589808"
        }
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait(mock_response)

        trading_pairs = asyncio.get_event_loop().run_until_complete(self.data_source.fetch_trading_pairs())

        self.assertEqual(1, len(trading_pairs))
        self.assertEqual("BTC-USDT", trading_pairs[0])

    @patch("aiohttp.ClientSession.get")
    def test_get_last_traded_prices_requests_rest_api_price_when_subscription_price_not_available(self, mock_get):
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

        self._configure_mock_api(mock_get)
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
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait(mock_response)

        results = asyncio.get_event_loop().run_until_complete(
            self.data_source.get_last_traded_prices([self.trading_pair]))

        self.assertEqual(results[self.trading_pair], float(mock_response["result"][0]["last_price"]))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_registers_to_orders_trades_and_instruments(self, ws_connect_mock):
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}
        ws_connect_mock.return_value = self._create_ws_mock()

        task = asyncio.get_event_loop().create_task(self.data_source.listen_for_subscriptions())
        # Add message to be processed after subscriptions, to unlock the test
        self.ws_incoming_messages.put_nowait({"topic": "test_topic.BTCUSDT"})
        # Lock the test to let the async task run
        received_messages_queue = self.data_source._messages_queues["test_topic"]
        asyncio.get_event_loop().run_until_complete(received_messages_queue.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertEqual(3, len(self.ws_sent_messages))
        expected_orders_subscription = {'op': 'subscribe', 'args': ['orderBook_200.100ms.BTCUSDT']}
        expected_trades_subscription = {'op': 'subscribe', 'args': ['trade.BTCUSDT']}
        expected_instruments_subscription = {'op': 'subscribe', 'args': ['instrument_info.100ms.BTCUSDT']}
        self.assertEqual(expected_orders_subscription, self.ws_sent_messages[0])
        self.assertEqual(expected_trades_subscription, self.ws_sent_messages[1])
        self.assertEqual(expected_instruments_subscription, self.ws_sent_messages[2])

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_raises_cancel_exceptions(self, ws_connect_mock):
        ws_connect_mock.return_value = self._create_ws_mock()

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

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_ws_connection_exception_details_are_logged(self, ws_connect_mock, hb_app_mock):
        ws_connect_mock.side_effect = Exception()

        self.listening_task = asyncio.get_event_loop().create_task(self.data_source.listen_for_subscriptions())
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occurred during bybit WebSocket Connection ()"))

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exceptions_details(self, ws_connect_mock, hb_app_mock):
        sync_queue = asyncio.Queue()

        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}
        websocket_mock = self._create_ws_mock()
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

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error with WebSocket connection ()"))

    def test_listen_for_trades(self, ):
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

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
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

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
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSD": "BTC-USD"}}

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
                                      'timestamp_e6': 1628703196211205})

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
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSD": "BTC-USD"}}

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
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSD": "BTC-USD"}}

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

    def test_listen_for_instruments_info_snapshot_event(self):
        BybitAPIOrderBookDataSource._last_traded_prices = {None: {"BTC-USD": 0.0}}

        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_instruments_info())

        # Add trade event message be processed
        data_source_queue = self.data_source._messages_queues[CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC]
        data_source_queue.put_nowait({'topic': 'instrument_info.100ms.BTCUSD',
                                      'type': 'snapshot',
                                      'data': {'id': 1,
                                               'symbol': 'BTCUSD',
                                               'last_price_e4': 463550000,
                                               'last_price': '46355.00',
                                               'bid1_price_e4': 463545000,
                                               'bid1_price': '46354.50',
                                               'ask1_price_e4': 463550000,
                                               'ask1_price': '46355.00'},
                                      'cross_seq': 8946315343,
                                      'timestamp_e6': 1628711274147854})

        # Lock the test to let the async task run
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
        last_traded_prices = asyncio.get_event_loop().run_until_complete(
            BybitAPIOrderBookDataSource.get_last_traded_prices(["BTC-USD"]))

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertEqual(46355.0, last_traded_prices["BTC-USD"])

    def test_listen_for_instruments_info_delta_event(self, ):
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSD": "BTC-USD"}}
        BybitAPIOrderBookDataSource._last_traded_prices = {None: {"BTC-USD": 0.0}}

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

        # Lock the test to let the async task run
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
        last_traded_prices = asyncio.get_event_loop().run_until_complete(
            BybitAPIOrderBookDataSource.get_last_traded_prices(["BTC-USD"]))

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertEqual(46354.5, last_traded_prices["BTC-USD"])

    def test_listen_for_instruments_info_raises_cancel_exceptions(self):
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_instruments_info())

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

    def test_listen_for_instruments_info_logs_exception_details(self, ):
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSD": "BTC-USD"}}

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

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_successful(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)
        sync_queue.append(2)

        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSD": "BTC-USDT"}}

        self._configure_mock_api(mock_get)
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
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait(mock_response)

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

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_for_unknown_pair_fails(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)
        sync_queue.append(2)

        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"UNKNOWN": "UNK-NOWN"}}

        self._configure_mock_api(mock_get)
        mock_response = {}
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait(mock_response)

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

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_fails_when_api_request_fails(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)
        sync_queue.append(2)

        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

        self._configure_mock_api(mock_get)
        mock_response = {}
        self.api_responses_status.append(405)
        self.api_responses_json.put_nowait(mock_response)

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
                                        f"at {CONSTANTS.ORDER_BOOK_ENDPOINT}. HTTP 405. Response: {dict()})"))

    def test_listen_for_snapshots_raises_cancel_exceptions(self):
        trades_queue = asyncio.Queue()
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

    @patch("aiohttp.ClientSession.get")
    def test_get_new_order_book(self, mock_get):
        BybitAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSD": "BTC-USDT"}}

        self._configure_mock_api(mock_get)
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
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait(mock_response)

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
