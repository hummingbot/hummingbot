import logging
from logging import StreamHandler
from typing import List

from telegram.error import NetworkError
from telegram.ext import Updater


class TelegramLog:
    def __init__(self, bot_token: str, chat_ids: List[str], project_name: str):

        updater = Updater(token=bot_token, use_context=True)

        self.bot = updater.bot
        self.chat_ids = chat_ids
        self.project_name = project_name

    def send(self, data):
        message = f"#{self.project_name}\n\n{data}"
        for _id in self.chat_ids:
            try:
                self.bot.send_message(chat_id=_id, text=message)
            except NetworkError:
                pass


class TelegramHandler(StreamHandler):
    def __init__(
            self,
            bot_token: str,
            chat_ids: List[str],
            project_name: str = "hummingbot",
            level: int = logging.ERROR,
    ):

        super(TelegramHandler, self).__init__()
        self.telegram_broker = TelegramLog(bot_token, chat_ids, project_name)
        self.setLevel(level)

    def emit(self, record):
        msg = self.format(record)
        self.telegram_broker.send(msg)
