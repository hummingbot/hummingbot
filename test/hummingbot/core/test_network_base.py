import asyncio
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
import unittest


class SampleNetwork(NetworkBase):
    async def check_network(self) -> NetworkStatus:
        "Override check_network to always return connected"
        return NetworkStatus.CONNECTED


class NetworkBaseTest(unittest.TestCase):
    def test_init(self):
        """
        This lets us know if the initial values have changed and extends
        code coverage to the class's properties.
        """
        nb = NetworkBase()

        self.assertEqual(nb.network_status, NetworkStatus.STOPPED)
        self.assertEqual(nb.check_network_task, None)
        self.assertEqual(nb.check_network_interval, 60.0)
        self.assertEqual(nb.network_error_wait_time, 60.0)
        self.assertEqual(nb.check_network_timeout, 60.0)
        self.assertEqual(nb.started, False)

        # test that setters work
        nb.check_network_interval = 15.0
        self.assertEqual(nb.check_network_interval, 15.0)

        nb.network_error_wait_time = 25.0
        self.assertEqual(nb.network_error_wait_time, 25.0)

        nb.check_network_timeout = 45.0
        self.assertEqual(nb.check_network_timeout, 45.0)

    def test_network(self):
        """
        NetworkBase has a couple of method sketches that do not do anything
        but are used by child classes.
        """

        nb = NetworkBase()

        self.assertEqual(asyncio.get_event_loop().run_until_complete(nb.start_network()), None)

        self.assertEqual(asyncio.get_event_loop().run_until_complete(nb.stop_network()), None)

        self.assertEqual(asyncio.get_event_loop().run_until_complete(nb.check_network()), NetworkStatus.NOT_CONNECTED)

    def test_start_and_stop_network(self):
        """
        Assert that start and stop update the started property.
        """

        nb = NetworkBase()

        nb.start()
        self.assertEqual(nb.started, True)

        nb.stop()
        self.assertEqual(nb.started, False)

    def test_update_network_status(self):
        """
        Use SampleNetwork to test that the network status gets updated
        """
        sample = SampleNetwork()

        self.assertEqual(sample.network_status, NetworkStatus.STOPPED)

        sample.check_network_interval = 0.1
        sample.network_error_wait_time = 0.1
        sample.check_network_timeout = 0.1

        sample.start()
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.2))

        self.assertEqual(sample.network_status, NetworkStatus.CONNECTED)

        sample.stop()
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.2))

        self.assertEqual(sample.started, False)
