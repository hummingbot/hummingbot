import asyncio
import unittest
from typing import Awaitable

from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class WebAssistantsFactoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_rest_assistant(self):
        factory = WebAssistantsFactory()

        rest_assistant = self.async_run_with_timeout(factory.get_rest_assistant())

        self.assertIsInstance(rest_assistant, RESTAssistant)

    def test_get_ws_assistant(self):
        factory = WebAssistantsFactory()

        ws_assistant = self.async_run_with_timeout(factory.get_ws_assistant())

        self.assertIsInstance(ws_assistant, WSAssistant)
