#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

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

        # Register command handler and start telegram message polling
        handles = [ MessageHandler(Filters.text, self.handler)]
        for handle in handles:
            self._updater.dispatcher.add_handler(handle)
        self._updater.start_polling(
            clean=True,
            bootstrap_retries=-1,
            timeout=30,
            read_latency=60,
        )
        self.logger().info("Telegram is listening...")

    def stop(self) -> None:
        """ Stops all running telegram threads. """
        self._updater.stop()

    def send_msg(self, msg: str) -> None:
        """ Send a message to telegram channel """
        self._send_msg(msg)

    @authorized_only
    def handler(self, bot: Bot, update: Update) -> None:
        try:
            self._hb._handle_command(update.message.text)
        except Exception as e:
            self._send_msg(str(e), bot=bot)

    @staticmethod
    def _divide_chunks(arr: List[Any], n: int = 6):
        """ Break a list into chunks of size N """
        for i in range(0, len(arr), n):
            yield arr[i:i + n]

    def _send_msg(self, msg: str, bot: Bot = None, parse_mode: ParseMode = ParseMode.MARKDOWN) -> None:
        """
        Send given markdown message
        """
        bot = bot or self._updater.bot

        # command options that show up on user's screen
        keyboard = self._divide_chunks(self._hb.parser.commands)
        reply_markup = ReplyKeyboardMarkup(keyboard)

        try:
            try:
                bot.send_message(
                    self._chat_id,
                    text=msg,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            except NetworkError as network_err:
                # Sometimes the telegram server resets the current connection,
                # if this is the case we send the message again.
                self.logger().warning('Telegram NetworkError: %s! Trying one more time.', network_err.message)
                bot.send_message(
                    self._chat_id,
                    text=msg,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
        except TelegramError as telegram_err:
            self.logger().warning('TelegramError: %s! Giving up on that message.', telegram_err.message)
