from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_user_stream_data_source import (
    GrvtPerpetualAPIUserStreamDataSource,
)


class GrvtPerpetualAPIUserStreamDataSourceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.auth = MagicMock()
        self.auth.get_ws_auth_headers = AsyncMock(return_value={"Cookie": "gravity=cookie"})
        self.connector = MagicMock()
        self.connector.trading_account_id = "123456"
        self.api_factory = MagicMock()
        self.ws = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws)
        self.data_source = GrvtPerpetualAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=["BTC-USDT"],
            connector=self.connector,
            api_factory=self.api_factory,
        )

    async def test_connected_websocket_assistant(self):
        ws = await self.data_source._connected_websocket_assistant()
        self.assertEqual(self.ws, ws)
        self.ws.connect.assert_awaited()

    async def test_subscribe_channels(self):
        await self.data_source._subscribe_channels(self.ws)
        self.assertEqual(4, self.ws.send.await_count)
