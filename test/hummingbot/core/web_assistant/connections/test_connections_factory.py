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

    async def test_disable_tls_1_3_with_existing_client(self):
        """Test that disabling TLS 1.3 with an existing client adds it to clients_to_close."""
        factory = ConnectionsFactory()

        # Create and verify initial client
        await factory.get_rest_connection()
        self.assertIsNotNone(factory._shared_client)
        initial_client = factory._shared_client

        # Disable TLS 1.3 and verify changes
        factory.set_disable_tls_1_3(True)
        self.assertTrue(factory._disable_tls_1_3)
        self.assertIsNone(factory._shared_client)
        self.assertEqual(len(factory._clients_to_close), 1)
        self.assertEqual(factory._clients_to_close[0], initial_client)

        await factory.close()

    async def test_client_recreation_after_tls_setting_change(self):
        """Test that a new client is created with different settings after TLS change."""
        factory = ConnectionsFactory()

        # Get initial client
        await factory.get_rest_connection()
        self.assertIsNotNone(factory._shared_client)
        initial_client = factory._shared_client

        # Change TLS setting and get new client
        factory.set_disable_tls_1_3(True)
        await factory.get_rest_connection()
        self.assertIsNotNone(factory._shared_client)
        new_client = factory._shared_client

        # Verify clients are different
        self.assertNotEqual(initial_client, new_client)

        await factory.close()

    async def test_clients_to_close_are_cleared_after_close(self):
        """Test that clients_to_close list is cleared after closing."""
        factory = ConnectionsFactory()

        # Create initial client and change settings to add it to clients_to_close
        await factory.get_rest_connection()
        factory.set_disable_tls_1_3(True)
        self.assertEqual(len(factory._clients_to_close), 1)

        # Close all clients
        await factory.close()
        self.assertEqual(len(factory._clients_to_close), 0)

    async def test_singleton_behavior_with_tls_settings(self):
        """Test that TLS settings are shared across factory instances."""
        factory1 = ConnectionsFactory()
        factory2 = ConnectionsFactory()

        # Change setting using class method
        factory1.set_disable_tls_1_3(True)
        self.assertTrue(factory1._disable_tls_1_3)

        # Create client with second factory
        await factory2.get_rest_connection()
        self.assertIsNotNone(factory2._shared_client)
        factory2.set_disable_tls_1_3(False)

        # Verify that the fields are shared at instance level but not at class level
        self.assertIs(factory1, factory2)
        self.assertFalse(factory1._disable_tls_1_3)
        self.assertIsNone(factory1._shared_client)
        self.assertFalse(hasattr(ConnectionsFactory, '_shared_client'))

        await factory1.close()
