#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

"""
This module manage Telegram communication
"""
import logging
from typing import (
    Any,
    Callable,
    Dict,
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
    CommandHandler,
    Updater,
)

from hummingbot.logger import HummingbotLogger
from hummingbot.client.config.config_helpers import read_configs_from_yml
from hummingbot.client.config.global_config_map import global_config_map


def authorized_only(command_handler: Callable[[Any, Bot, Update], None]) -> Callable[..., Any]:
    """
    Decorator to check if the message comes from the correct chat_id
    :param command_handler: Telegram CommandHandler
    :return: decorated function
    """
    def wrapper(self, *args, **kwargs):
        """ Decorator logic """
        update = kwargs.get('update') or args[1]

        # Reject unauthorized messages
        chat_id = int(self._chat_id)

        if int(update.message.chat_id) != chat_id:
            TelegramNotifier.logger().info('Rejected unauthorized message from: %s', update.message.chat_id)
            return wrapper

        TelegramNotifier.logger().info(f"Executing handler: {command_handler.__name__}, for chat_id: {chat_id}")
        try:
            return command_handler(self, *args, **kwargs)
        except BaseException:
            TelegramNotifier.logger().exception('Exception occurred within Telegram module')

    return wrapper


class TelegramNotifier:
    """  This class handles all telegram communication """
    tn_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.tn_logger is None:
            cls.tn_logger = logging.getLogger(__name__)
        return cls.tn_logger

    def __init__(self, token: str, chat_id: str) -> None:
        self._token = token or global_config_map.get("telegram_token").value
        self._chat_id = chat_id or global_config_map.get("telegram_chat_id").value
        self._updater = Updater(token=token, workers=0)

        # Register command handler and start telegram message polling
        handles = [
            CommandHandler('status', self._status),
            # CommandHandler('start', self._start),
            # CommandHandler('stop', self._stop),
            # CommandHandler('help', self._help),
        ]
        for handle in handles:
            self._updater.dispatcher.add_handler(handle)
        self._updater.start_polling(
            clean=True,
            bootstrap_retries=-1,
            timeout=30,
            read_latency=60,
        )
        self.logger().info('rpc.telegram is listening for following commands: %s', [h.command for h in handles])

    def cleanup(self) -> None:
        """
        Stops all running telegram threads.
        """
        self._updater.stop()

    def send_msg(self, msg: Dict[str, Any]) -> None:
        """ Send a message to telegram channel """
        message = '{status}'.format(**msg)
        self._send_msg(message)

    @authorized_only
    def _status(self, bot: Bot, update: Update) -> None:
        """
        Handler for /status.
        Returns the current TradeThread status
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        try:
            messages = ["hi", "im here",]
            for msg in messages:
                self._send_msg(msg, bot=bot)
        except Exception as e:
            self._send_msg(str(e), bot=bot)

    def _send_msg(self, msg: str, bot: Bot = None, parse_mode: ParseMode = ParseMode.MARKDOWN) -> None:
        """
        Send given markdown message
        """
        bot = bot or self._updater.bot

        # command options that show up on user's screen
        keyboard = [['/status', '/start', '/stop', '/help']]
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


if __name__ == '__main__':
    read_configs_from_yml()
    tb: TelegramNotifier = TelegramNotifier(token=global_config_map["telegram_token"].value,
                                            chat_id=global_config_map["telegram_chat_id"].value)
