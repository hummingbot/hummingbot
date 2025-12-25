import asyncio
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_api_order_book_data_source import (
    EvedexPerpetualAPIOrderBookDataSource,
)


class DummyWSAssistant:
    def __init__(self):
        self.connected = False
        self.sent = []

    async def connect(self, ws_url: str, ping_timeout: int, **kwargs):
        self.connected = True

    async def send(self, request):
        self.sent.append(request.payload)

    async def iter_messages(self):
        yield SimpleNamespace(data=None)


class DummyRESTAssistant:
    async def execute_request(self, *args, **kwargs):
        return {}


class EvedexPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.ws_assistant = DummyWSAssistant()
        self.rest_assistant = DummyRESTAssistant()
        self.data_source = EvedexPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-USD"],
            rest_assistant=self.rest_assistant,
            ws_assistant=self.ws_assistant,
            throttler=None,  # Not used in tests
            environment="demo",
        )

    async def test_subscribe_public_channels_sends_requests(self):
        await self.data_source._subscribe_public_channels()

        channels = [payload["params"]["channel"] for payload in self.ws_assistant.sent]
        self.assertIn("futures-perp-demo:orderBook-BTCUSD-0.1", channels)
        self.assertIn("futures-perp-demo:recent-trade-BTCUSD", channels)

    def test_build_order_book_diff_returns_message(self):
        channel = "futures-perp-demo:orderBook-BTCUSD-0.1"
        message = self.data_source._build_order_book_diff(
            channel,
            {"t": 1234567890, "bids": [[1, 2]], "asks": [[3, 4]]},
        )

        self.assertIsNotNone(message)
        self.assertEqual("BTC-USD", message.content["trading_pair"])
        self.assertEqual(1234567890, message.content["update_id"])

    def test_build_trade_message_returns_message(self):
        channel = "futures-perp-demo:recent-trade-BTCUSD"
        message = self.data_source._build_trade_message(
            channel,
            {"t": 1234567890, "tradeId": "id-1", "price": "100", "quantity": "0.1"},
        )

        self.assertIsNotNone(message)
        self.assertEqual("BTC-USD", message.content["trading_pair"])
        self.assertEqual("id-1", message.content["trade_id"])
