import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.bitget.bitget_constants as CONSTANTS
import hummingbot.connector.exchange.bitget.bitget_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bitget.bitget_api_order_book_data_source import BitgetAPIOrderBookDataSource
from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BitgetAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    """
    Unit tests for BitgetAPIOrderBookDataSource class
    """

    level: int = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset: str = "COINALPHA"
        cls.quote_asset: str = "USDT"
        cls.trading_pair: str = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair: str = f"{cls.base_asset}{cls.quote_asset}"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()

        self.log_records: List[Any] = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant: NetworkMockingAssistant = NetworkMockingAssistant()
        self.client_config_map: ClientConfigAdapter = ClientConfigAdapter(ClientConfigMap())

        self.connector = BitgetExchange(
            bitget_api_key="test_api_key",
            bitget_secret_key="test_secret_key",
            bitget_passphrase="test_passphrase",
            trading_pairs=[self.trading_pair]
        )
        self.data_source = BitgetAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({
                self.exchange_trading_pair: self.trading_pair
            })
        )

    def handle(self, record: Any) -> None:
        """
        Handle logging records by appending them to the log_records list.

        :param record: The log record to be handled.
        """
        self.log_records.append(record)

    def ws_trade_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for trade updates.

        :return: Dict[str, Any]: Mock trade response data.
        """
        return {
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.PUBLIC_WS_TRADE,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "ts": "1695709835822",
                    "price": "26293.4",
                    "size": "0.0013",
                    "side": "buy",
                    "tradeId": "1000000000"
                },
                {
                    "ts": "1695709835822",
                    "price": "24293.5",
                    "size": "0.0213",
                    "side": "sell",
                    "tradeId": "1000000001"
                }
            ]
        }

    def rest_last_traded_price_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock REST response for last traded price.

        :return: Dict[str, Any]: Mock last traded price response data.
        """
        return {
            "code": "00000",
            "msg": "success",
            "data": [
                {
                    "instId": self.exchange_trading_pair,
                    "lastPr": "2200.10",
                    "open24h": "0.00",
                    "high24h": "0.00",
                    "low24h": "0.00",
                    "change24h": "0.00",
                    "bidPr": "1792",
                    "askPr": "2200.1",
                    "bidSz": "0.0084",
                    "askSz": "19740.8811",
                    "baseVolume": "0.0000",
                    "quoteVolume": "0.0000",
                    "openUtc": "0.00",
                    "changeUtc24h": "0",
                    "ts": "1695702438018"
                }
            ]
        }

    def ws_order_book_snapshot_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for order book snapshot.

        :return: Dict[str, Any]: Mock order book snapshot response data.
        """
        return {
            "action": "snapshot",
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.PUBLIC_WS_BOOKS,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "asks": [
                        ["26274.9", "0.0009"],
                        ["26275.0", "0.0500"]
                    ],
                    "bids": [
                        ["26274.8", "0.0009"],
                        ["26274.7", "0.0027"]
                    ],
                    "checksum": 0,
                    "seq": 123,
                    "ts": "1695710946294"
                }
            ],
            "ts": 1695710946294
        }

    def ws_order_book_diff_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for order book diff updates.

        :return: Dict[str, Any]: Mock order book diff response data.
        """
        snapshot: Dict[str, Any] = self.ws_order_book_snapshot_mock_response()
        snapshot["action"] = "update"

        return snapshot

    def ws_error_event_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for error events.

        :return: Dict[str, Any]: Mock error event response data.
        """

        return {
            "event": "error",
            "code": "30005",
            "msg": "Invalid request"
        }

    def rest_order_book_snapshot_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock REST response for order book snapshot.

        :return: Dict[str, Any]: Mock order book snapshot response data.
        """
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1698303884579,
            "data": {
                "asks": [
                    ["26274.9", "0.0009"],
                    ["26275.0", "0.0500"]
                ],
                "bids": [
                    ["26274.8", "0.0009"],
                    ["26274.7", "0.0027"]
                ],
                "ts": "1695710946294"
            },
            "ts": 1695710946294
        }

    def _is_logged(self, log_level: str, message: str) -> bool:
        """
        Check if a specific log message with the given level exists in the log records.

        :param log_level: The log level to check (e.g., "INFO", "ERROR").
        :param message: The log message to check for.

        :return: True if the log message exists with the specified level, False otherwise.
        """
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    @aioresponses()
    def test_get_last_traded_prices(self, mock_get: aioresponses) -> None:
        """
        Test retrieval of last traded prices from the REST API.

        :param mock_get: Mocked HTTP response object.
        """
        mock_response: Dict[str, Any] = self.rest_last_traded_price_mock_response()
        url: str = web_utils.public_rest_url(CONSTANTS.PUBLIC_TICKERS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_get.get(regex_url, body=json.dumps(mock_response))

        results: List[Dict[str, float]] = self.local_event_loop.run_until_complete(
            asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair]))
        )
        result: Dict[str, float] = results[0]

        self.assertEqual(result[self.trading_pair], float("2200.1"))

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_get: aioresponses) -> None:
        """
        Test successful retrieval of a new order book snapshot from the REST API.

        :param mock_get: Mocked HTTP response object.
        """
        mock_response: Dict[str, Any] = self.rest_order_book_snapshot_mock_response()
        url: str = web_utils.public_rest_url(CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_get.get(regex_url, body=json.dumps(mock_response))

        results: List[OrderBook] = self.local_event_loop.run_until_complete(
            asyncio.gather(self.data_source.get_new_order_book(self.trading_pair))
        )
        order_book: OrderBook = results[0]
        data: Dict[str, Any] = mock_response["data"]
        update_id: int = int(data["ts"])

        self.assertTrue(isinstance(order_book, OrderBook))
        self.assertEqual(order_book.snapshot_uid, update_id)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())

        self.assertEqual(2, len(bids))
        self.assertEqual(float(data["bids"][0][0]), bids[0].price)
        self.assertEqual(float(data["bids"][0][1]), bids[0].amount)
        self.assertEqual(update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(float(data["asks"][0][0]), asks[0].price)
        self.assertEqual(float(data["asks"][0][1]), asks[0].amount)
        self.assertEqual(update_id, asks[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(
        self, mock_ws: AsyncMock
    ) -> None:
        """
        Test subscription to WebSocket channels for trades and order book diffs.

        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        subscription_topics: List[Dict[str, str]] = []

        for channel in [CONSTANTS.PUBLIC_WS_BOOKS, CONSTANTS.PUBLIC_WS_TRADE]:
            subscription_topics.append({
                "instType": "SPOT",
                "channel": channel,
                "instId": self.exchange_trading_pair
            })

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps({
                "event": "subscribe",
                "args": subscription_topics
            })
        )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_subscriptions()
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            mock_ws.return_value
        )

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_ws_subscription: Dict[str, Any] = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "SPOT",
                    "channel": CONSTANTS.PUBLIC_WS_BOOKS,
                    "instId": self.exchange_trading_pair
                },
                {
                    "instType": "SPOT",
                    "channel": CONSTANTS.PUBLIC_WS_TRADE,
                    "instId": self.exchange_trading_pair
                }
            ]
        }

        self.assertEqual(expected_ws_subscription, sent_subscription_messages[0])
        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(
        self, mock_ws: MagicMock, _: MagicMock
    ) -> None:
        """
        Test that listen_for_subscriptions raises CancelledError when WebSocket connection is cancelled.

        :param mock_ws: Mocked WebSocket connection object.
        :param _: Mocked sleep function (unused).
        """
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(
        self, mock_ws: AsyncMock, sleep_mock: MagicMock
    ) -> None:
        """
        Test that listen_for_subscriptions logs exception details when an error occurs.

        :param mock_ws: Mocked WebSocket connection object.
        :param sleep_mock: Mocked sleep function.
        """
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError

        try:
            await self.data_source.listen_for_subscriptions()
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error occurred when listening to order book streams. "
            "Retrying in 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_raises_cancel_exception(self, mock_ws: AsyncMock) -> None:
        """
        Test that _subscribe_channels raises CancelledError when WebSocket send is cancelled.

        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_raises_exception_and_logs_error(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that _subscribe_channels logs an error when an unexpected exception occurs.

        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred subscribing to public channels..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_trades(self, mock_ws: AsyncMock) -> None:
        """
        Test processing of trade updates from WebSocket messages.

        :param mock_ws: Mocked WebSocket connection object.
        """
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_response: Dict[str, Any] = self.ws_trade_mock_response()

        mock_ws.get.side_effect = [mock_response, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_ws

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        )

        trade1: OrderBookMessage = await msg_queue.get()
        trade2: OrderBookMessage = await msg_queue.get()

        self.assertTrue(msg_queue.empty())
        self.assertEqual(1000000000, trade1.trade_id)
        self.assertEqual(1000000001, trade2.trade_id)

    async def test_listen_for_trades_raises_cancelled_exception(self) -> None:
        """
        Test that listen_for_trades raises CancelledError when the message queue is cancelled.
        """
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_diffs_successful(self, mock_ws: AsyncMock) -> None:
        """
        Test successful processing of order book diff updates from WebSocket messages.

        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_response: Dict[str, Any] = self.ws_order_book_diff_mock_response()

        mock_ws.get.side_effect = [mock_response, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_ws

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()
        data: Dict[str, Any] = mock_response["data"][0]
        expected_update_id: int = int(data["ts"])

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(data["ts"]) * 1e-3, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks

        self.assertEqual(2, len(bids))
        self.assertEqual(float(data["bids"][0][0]), bids[0].price)
        self.assertEqual(float(data["bids"][0][1]), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(float(data["asks"][0][0]), asks[0].price)
        self.assertEqual(float(data["asks"][0][1]), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_snapshots_successful(self, mock_ws: AsyncMock) -> None:
        """
        Test successful processing of order book snapshot updates from WebSocket messages.

        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_response: Dict[str, Any] = self.ws_order_book_snapshot_mock_response()

        mock_ws.get.side_effect = [mock_response, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_ws

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()
        data: Dict[str, Any] = mock_response["data"][0]
        expected_update_id: int = int(data["ts"])

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(data["ts"]) * 1e-3, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks

        self.assertEqual(2, len(bids))
        self.assertEqual(float(data["bids"][0][0]), bids[0].price)
        self.assertEqual(float(data["bids"][0][1]), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(float(data["asks"][0][0]), asks[0].price)
        self.assertEqual(float(data["asks"][0][1]), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_snapshots_raises_cancelled_exception(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that listen_for_order_book_snapshots raises CancelledError when the message queue is cancelled.

        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_ws.get.side_effect = asyncio.CancelledError
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_ws

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_snapshots_logs_exception(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_order_book_snapshots logs an error
        when processing invalid snapshot data.

        :param mock_ws: Mocked WebSocket connection object.
        """
        incomplete_mock_response: Dict[str, Any] = self.ws_order_book_snapshot_mock_response()
        incomplete_mock_response["data"] = [
            {
                "instId": self.exchange_trading_pair,
                "ts": 1542337219120
            }
        ]

        mock_ws.get.side_effect = [incomplete_mock_response, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_ws

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error when processing public order book snapshots from exchange"
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_trades_logs_exception(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_trades logs an error when processing invalid trade data.

        :param mock_ws: Mocked WebSocket connection object.
        """
        incomplete_mock_response: Dict[str, Any] = self.ws_trade_mock_response()
        incomplete_mock_response["data"] = [
            {
                "instId": self.exchange_trading_pair,
                "ts": 1542337219120
            }
        ]

        mock_ws.get.side_effect = [incomplete_mock_response, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_ws

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error when processing public trade updates from exchange"
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_process_message_for_unknown_channel_event_error_raises(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Verify that an event message with 'event': 'error'
        raises IOError in _process_message_for_unknown_channel.
        """
        mock_response = self.ws_error_event_mock_response()

        with self.assertRaises(IOError) as context:
            asyncio.get_event_loop().run_until_complete(
                self.data_source._process_message_for_unknown_channel(mock_response, mock_ws)
            )

        self.assertIn("Failed to subscribe to public channels", str(context.exception))
        self.assertIn("Invalid request", str(context.exception))
