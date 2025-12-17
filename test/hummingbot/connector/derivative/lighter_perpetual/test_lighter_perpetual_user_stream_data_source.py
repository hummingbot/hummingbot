import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, call

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterPerpetualAuth
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import LighterPerpetualDerivative
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source import (
    LighterPerpetualUserStreamDataSource,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterPerpetualUserStreamDataSourceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.loop = asyncio.get_event_loop()
        self.auth = AsyncMock(spec=LighterPerpetualAuth)
        self.auth.create_auth_token = AsyncMock(return_value="token")
        self.connector = MagicMock(spec=LighterPerpetualDerivative)
        self.connector.account_index = 1
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="1")
        self.api_factory = MagicMock(spec=WebAssistantsFactory)
        self.ws = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws)
        self.data_source = LighterPerpetualUserStreamDataSource(
            auth=self.auth,
            trading_pairs=["BTC-USD"],
            connector=self.connector,
            api_factory=self.api_factory,
        )

    async def test_subscribe_channels(self):
        await self.data_source._subscribe_channels(self.ws)
        payloads = [call.args[0].payload for call in self.ws.send.call_args_list]
        expected_channels = {
            CONSTANTS.PRIVATE_WS_ACCOUNT_ALL_CHANNEL.format(account_index=1),
            CONSTANTS.PRIVATE_WS_ACCOUNT_ALL_ORDERS_CHANNEL.format(account_index=1),
            CONSTANTS.PRIVATE_WS_ACCOUNT_ALL_TRADES_CHANNEL.format(account_index=1),
            CONSTANTS.PRIVATE_WS_ACCOUNT_ALL_POSITIONS_CHANNEL.format(account_index=1),
            CONSTANTS.PRIVATE_WS_ACCOUNT_MARKET_CHANNEL.format(
                account_index=1, market_id="1"
            ),
        }
        sent_channels = {payload["channel"] for payload in payloads}
        self.assertEqual(expected_channels, sent_channels)
        for payload in payloads:
            self.assertEqual("token", payload["auth"])

    async def test_process_event_message_puts_on_queue(self):
        queue = asyncio.Queue()
        event = {"channel": "account_all_orders/1", "data": {}}
        await self.data_source._process_event_message(event, queue)
        self.assertEqual(event, await queue.get())

    async def test_process_event_message_raises_on_error(self):
        queue = asyncio.Queue()
        with self.assertRaises(IOError):
            await self.data_source._process_event_message({"type": "error"}, queue)
