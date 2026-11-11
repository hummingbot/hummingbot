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
        self.connector._unified_account = True
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
                "instType": CONSTANTS.INST_TYPE_UTA,
                "topic": CONSTANTS.WS_ORDERS_ENDPOINT,
                "symbol": self.exchange_trading_pair
            },
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "orderId": order.exchange_order_id,
                    "clientOid": order.client_order_id,
                    "qty": str(order.amount),
                    "amount": str(order.amount * order.price),
                    "orderType": order.order_type.name.lower(),
                    "timeInForce": CONSTANTS.DEFAULT_TIME_IN_FORCE.lower(),
                    "side": order.trade_type.name.lower(),
                    "cumExecQty": "0",
                    "cumExecValue": "0",
                    "avgPrice": str(order.price),
                    "orderStatus": "live",
                    "createdTime": "1695797773257",
                    "updatedTime": "1695797773326",
                    "feeDetail": [
                        {
                            "feeCoin": "BTC",
                            "fee": "-0.00000018"
                        }
                    ],
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
                "instType": CONSTANTS.INST_TYPE_UTA,
                "topic": CONSTANTS.WS_ORDERS_ENDPOINT
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
                    "instType": CONSTANTS.INST_TYPE_UTA,
                    "topic": CONSTANTS.WS_ACCOUNT_ENDPOINT
                },
                {
                    "instType": CONSTANTS.INST_TYPE_UTA,
                    "topic": CONSTANTS.WS_FILL_ENDPOINT
                },
                {
                    "instType": CONSTANTS.INST_TYPE_UTA,
                    "topic": CONSTANTS.WS_ORDERS_ENDPOINT
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
        sleep_mock.side_effect = [None, asyncio.CancelledError()]
        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(msg_queue)

        self.assertEqual(2, mock_ws.call_count)
        self.assertIsNone(self.data_source._ws_assistant)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_iter_message_throws_exception(
        self,
        sleep_mock: MagicMock,
        mock_ws: AsyncMock
    ) -> None:
        """
        An error while reading the stream tears the session down: the ping task stops and the
        websocket reference is cleared before the retry.

        :param sleep_mock: Mocked retry sleep, which ends the listener.
        :param mock_ws: Mocked WebSocket connection object.
        """
        self.data_source._refresh_server_time_offset = AsyncMock()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_exception(
            websocket_mock=mock_ws.return_value,
            exception=Exception("Test error")
        )
        sleep_mock.side_effect = asyncio.CancelledError
        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(msg_queue)

        self.assertEqual(1, mock_ws.call_count)
        self.assertIsNone(self.data_source._ws_assistant)
        self.assertIsNone(self.data_source._ping_task)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_sends_one_ping_after_subscribing(self, mock_ws: AsyncMock) -> None:
        self.data_source._refresh_server_time_offset = AsyncMock()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps({"event": "subscribe", "arg": {"instType": CONSTANTS.INST_TYPE_UTA,
                                                              "topic": CONSTANTS.WS_ORDERS_ENDPOINT}})
        )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(asyncio.Queue())
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(
            [CONSTANTS.PUBLIC_WS_PING_REQUEST],
            self.mocking_assistant.text_messages_sent_through_websocket(mock_ws.return_value)
        )
        self.assertIsNotNone(self.data_source._ping_task)
        self.listening_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await self.listening_task

    async def test_send_interval_ping_waits_one_interval_before_pinging(self) -> None:
        ws = AsyncMock()
        ping_task = self.local_event_loop.create_task(self.data_source.send_interval_ping(ws))
        await asyncio.sleep(0)

        ws.send.assert_not_called()
        ping_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await ping_task

    async def test_user_stream_interruption_stops_the_ping_task(self) -> None:
        ws = AsyncMock()
        await self.data_source._subscribe_channels(websocket_assistant=ws)
        ping_task = self.data_source._ping_task

        await self.data_source._on_user_stream_interruption(websocket_assistant=ws)

        self.assertTrue(ping_task.cancelled())
        self.assertIsNone(self.data_source._ping_task)
        ws.disconnect.assert_awaited_once()

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
        # The V3 UTA private subscription no longer resolves per-symbol instIds (it subscribes the
        # account/fill/order channels with instType "UTA"), so the subscription failure is injected
        # at the websocket send call instead of at exchange_symbol_associated_to_pair.
        ws_mock = AsyncMock()
        ws_mock.send.side_effect = Exception("subscribe failed")
        self.data_source._connected_websocket_assistant = AsyncMock(return_value=ws_mock)
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

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_rejects_login_echo_with_error_code(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        A response echoing the "login" event but carrying a non-zero code is a rejected session.
        The listener must fail authentication rather than subscribe on it.

        :param mock_ws: Mocked WebSocket connection object.
        """
        failed_login: Dict[str, Any] = self.ws_login_event_mock_response()
        failed_login["code"] = "30005"
        failed_login["msg"] = "Login failed"

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(failed_login)
        )

        output_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertTrue(self._is_logged(
            "ERROR",
            f"Error authenticating the private websocket connection. Response message {failed_login}"
        ))
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_restarts_when_subscription_is_rejected(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        A rejected private subscription leaves the connection up but silent, so the listener must
        tear the session down and reconnect instead of only logging. It pauses first, so a
        rejection that never clears does not reconnect about once a second.

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

        async def _sleep(delay: float) -> None:
            # Return at once from the rejection pause, and park the listener's own retry wait so it
            # does not reconnect while the test checks what happened.
            if delay != CONSTANTS.WS_SUBSCRIPTION_RETRY_INTERVAL_SECONDS:
                await asyncio.Event().wait()

        self.data_source._sleep = AsyncMock(side_effect=_sleep)
        self.data_source._refresh_server_time_offset = AsyncMock()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))
        self.data_source._sleep.assert_any_await(CONSTANTS.WS_SUBSCRIPTION_RETRY_INTERVAL_SECONDS)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_authenticate_refreshes_the_server_time_offset_first(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        The login signature is rejected once its timestamp drifts more than 30 seconds from the
        exchange clock (30014). TimeSynchronizer derives that timestamp from perf_counter, which
        stalls while the host is suspended, so the offset has to be re-sampled before signing.
        """
        self.data_source._refresh_server_time_offset = AsyncMock()

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )

        output_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.data_source._refresh_server_time_offset.assert_called()

    @patch("hummingbot.connector.exchange.bitget.bitget_web_utils.get_current_server_time", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_authenticate_keeps_the_existing_offset_when_the_time_resync_fails(
        self,
        mock_ws: AsyncMock,
        server_time_mock: AsyncMock
    ) -> None:
        """
        A failed resync must not block the login, and must not cost the offset the connector
        already has: with no samples left the synchronizer signs with the local clock, which the
        exchange refuses (30014) whenever that clock is more than 30 seconds out.
        """
        synchronizer = self.connector._time_synchronizer
        for _ in range(5):
            synchronizer.add_time_offset_ms_sample(-60_000.0)
        server_time_mock.side_effect = IOError("server time unavailable")

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )

        output_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        self.assertEqual("login", sent[0]["op"])
        server_time_mock.assert_awaited()
        self.assertEqual(-60_000.0, synchronizer.time_offset_ms)

    @patch("hummingbot.connector.exchange.bitget.bitget_web_utils.get_current_server_time", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_authenticate_discards_stale_clock_samples_before_resampling(
        self,
        mock_ws: AsyncMock,
        server_time_mock: AsyncMock
    ) -> None:
        """
        TimeSynchronizer derives its offset from the median and weighted average of a five-sample
        deque, so appending one fresh sample to five stale ones barely moves it: after an
        hour-long suspend the offset is still around 49 minutes out, well outside the exchange's
        30-second window, and five fresh samples are needed to recover. The stale samples have to
        be discarded for the refresh to mean anything.
        """
        synchronizer = self.connector._time_synchronizer
        for _ in range(5):
            synchronizer.add_time_offset_ms_sample(-3_600_000.0)
        self.assertEqual(-3_600_000.0, synchronizer.time_offset_ms)
        # Freeze the local counter so the fresh sample is exactly the server time minus it.
        synchronizer._current_seconds_counter = MagicMock(return_value=1_000.0)
        server_time_mock.return_value = 1_000_000.0

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )

        output_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        # One fresh sample is now the whole offset, so the login timestamp is usable again.
        self.assertEqual(0.0, synchronizer.time_offset_ms)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_unified_account_connects_to_the_v3_private_websocket(self, mock_ws: AsyncMock) -> None:
        self.data_source._refresh_server_time_offset = AsyncMock()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(asyncio.Queue())
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual("wss://ws.bitget.com/v3/ws/private", mock_ws.call_args.args[0])
