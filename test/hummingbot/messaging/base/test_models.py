import unittest
from datetime import datetime

from hummingbot.messaging.base.models import BotInstance, BrokerMessage, MessageStatus


class MessageModelsTest(unittest.TestCase):
    def test_message_status_enum(self):
        """Test that MessageStatus enum has the expected values"""
        self.assertEqual(MessageStatus.NEW.value, "new")
        self.assertEqual(MessageStatus.PROCESSING.value, "processing")
        self.assertEqual(MessageStatus.COMPLETED.value, "completed")
        self.assertEqual(MessageStatus.FAILED.value, "failed")

    def test_broker_message_creation(self):
        """Test creating a BrokerMessage instance"""
        now = datetime.utcnow()
        message = BrokerMessage(
            id=123,
            instance_id="test_instance|default",
            strategy_name="some_strategy",
            command="status",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.NEW,
            created_at=now,
            updated_at=now,
            response=None,
            error=None
        )

        self.assertEqual(message.id, 123)
        self.assertEqual(message.instance_id, "test_instance|default")
        self.assertEqual(message.strategy_name, "some_strategy")
        self.assertEqual(message.command, "status")
        self.assertEqual(message.source, "telegram")
        self.assertEqual(message.chat_id, "12345")
        self.assertEqual(message.status, MessageStatus.NEW)
        self.assertEqual(message.created_at, now)
        self.assertEqual(message.updated_at, now)
        self.assertIsNone(message.response)
        self.assertIsNone(message.error)

    def test_broker_message_with_response(self):
        """Test BrokerMessage with response and error"""
        now = datetime.utcnow()
        message = BrokerMessage(
            id=124,
            instance_id="test_instance|default",
            strategy_name="some_strategy",
            command="status",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.COMPLETED,
            created_at=now,
            updated_at=now,
            response="Command executed successfully",
            error=None
        )

        self.assertEqual(message.status, MessageStatus.COMPLETED)
        self.assertEqual(message.response, "Command executed successfully")
        self.assertIsNone(message.error)

    def test_broker_message_with_error(self):
        """Test BrokerMessage with error"""
        now = datetime.utcnow()
        message = BrokerMessage(
            id=125,
            instance_id="test_instance|default",
            strategy_name="some_strategy",
            command="invalid_command",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.FAILED,
            created_at=now,
            updated_at=now,
            response=None,
            error="Invalid command"
        )

        self.assertEqual(message.status, MessageStatus.FAILED)
        self.assertIsNone(message.response)
        self.assertEqual(message.error, "Invalid command")

    def test_bot_instance_creation(self):
        """Test creating a BotInstance"""
        instance = BotInstance(
            composite_id="instance_1|strategy_1",
            instance_id="instance_1",
            strategy_file="strategy_1",
            strategy_name="Strategy One",
            markets=["binance", "kucoin"],
            description="Test bot instance"
        )

        self.assertEqual(instance.composite_id, "instance_1|strategy_1")
        self.assertEqual(instance.instance_id, "instance_1")
        self.assertEqual(instance.strategy_file, "strategy_1")
        self.assertEqual(instance.strategy_name, "Strategy One")
        self.assertEqual(instance.markets, ["binance", "kucoin"])
        self.assertEqual(instance.description, "Test bot instance")

    def test_bot_instance_with_minimal_args(self):
        """Test creating a BotInstance with minimal arguments"""
        instance = BotInstance(
            composite_id="instance_2|strategy_2",
            instance_id="instance_2",
            strategy_file="strategy_2"
        )

        self.assertEqual(instance.composite_id, "instance_2|strategy_2")
        self.assertEqual(instance.instance_id, "instance_2")
        self.assertEqual(instance.strategy_file, "strategy_2")
        self.assertIsNone(instance.strategy_name)
        self.assertIsNone(instance.markets)
        self.assertIsNone(instance.description)


if __name__ == "__main__":
    unittest.main()
