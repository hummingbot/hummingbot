import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest

# from test.track_memory_usage import track_memory_growth
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.coinbase_advanced_trade import (
    coinbase_advanced_trade_constants as CONSTANTS,
    coinbase_advanced_trade_web_utils as web_utils,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_api_order_book_data_source import (
    CoinbaseAdvancedTradeAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_exchange import (
    CoinbaseAdvancedTradeExchange,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils import (
    get_timestamp_from_exchange_time,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class CoinbaseAdvancedTradeAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    # logging.Level required to receive logs from the data source logger
    quote_asset = None
    base_asset = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.listening_task = None

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = CoinbaseAdvancedTradeExchange(
            client_config_map=client_config_map,
            coinbase_advanced_trade_api_key="",
            coinbase_advanced_trade_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.data_source = CoinbaseAdvancedTradeAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                                       connector=self.connector,
                                                                       api_factory=self.connector._web_assistants_factory,
                                                                       domain=self.domain)
        self.set_loggers(self.data_source.logger())

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    async def asyncTearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        await super().asyncTearDown()

    def tearDown(self) -> None:
        super().tearDown()

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.local_event_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _successfully_subscribed_event(self):
        return {}

    def _trade_update_event(self):
        resp = {
            "channel": "market_trades",
            "client_id": "",
            "timestamp": "2023-02-09T20:19:35.39625135Z",
            "sequence_num": 0,
            "events": [
                {
                    "type": "snapshot",
                    "trades": [
                        {
                            "trade_id": "12345",
                            "product_id": self.ex_trading_pair,
                            "price": "1260.01",
                            "size": "0.3",
                            "side": "BUY",
                            "time": "2019-08-14T20:42:27.265Z",
                        },
                        {
                            "trade_id": "67890",
                            "product_id": self.ex_trading_pair,
                            "price": "1260.01",
                            "size": "0.3",
                            "side": "SELL",
                            "time": "2019-08-14T20:42:27.265Z",
                        }
                    ]
                }
            ]
        }
        return resp

    def _order_diff_event(self):
        resp = {
            "channel": "l2_data",
            "client_id": "",
            "timestamp": "2023-02-09T20:32:50.714964855Z",
            "sequence_num": 1,
            "events": [
                {
                    "type": "update",
                    "product_id": self.ex_trading_pair,
                    "updates": [
                        {
                            "side": "bid",
                            "event_time": "1970-01-01T00:00:00Z",
                            "price_level": "21921.73",
                            "new_quantity": "0.06317902"
                        },
                        {
                            "side": "bid",
                            "event_time": "1970-01-01T00:00:00Z",
                            "price_level": "21921.3",
                            "new_quantity": "0.02"
                        },
                        {
                            "side": "ask",
                            "event_time": "1970-01-01T00:00:00Z",
                            "price_level": "21921.73",
                            "new_quantity": "0.06317902"
                        },
                        {
                            "side": "ask",
                            "event_time": "1970-01-01T00:00:00Z",
                            "price_level": "21921.3",
                            "new_quantity": "0.02"
                        },
                    ]
                }
            ]
        }
        return resp

    @staticmethod
    def _snapshot_response():
        resp = {
            "pricebook": {
                "product_id": "BTC-ETH",
                "bids": [
                    {
                        "price": "4",
                        "size": "431"
                    }
                ],
                "asks": [
                    {
                        "price": "4.000002",
                        "size": "12"
                    }
                ],
                "time": "2023-07-11T22:34:09+02:00"
            }
        }
        return resp

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_EP, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self._snapshot_response()

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = get_timestamp_from_exchange_time(resp["pricebook"]["time"], "s")

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(4, bids[0].price)
        self.assertEqual(431, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(4.000002, asks[0].price)
        self.assertEqual(12, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

        mock_api.clear()

    @aioresponses()
    # @track_memory_growth()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_EP, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    # @track_memory_growth(runs=10)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = None
        result_subscribe_diffs = None

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(3, len(sent_subscription_messages))

        subs = {"market_trades": False, "level2": False, "heartbeats": False}
        for message in sent_subscription_messages:
            self.assertEqual("subscribe", message["type"])
            self.assertEqual(self.ex_trading_pair.upper(), message["product_ids"][0])
            subs[message["channel"]] = True
        self.assertTrue(subs["market_trades"])
        self.assertTrue(subs["level2"])
        self.assertTrue(subs["heartbeats"])

        self.assertTrue(self.is_logged(
            "INFO",
            f"Subscribed to order book channels for: {self.ex_trading_pair.upper()}"
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self.is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.local_event_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.local_event_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self.is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.WS_ORDER_SUBSCRIPTION_KEYS[1]] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.local_event_loop.create_task(
                self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.WS_ORDER_SUBSCRIPTION_KEYS[1]] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(12345, msg.trade_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.WS_ORDER_SUBSCRIPTION_KEYS[0]] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.local_event_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = self._order_diff_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.WS_ORDER_SUBSCRIPTION_KEYS[0]] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(int(get_timestamp_from_exchange_time(diff_event["timestamp"], 's')), msg.update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_EP, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError, repeat=True)

        # with self.assertRaises(asyncio.CancelledError):
        self.async_run_with_timeout(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())
        )
