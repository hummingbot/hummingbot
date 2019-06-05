#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import logging
from typing import (
    Any,
    List,
    Callable,
    Optional,
)
from telegram.bot import Bot
from telegram.parsemode import ParseMode
from telegram.replykeyboardmarkup import ReplyKeyboardMarkup
from telegram.update import Update
from telegram.error import (
    NetworkError,
    TelegramError,
)
from telegram.ext import (
    MessageHandler,
    Filters,
    Updater,
)

from hummingbot.logger import HummingbotLogger
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler


DISABLED_COMMANDS = {
    "config",               # disabled because it requires additional logic in the ui
    "export_private_key",   # disabled for security
}


def authorized_only(handler: Callable[[Any, Bot, Update], None]) -> Callable[..., Any]:
    """ Decorator to check if the message comes from the correct chat_id """
    def wrapper(self, *args, **kwargs):
        update = kwargs.get('update') or args[1]

        # Reject unauthorized messages
        chat_id = int(self._chat_id)

        if int(update.message.chat_id) != chat_id:
            TelegramNotifier.logger().info("Rejected unauthorized message from: %s", update.message.chat_id)
            return wrapper

        try:
            return handler(self, *args, **kwargs)
        except Exception as e:
            TelegramNotifier.logger().exception(f"Exception occurred within Telegram module: {e}")

    return wrapper


class TelegramNotifier(NotifierBase):
    tn_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.tn_logger is None:
            cls.tn_logger = logging.getLogger(__name__)
        return cls.tn_logger

    def __init__(self, token: str, chat_id: str, hb: "HummingbotApplication") -> None:
        super().__init__()
        self._token = token or global_config_map.get("telegram_token").value
        self._chat_id = chat_id or global_config_map.get("telegram_chat_id").value
        self._updater = Updater(token=token, workers=0)
        self._hb = hb
        self._ev_loop = asyncio.get_event_loop()
        self._async_call_scheduler = AsyncCallScheduler.shared_instance()

        # Register command handler and start telegram message polling
        handles = [MessageHandler(Filters.text, self.handler)]
        for handle in handles:
            self._updater.dispatcher.add_handler(handle)

    def start(self):
        if not self._started:
            self._started = True
            self._updater.start_polling(
                clean=True,
                bootstrap_retries=-1,
                timeout=30,
                read_latency=60,
            )
            self.logger().info("Telegram is listening...")

    def stop(self) -> None:
        if self._started or self._updater.running:
            self._updater.stop()

    @authorized_only
    def handler(self, bot: Bot, update: Update) -> None:
        asyncio.ensure_future(self.handler_loop(bot, update), loop=self._ev_loop)

    async def handler_loop(self, bot: Bot, update: Update) -> None:
        try:
            input_text = update.message.text.strip()
            output = f"\n[Telegram Input] {input_text}"
            self._hb.app.log(output)

            # if the command does starts with any disabled commands
            if any([input_text.startswith(dc) for dc in DISABLED_COMMANDS]):
                self.send_msg(f"Command {input_text} is disabled from telegram", bot=bot)
            else:
                await self._async_call_scheduler.call_async(lambda: self._hb._handle_command(input_text))
        except Exception as e:
            self.send_msg(str(e), bot=bot)

    @staticmethod
    def _divide_chunks(arr: List[Any], n: int = 5):
        """ Break a list into chunks of size N """
        for i in range(0, len(arr), n):
            yield arr[i:i + n]

    def send_msg(self, msg: str, bot: Bot = None) -> None:
        asyncio.ensure_future(self.send_msg_async(msg, bot), loop=self._ev_loop)

    async def send_msg_async(self, msg: str, bot: Bot = None) -> None:
        """
        Send given markdown message
        """
        bot = bot or self._updater.bot

        # command options that show up on user's screen
        approved_commands = [c for c in self._hb.parser.commands if c not in DISABLED_COMMANDS]
        keyboard = self._divide_chunks(approved_commands)
        reply_markup = ReplyKeyboardMarkup(keyboard)

        # wrapping text in ``` to prevent formatting issues
        formatted_msg = f'```\n{msg}\n```'

        try:
            try:
                await self._async_call_scheduler.call_async(lambda: bot.send_message(
                    self._chat_id,
                    text=formatted_msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                ), app_warning_msg=None)
            except NetworkError as network_err:
                # Sometimes the telegram server resets the current connection,
                # if this is the case we send the message again.
                self.logger().network(f"Telegram NetworkError: {network_err.message}! Trying one more time",
                                      exc_info=True)
                await self._async_call_scheduler.call_async(lambda: bot.send_message(
                    self._chat_id,
                    text=msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                ), app_warning_msg=None)
        except TelegramError as telegram_err:
            self.logger().network(f"TelegramError: {telegram_err.message}! Giving up on that message.",
                                  exc_info=True)
