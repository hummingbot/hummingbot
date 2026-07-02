import unittest

from hummingbot.connector.exchange.twofinance.twofinance_api_user_stream_data_source import (
    TwoFinanceAPIUserStreamDataSource,
)


class FakeWSAssistant:
    def __init__(self):
        self.connect_calls = []
        self.sent_payloads = []

    async def connect(self, ws_url, ws_headers=None, **kwargs):
        self.connect_calls.append({"ws_url": ws_url, "ws_headers": ws_headers or {}, **kwargs})

    async def send(self, request):
        self.sent_payloads.append(dict(request.payload))


class FakeAPIFactory:
    def __init__(self):
        self.ws = FakeWSAssistant()

    async def get_ws_assistant(self):
        return self.ws


class TwoFinanceAPIUserStreamDataSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_stream_connects_with_bearer_and_subscribes_private_channels(self):
        api_factory = FakeAPIFactory()
        data_source = TwoFinanceAPIUserStreamDataSource(
            api_factory=api_factory,
            auth_headers={"Authorization": "Bearer private-token"},
            engine_id="engine-btc-usdt",
            wallet_id=7,
            ws_url="ws://matchengine.local:10000",
        )

        ws = await data_source._connected_websocket_assistant()
        await data_source._subscribe_channels(ws)

        self.assertEqual(api_factory.ws.connect_calls[0]["ws_url"], "ws://matchengine.local:10000")
        self.assertEqual(
            api_factory.ws.connect_calls[0]["ws_headers"],
            {"Authorization": "Bearer private-token"},
        )
        self.assertEqual(api_factory.ws.sent_payloads[0], {"method": "subscribe", "params": ["7@WALLET"]})


if __name__ == "__main__":
    unittest.main()
