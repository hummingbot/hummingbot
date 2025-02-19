from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection


class ConnectionsFactoryTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    async def test_get_rest_connection(self):
        factory = ConnectionsFactory()

        rest_connection = await factory.get_rest_connection()

        self.assertIsInstance(rest_connection, RESTConnection)

    async def test_get_ws_connection(self):
        factory = ConnectionsFactory()

        rest_connection = await factory.get_ws_connection()

        self.assertIsInstance(rest_connection, WSConnection)
