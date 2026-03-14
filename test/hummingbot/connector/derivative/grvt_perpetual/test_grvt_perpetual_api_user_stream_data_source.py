import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_user_stream_data_source import (
    GRVTPerpetualUserStreamDataSource,
)


class GRVTPerpetualUserStreamDataSourceTests(TestCase):
    def setUp(self):
        self.auth = MagicMock()
        self.auth.get_auth_headers = MagicMock(return_value={"GRVT-API-KEY": "test_key"})
        
        self.connector = MagicMock()
        
        self.data_source = GRVTPerpetualUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=MagicMock(),
            domain="grvt_perpetual",
        )


class GRVTPerpetualUserStreamDataSourceAsyncTests(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.trading_pair = "BTC-USDT"

    async def asyncSetUp(self):
        await super().asyncSetUp()
        
        self.auth = MagicMock()
        self.auth.get_auth_headers = MagicMock(return_value={"GRVT-API-KEY": "test_key"})
        
        self.connector = MagicMock()
        
        self.data_source = GRVTPerpetualUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=MagicMock(),
            domain="grvt_perpetual",
        )

    async def test_subscribe_channels(self):
        ws_assistant = AsyncMock()
        
        await self.data_source._subscribe_channels(ws_assistant)
        
        # Verify that send was called
        ws_assistant.send.assert_called_once()

    async def test_on_user_stream_interruption(self):
        ws_assistant = AsyncMock()
        
        await self.data_source._on_user_stream_interruption(ws_assistant)
        
        # Verify disconnect was called
        ws_assistant.disconnect.assert_called_once()

    async def test_connected_websocket_assistant(self):
        api_factory = AsyncMock()
        ws_assistant = AsyncMock()
        api_factory.get_ws_assistant = AsyncMock(return_value=ws_assistant)
        
        self.data_source._api_factory = api_factory
        
        result = await self.data_source._connected_websocket_assistant()
        
        # Verify connection was attempted
        ws_assistant.connect.assert_called_once()
