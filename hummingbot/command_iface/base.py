from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Set

import pandas as pd

from hummingbot.command_iface.exceptions import CommandDisabledError
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.notifier.notifier_base import NotifierBase

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class CommandInterface(ABC, NotifierBase):
    """
    Base interface for remote command execution and command handling.
    This class provides a structure for implementing command interfaces
    in different environments (e.g., Telegram, WebSocket).
    """

    DISABLED_COMMANDS: Set[str] = {
        "connect",
        "create",
        "import",
        "export",
    }

    def __init__(self, hb_app: "HummingbotApplication"):
        super().__init__()
        self._hb_app = hb_app
        self._started = False

    @property
    @abstractmethod
    def source(self) -> str:
        raise NotImplementedError("Subclasses must implement the source property.")

    def validate_command(self, command: str) -> None:
        """
        Validate if command can be executed
        :param command: Command to validate
        :raises: CommandDisabledError if command is disabled
        """
        clean_command = command[1:] if command.startswith("/") else command
        if any(clean_command.startswith(cmd) for cmd in self.DISABLED_COMMANDS):
            raise CommandDisabledError(f"Command '{command}' is disabled in this interface.")

    async def execute_command(self, command: str) -> None:
        """
        Execute a command
        :param command: Command to execute
        :param context: Optional context information
        """
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        try:
            # Validate and execute command
            self.validate_command(command)
            self._hb_app.app.log(f"\n{self.source} >>> {command}")

            # Set display options to max, so that telegram does not display truncated data
            pd.set_option('display.max_rows', 500)
            pd.set_option('display.max_columns', 500)
            pd.set_option('display.width', 1000)

            await async_scheduler.call_async(self._hb_app._handle_command, command)

            # Reset to normal, so that pandas's default autodetect width still works
            pd.set_option('display.max_rows', 0)
            pd.set_option('display.max_columns', 0)
            pd.set_option('display.width', 0)
        except CommandDisabledError as e:
            self.add_message_to_queue(str(e))
