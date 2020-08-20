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

import hummingbot
import pandas as pd
from hummingbot.logger import HummingbotLogger
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_ensure_future


DISABLED_COMMANDS = {
    "connect",             # disabled because telegram can't display secondary prompt
    "create",              # disabled because telegram can't display secondary prompt
    "import",              # disabled because telegram can't display secondary prompt
    "export",              # disabled for security
}

# Telegram does not allow sending messages longer than 4096 characters
TELEGRAM_MSG_LENGTH_LIMIT = 3000


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

    def __init__(self,
                 token: str,
                 chat_id: str,
                 hb: "hummingbot.client.hummingbot_application.HummingbotApplication") -> None:
        super().__init__()
        self._token = token or global_config_map.get("telegram_token").value
        self._chat_id = chat_id or global_config_map.get("telegram_chat_id").value
        self._updater = Updater(token=token, workers=0)
        self._hb = hb
        self._ev_loop = asyncio.get_event_loop()
        self._async_call_scheduler = AsyncCallScheduler.shared_instance()
        self._msg_queue: asyncio.Queue = asyncio.Queue()
        self._send_msg_task: Optional[asyncio.Task] = None

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
            self._send_msg_task = safe_ensure_future(self.send_msg_from_queue(), loop=self._ev_loop)
            self.logger().info("Telegram is listening...")

    def stop(self) -> None:
        if self._started or self._updater.running:
            self._updater.stop()
        if self._send_msg_task:
            self._send_msg_task.cancel()

    @authorized_only
    def handler(self, bot: Bot, update: Update) -> None:
        safe_ensure_future(self.handler_loop(bot, update), loop=self._ev_loop)

    async def handler_loop(self, bot: Bot, update: Update) -> None:
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        try:
            input_text = update.message.text.strip()
            output = f"\n[Telegram Input] {input_text}"

            self._hb.app.log(output)

            # if the command does starts with any disabled commands
            if any([input_text.lower().startswith(dc) for dc in DISABLED_COMMANDS]):
                self.add_msg_to_queue(f"Command {input_text} is disabled from telegram")
            else:
                # Set display options to max, so that telegram does not display truncated data
                pd.set_option('display.max_rows', 500)
                pd.set_option('display.max_columns', 500)
                pd.set_option('display.width', 1000)

                await async_scheduler.call_async(self._hb._handle_command, input_text)

                # Reset to normal, so that pandas's default autodetect width still works
                pd.set_option('display.max_rows', 0)
                pd.set_option('display.max_columns', 0)
                pd.set_option('display.width', 0)
        except Exception as e:
            self.add_msg_to_queue(str(e))

    @staticmethod
    def _divide_chunks(arr: List[Any], n: int = 5):
        """ Break a list into chunks of size N """
        for i in range(0, len(arr), n):
            yield arr[i:i + n]

    def add_msg_to_queue(self, msg: str):
        lines: List[str] = msg.split("\n")
        msg_chunks: List[List[str]] = self._divide_chunks(lines, 30)
        for chunk in msg_chunks:
            self._msg_queue.put_nowait("\n".join(chunk))

    async def send_msg_from_queue(self):
        while True:
            try:
                new_msg: str = await self._msg_queue.get()
                if isinstance(new_msg, str) and len(new_msg) > 0:
                    await self.send_msg_async(new_msg)
            except Exception as e:
                self.logger().error(str(e))
            await asyncio.sleep(1)

    async def send_msg_async(self, msg: str, bot: Bot = None) -> None:
        """
        Send given markdown message
        """
        bot = bot or self._updater.bot

        # command options that show up on user's screen
        approved_commands = ["start", "stop", "status", "history", "config"]
        keyboard = self._divide_chunks(approved_commands)
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        # wrapping text in ``` to prevent formatting issues
        formatted_msg = f'\n{msg}\n'

        try:
            try:
                await self._async_call_scheduler.call_async(lambda: bot.send_message(
                    self._chat_id,
                    text=formatted_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                ))
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
                ))
        except TelegramError as telegram_err:
            self.logger().network(f"TelegramError: {telegram_err.message}! Giving up on that message.",
                                  exc_info=True)
