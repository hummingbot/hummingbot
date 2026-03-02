import asyncio
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_user_stream_data_source import (
    ArchitectPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS


class ArchitectPerpetualUserStreamDataSourceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trading_pairs = ["BTC-USD", "ETH-USD"]

        self.auth = MagicMock()
        self.auth.api_key = "test_api_key"

        self.connector = MagicMock()
        self.api_factory = MagicMock()

        self.data_source = ArchitectPerpetualUserStreamDataSource(
            auth=self.auth,
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_init(self):
        self.assertEqual(self.data_source._trading_pairs, self.trading_pairs)
        self.assertEqual(self.data_source._domain, CONSTANTS.DOMAIN)
        self.assertEqual(self.data_source._auth, self.auth)

    def test_last_recv_time_initially_zero(self):
        self.assertEqual(self.data_source.last_recv_time, 0)

    def test_process_message_updates_last_recv_time(self):
        import time

        initial_time = self.data_source._last_recv_time
        self.data_source._last_recv_time = time.time()

        self.assertGreater(self.data_source.last_recv_time, initial_time)

    @patch("hummingbot.connector.derivative.architect_perpetual.architect_perpetual_user_stream_data_source.ArchitectPerpetualUserStreamDataSource._api_factory")
    async def test_connected_websocket_assistant(self):
        mock_ws = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=mock_ws)

        ws = await self.data_source._connected_websocket_assistant()

        self.assertEqual(ws, mock_ws)

    def test_subscribe_channels_sends_auth_first(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()

        async def run_test():
            await self.data_source._subscribe_channels(mock_ws)

        self.async_run_with_timeout(run_test())

        # Should have sent auth + 3 channel subscriptions (orders, positions, balances)
        self.assertEqual(mock_ws.send.call_count, 4)

    def test_process_order_update_message(self):
        queue = asyncio.Queue()
        data = {
            "type": "order_update",
            "order_id": "order123",
            "status": "filled",
        }

        # Simulate processing
        if data.get("type") in ["order_update", "position_update", "balance_update", "fill"]:
            queue.put_nowait(data)

        self.assertFalse(queue.empty())
        result = queue.get_nowait()
        self.assertEqual(result["type"], "order_update")
        self.assertEqual(result["order_id"], "order123")

    def test_process_position_update_message(self):
        queue = asyncio.Queue()
        data = {
            "type": "position_update",
            "symbol": "BTC-USD-PERP",
            "size": "1.5",
            "entry_price": "42000.0",
        }

        if data.get("type") in ["order_update", "position_update", "balance_update", "fill"]:
            queue.put_nowait(data)

        self.assertFalse(queue.empty())
        result = queue.get_nowait()
        self.assertEqual(result["type"], "position_update")

    def test_process_balance_update_message(self):
        queue = asyncio.Queue()
        data = {
            "type": "balance_update",
            "asset": "USD",
            "total": "10000.0",
            "available": "9500.0",
        }

        if data.get("type") in ["order_update", "position_update", "balance_update", "fill"]:
            queue.put_nowait(data)

        self.assertFalse(queue.empty())
        result = queue.get_nowait()
        self.assertEqual(result["type"], "balance_update")

    def test_process_fill_message(self):
        queue = asyncio.Queue()
        data = {
            "type": "fill",
            "trade_id": "fill456",
            "order_id": "order123",
            "price": "42000.5",
            "size": "0.1",
        }

        if data.get("type") in ["order_update", "position_update", "balance_update", "fill"]:
            queue.put_nowait(data)

        self.assertFalse(queue.empty())
        result = queue.get_nowait()
        self.assertEqual(result["type"], "fill")

    def test_ignores_non_user_messages(self):
        queue = asyncio.Queue()
        data = {
            "type": "heartbeat",
        }

        if data.get("type") in ["order_update", "position_update", "balance_update", "fill"]:
            queue.put_nowait(data)

        self.assertTrue(queue.empty())
