import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.mock.mock_mqtt_server import FakeMQTTBroker
from typing import Awaitable
from unittest.mock import MagicMock, PropertyMock, patch

from async_timeout import timeout

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.hummingbot_application import HummingbotApplication


@patch("hummingbot.remote_iface.mqtt.MQTTGateway._INTERVAL_HEALTH_CHECK", 0.0)
@patch("hummingbot.remote_iface.mqtt.MQTTGateway._INTERVAL_RESTART_LONG", 0.0)
@patch("hummingbot.remote_iface.mqtt.MQTTGateway._INTERVAL_RESTART_SHORT", 0.0)
class RemoteIfaceMQTTTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.instance_id = 'TEST_ID'
        cls.fake_err_msg = "Some error"
        cls.client_config_map = ClientConfigAdapter(ClientConfigMap())
        cls.hbapp = HummingbotApplication(client_config_map=cls.client_config_map)
        cls.client_config_map.mqtt_bridge.mqtt_port = 1888
        cls.prev_instance_id = cls.client_config_map.instance_id
        cls.client_config_map.instance_id = cls.instance_id
        cls.fake_mqtt_broker = FakeMQTTBroker()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_config_map.instance_id = cls.prev_instance_id
        del cls.fake_mqtt_broker
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop: asyncio.BaseEventLoop = self.local_event_loop
        self.hbapp.ev_loop = self.ev_loop
        self.log_records = []
        self.resume_test_event = asyncio.Event()
        self.hbapp.logger().setLevel(1)
        self.hbapp.logger().addHandler(self)
        # MQTT Transport Patcher
        self.mqtt_transport_patcher = patch(
            'commlib.transports.mqtt.MQTTTransport'
        )
        self.addCleanup(self.mqtt_transport_patcher.stop)
        self.mqtt_transport_mock = self.mqtt_transport_patcher.start()
        self.mqtt_transport_mock.side_effect = self.fake_mqtt_broker.create_transport
        # MQTT Patch Loggers Patcher
        self.patch_loggers_patcher = patch(
            'hummingbot.remote_iface.mqtt.MQTTGateway.patch_loggers'
        )
        self.addCleanup(self.patch_loggers_patcher.stop)
        self.patch_loggers_mock = self.patch_loggers_patcher.start()
        self.patch_loggers_mock.return_value = None

    async def asyncSetUp(self):
        await super().asyncSetUp()
        # await self.hbapp.start_mqtt_async()

    async def asyncTearDown(self):
        await self.hbapp.stop_mqtt_async()
        await asyncio.sleep(0.1)
        await super().asyncTearDown()

    def tearDown(self):
        # self.ev_loop.run_until_complete(self.hbapp.stop_mqtt_async())
        # self.ev_loop.run_until_complete(asyncio.sleep(0.1))
        self.fake_mqtt_broker.clear()
        self.mqtt_transport_patcher.stop()
        self.patch_loggers_patcher.stop()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and str(record.getMessage()) == str(message) for record in self.log_records)

    async def wait_for_logged(self, log_level: str, message: str):
        try:
            async with timeout(3):
                while not self._is_logged(log_level=log_level, message=message):
                    await asyncio.sleep(0.1)
        except asyncio.TimeoutError as e:
            print(f"Message: {message} was not logged.")
            print(f"Received Logs: {[record.getMessage() for record in self.log_records]}")
            raise e

    async def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = await asyncio.wait_for(coroutine, timeout)
        return ret

    async def _create_exception_and_unlock_test_with_event_async(self, *args, **kwargs):
        self.resume_test_event.set()
        raise RuntimeError(self.fake_err_msg)

    def _create_exception_and_unlock_test_with_event(self, *args, **kwargs):
        self.resume_test_event.set()
        raise RuntimeError(self.fake_err_msg)

    def _create_exception_and_unlock_test_with_event_not_impl(self, *args, **kwargs):
        self.resume_test_event.set()
        raise NotImplementedError(self.fake_err_msg)

    async def test_start_mqtt_command(self):
        await self.hbapp.start_mqtt_async()
        await self.wait_for_logged("INFO", "MQTT Bridge connected with success.")

    @patch('hummingbot.remote_iface.mqtt.MQTTGateway.start')
    async def test_start_mqtt_command_fails(
        self,
        mqtt_start_mock: MagicMock,
    ):
        mqtt_start_mock.side_effect = self._create_exception_and_unlock_test_with_event
        await self.hbapp.start_mqtt_async()
        await self.wait_for_logged("ERROR", f"Failed to connect MQTT Bridge: {self.fake_err_msg}")

    @patch('hummingbot.client.command.mqtt_command.MQTTCommand._mqtt_sleep_rate_autostart_retry', new_callable=PropertyMock)
    @patch('hummingbot.remote_iface.mqtt.MQTTGateway.health', new_callable=PropertyMock)
    async def test_start_mqtt_command_retries_with_autostart(
        self,
        mqtt_health_mock: PropertyMock,
        autostart_retry_mock: PropertyMock,
    ):
        mqtt_health_mock.side_effect = self._create_exception_and_unlock_test_with_event
        autostart_retry_mock.return_value = 0.0
        self.client_config_map.mqtt_bridge.mqtt_autostart = True
        self.hbapp.mqtt_start()
        await self.async_run_with_timeout(self.resume_test_event.wait())
        await self.wait_for_logged(
            "ERROR",
            f"Failed to connect MQTT Bridge: {self.fake_err_msg}. Retrying in 0.0 seconds."
        )
        mqtt_health_mock.side_effect = lambda: True
        await self.wait_for_logged("INFO", "MQTT Bridge connected with success.")
