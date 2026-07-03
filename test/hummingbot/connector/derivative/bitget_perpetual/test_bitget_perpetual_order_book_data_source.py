import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_api_order_book_data_source import (
    BitgetPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BitgetPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    """Test case for BitgetPerpetualAPIOrderBookDataSource."""

    level: int = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset: str = "BTC"
        cls.quote_asset: str = "USDT"
        cls.trading_pair: str = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair: str = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records: List[Any] = []
        self.listening_task: Optional[asyncio.Task] = None

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitgetPerpetualDerivative(
            client_config_map,
            bitget_perpetual_api_key="test_api_key",
            bitget_perpetual_secret_key="test_secret_key",
            bitget_perpetual_passphrase="test_passphrase",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = BitgetPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )
        self._original_full_order_book_reset_time = (
            self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        )
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({
                self.exchange_trading_pair: self.trading_pair
            })
        )

    async def asyncSetUp(self) -> None:
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        if self.listening_task:
            self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record: Any) -> None:
        """
        Handle logging records by appending them to the log_records list.

        :param record: The log record to be handled.
        """
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        """
        Check if a specific message was logged with the given log level.

        :param log_level: The log level to check (e.g., "INFO", "ERROR").
        :param message: The message to check for in the logs.
        :return: True if the message was logged with the specified level, False otherwise.
        """
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def rest_order_book_snapshot_mock_response(self) -> Dict[str, Any]:
        """
        Get a mock REST snapshot message for order book.

        :return: A dictionary containing the mock REST snapshot message.
        """
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695870963008,
            "data": {
                "asks": [
                    [26347.5, 0.25],
                    [26348.0, 0.16]
                ],
                "bids": [
                    [26346.5, 0.16],
                    [26346.0, 0.32]
                ],
                "ts": "1695870968804",
                "scale": "0.1",
                "precision": "scale0",
                "isMaxPrecision": "NO"
            }
        }

    def ws_order_book_diff_mock_response(self) -> Dict[str, Any]:
        """
        Get a mock WebSocket diff message for order book updates.

        :return: A dictionary containing the mock WebSocket diff message.
        """
        snapshot: Dict[str, Any] = self.ws_order_book_snapshot_mock_response()
        snapshot["action"] = "update"

        return snapshot

    def ws_order_book_snapshot_mock_response(self) -> Dict[str, Any]:
        """
        Get a mock WebSocket snapshot message for order book.

        :return: A dictionary containing the mock WebSocket snapshot message.
        """
        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.PUBLIC_WS_BOOKS,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "asks": [
                        ["27000.5", "8.760"],
                        ["27001.0", "0.400"]
                    ],
                    "bids": [
                        ["27000.0", "2.710"],
                        ["26999.5", "1.460"]
                    ],
                    "checksum": 0,
                    "seq": 123,
                    "ts": "1695716059516"
                }
            ],
            "ts": 1695716059516
        }

    def ws_ticker_mock_response(self) -> Dict[str, Any]:
        """
        Get a mock WebSocket message for funding info.

        :return: A dictionary containing the mock funding info message.
        """
        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.PUBLIC_WS_TICKER,
                "instId": self.exchange_trading_pair,
            },
            "data": [
                {
                    "instId": self.exchange_trading_pair,
                    "lastPr": "27000.5",
                    "bidPr": "27000",
                    "askPr": "27000.5",
                    "bidSz": "2.71",
                    "askSz": "8.76",
                    "open24h": "27000.5",
                    "high24h": "30668.5",
                    "low24h": "26999.0",
                    "change24h": "-0.00002",
                    "fundingRate": "0.000010",
                    "nextFundingTime": "1695722400000",
                    "markPrice": "27000.0",
                    "indexPrice": "25702.4",
                    "holdingAmount": "929.502",
                    "baseVolume": "368.900",
                    "quoteVolume": "10152429.961",
                    "openUtc": "27000.5",
                    "symbolType": 1,
                    "symbol": self.exchange_trading_pair,
                    "deliveryPrice": "0",
                    "ts": "1695715383021"
                }
            ]
        }

    async def expected_subscription_response(self, trading_pair: str) -> Dict[str, Any]:
        """
        Get a mock subscription response for a given trading pair.

        :param trading_pair: The trading pair to get the subscription response.
        :return: A dictionary containing the mock subscription response.
        """
        product_type = await self.connector.product_type_associated_to_trading_pair(
            trading_pair=trading_pair
        )
        symbol = await self.connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        return {
            "op": "subscribe",
            "args": [
                {
                    "instType": product_type,
                    "channel": CONSTANTS.PUBLIC_WS_BOOKS,
                    "instId": symbol
                },
                {
                    "instType": product_type,
                    "channel": CONSTANTS.PUBLIC_WS_TRADE,
                    "instId": symbol
                },
                {
                    "instType": product_type,
                    "channel": CONSTANTS.PUBLIC_WS_TICKER,
                    "instId": symbol
                }
            ],
        }

    def expected_funding_info_data(self) -> Dict[str, Any]:
        """
        Get a mock REST message for funding info.

        :return: A dictionary containing the mock REST funding info message.
        """
        return {
            "data": [{
                "symbol": self.exchange_trading_pair,
                "indexPrice": "35000",
                "nextUpdate": "1627311600000",
                "fundingRate": "0.0002",
                "markPrice": "35000",
            }],
        }

    def ws_trade_mock_response(self) -> Dict[str, Any]:
        """
        Get a mock WebSocket trade message for order book updates.

        :return: A dictionary containing the mock WebSocket trade message.
        """
        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.PUBLIC_WS_TRADE,
                "instId": "BTCUSDT"
            },
            "data": [
                {
                    "ts": "1695716760565",
                    "price": "27000.5",
                    "size": "0.001",
                    "side": "buy",
                    "tradeId": "1"
                },
                {
                    "ts": "1695716759514",
                    "price": "27000.0",
                    "size": "0.001",
                    "side": "sell",
                    "tradeId": "2"
                }
            ],
            "ts": 1695716761589
        }

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api) -> None:
        """
        Test successful retrieval of a new order book.

        :param mock_api: Mocked API response object.
        :return: None
        """
        url: str = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp: Dict[str, Any] = self.rest_order_book_snapshot_mock_response()
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book = await self.data_source.get_new_order_book(self.trading_pair)
        expected_update_id: int = int(resp["data"]["ts"])
        bids: List[Any] = list(order_book.bid_entries())
        asks: List[Any] = list(order_book.ask_entries())

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        self.assertEqual(2, len(bids))
        self.assertEqual(26346.5, bids[0].price)
        self.assertEqual(0.16, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(26347.5, asks[0].price)
        self.assertEqual(0.25, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api) -> None:
        """
        Test that get_new_order_book raises an IOError on a failed API request.

        :param mock_api: Mocked API response object.
        :return: None
        """
        url: str = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400)

        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_trades_diffs_and_funding_info(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test subscription to trades, diffs, and funding info via WebSocket.

        :param mock_ws: Mocked WebSocket connection.
        :return: None
        """
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        result_subscribe_diffs: Dict[str, Any] = self.ws_order_book_diff_mock_response()
        result_subscribe_funding_info: Dict[str, Any] = self.ws_ticker_mock_response()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_funding_info),
        )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_subscriptions()
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_subscription: Dict[str, Any] = await self.expected_subscription_response(
            self.trading_pair
        )

        self.assertEqual(1, len(sent_subscription_messages))
        self.assertEqual(expected_subscription, sent_subscription_messages[0])
        self.assertTrue(self._is_logged("INFO", "Subscribed to public channels..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_for_usdc_product_type_pair(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test subscription to trades, diffs, and funding info for USDC product type pair.

        :param mock_ws: Mocked WebSocket connection.
        :return: None
        """
        local_base_asset: str = "BTC"
        local_quote_asset: str = "USDC"
        local_trading_pair: str = f"{local_base_asset}-{local_quote_asset}"
        local_symbol: str = f"{local_base_asset}{local_quote_asset}"

        local_data_source = BitgetPerpetualAPIOrderBookDataSource(
            trading_pairs=[local_trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )
        self.connector._set_trading_pair_symbol_map(
            bidict({
                local_symbol: local_trading_pair
            })
        )

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        result_subscribe_diffs: Dict[str, Any] = self.ws_order_book_diff_mock_response()
        result_subscribe_funding_info: Dict[str, Any] = self.ws_ticker_mock_response()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_funding_info),
        )

        self.listening_task = self.local_event_loop.create_task(
            local_data_source.listen_for_subscriptions()
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_subscription: Dict[str, Any] = await self.expected_subscription_response(
            local_trading_pair
        )

        self.assertEqual(1, len(sent_subscription_messages))
        self.assertEqual(expected_subscription, sent_subscription_messages[0])
        self.assertTrue(self._is_logged("INFO", "Subscribed to public channels..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_for_usd_product_type_pair(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test subscription to trades, diffs, and funding info for USD product type pair.

        :param mock_ws: Mocked WebSocket connection.
        :return: None
        """
        local_base_asset: str = "BTC"
        local_quote_asset: str = "USD"
        local_trading_pair: str = f"{local_base_asset}-{local_quote_asset}"
        local_symbol: str = f"{local_base_asset}{local_quote_asset}"

        local_data_source = BitgetPerpetualAPIOrderBookDataSource(
            trading_pairs=[local_trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )
        self.connector._set_trading_pair_symbol_map(
            bidict({
                local_symbol: local_trading_pair
            })
        )

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        result_subscribe_diffs: Dict[str, Any] = self.ws_order_book_diff_mock_response()
        result_subscribe_funding_info: Dict[str, Any] = self.ws_ticker_mock_response()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_funding_info),
        )

        self.listening_task = self.local_event_loop.create_task(
            local_data_source.listen_for_subscriptions()
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_subscription: Dict[str, Any] = await self.expected_subscription_response(
            local_trading_pair
        )

        self.assertEqual(1, len(sent_subscription_messages))
        self.assertEqual(expected_subscription, sent_subscription_messages[0])
        self.assertTrue(self._is_logged("INFO", "Subscribed to public channels..."))

    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(
        self,
        mock_ws: MagicMock
    ) -> None:
        """
        Test that listen_for_subscriptions raises a CancelledError.

        :param mock_ws: Mocked WebSocket connection.
        :return: None
        """
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(
        self,
        mock_ws: AsyncMock,
        sleep_mock: AsyncMock
    ) -> None:
        """
        Test that listen_for_subscriptions logs exception details.

        :param mock_ws: Mocked WebSocket connection.
        :param sleep_mock: Mocked sleep function.
        :return: None
        """
        mock_ws.side_effect = Exception("Test Error")
        sleep_mock.side_effect = asyncio.CancelledError()

        try:
            await self.data_source.listen_for_subscriptions()
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. "
                "Retrying in 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_raises_cancel_exception(self, mock_ws: AsyncMock) -> None:
        """
        Test that _subscribe_channels raises a CancelledError.

        :return: None
        """
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_raises_exception_and_logs_error(self, mock_ws: AsyncMock) -> None:
        """
        Test that _subscribe_channels raises an exception and logs the error.

        :return: None
        """
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to public channels...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_trades_cancelled_when_listening(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_trades raises a CancelledError when cancelled.

        :return: None
        """
        mock_ws.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_ws
        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_trades_logs_exception(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_trades logs an exception for invalid data.

        :return: None
        """
        incomplete_resp: Dict[str, Any] = {}
        mock_ws.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
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
    async def test_listen_for_trades_successful(self, mock_ws: AsyncMock) -> None:
        """
        Test successful processing of trade updates.

        :return: None
        """
        trade_event: Dict[str, Any] = self.ws_trade_mock_response()
        mock_ws.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_ws
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(int(trade_event["data"][0]["tradeId"]), msg.trade_id)
        self.assertEqual(int(trade_event["data"][0]["ts"]) * 1e-3, msg.timestamp)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_diffs_cancelled(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_order_book_diffs raises a CancelledError when cancelled.

        :return: None
        """
        mock_ws.get.side_effect = asyncio.CancelledError()
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_diffs_logs_exception(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_order_book_diffs logs an exception for invalid data.

        :return: None
        """
        incomplete_resp: Dict[str, Any] = self.ws_order_book_diff_mock_response()
        incomplete_resp["data"] = 1

        mock_ws.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_ws
        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error when processing public order book updates from exchange"
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_diffs_successful(self, mock_ws: AsyncMock) -> None:
        """
        Test successful processing of order book diff updates.

        :return: None
        """
        diff_event: Dict[str, Any] = self.ws_order_book_diff_mock_response()
        mock_ws.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_ws
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()
        expected_update_id: int = int(diff_event["data"][0]["ts"])
        expected_timestamp: float = expected_update_id * 1e-3
        bids: List[Any] = msg.bids
        asks: List[Any] = msg.asks

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(expected_timestamp, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)
        self.assertEqual(2, len(bids))
        self.assertEqual(27000.0, bids[0].price)
        self.assertEqual(2.71, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(27000.5, asks[0].price)
        self.assertEqual(8.760, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(
        self,
        mock_api
    ) -> None:
        """
        Test that listen_for_order_book_snapshots raises a CancelledError when fetching a snapshot.

        :param mock_api: Mocked API response object.
        :return: None
        """
        url: str = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, exception=asyncio.CancelledError)
        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)

    @aioresponses()
    async def test_listen_for_order_book_snapshots_log_exception(self, mock_api) -> None:
        """
        Test that listen_for_order_book_snapshots logs an exception for failed snapshot fetching.

        :param mock_api: Mocked API response object.
        :return: None
        """
        url: str = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_api.get(regex_url, exception=Exception)
        mock_api.get(regex_url, exception=asyncio.CancelledError)

        try:
            self.data_source._sleep = AsyncMock()
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unexpected error fetching order book snapshot for {self.trading_pair}."
            )
        )

    @aioresponses()
    async def test_listen_for_order_book_rest_snapshots_successful(self, mock_api) -> None:
        """
        Test successful processing of REST order book snapshots.

        :param mock_api: Mocked API response object.
        :return: None
        """
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp: Dict[str, Any] = self.rest_order_book_snapshot_mock_response()
        mock_api.get(regex_url, body=json.dumps(resp))

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()
        expected_update_id: float = float(resp["data"]["ts"])
        expected_timestamp: float = expected_update_id * 1e-3
        bids: List[Any] = msg.bids
        asks: List[Any] = msg.asks

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(expected_timestamp, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)
        self.assertEqual(2, len(bids))
        self.assertEqual(26346.5, bids[0].price)
        self.assertEqual(0.16, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(26347.5, asks[0].price)
        self.assertEqual(0.25, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_snapshots_successful(self, mock_ws: AsyncMock) -> None:
        """
        Test successful processing of WebSocket order book snapshots.

        :return: None
        """
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = (
            self._original_full_order_book_reset_time
        )
        event: Dict[str, Any] = self.ws_order_book_snapshot_mock_response()
        mock_ws.get.side_effect = [event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_ws
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()
        expected_update_id: int = int(event["data"][0]["ts"])
        expected_timestamp: float = expected_update_id * 1e-3
        bids: List[Any] = msg.bids
        asks: List[Any] = msg.asks

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(expected_timestamp, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)
        self.assertEqual(2, len(bids))
        self.assertEqual(27000.0, bids[0].price)
        self.assertEqual(2.71, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(27000.5, asks[0].price)
        self.assertEqual(8.760, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    async def test_listen_for_funding_info_cancelled_when_listening(self) -> None:
        """
        Test that listen_for_funding_info raises a CancelledError when cancelled.

        :return: None
        """
        mock_queue: MagicMock = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[
            self.data_source._funding_info_messages_queue_key
        ] = mock_queue
        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_funding_info(msg_queue)

    async def test_listen_for_funding_info_logs_exception(self) -> None:
        """
        Test that listen_for_funding_info logs an exception for invalid data.

        :return: None
        """
        incomplete_resp: Dict[str, Any] = self.ws_ticker_mock_response()
        incomplete_resp["data"] = 1
        mock_queue: AsyncMock = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[
            self.data_source._funding_info_messages_queue_key
        ] = mock_queue
        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_funding_info(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error when processing public funding info updates from exchange"
            )
        )

    async def test_listen_for_funding_info_successful(self) -> None:
        """
        Test successful processing of funding info updates.

        :return: None
        """
        funding_info_event: Dict[str, Any] = self.ws_ticker_mock_response()
        mock_queue: AsyncMock = AsyncMock()
        mock_queue.get.side_effect = [funding_info_event, asyncio.CancelledError()]
        self.data_source._message_queue[
            self.data_source._funding_info_messages_queue_key
        ] = mock_queue
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_funding_info(msg_queue)
        )

        msg: FundingInfoUpdate = await msg_queue.get()
        funding_update: Dict[str, Any] = funding_info_event["data"][0]
        expected_index_price: Decimal = Decimal(str(funding_update["indexPrice"]))
        expected_mark_price: Decimal = Decimal(str(funding_update["markPrice"]))
        expected_funding_time: float = int(funding_update["nextFundingTime"]) * 1e-3
        expected_rate: Decimal = Decimal(funding_update["fundingRate"])

        self.assertEqual(self.trading_pair, msg.trading_pair)
        self.assertEqual(expected_index_price, msg.index_price)
        self.assertEqual(expected_mark_price, msg.mark_price)
        self.assertEqual(expected_funding_time, msg.next_funding_utc_timestamp)
        self.assertEqual(expected_rate, msg.rate)

    @aioresponses()
    async def test_get_funding_info(self, mock_api) -> None:
        """
        Test successful retrieval of funding info via REST.

        :param mock_api: Mocked API response object.
        :return: None
        """
        rate_url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_FUNDING_RATE_ENDPOINT)
        rate_regex_url = re.compile(rate_url.replace(".", r"\.").replace("?", r"\?"))
        mark_url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_SYMBOL_PRICE_ENDPOINT)
        mark_regex_url = re.compile(mark_url.replace(".", r"\.").replace("?", r"\?"))

        resp: Dict[str, Any] = self.expected_funding_info_data()
        mock_api.get(rate_regex_url, body=json.dumps(resp))
        mock_api.get(mark_regex_url, body=json.dumps(resp))

        funding_info: FundingInfo = await self.data_source.get_funding_info(self.trading_pair)
        msg_result: Dict[str, Any] = resp["data"][0]

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(msg_result["indexPrice"])), funding_info.index_price)
        self.assertEqual(Decimal(str(msg_result["markPrice"])), funding_info.mark_price)
        self.assertEqual(
            int(msg_result["nextUpdate"]) * 1e-3,
            funding_info.next_funding_utc_timestamp
        )
        self.assertEqual(Decimal(str(msg_result["fundingRate"])), funding_info.rate)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_events_enqueued_correctly_after_channel_detection(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that events are correctly enqueued after channel detection.

        :param mock_ws: Mocked WebSocket connection.
        :return: None
        """
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        diff_event: Dict[str, Any] = self.ws_order_book_diff_mock_response()
        funding_event: Dict[str, Any] = self.ws_ticker_mock_response()
        trade_event: Dict[str, Any] = self.ws_trade_mock_response()
        snapshot_event: Dict[str, Any] = self.ws_order_book_snapshot_mock_response()

        for event in [snapshot_event, diff_event, funding_event, trade_event]:
            self.mocking_assistant.add_websocket_aiohttp_message(
                websocket_mock=mock_ws.return_value,
                message=json.dumps(event),
            )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_subscriptions()
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        snapshot_queue = self.data_source._message_queue[
            self.data_source._snapshot_messages_queue_key
        ]
        diff_queue = self.data_source._message_queue[
            self.data_source._diff_messages_queue_key
        ]
        funding_queue = self.data_source._message_queue[
            self.data_source._funding_info_messages_queue_key
        ]
        trade_queue = self.data_source._message_queue[
            self.data_source._trade_messages_queue_key
        ]

        self.assertEqual(1, snapshot_queue.qsize())
        self.assertEqual(snapshot_event, snapshot_queue.get_nowait())
        self.assertEqual(1, diff_queue.qsize())
        self.assertEqual(diff_event, diff_queue.get_nowait())
        self.assertEqual(1, funding_queue.qsize())
        self.assertEqual(funding_event, funding_queue.get_nowait())
        self.assertEqual(1, trade_queue.qsize())
        self.assertEqual(trade_event, trade_queue.get_nowait())
