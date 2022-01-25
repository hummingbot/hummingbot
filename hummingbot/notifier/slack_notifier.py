#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
import asyncio
import logging
from typing import (
    Any,
    List,
    Optional,
)
# from notifier import api

import slack

import hummingbot
from hummingbot.logger import HummingbotLogger
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_ensure_future

# client = slack.WebClient(token=global_config_map.get("slack_token").value)
# verification_token = global_config_map.get("slack_verification_token").value

# api = Flask(__name__)

DISABLED_COMMANDS = {
    "connect",             # disabled because telegram can't display secondary prompt
    "create",              # disabled because telegram can't display secondary prompt
    "import",              # disabled because telegram can't display secondary prompt
    "export",              # disabled for security
}


class SlackNotifier(NotifierBase):
    tn_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.tn_logger is None:
            cls.tn_logger = logging.getLogger(__name__)
        return cls.tn_logger

    def __init__(self,
                 token: str,
                 channel: str,
                 hb: "hummingbot.client.hummingbot_application.HummingbotApplication") -> None:
        super().__init__()
        self._token = token or global_config_map.get("slack_token").value
        self._channel = channel or global_config_map.get("slack_channel").value
        self._hb = hb
        self._ev_loop = asyncio.get_event_loop()
        self._async_call_scheduler = AsyncCallScheduler.shared_instance()
        self._msg_queue: asyncio.Queue = asyncio.Queue()
        self._send_msg_task: Optional[asyncio.Task] = None

    def start(self):
        if not self._started:
            self._started = True
            self._send_msg_task = safe_ensure_future(self.send_msg_from_queue(), loop=self._ev_loop)
            self.logger().info("Slack is listening...")

    def stop(self) -> None:
        if self._send_msg_task:
            self._send_msg_task.cancel()

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

    def set_default(obj):
        if isinstance(obj, set):
            return list(obj)
        raise TypeError

    async def send_msg_async(self, msg: str, bot = None) -> None:
        """
        Send given markdown message
        """
        bot = slack.WebClient(token=self._token)  # bot or self._updater.bot

        await self._async_call_scheduler.call_async(lambda: bot.chat_postMessage(
            channel=self._channel,
            text=msg
        ))


# if __name__ == 'hummingbot.notifier.slack_notifier':
#     api.run(port=5000)
