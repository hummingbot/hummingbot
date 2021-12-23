import asyncio
from typing import Optional
from unittest.mock import patch, MagicMock, AsyncMock

from hummingbot.client.ui.hummingbot_cli import HummingbotCLI


class CLIMockingAssistant:
    def __init__(self, app: HummingbotCLI):
        self._app = app
        self._prompt_patch = patch(
            "hummingbot.client.ui.hummingbot_cli.HummingbotCLI.prompt"
        )
        self._prompt_mock: Optional[AsyncMock] = None
        self._prompt_replies = asyncio.Queue()
        self._log_patch = patch(
            "hummingbot.client.ui.hummingbot_cli.HummingbotCLI.log"
        )
        self._log_mock: Optional[MagicMock] = None
        self._log_calls = []
        self._to_stop_config_msg = "to_stop_config"

        self.ev_loop = asyncio.get_event_loop()

    def start(self):
        self._prompt_mock = self._prompt_patch.start()
        self._prompt_mock.side_effect = self._get_next_prompt_reply
        self._log_mock = self._log_patch.start()
        self._log_mock.side_effect = self._register_log_call

    def stop(self):
        self._prompt_patch.stop()
        self._log_patch.stop()

    def queue_prompt_reply(self, msg: str):
        self._prompt_replies.put_nowait(msg)

    def queue_prompt_to_stop_config(self):
        self._prompt_replies.put_nowait(self._to_stop_config_msg)

    def check_log_called_with(self, msg: str) -> bool:
        called_with = msg in self._log_calls
        return called_with

    async def _get_next_prompt_reply(self, prompt: str, is_password: bool = False):
        msg = await self._prompt_replies.get()
        if msg == self._to_stop_config_msg:
            self._app.to_stop_config = True
            msg = " "
        return msg

    def _register_log_call(self, text: str, save_log: bool = True):
        self._log_calls.append(text)

    def toggle_logs(self):
        self._app.toggle_right_pane()
