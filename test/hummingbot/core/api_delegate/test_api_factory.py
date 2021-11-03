import asyncio
import unittest
from typing import Awaitable

from hummingbot.core.api_delegate.api_factory import APIFactory
from hummingbot.core.api_delegate.rest_delegate import RESTDelegate
from hummingbot.core.api_delegate.ws_delegate import WSDelegate


class APIFactoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_rest_delegate(self):
        factory = APIFactory()

        rest_delegate = self.async_run_with_timeout(factory.get_rest_delegate())

        self.assertIsInstance(rest_delegate, RESTDelegate)

    def test_get_ws_delegate(self):
        factory = APIFactory()

        ws_delegate = self.async_run_with_timeout(factory.get_ws_delegate())

        self.assertIsInstance(ws_delegate, WSDelegate)
