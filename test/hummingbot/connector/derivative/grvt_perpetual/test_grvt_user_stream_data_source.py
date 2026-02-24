import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.grvt_perpetual.grvt_auth import GrvtAuth
from hummingbot.connector.derivative.grvt_perpetual.grvt_user_stream_data_source import (
    GrvtUserStreamDataSource,
)


class GrvtUserStreamDataSourceTests(TestCase):
    def test_subscribe_channels(self):
        auth = GrvtAuth(api_key="k", api_secret="s")
        connector = MagicMock()
        connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-USDC")
        api_factory = MagicMock()
        ws = AsyncMock()
        api_factory.get_ws_assistant = AsyncMock(return_value=ws)

        ds = GrvtUserStreamDataSource(
            auth=auth,
            trading_pairs=["BTC-USDC"],
            connector=connector,
            api_factory=api_factory,
        )
        asyncio.run(ds._subscribe_channels(ws))
        self.assertTrue(ws.send.called)
