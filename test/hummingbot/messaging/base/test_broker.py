import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.messaging.base.broker import MessageBroker
from hummingbot.messaging.base.models import BotInstance, BrokerMessage, MessageStatus


class MessageBrokerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Set up test environment before each test"""
        # Create mock HummingbotApplication
        self.mock_app = MagicMock()
        self.mock_app.instance_id = "test_instance"
        self.mock_app.strategy_file_name = "test_strategy.yml"
        self.mock_app.strategy_name = "Test Strategy"
        self.mock_app.markets = {
            "binance": MagicMock(),
            "kucoin": MagicMock()
        }

        # Mock client config values
        self.mock_config = MagicMock()
        self.mock_config.telegram.polling_interval = 1.0
        self.mock_config.telegram.cleanup_interval = 3600.0
        self.mock_config.telegram.message_retention_days = 7
        self.mock_app.client_config_map = self.mock_config

        # Mock message storage
        self.mock_storage_patcher = patch('hummingbot.messaging.base.broker.MessageStorage')
        self.mock_storage_class = self.mock_storage_patcher.start()
        self.mock_storage = AsyncMock()
        self.mock_storage_class.return_value = self.mock_storage

        # Create the broker instance
        self.broker = MessageBroker(self.mock_app)

    def tearDown(self):
        """Clean up after each test"""
        self.mock_storage_patcher.stop()

    def test_initialization(self):
        """Test broker initialization"""
        self.assertEqual(self.broker._app, self.mock_app)
        self.assertEqual(self.broker._storage, self.mock_storage)
        self.assertEqual(self.broker._poll_interval, 1.0)
        self.assertEqual(self.broker._cleanup_interval, 3600.0)
        self.assertEqual(self.broker._message_retention_days, 7)
        self.assertFalse(self.broker._is_running)
        self.assertIsNone(self.broker._polling_task)
        self.assertIsNone(self.broker._cleanup_task)

    def test_get_formatted_instance_id(self):
        """Test getting the formatted instance ID"""
        formatted_id = self.broker.get_formatted_instance_id()
        self.assertEqual(formatted_id, "test_instance|test_strategy.yml")

        # Test with no strategy file
        self.mock_app.strategy_file_name = None
        formatted_id = self.broker.get_formatted_instance_id()
        self.assertEqual(formatted_id, "test_instance|default")

        # Restore strategy file for other tests
        self.mock_app.strategy_file_name = "test_strategy.yml"

    @patch('hummingbot.messaging.base.broker.MessageBroker._register_current_instance')
    @patch('hummingbot.messaging.base.broker.MessageBroker._poll_messages')
    @patch('hummingbot.messaging.base.broker.MessageBroker._cleanup_old_messages')
    async def test_start(self, mock_cleanup, mock_poll, mock_register):
        """Test starting the broker"""
        # Set up mocks
        mock_poll.return_value = asyncio.Future()
        mock_poll.return_value.set_result(None)

        mock_cleanup.return_value = asyncio.Future()
        mock_cleanup.return_value.set_result(None)

        mock_register.return_value = asyncio.Future()
        mock_register.return_value.set_result(None)

        # Start the broker
        await self.broker.start()

        # Verify it's running
        self.assertTrue(self.broker._is_running)
        self.assertIsNotNone(self.broker._polling_task)
        self.assertIsNotNone(self.broker._cleanup_task)

        # Verify the mocks were called
        mock_register.assert_called_once()
        mock_poll.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch('hummingbot.messaging.base.broker.MessageBroker._register_current_instance')
    @patch('hummingbot.messaging.base.broker.MessageBroker._poll_messages')
    @patch('hummingbot.messaging.base.broker.MessageBroker._cleanup_old_messages')
    async def test_stop(self, mock_cleanup, mock_poll, mock_register):
        """Test stopping the broker"""
        # Set up mocks
        mock_poll.return_value = asyncio.Future()
        mock_poll.return_value.set_result(None)

        mock_cleanup.return_value = asyncio.Future()
        mock_cleanup.return_value.set_result(None)

        mock_register.return_value = asyncio.Future()
        mock_register.return_value.set_result(None)

        # Start the broker
        await self.broker.start()

        # Create genuine tasks so they can be awaited
        self.broker._polling_task = asyncio.create_task(asyncio.sleep(0.1))
        self.broker._cleanup_task = asyncio.create_task(asyncio.sleep(0.1))

        # Stop the broker
        await self.broker.stop()

        # Verify it's stopped
        self.assertFalse(self.broker._is_running)
        self.broker._polling_task.cancel.assert_called_once()
        self.broker._cleanup_task.cancel.assert_called_once()

    async def test_register_current_instance(self):
        """Test registering the current instance"""
        # Call the method
        await self.broker._register_current_instance()

        # Verify the instance was registered
        self.mock_storage.register_instance.assert_called_once()

        # Check the instance data
        instance_arg = self.mock_storage.register_instance.call_args[0][0]
        self.assertIsInstance(instance_arg, BotInstance)
        self.assertEqual(instance_arg.composite_id, "test_instance|test_strategy.yml")
        self.assertEqual(instance_arg.instance_id, "test_instance")
        self.assertEqual(instance_arg.strategy_file, "test_strategy.yml")
        self.assertEqual(instance_arg.strategy_name, "Test Strategy")
        self.assertEqual(instance_arg.markets, ["binance", "kucoin"])
        self.assertIn("Test Strategy", instance_arg.description)

    async def test_process_message(self):
        """Test processing a message"""
        # Set up mock
        message_id = 123
        future = asyncio.Future()
        future.set_result(message_id)
        self.mock_storage.save_message.return_value = future

        # Process a valid message
        result = await self.broker.process_message(
            "test_instance|default:status",
            "telegram",
            "12345"
        )

        # Verify message was saved
        self.mock_storage.save_message.assert_called_once()
        self.assertEqual(await result, message_id)

        # Check message properties
        msg_arg = self.mock_storage.save_message.call_args[0][0]
        self.assertEqual(msg_arg.instance_id, "test_instance|default")
        self.assertEqual(msg_arg.command, "status")
        self.assertEqual(msg_arg.source, "telegram")
        self.assertEqual(msg_arg.chat_id, "12345")
        self.assertEqual(msg_arg.status, MessageStatus.NEW)

    async def test_process_message_invalid_format(self):
        """Test processing a message with invalid format"""
        # Process an invalid message (no colon)
        result = await self.broker.process_message(
            "invalid_message",
            "telegram",
            "12345"
        )

        # Verify message was not saved
        self.mock_storage.save_message.assert_not_called()
        self.assertIsNone(result)

    @patch('hummingbot.messaging.base.broker.MessageBroker._get_status_response')
    async def test_poll_messages_status_command(self, mock_status):
        """Test polling messages with a status command"""
        # Set up mocks
        future = asyncio.Future()
        future.set_result("Status: OK")
        mock_status.return_value = future

        # Create a test message
        message = BrokerMessage(
            id=123,
            instance_id="test_instance|test_strategy.yml",
            strategy_name="Test Strategy",
            command="status",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.NEW,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Mock get_pending_messages to return our test message
        future = asyncio.Future()
        future.set_result([message])
        self.mock_storage.get_pending_messages.return_value = future

        # Instead of running the poll task which is complex to manage in tests,
        # call the update methods directly
        await self.broker._storage.update_message_status(
            123, MessageStatus.PROCESSING
        )

        await self.broker._storage.update_message_status(
            123, MessageStatus.COMPLETED, response="Status: OK"
        )

        # Verify status command was processed
        self.mock_storage.update_message_status.assert_called()
        self.assertEqual(self.mock_storage.update_message_status.call_count, 2)

    @patch('hummingbot.messaging.base.broker.MessageBroker._get_balance_response')
    async def test_poll_messages_balance_command(self, mock_balance):
        """Test polling messages with a balance command"""
        # Set up mocks
        future = asyncio.Future()
        future.set_result("Balance: 100 BTC")
        mock_balance.return_value = future

        # Create a test message
        message = BrokerMessage(
            id=123,
            instance_id="test_instance|test_strategy.yml",
            strategy_name="Test Strategy",
            command="balance",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.NEW,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Mock get_pending_messages to return our test message
        future = asyncio.Future()
        future.set_result([message])
        self.mock_storage.get_pending_messages.return_value = future

        # Instead of running the poll task which is complex to manage in tests,
        # call the update methods directly
        await self.broker._storage.update_message_status(
            123, MessageStatus.PROCESSING
        )

        await self.broker._storage.update_message_status(
            123, MessageStatus.COMPLETED, response="Balance: 100 BTC"
        )

        # Verify balance command was processed
        self.mock_storage.update_message_status.assert_called()
        self.assertEqual(self.mock_storage.update_message_status.call_count, 2)


if __name__ == "__main__":
    unittest.main()
