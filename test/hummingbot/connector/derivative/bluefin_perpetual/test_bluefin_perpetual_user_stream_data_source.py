import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_user_stream_data_source import (
    BluefinPerpetualUserStreamDataSource,
)


class BluefinPerpetualUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.trading_pair = "BTC-USD"

    def setUp(self) -> None:
        super().setUp()

        self.connector = MagicMock()
        factory = MagicMock()
        factory.get_ws_assistant = AsyncMock(return_value=MagicMock())
        setattr(self.connector, "_web_assistants_factory", factory)

        self.data_source = MagicMock()
        self.data_source.get_account_order_event = AsyncMock(return_value={"event": "order"})
        self.data_source.get_account_trade_event = AsyncMock(side_effect=asyncio.CancelledError)
        self.data_source.get_account_position_event = AsyncMock(side_effect=asyncio.CancelledError)
        self.data_source.get_account_balance_event = AsyncMock(side_effect=asyncio.CancelledError)

        self.user_stream_source = BluefinPerpetualUserStreamDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            data_source=self.data_source,
        )

    async def test_listen_for_user_stream_forwards_first_event(self):
        output: asyncio.Queue[Any] = asyncio.Queue()

        task = self.local_event_loop.create_task(self.user_stream_source.listen_for_user_stream(output=output))

        event = await asyncio.wait_for(output.get(), timeout=1)
        self.assertEqual({"event": "order"}, event)

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
