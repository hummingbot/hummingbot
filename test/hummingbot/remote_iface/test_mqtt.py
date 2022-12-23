import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from async_timeout import timeout

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.mock_api.mock_mqtt_server import FakeMQTTBroker
from hummingbot.remote_iface.mqtt import MQTTGateway


class RemoteIfaceMQTTTests(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.instance_id = 'TEST_ID'
        cls.hbapp = HummingbotApplication()
        cls.hbapp.client_config_map.mqtt_bridge.mqtt_port = 1888
        cls.hbapp.client_config_map.instance_id = cls.instance_id
        cls.command_topics = [
            'start',
            'stop',
            'config',
            'import',
            'status',
            'history',
            'balance/limit',
            'balance/paper',
        ]
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.START_URI = 'hbot/$UID/start'
        cls.STOP_URI = 'hbot/$UID/stop'
        cls.CONFIG_URI = 'hbot/$UID/config'
        cls.IMPORT_URI = 'hbot/$UID/import'
        cls.STATUS_URI = 'hbot/$UID/status'
        cls.HISTORY_URI = 'hbot/$UID/history'
        cls.BALANCE_LIMIT_URI = 'hbot/$UID/balance/limit'
        cls.BALANCE_PAPER_URI = 'hbot/$UID/balance/paper'

    @classmethod
    def tearDownClass(cls) -> None:
        pass

    def setUp(self) -> None:
        super().setUp()
        self.fake_mqtt_broker = FakeMQTTBroker()
        self.gateway = MQTTGateway(self.hbapp)

    def tearDown(self):
        self.fake_mqtt_broker._transport._received_msgs = {}

    def is_msg_received(self, topic, content=None):
        msg_found = False
        if topic in self.fake_mqtt_broker.received_msgs:
            if not content:
                msg_found = True
            else:
                for msg in self.fake_mqtt_broker.received_msgs[topic]:
                    if content == msg['msg']:
                        msg_found = True
                        break
        return msg_found

    async def wait_for_rcv(self, topic, content=None):
        try:
            async with timeout(2):
                while not self.is_msg_received(topic=topic, content=content):
                    await asyncio.sleep(0.1)
        except asyncio.TimeoutError as e:
            print(f"Topic: {topic} was not received.")
            print(f"Received Messages: {self.fake_mqtt_broker.received_msgs}")
            raise e

    def start_mqtt(self,
                   mock_mqtt):
        mock_mqtt.side_effect = self.fake_mqtt_broker.create_transport
        self.gateway.start_notifier()
        self.gateway.start_commands()
        self.gateway.start_event_fw()
        self.gateway.patch_logger_class()
        self.gateway.run()

    def hb_status_notify(self, *args, **kwargs):
        msg = "FAKE STATUS MOCK"
        self.hbapp.notify(msg)
        return msg

    def get_topic_for(self,
                      topic):
        return topic.replace('$UID', self.hbapp.uid)

    def build_fake_strategy(self,
                            status_check_all_mock: AsyncMock,
                            load_strategy_config_map_from_file: AsyncMock,
                            invalid_strategy: bool = True):
        if invalid_strategy:
            strategy_name = "some_strategy"
        else:
            strategy_name = "avellaneda_market_making"
        status_check_all_mock.return_value = True
        strategy_conf_var = ConfigVar("strategy", None)
        strategy_conf_var.value = strategy_name
        load_strategy_config_map_from_file.return_value = {"strategy": strategy_conf_var}
        return strategy_name

    def send_fake_import_cmd(self,
                             status_check_all_mock: AsyncMock,
                             load_strategy_config_map_from_file: AsyncMock,
                             invalid_strategy: bool = True):
        import_topic = self.get_topic_for(self.IMPORT_URI)

        strategy_name = self.build_fake_strategy(status_check_all_mock=status_check_all_mock,
                                                 load_strategy_config_map_from_file=load_strategy_config_map_from_file,
                                                 invalid_strategy=invalid_strategy)

        self.fake_mqtt_broker.publish_to_subscription(import_topic, {'strategy': strategy_name})

    @patch("commlib.transports.mqtt.MQTTTransport")
    def test_mqtt_subscribed_topics(self,
                                    mock_mqtt):
        self.start_mqtt(mock_mqtt=mock_mqtt)
        self.assertTrue(self.gateway is not None)
        subscribed_mqtt_topics = sorted(list([f"hbot/{self.instance_id}/{topic}" for topic in self.command_topics]))
        self.assertEqual(subscribed_mqtt_topics, sorted(list(self.fake_mqtt_broker.subscriptions.keys())))

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    @patch("commlib.transports.mqtt.MQTTTransport")
    def test_mqtt_command_import(self,
                                 mock_mqtt,
                                 status_check_all_mock: AsyncMock,
                                 load_strategy_config_map_from_file: AsyncMock):
        self.start_mqtt(mock_mqtt=mock_mqtt)
        self.send_fake_import_cmd(status_check_all_mock=status_check_all_mock,
                                  load_strategy_config_map_from_file=load_strategy_config_map_from_file,
                                  invalid_strategy=False)

        notify_topic = f"hbot/{self.instance_id}/notify"
        start_msg = '\nEnter "start" to start market making.'
        self.ev_loop.run_until_complete(self.wait_for_rcv(notify_topic, start_msg))
        self.assertTrue(self.is_msg_received(notify_topic, 'Configuration from avellaneda_market_making.yml file is imported.'))
        self.assertTrue(self.is_msg_received(notify_topic, start_msg))

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    @patch("commlib.transports.mqtt.MQTTTransport")
    def test_mqtt_command_start(self,
                                mock_mqtt,
                                status_check_all_mock: AsyncMock,
                                load_strategy_config_map_from_file: AsyncMock):
        self.start_mqtt(mock_mqtt=mock_mqtt)

        self.send_fake_import_cmd(status_check_all_mock=status_check_all_mock,
                                  load_strategy_config_map_from_file=load_strategy_config_map_from_file)

        start_topic = self.get_topic_for(self.START_URI)

        self.fake_mqtt_broker.publish_to_subscription(start_topic, {})
        notify_topic = f"hbot/{self.instance_id}/notify"
        start_msg = "Invalid strategy. Start aborted."
        self.ev_loop.run_until_complete(self.wait_for_rcv(notify_topic, start_msg))
        self.assertTrue(self.is_msg_received(notify_topic, start_msg))

    @patch("commlib.transports.mqtt.MQTTTransport")
    def test_mqtt_command_stop(self,
                               mock_mqtt):
        self.start_mqtt(mock_mqtt=mock_mqtt)

        topic = self.get_topic_for(self.STOP_URI)

        self.fake_mqtt_broker.publish_to_subscription(topic, {})
        log_topic = f"hbot/{self.instance_id}/log"
        notify_topic = f"hbot/{self.instance_id}/notify"
        log_msg = "stop command initiated."
        notify_msg = "All outstanding orders canceled."
        self.ev_loop.run_until_complete(self.wait_for_rcv(notify_topic, notify_msg))
        self.assertTrue(self.is_msg_received(log_topic, log_msg))
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    @patch("commlib.transports.mqtt.MQTTTransport")
    def test_mqtt_command_config(self,
                                 mock_mqtt):
        self.start_mqtt(mock_mqtt=mock_mqtt)

        topic = self.get_topic_for(self.CONFIG_URI)

        self.fake_mqtt_broker.publish_to_subscription(topic, {})
        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msg = "\nGlobal Configurations:"
        self.ev_loop.run_until_complete(self.wait_for_rcv(notify_topic, notify_msg))
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    @patch("hummingbot.client.command.status_command.StatusCommand.strategy_status", new_callable=AsyncMock)
    @patch("commlib.transports.mqtt.MQTTTransport")
    def test_mqtt_z_command_status(self,
                                   mock_mqtt,
                                   strategy_status_mock: AsyncMock,
                                   status_check_all_mock: AsyncMock,
                                   load_strategy_config_map_from_file: AsyncMock):
        strategy_status_mock.side_effect = self.hb_status_notify

        self.start_mqtt(mock_mqtt=mock_mqtt)

        topic = self.get_topic_for(self.STATUS_URI)

        notify_topic = f"hbot/{self.instance_id}/notify"

        self.fake_mqtt_broker.publish_to_subscription(topic, {})
        notify_msg = "FAKE STATUS MOCK"
        self.ev_loop.run_until_complete(self.wait_for_rcv(notify_topic, notify_msg))
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))
