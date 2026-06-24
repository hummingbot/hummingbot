import unittest

from hummingbot.connector.exchange.twofinance.twofinance_matchengine_client import MatchEngineClient
from hummingbot.connector.exchange.twofinance.twofinance_matchengine_schemas import CommandStatus, OrderCommand
from hummingbot.core.web_assistant.connections.data_types import WSResponse


class FakeConnection:
    def __init__(self):
        self.connected = False


class FakeWSAssistant:
    def __init__(self):
        self._connection = FakeConnection()
        self.connect_calls = []
        self.sent_payloads = []
        self.incoming = []

    async def connect(self, ws_url, ws_headers=None, **kwargs):
        self._connection.connected = True
        self.connect_calls.append({"ws_url": ws_url, "ws_headers": ws_headers or {}, **kwargs})

    async def send(self, request):
        self.sent_payloads.append(dict(request.payload))

    async def receive(self):
        if not self.incoming:
            return None
        return WSResponse(self.incoming.pop(0))


class FakeAPIFactory:
    def __init__(self):
        self.ws = FakeWSAssistant()

    async def get_ws_assistant(self):
        return self.ws


class TwoFinanceMatchEngineClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api_factory = FakeAPIFactory()
        self.client = MatchEngineClient(
            api_factory=self.api_factory,
            ws_url="ws://matchengine.local:10000",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    async def test_send_command_connects_with_bearer_header_and_payload(self):
        command = OrderCommand(
            client_order_id="HBOT-2F-1",
            engine_id="engine-btc-usdt",
            symbol_id=1,
            market="BTC-USDT",
            wallet_id=7,
            side="BUY",
            order_type="LIMIT",
            quantity="1",
            price="100",
        )

        await self.client.send_command(command)

        self.assertEqual(self.api_factory.ws.connect_calls[0]["ws_url"], "ws://matchengine.local:10000")
        self.assertEqual(
            self.api_factory.ws.connect_calls[0]["ws_headers"],
            {"Authorization": "Bearer test-token"},
        )
        self.assertEqual(self.api_factory.ws.sent_payloads[0]["schema"], "matchengine.order_command.v1")
        self.assertEqual(self.api_factory.ws.sent_payloads[0]["client_order_id"], "HBOT-2F-1")
        self.assertEqual(self.api_factory.ws.sent_payloads[0]["idempotency_key"], "HBOT-2F-1")

    async def test_receive_ack_tracks_exchange_order_id(self):
        command = OrderCommand(
            client_order_id="HBOT-2F-2",
            engine_id="engine-btc-usdt",
            symbol_id=1,
            market="BTC-USDT",
            wallet_id=7,
            side="SELL",
            order_type="LIMIT",
            quantity="1",
            price="101",
        )
        await self.client.send_command(command)
        self.api_factory.ws.incoming.append(
            {
                "message_type": "ACK",
                "status": "accepted-to-queue",
                "client_order_id": "HBOT-2F-2",
                "order_id": 123,
            }
        )

        response = await self.client.receive_once()

        self.assertEqual(response.status, CommandStatus.ACCEPTED_TO_QUEUE)
        self.assertEqual(self.client.orders["HBOT-2F-2"].exchange_order_id, "123")
        self.assertEqual(self.client.orders_by_exchange_id["123"], "HBOT-2F-2")


if __name__ == "__main__":
    unittest.main()
