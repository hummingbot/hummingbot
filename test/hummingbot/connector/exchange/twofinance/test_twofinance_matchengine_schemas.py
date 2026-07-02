import unittest
from decimal import Decimal

from hummingbot.connector.exchange.twofinance.twofinance_matchengine_schemas import (
    CommandStatus,
    MatchEngineEvent,
    OrderCommand,
    event_order_state,
    parse_command_response,
)
from hummingbot.core.data_type.in_flight_order import OrderState


class TwoFinanceMatchEngineSchemasTests(unittest.TestCase):
    def test_order_command_serializes_canonical_schema(self):
        command = OrderCommand(
            client_order_id="HBOT-2F-1",
            engine_id="engine-btc-usdt",
            symbol_id=1,
            market="BTC-USDT",
            wallet_id=7,
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("0.1"),
            price=Decimal("100.50"),
            time_in_force="GTC",
        )

        payload = command.to_payload()

        self.assertEqual(payload["schema"], "matchengine.order_command.v1")
        self.assertEqual(payload["operation"], "ADD")
        self.assertEqual(payload["client_order_id"], "HBOT-2F-1")
        self.assertEqual(payload["idempotency_key"], "HBOT-2F-1")
        self.assertEqual(payload["quantity"], "0.1")
        self.assertEqual(payload["price"], "100.50")

    def test_command_response_parses_ack_and_reject(self):
        ack = parse_command_response(
            {"message_type": "ACK", "status": "accepted-to-queue", "client_order_id": "cid", "order_id": 42}
        )
        reject = parse_command_response(
            {"message_type": "ERROR", "error_code": "BALANCE_INSUFICIENT", "client_order_id": "cid"}
        )

        self.assertEqual(ack.status, CommandStatus.ACCEPTED_TO_QUEUE)
        self.assertEqual(ack.order_id, "42")
        self.assertEqual(reject.status, CommandStatus.REJECTED_BY_RISK)

        simple_ack = parse_command_response({"type": 12, "timestamp": 123456789})
        real_reject = parse_command_response(
            {
                "schema": "matchengine.order_response.v1",
                "message_type": "REJECT",
                "status": "rejected",
                "reason_code": "INVALID_MESSAGE_ORDER_LIMIT",
                "error_code": 35,
            }
        )

        self.assertEqual(simple_ack.status, CommandStatus.ACCEPTED_TO_QUEUE)
        self.assertIsNone(simple_ack.client_order_id)
        self.assertIsNone(simple_ack.order_id)
        self.assertEqual(real_reject.status, CommandStatus.REJECTED_BY_PARSER)
        self.assertEqual(real_reject.reason, "INVALID_MESSAGE_ORDER_LIMIT")

    def test_event_order_state_uses_engine_status(self):
        event = MatchEngineEvent.from_payload(
            {
                "schema": "matchengine.event.v1",
                "sequence": 2,
                "event_id": "engine:2",
                "event_type": "ORDER_EXECUTED",
                "symbol_id": 1,
                "market": "BTC-USDT",
                "payload": {"order_status": 2, "client_order_id": "cid", "order_id": 99},
            }
        )

        self.assertEqual(event_order_state(event), OrderState.FILLED)


if __name__ == "__main__":
    unittest.main()
