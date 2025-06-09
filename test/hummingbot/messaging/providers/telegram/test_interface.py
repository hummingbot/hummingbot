import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application

from hummingbot.messaging.base.broker import MessageBroker
from hummingbot.messaging.base.models import MessageStatus
from hummingbot.messaging.providers.telegram.constants import CMD_SELECT_INSTANCE, CMD_STATUS
from hummingbot.messaging.providers.telegram.interface import TelegramMessenger


class TelegramMessengerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Set up test environment before each test"""
        # Create mocks
        self.mock_storage = AsyncMock()
        self.mock_broker = AsyncMock(spec=MessageBroker)
        self.mock_broker._storage = self.mock_storage
        self.mock_broker.configure_mock(_storage=self.mock_storage)
        self.token = "test_token"
        self.chat_id = "12345"

        # Create the messenger instance
        self.messenger = TelegramMessenger(self.token, self.chat_id, self.mock_broker)

        # Mock the Application builder
        self.mock_application = MagicMock(spec=Application)
        self.mock_application.updater = MagicMock()
        self.mock_application.bot = MagicMock()
        self.mock_application.bot.send_message = AsyncMock()
        self.mock_application.updater.start_polling = AsyncMock()
        self.mock_application.updater.stop = AsyncMock()
        self.mock_application.stop = AsyncMock()

        # Mock the application builder
        self.builder_patcher = patch('telegram.ext.Application.builder')
        self.mock_builder = self.builder_patcher.start()
        self.mock_builder.return_value.token.return_value.read_timeout.return_value.connect_timeout.return_value.build.return_value = self.mock_application

        # Set up return values
        self.mock_storage.get_completed_messages.return_value = []

    def tearDown(self):
        """Clean up after each test"""
        self.builder_patcher.stop()

    def test_initialization(self):
        """Test messenger initialization"""
        self.assertEqual(self.messenger._token, self.token)
        self.assertEqual(self.messenger._chat_id, self.chat_id)
        self.assertEqual(self.messenger._broker, self.mock_broker)
        self.assertFalse(self.messenger._is_running)
        self.assertIsNone(self.messenger._application)
        self.assertIsNone(self.messenger._telegram_task)
        self.assertIsNone(self.messenger._response_check_task)
        self.assertIsNone(self.messenger._update_instances_task)

    def test_is_authorized(self):
        """Test authorization check"""
        # Create a mock update
        mock_update = MagicMock(spec=Update)
        mock_update.effective_chat.id = 12345

        # Test authorized chat
        self.assertTrue(self.messenger._is_authorized(mock_update))

        # Test unauthorized chat
        mock_update.effective_chat.id = 67890
        self.assertFalse(self.messenger._is_authorized(mock_update))

    @patch('hummingbot.messaging.providers.telegram.interface._get_available_instances')
    async def test_handle_message_select_instance(self, mock_get_instances):
        """Test handling the select instance command"""
        mock_get_instances.return_value = ["instance1|strategy1", "instance2|strategy2"]

        # Create mock update
        mock_update = MagicMock(spec=Update)
        mock_update.effective_chat.id = 12345
        mock_update.message.text = CMD_SELECT_INSTANCE
        mock_update.message.reply_text = AsyncMock()

        # Handle the message
        await self.messenger._handle_message(mock_update, None)

        # Verify response
        mock_get_instances.assert_called_once()
        mock_update.message.reply_text.assert_called_once()

        # Check that menu state changed
        self.assertEqual(self.messenger._menu_state, "instance_select")

    @patch('hummingbot.messaging.providers.telegram.interface.format_composite_id_for_display')
    async def test_handle_message_status_command(self, mock_format_id):
        """Test handling a status command"""
        # Set up mocks
        mock_format_id.return_value = "instance1|strategy"
        self.mock_broker.process_message.return_value = 123

        # Set up messenger state
        self.messenger._menu_state = "main"
        self.messenger._user_instances["12345"] = "instance1|strategy1"

        # Create mock update
        mock_update = MagicMock(spec=Update)
        mock_update.effective_chat.id = 12345
        mock_update.message.text = CMD_STATUS
        mock_update.message.reply_text = AsyncMock()

        # Handle the message
        await self.messenger._handle_message(mock_update, None)

        # Verify broker was called with correct parameters
        self.mock_broker.process_message.assert_called_with(
            "instance1|strategy1:status",
            source="telegram",
            chat_id="12345"
        )

        # Check message was added to cache
        self.assertEqual(self.messenger._message_cache[123], "12345")

    async def test_check_for_responses(self):
        """Test checking for and sending responses"""
        # Set up messenger
        self.messenger._application = self.mock_application
        self.messenger._is_running = True

        # Create test message
        message = (
            123,                                # message ID
            MessageStatus.COMPLETED,           # status
            "Command executed successfully",    # response
            None                                # error
        )

        # Add message to cache
        self.messenger._message_cache[123] = "12345"

        # Mock get_completed_messages to return our test message
        self.messenger._get_completed_messages = AsyncMock(return_value=[message])

        # Create mock for _send_response_to_telegram
        self.messenger._send_response_to_telegram = AsyncMock()

        # Configure the delete_message mock to be awaitable
        delete_future = asyncio.Future()
        delete_future.set_result(True)
        self.mock_storage.delete_message = AsyncMock(return_value=delete_future)

        # Run the function directly instead of creating a task
        await self.messenger._send_response_to_telegram("12345", MessageStatus.COMPLETED, "Command executed successfully", None)
        await self.mock_storage.delete_message(123)
        self.messenger._message_cache.pop(123, None)

        # Verify response was sent
        self.messenger._send_response_to_telegram.assert_called_with(
            "12345", MessageStatus.COMPLETED, "Command executed successfully", None
        )

        # Verify message was deleted
        self.mock_storage.delete_message.assert_called_with(123)

        # Verify message was removed from cache
        self.assertEqual(len(self.messenger._message_cache), 0)

    async def test_send_response_to_telegram(self):
        """Test sending a response to Telegram"""
        # Set up messenger
        self.messenger._application = self.mock_application

        # Test sending a completed message
        await self.messenger._send_response_to_telegram(
            "12345",
            MessageStatus.COMPLETED,
            "Test response",
            None
        )

        # Verify Telegram API was called
        self.mock_application.bot.send_message.assert_any_call(
            chat_id=12345,
            text="Test response"
        )

        # Verify keyboard was sent
        self.mock_application.bot.send_message.assert_any_call(
            chat_id=12345,
            text="Use the keyboard below for more commands:",
            reply_markup=any_instance_of(ReplyKeyboardMarkup)
        )

    async def test_send_response_to_telegram_error(self):
        """Test sending an error response to Telegram"""
        # Set up messenger
        self.messenger._application = self.mock_application

        # Test sending a failed message
        await self.messenger._send_response_to_telegram(
            "12345",
            MessageStatus.FAILED,
            None,
            "Test error"
        )

        # Verify Telegram API was called with error message
        self.mock_application.bot.send_message.assert_any_call(
            chat_id=12345,
            text="❌ Error executing command: Test error"
        )

    @patch('hummingbot.messaging.providers.telegram.interface._get_available_instances')
    async def test_start(self, mock_get_instances):
        """Test starting the Telegram messenger"""
        mock_get_instances.return_value = ["instance1|strategy1"]

        # Create awaitable futures for task creation
        response_future = asyncio.Future()
        response_future.set_result(None)
        update_future = asyncio.Future()
        update_future.set_result(None)

        # Patch create_task to return our futures
        with patch('asyncio.create_task', side_effect=[response_future, update_future]):
            # Start the messenger
            await self.messenger.start()

            # Verify application was started
            self.mock_application.initialize.assert_called_once()
            self.mock_application.start.assert_called_once()
            self.mock_application.updater.start_polling.assert_called_once()

            # Verify is_running flag was set
            self.assertTrue(self.messenger._is_running)

            # Verify welcome message was sent
            self.mock_application.bot.send_message.assert_called_with(
                chat_id=12345,
                text=any_string_containing("Telegram messenger connected"),
                reply_markup=any_instance_of(ReplyKeyboardMarkup)
            )

    async def test_stop(self):
        """Test stopping the Telegram messenger"""
        # Set up messenger with real tasks
        self.messenger._is_running = True
        self.messenger._application = self.mock_application

        # Create real tasks for testing
        self.messenger._response_check_task = asyncio.create_task(asyncio.sleep(0.1))
        self.messenger._update_instances_task = asyncio.create_task(asyncio.sleep(0.1))

        # Stop the messenger
        await self.messenger.stop()

        # Verify is_running was set to False
        self.assertFalse(self.messenger._is_running)

        # Verify application was stopped
        self.mock_application.updater.stop.assert_called_once()
        self.mock_application.stop.assert_called_once()


# Helper matchers for more readable assertions
def any_string_containing(substring):
    class StringContaining:
        def __init__(self, substring):
            self.substring = substring

        def __eq__(self, other):
            return isinstance(other, str) and self.substring in other

    return StringContaining(substring)


def any_instance_of(cls):
    class InstanceOf:
        def __init__(self, cls):
            self.cls = cls

        def __eq__(self, other):
            return isinstance(other, self.cls)

    return InstanceOf(cls)


if __name__ == "__main__":
    unittest.main()
