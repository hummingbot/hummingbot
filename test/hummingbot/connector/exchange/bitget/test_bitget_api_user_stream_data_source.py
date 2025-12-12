import asyncio
import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

import hummingbot.connector.exchange.bitget.bitget_constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bitget.bitget_api_user_stream_data_source import BitgetAPIUserStreamDataSource
from hummingbot.connector.exchange.bitget.bitget_auth import BitgetAuth
from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class BitgetAPIUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    """
    Unit tests for BitgetAPIUserStreamDataSource class
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
        self.time_synchronizer = MagicMock()
        self.time_synchronizer.time.return_value = 1640001112.223

        self.auth = BitgetAuth(
            api_key="test_api_key",
            secret_key="test_secret_key",
            passphrase="test_passphrase",
            time_provider=self.time_synchronizer
        )
        self.connector = BitgetExchange(
            bitget_api_key="test_api_key",
            bitget_secret_key="test_secret_key",
            bitget_passphrase="test_passphrase",
            trading_pairs=[self.trading_pair]
        )
        self.connector._web_assistants_factory._auth = self.auth
        self.data_source = BitgetAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({self.exchange_trading_pair: self.trading_pair})
        )

    @property
    def expected_fill_trade_id(self) -> str:
        """
        Get the expected trade ID for order fill events.

        :return: The expected trade ID.
        """
        return "12345678"

    @property
    def expected_exchange_order_id(self) -> str:
        """
        Get the expected exchange order ID for orders.

        :return: The expected exchange order ID.
        """
        return "1234567890"

    def ws_login_event_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for login events.

        :return: Mock login event response data.
        """
        return {
            "event": "login",
            "code": "0",
            "msg": ""
        }

    def ws_error_event_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for error events.

        :return: Mock error event response data.
        """
        return {
            "event": "error",
            "code": "30005",
            "msg": "Invalid request"
        }

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for a order event.

        :param order: The in-flight order to generate the event for.
        :return: Mock order event response data.
        """
        return {
            "action": "snapshot",
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "instId": self.exchange_trading_pair,
                    "orderId": order.exchange_order_id,
                    "clientOid": order.client_order_id,
                    "size": str(order.amount),
                    "newSize": "0.0000",
                    "notional": "0.000000",
                    "orderType": order.order_type.name.lower(),
                    "force": CONSTANTS.DEFAULT_TIME_IN_FORCE.lower(),
                    "side": order.trade_type.name.lower(),
                    "fillPrice": "0.0",
                    "tradeId": self.expected_fill_trade_id,
                    "baseVolume": "0.0000",
                    "fillTime": "1695797773286",
                    "fillFee": "-0.00000018",
                    "fillFeeCoin": "BTC",
                    "tradeScope": "T",
                    "accBaseVolume": "0.0000",
                    "priceAvg": str(order.price),
                    "status": "live",
                    "cTime": "1695797773257",
                    "uTime": "1695797773326",
                    "stpMode": "cancel_taker",
                    "feeDetail": [
                        {
                            "feeCoin": "BTC",
                            "fee": "-0.00000018"
                        }
                    ],
                    "enterPointSource": "WEB"
                }
            ],
            "ts": 1695797773370
        }

    def handle(self, record: Any) -> None:
        """
        Handle logging records by appending them to the log_records list.

        :param record: The log record to be handled.
        """
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        """
        Check if a specific log message with the given level exists in the log records.

        :param log_level: The log level to check (e.g., "INFO", "ERROR").
        :param message: The log message to check for.
        :return: True if the log message exists with the specified level, False otherwise.
        """
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def tearDown(self) -> None:
        if self.listening_task and not self.listening_task.cancel():
            super().tearDown()

    def _raise_exception(self, exception_class: type) -> None:
        """
        Raise the specified exception for testing purposes.

        :param exception_class: The exception class to raise.
        """
        raise exception_class

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_subscribes_to_orders_events(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_user_stream subscribes to order events correctly.

        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        result_subscribe_orders: Dict[str, Any] = {
            "event": "subscribe",
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": self.exchange_trading_pair
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_orders)
        )

        output_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_login: Dict[str, Any] = {
            "op": "login",
            "args": [
                {
                    "apiKey": "test_api_key",
                    "passphrase": "test_passphrase",
                    "timestamp": str(int(self.time_synchronizer.time())),
                    "sign": "xmIN5Kt+K9U1gXlJ4RnlBjav++39oTR1CR97YWmrWtQ="
                }
            ]
        }
        expected_orders_subscription: Dict[str, Any] = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "SPOT",
                    "channel": CONSTANTS.WS_ACCOUNT_ENDPOINT,
                    "coin": "default"
                },
                {
                    "instType": "SPOT",
                    "channel": CONSTANTS.WS_FILL_ENDPOINT,
                    "coin": "default"
                },
                {
                    "instType": "SPOT",
                    "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                    "instId": self.exchange_trading_pair
                }
            ]
        }

        self.assertEqual(2, len(sent_messages))
        self.assertEqual(expected_login, sent_messages[0])
        self.assertEqual(expected_orders_subscription, sent_messages[1])
        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_logs_error_when_login_fails(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_user_stream logs an error when login fails.

        :param mock_ws: Mocked WebSocket connection object.
        """
        error_mock_response: Dict[str, Any] = self.ws_error_event_mock_response()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(error_mock_response)
        )

        output_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertTrue(self._is_logged(
            "ERROR",
            f"Error authenticating the private websocket connection. Response message {error_mock_response}"
        ))
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_invalid_payload(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_user_stream does not queue invalid payloads.

        :param mock_ws: Mocked WebSocket connection object.
        """
        msg_queue: asyncio.Queue = asyncio.Queue()
        order_id: str = "11"

        self.connector.start_tracking_order(
            order_id=order_id,
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("1000"),
            amount=Decimal("1"),
            initial_state=OrderState.OPEN
        )
        order: InFlightOrder = self.connector.in_flight_orders[order_id]
        mock_response: Dict[str, Any] = self.order_event_for_new_order_websocket_update(order)
        event_without_data: Dict[str, Any] = {"arg": mock_response["arg"]}
        invalid_event: str = "invalid message content"

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(event_without_data)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=invalid_event
        )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(self._is_logged(
            "WARNING",
            f"Message for unknown channel received: {invalid_event}"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_connection_failed(
        self,
        sleep_mock: MagicMock,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that listen_for_user_stream logs an error when the WebSocket connection fails.

        :param sleep_mock: Mocked sleep function.
        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_ws.side_effect = Exception("Test error")
        sleep_mock.side_effect = asyncio.CancelledError
        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listening_process_canceled_when_cancel_exception_during_initialization(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that listen_for_user_stream raises CancelledError during initialization.

        :param mock_ws: Mocked WebSocket connection object.
        """
        messages: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(messages)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listening_process_canceled_when_cancel_exception_during_authentication(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that listen_for_user_stream raises CancelledError during authentication.

        :param mock_ws: Mocked WebSocket connection object.
        """
        messages: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(messages)

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
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listening_process_logs_exception_during_events_subscription(
        self,
        sleep_mock: MagicMock,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that listen_for_user_stream logs an error during event subscription failure.

        :param sleep_mock: Mocked sleep function.
        :param mock_ws: Mocked WebSocket connection object.
        """
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(
            side_effect=ValueError("Invalid trading pair")
        )
        messages: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = asyncio.CancelledError

        try:
            await self.data_source.listen_for_user_stream(messages)
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error occurred subscribing to private channels..."
        ))
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_processes_order_event(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_user_stream correctly processes order events.

        :param mock_ws: Mocked WebSocket connection object.
        """
        order_id: str = "11"

        self.connector.start_tracking_order(
            order_id=order_id,
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("1000"),
            amount=Decimal("1"),
            initial_state=OrderState.OPEN
        )
        order: InFlightOrder = self.connector.in_flight_orders[order_id]
        expected_order_event: Dict[str, Any] = self.order_event_for_new_order_websocket_update(
            order
        )

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(expected_order_event)
        )

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(1, msg_queue.qsize())
        order_event_message = msg_queue.get_nowait()
        self.assertEqual(expected_order_event, order_event_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_logs_details_for_order_event_with_errors(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that listen_for_user_stream logs error details for invalid order events.

        :param mock_ws: Mocked WebSocket connection object.
        """
        error_mock_response: Dict[str, Any] = self.ws_error_event_mock_response()

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(error_mock_response)
        )

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(self._is_logged(
            "ERROR",
            f"Failed to subscribe to private channels: {error_mock_response['msg']} ({error_mock_response['code']})"
        ))
