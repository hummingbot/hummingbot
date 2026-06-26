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

    async def test_simple_ack_is_associated_with_pending_command_without_order_id(self):
        command = OrderCommand(
            client_order_id="HBOT-2F-3",
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
        self.api_factory.ws.incoming.append({"type": 12, "timestamp": 123456789})

        response = await self.client.receive_once()

        self.assertEqual(response.status, CommandStatus.ACCEPTED_TO_QUEUE)
        self.assertIs(self.client.orders["HBOT-2F-3"].last_response, response)
        self.assertIsNone(self.client.orders["HBOT-2F-3"].exchange_order_id)

        self.api_factory.ws.incoming.append(
            {
                "schema": "matchengine.event.v1",
                "sequence": 1,
                "event_id": "engine:1",
                "event_type": "ORDER_ACCEPTED",
                "symbol_id": 1,
                "payload": {"client_order_id": "HBOT-2F-3", "order_id": 124, "order_status": 1},
            }
        )
        exchange_order_id = await self.client.wait_for_exchange_order_id("HBOT-2F-3", 1)

        self.assertEqual(exchange_order_id, "124")
        self.assertEqual(self.client.orders_by_exchange_id["124"], "HBOT-2F-3")

    async def test_cancel_ack_does_not_steal_exchange_order_mapping(self):
        create_command = OrderCommand(
            client_order_id="HBOT-2F-OPEN",
            engine_id="engine-btc-usdt",
            symbol_id=1,
            market="BTC-USDT",
            wallet_id=7,
            side="BUY",
            order_type="LIMIT",
            quantity="1",
            price="100",
        )
        cancel_command = OrderCommand(
            client_order_id="HBOT-2F-CANCEL",
            engine_id="engine-btc-usdt",
            symbol_id=1,
            market="BTC-USDT",
            wallet_id=7,
            side="BUY",
            order_type="LIMIT",
            quantity="0",
            operation="DELETE",
            order_id="124",
        )
        await self.client.send_command(create_command)
        self.api_factory.ws.incoming.append(
            {
                "schema": "matchengine.event.v1",
                "sequence": 1,
                "event_id": "engine:1",
                "event_type": "ORDER_ACCEPTED",
                "symbol_id": 1,
                "payload": {"client_order_id": "HBOT-2F-OPEN", "order_id": 124, "order_status": 1},
            }
        )
        await self.client.receive_once()

        await self.client.send_command(cancel_command)
        self.api_factory.ws.incoming.append(
            {
                "message_type": "ACK",
                "status": "accepted-to-queue",
                "client_order_id": "HBOT-2F-CANCEL",
                "order_id": 124,
            }
        )
        await self.client.receive_once()

        self.assertEqual(self.client.orders_by_exchange_id["124"], "HBOT-2F-OPEN")

    async def test_reject_without_client_order_id_fails_pending_command_response(self):
        command = OrderCommand(
            client_order_id="HBOT-2F-4",
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
        self.api_factory.ws.incoming.append(
            {
                "schema": "matchengine.order_response.v1",
                "message_type": "REJECT",
                "status": "rejected",
                "reason_code": "INVALID_MESSAGE_ORDER_LIMIT",
                "error_code": 35,
            }
        )

        response = await self.client.receive_once()

        self.assertEqual(response.status, CommandStatus.REJECTED_BY_PARSER)
        self.assertEqual(response.reason, "INVALID_MESSAGE_ORDER_LIMIT")
        self.assertIs(self.client.orders["HBOT-2F-4"].last_response, response)


if __name__ == "__main__":
    unittest.main()
