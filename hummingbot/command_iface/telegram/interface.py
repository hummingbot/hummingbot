import asyncio
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from telegram import ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.helpers import escape_markdown

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.command_iface.base import CommandInterface
from hummingbot.command_iface.exceptions import AuthenticationError
from hummingbot.command_iface.telegram.constants import (
    ADDITIONAL_MENU,
    CMD_BACK,
    CMD_MORE,
    COMMANDS_MAPPING,
    MAIN_MENU,
    TELEGRAM_MAX_MESSAGE_LENGTH,
    TELEGRAM_POLL_READ_TIMEOUT,
    TELEGRAM_POLL_TIMEOUT,
)
from hummingbot.command_iface.telegram.utils import split_message
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.notifier.notifier_base import NotifierBase

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class MenuState(Enum):
    """Menu state tracking"""
    MAIN = auto()
    ADDITIONAL = auto()


class TelegramCommandInterface(CommandInterface):
    """
    Telegram interface for Hummingbot commands and notifications.
    """

    @property
    def source(self) -> str:
        return "Telegram"

    def __init__(self, token: str, chat_id: str, hb_app: "HummingbotApplication") -> None:
        CommandInterface.__init__(self, hb_app)
        NotifierBase.__init__(self)

        # Initialize Telegram bot
        self._token = token
        self._chat_id = chat_id
        self._application: Optional[Application] = None
        self._telegram_task: Optional[asyncio.Task] = None
        self._ready = asyncio.Event()
        self._started = False
        self._menu_state = MenuState.MAIN

    def _is_authorized(self, update: Update) -> bool:
        """Check if message comes from authorized chat"""
        if not update.effective_chat:
            return False
        return str(update.effective_chat.id) == self._chat_id

    async def _handle_telegram_message(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages from Telegram"""
        if not self._is_authorized(update):
            await self._send_message("Unauthorized access")
            raise AuthenticationError("Unauthorized Telegram chat")

        text = update.message.text

        # Handle menu navigation
        if text == CMD_MORE:
            self._menu_state = MenuState.ADDITIONAL
            await update.message.reply_text(
                "List of additional commands:",
                reply_markup=ReplyKeyboardMarkup(ADDITIONAL_MENU, resize_keyboard=True)
            )
            return

        if text == CMD_BACK:
            self._menu_state = MenuState.MAIN
            await update.message.reply_text(
                "Returning to main menu:",
                reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
            )
            return

        # Handle commands
        command = COMMANDS_MAPPING.get(text)
        if command:
            await self.execute_command(command)

    async def _send_message(self, message: str) -> None:
        """Send formatted message to Telegram"""
        if not self._application or not self._application.bot:
            self.logger().error("Telegram bot not initialized")
            return

        try:
            # Split message into parts if needed
            message_parts = split_message(message)

            for part in message_parts:
                # Escape special characters for markdown
                escaped_message = escape_markdown(part)

                try:
                    await self._application.bot.send_message(
                        chat_id=self._chat_id,
                        text=f"```\n{escaped_message}\n```",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    # Add small delay between messages to avoid rate limiting
                    if len(message_parts) > 1:
                        await self._sleep(0.1)

                except TelegramError as e:
                    # Handle specific Telegram errors
                    if "Message is too long" in str(e):
                        self.logger().warning(f"Message part exceeds Telegram length limit: {len(part)} chars")
                        # Try sending without code formatting as fallback
                        await self._application.bot.send_message(
                            chat_id=self._chat_id,
                            text=escaped_message,
                            parse_mode=ParseMode.MARKDOWN_V2
                        )
                    else:
                        raise e

        except TelegramError as e:
            self.logger().error(f"Error sending telegram message: {str(e)}")
            # Try sending without formatting as last resort
            try:
                await self._application.bot.send_message(
                    chat_id=self._chat_id,
                    text=message[:TELEGRAM_MAX_MESSAGE_LENGTH]
                )
            except Exception as e2:
                self.logger().error(f"Failed to send even unformatted message: {str(e2)}")

    async def _handle_start_command(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        if not self._is_authorized(update):
            await self._send_message("Unauthorized access")
            return

        await update.message.reply_text(
            "Welcome to Hummingbot Telegram bot!",
            reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        )

    def start(self) -> None:
        """Start the Telegram interface"""
        if not self._started:
            self._started = True
            self._telegram_task = safe_ensure_future(self._start_telegram_bot())
            NotifierBase.start(self)

    def stop(self) -> None:
        """Stop the Telegram interface"""
        if self._started:
            self._started = False

            if self._ready.is_set():
                self._ready.clear()

            if self._application and self._application.updater.running:
                safe_ensure_future(self._application.updater.stop())

            if self._application and self._application.running:
                safe_ensure_future(self._application.stop())

            if self._telegram_task:
                self._telegram_task.cancel()
                self._telegram_task = None

            NotifierBase.stop(self)
            self.logger().info("Telegram interface stopped")

    async def _start_telegram_bot(self) -> None:
        """Initialize and start Telegram bot"""
        try:
            # Initialize with polling parameters
            self._application = Application.builder() \
                .token(self._token) \
                .read_timeout(TELEGRAM_POLL_READ_TIMEOUT) \
                .connect_timeout(TELEGRAM_POLL_TIMEOUT) \
                .build()

            # Add handlers before initialization
            self._application.add_handler(CommandHandler("start", self._handle_start_command))
            self._application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_telegram_message)
            )

            try:
                # Initialize the application
                await self._application.initialize()
                # Start the application
                await self._application.start()
                # Start polling
                await self._application.updater.start_polling()

            except Exception as e:
                self.logger().error(f"Failed to initialize Telegram bot: {str(e)}")
                raise

            self._ready.set()
            self.logger().info("Telegram bot started successfully")

        except Exception as e:
            self.logger().error(f"Failed to start Telegram bot: {str(e)}", exc_info=True)
            raise

    @classmethod
    def from_client_config(
        cls,
        client_config_map: ClientConfigMap,
        hb_app: "HummingbotApplication"
    ) -> Optional["TelegramCommandInterface"]:
        """Create TelegramCommandInterface from client config"""
        telegram_config = client_config_map.telegram
        if not telegram_config.enabled:
            return None

        if not telegram_config.token or not telegram_config.chat_id:
            cls.logger().error("Telegram configuration incomplete.")
            return None

        return cls(
            token=telegram_config.token,
            chat_id=telegram_config.chat_id,
            hb_app=hb_app
        )
