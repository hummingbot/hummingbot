import asyncio
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.polkadex.polkadex_query_executor import GrapQLQueryExecutor


class PolkadexQueryExecutorTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.AppSyncWebsocketsTransport")
    @patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.Client")
    def test_create_ws_session(self, mock_client, mock_transport):
        exec = GrapQLQueryExecutor(MagicMock(), "")
        mock_client_obj = MagicMock()
        mock_client.return_value = mock_client_obj
        mock_client_obj.connect_async.side_effect = AsyncMock(return_value="Done")
        result = self.async_run_with_timeout(exec.create_ws_session())
        self.assertIsNone(result)
