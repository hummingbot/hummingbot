from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, Mock, patch

from hummingbot.command_iface.base import CommandInterface
from hummingbot.command_iface.exceptions import CommandDisabledError


class TestCommandImplementation:
    """Helper class for testing CommandInterface implementation"""

    def __init__(self, hb_app):
        self.interface = CommandInterfaceImpl(hb_app)

    def get_messages(self) -> list:
        return self.interface.get_messages()

    async def execute_command(self, command: str):
        await self.interface.execute_command(command)

    def validate_command(self, command: str):
        self.interface.validate_command(command)


class CommandInterfaceImpl(CommandInterface):
    """Actual implementation of CommandInterface for testing"""

    def __init__(self, hb_app):
        super().__init__(hb_app)
        self._messages = []

    @property
    def source(self) -> str:
        return "Test"

    def add_message_to_queue(self, msg: str) -> None:
        self._messages.append(msg)

    def get_messages(self) -> list:
        return self._messages


class TestCommandInterface(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.mock_hb = Mock()
        self.mock_hb.app = Mock()
        self.mock_hb.app.log = Mock()
        self.test_impl = TestCommandImplementation(self.mock_hb)

        self.mock_scheduler = AsyncMock()
        self.scheduler_patcher = patch(
            'hummingbot.core.utils.async_call_scheduler.AsyncCallScheduler.shared_instance',
            return_value=self.mock_scheduler
        )
        self.scheduler_patcher.start()

    def tearDown(self):
        self.scheduler_patcher.stop()
        super().tearDown()

    def test_validate_enabled_command(self):
        """Test validation of enabled command"""
        self.test_impl.validate_command("status")
        self.test_impl.validate_command("/status")

    def test_validate_disabled_command(self):
        """Test validation of disabled command"""
        with self.assertRaises(CommandDisabledError):
            self.test_impl.validate_command("connect")
        with self.assertRaises(CommandDisabledError):
            self.test_impl.validate_command("/connect")

    async def test_execute_command(self):
        """Test command execution"""
        self.mock_hb._handle_command = AsyncMock()

        await self.test_impl.execute_command("status")

        self.mock_hb.app.log.assert_called_once()
        self.mock_scheduler.call_async.assert_called_once_with(
            self.mock_hb._handle_command,
            "status"
        )

    async def test_execute_command_with_error(self):
        """Test command execution with error"""
        await self.test_impl.execute_command("connect")

        messages = self.test_impl.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            messages[0],
            "Command 'connect' is disabled in this interface."
        )
