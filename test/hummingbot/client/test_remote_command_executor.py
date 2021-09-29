import asyncio
from typing import Awaitable
from unittest import TestCase
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.remote_control.remote_command_executor import RemoteCommandExecutor


class RemoteCommandWebsocketTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = None
        self.ws_url = None
        self._hb = HummingbotApplication.main_application()
        self._rce = RemoteCommandExecutor.get_instance()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 30):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    async def listen_rce_messages(self):
        await self._rce.connect()
        async for response in self._rce._on_message():
            print(response)
        return False

    def test_messages_received(self):
        if self.api_key and self.ws_url:
            try:
                response = self.async_run_with_timeout(self.listen_rce_messages())
                print(response)
            except asyncio.TimeoutError:
                pass
