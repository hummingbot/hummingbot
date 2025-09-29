import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict
from hummingbot.connector.exchange.coinmate.coinmate_api_user_stream_data_source import (
    CoinmateAPIUserStreamDataSource
)
from hummingbot.connector.exchange.coinmate.coinmate_auth import CoinmateAuth
from hummingbot.connector.exchange.coinmate.coinmate_exchange import CoinmateExchange
from hummingbot.connector.test_support.network_mocking_assistant import (
    NetworkMockingAssistant
)


class CoinmateUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "EUR"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.domain = ""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.auth = CoinmateAuth(
            api_key="TEST_API_KEY",
            secret_key="TEST_SECRET",
            client_id="TEST_CLIENT_ID"
        )

        self.connector = CoinmateExchange(
            coinmate_api_key="",
            coinmate_secret_key="",
            coinmate_client_id="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = CoinmateAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(
            bidict({self.ex_trading_pair: self.trading_pair})
        )

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message
            for record in self.log_records
        )

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def _error_response(self) -> Dict[str, Any]:
        return {
            "error": True,
            "errorMessage": "ERROR MESSAGE",
            "data": None
        }

    def _user_stream_event_order_update(self):
        return {
            "event": "data",
            "channel": f"private-open_orders-{self.auth._client_id}",
            "payload": [
                {
                    "id": 12345,
                    "timestamp": 1234567890000,
                    "type": "BUY",
                    "price": 50000.0,
                    "amount": 0.5,
                    "original": 1.0,
                    "currencyPair": self.ex_trading_pair,
                    "orderChangePushEvent": "UPDATE"
                }
            ]
        }

    def _user_stream_event_balance_update(self):
        return {
            "event": "data",
            "channel": f"private-user_balances-{self.auth._client_id}",
            "payload": {
                self.base_asset: {
                    "currency": self.base_asset,
                    "balance": "10.0",
                    "reserved": "1.0",
                    "available": "9.0"
                },
                self.quote_asset: {
                    "currency": self.quote_asset,
                    "balance": "50000.0",
                    "reserved": "5000.0",
                    "available": "45000.0"
                }
            }
        }

    def _user_stream_event_trade_update(self):
        return {
            "event": "data",
            "channel": f"private-user-trades-{self.auth._client_id}",
            "payload": [
                {
                    "transactionId": 67890,
                    "date": 1234567890000,
                    "amount": 0.5,
                    "price": 50000.0,
                    "buyOrderId": 12345,
                    "sellOrderId": 0,
                    "orderType": "BUY",
                    "type": "BUY",
                    "fee": 75.0,
                    "tradeFeeType": "TAKER",
                    "currencyPair": self.ex_trading_pair
                }
            ]
        }

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_subscribes_to_orders_and_balances(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        successful_subscription_response = {
            "event": "subscribe_success",
            "data": {"channel": f"private-open_orders-{self.auth._client_id}"}
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(successful_subscription_response))

        output_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            ws_connect_mock.return_value)

        sent_subscription_messages = (
            self.mocking_assistant.json_messages_sent_through_websocket(
                websocket_mock=ws_connect_mock.return_value
            )
        )

        self.assertEqual(3, len(sent_subscription_messages))
        
        expected_orders_subscription = {
            "event": "subscribe",
            "data": {
                "channel": f"private-open_orders-{self.auth._client_id}",
                "clientId": self.auth._client_id,
                "publicKey": self.auth._api_key,
                "nonce": sent_subscription_messages[0]["data"]["nonce"],
                "signature": sent_subscription_messages[0]["data"]["signature"]
            }
        }
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[0])

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_connection_failed(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: (
            self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())
        )

        output_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output_queue))

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_iter_message_throws_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        try:
            await asyncio.wait_for(self.listening_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                          "Unexpected error while listening to user stream. Retrying after 5 seconds...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_order_update(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self._user_stream_event_order_update())
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = await msg_queue.get()
        self.assertEqual("order", msg["type"])
        self.assertEqual(12345, msg["data"][0]["id"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_balance_update(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self._user_stream_event_balance_update())
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = await msg_queue.get()
        self.assertEqual("balance", msg["type"])
        self.assertIn(self.base_asset, msg["data"])
        self.assertIn(self.quote_asset, msg["data"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_trade_update(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self._user_stream_event_trade_update())
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = await msg_queue.get()
        self.assertEqual("trade", msg["type"])
        self.assertEqual(67890, msg["data"][0]["transactionId"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_handles_ping_pong(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        
        ping_event = {"event": "ping"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(ping_event)
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        # Let the ping be processed
        await asyncio.sleep(0.1)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        
        # Should send pong response after subscriptions
        pong_sent = any(msg.get("event") == "pong" for msg in sent_messages)
        self.assertTrue(pong_sent)

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to private channels...")
        )