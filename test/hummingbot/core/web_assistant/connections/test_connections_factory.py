import asyncio
import unittest
from typing import Awaitable

from hummingbot.core.web_assistant.connections.connections_factory import (
    ConnectionsFactory
)
from hummingbot.core.web_assistant.connections.rest_connection import (
    RESTConnection
)
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection


class ConnectionsFactoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_rest_connection(self):
        factory = ConnectionsFactory()

        rest_connection = self.async_run_with_timeout(factory.get_rest_connection())

        self.assertIsInstance(rest_connection, RESTConnection)

    def test_get_ws_connection(self):
        factory = ConnectionsFactory()

        rest_connection = self.async_run_with_timeout(factory.get_ws_connection())

        self.assertIsInstance(rest_connection, WSConnection)
