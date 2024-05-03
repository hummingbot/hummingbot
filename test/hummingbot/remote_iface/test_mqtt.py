import asyncio
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from async_timeout import timeout

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketEvent, OrderExpiredEvent, SellOrderCreatedEvent
from hummingbot.core.mock_api.mock_mqtt_server import FakeMQTTBroker
from hummingbot.model.order import Order
from hummingbot.model.trade_fill import TradeFill
from hummingbot.remote_iface.mqtt import MQTTGateway, MQTTMarketEventForwarder


@patch("hummingbot.remote_iface.mqtt.MQTTGateway._INTERVAL_HEALTH_CHECK", 0.0)
@patch("hummingbot.remote_iface.mqtt.MQTTGateway._INTERVAL_RESTART_LONG", 0.0)
class RemoteIfaceMQTTTests(TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.instance_id = 'TEST_ID'
        cls.fake_err_msg = "Some error"

        cls.command_topics = [
            'start',
            'stop',
            'config',
            'import',
            'status',
            'history',
            'balance/limit',
            'balance/paper',
            'command_shortcuts',
        ]
        cls.START_URI = 'hbot/$instance_id/start'
        cls.STOP_URI = 'hbot/$instance_id/stop'
        cls.CONFIG_URI = 'hbot/$instance_id/config'
        cls.IMPORT_URI = 'hbot/$instance_id/import'
        cls.STATUS_URI = 'hbot/$instance_id/status'
        cls.HISTORY_URI = 'hbot/$instance_id/history'
        cls.BALANCE_LIMIT_URI = 'hbot/$instance_id/balance/limit'
        cls.BALANCE_PAPER_URI = 'hbot/$instance_id/balance/paper'
        cls.COMMAND_SHORTCUT_URI = 'hbot/$instance_id/command_shortcuts'
        cls.fake_mqtt_broker = FakeMQTTBroker()

    def setUp(self) -> None:
        super().setUp()

        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)

        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.client_config_map.instance_id = self.instance_id
        self.hbapp = HummingbotApplication(client_config_map=self.client_config_map)
        self.client_config_map.mqtt_bridge.mqtt_port = 1888
        self.client_config_map.mqtt_bridge.mqtt_commands = 1
        self.client_config_map.mqtt_bridge.mqtt_events = 1

        self.log_records = []
        # self.async_run_with_timeout(read_system_configs_from_yml())
        self.gateway = MQTTGateway(self.hbapp)
        self.test_market: MockPaperExchange = MockPaperExchange(
            client_config_map=self.client_config_map)
        self.hbapp.markets = {
            "test_market_paper_trade": self.test_market
        }
        self.resume_test_event = asyncio.Event()
        self.hbapp.logger().setLevel(1)
        self.hbapp.logger().addHandler(self)
        self.gateway.logger().setLevel(1)
        self.gateway.logger().addHandler(self)
        # Restart interval Patcher
        self.restart_interval_patcher = patch(
            'hummingbot.remote_iface.mqtt.MQTTGateway._INTERVAL_RESTART_SHORT',
            new_callable=PropertyMock
        )
        self.addCleanup(self.restart_interval_patcher.stop)
        self.restart_interval_mock = self.restart_interval_patcher.start()
        self.restart_interval_mock.return_value = 0.0
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

    def tearDown(self):
        self.async_loop.run_until_complete(asyncio.sleep(0.1))
        self.gateway.stop()
        del self.gateway
        self.async_loop.run_until_complete(asyncio.sleep(0.1))
        self.fake_mqtt_broker.clear()
        self.restart_interval_patcher.stop()
        self.mqtt_transport_patcher.stop()
        self.patch_loggers_patcher.stop()

        self.async_loop.stop()
        self.async_loop.close()
        asyncio.set_event_loop(self._original_async_loop)

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

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
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

    def is_msg_received(self, *args, **kwargs):
        return self.fake_mqtt_broker.is_msg_received(*args, **kwargs)

    async def wait_for_rcv(self, topic, content=None, msg_key = 'msg'):
        try:
            async with timeout(3):
                while not self.is_msg_received(topic=topic, content=content, msg_key = msg_key):
                    await asyncio.sleep(0.1)
        except asyncio.TimeoutError as e:
            print(f"Topic: {topic} was not received.")
            print(f"Received Messages: {self.fake_mqtt_broker.received_msgs}")
            raise e

    def start_mqtt(self):
        self.gateway.start()
        self.gateway.start_market_events_fw()

    def get_topic_for(
        self,
        topic
    ):
        return topic.replace('$instance_id', self.hbapp.instance_id)

    def build_fake_strategy(
        self,
        status_check_all_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock,
        invalid_strategy: bool = True,
        empty_name: bool = False
    ):
        if empty_name:
            strategy_name = ''
        elif invalid_strategy:
            strategy_name = "some_strategy"
        else:
            strategy_name = "avellaneda_market_making"
        status_check_all_mock.return_value = True
        strategy_conf_var = ConfigVar("strategy", None)
        strategy_conf_var.value = strategy_name
        load_strategy_config_map_from_file.return_value = {"strategy": strategy_conf_var}
        return strategy_name

    def send_fake_import_cmd(
        self,
        status_check_all_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock,
        invalid_strategy: bool = True,
        empty_name: bool = False
    ):
        import_topic = self.get_topic_for(self.IMPORT_URI)

        strategy_name = self.build_fake_strategy(
            status_check_all_mock=status_check_all_mock,
            load_strategy_config_map_from_file=load_strategy_config_map_from_file,
            invalid_strategy=invalid_strategy,
            empty_name=empty_name
        )

        self.fake_mqtt_broker.publish_to_subscription(import_topic, {'strategy': strategy_name})

    @staticmethod
    def emit_order_created_event(
        market: MockPaperExchange,
        order: LimitOrder
    ):
        event_cls = BuyOrderCreatedEvent if order.is_buy else SellOrderCreatedEvent
        event_tag = MarketEvent.BuyOrderCreated if order.is_buy else MarketEvent.SellOrderCreated
        market.trigger_event(
            event_tag,
            message=event_cls(
                order.creation_timestamp,
                OrderType.LIMIT,
                order.trading_pair,
                order.quantity,
                order.price,
                order.client_order_id,
                order.creation_timestamp * 1e-6
            )
        )

    @staticmethod
    def emit_order_expired_event(market: MockPaperExchange):
        event_cls = OrderExpiredEvent
        event_tag = MarketEvent.OrderExpired
        market.trigger_event(
            event_tag,
            message=event_cls(
                1671819499,
                "OID1"
            )
        )

    def build_fake_trades(self):
        ts = 1671819499
        config_file_path = "some-strategy.yml"
        strategy_name = "pure_market_making"
        market = "binance"
        symbol = "HBOT-COINALPHA"
        base_asset = "HBOT"
        quote_asset = "COINALPHA"
        order_id = "OID1"
        order = Order(
            id=order_id,
            config_file_path=config_file_path,
            strategy=strategy_name,
            market=market,
            symbol=symbol,
            base_asset=base_asset,
            quote_asset=quote_asset,
            creation_timestamp=0,
            order_type="LMT",
            amount=4,
            leverage=0,
            price=Decimal(1000),
            last_status="PENDING",
            last_update_timestamp=0,
        )
        trades = [
            TradeFill(
                config_file_path=config_file_path,
                strategy=strategy_name,
                market=market,
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                timestamp=ts,
                order_id=order_id,
                trade_type=TradeType.BUY.name,
                order_type=OrderType.LIMIT.name,
                price=Decimal(1000),
                amount=Decimal(1),
                trade_fee='{}',
                exchange_trade_id="EOID1",
                order=order),
            TradeFill(
                config_file_path=config_file_path,
                strategy=strategy_name,
                market=market,
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                timestamp=ts,
                order_id=order_id,
                trade_type=TradeType.BUY.name,
                order_type=OrderType.LIMIT.name,
                price=Decimal(1000),
                amount=Decimal(1),
                trade_fee='{}',
                exchange_trade_id="EOID1",
                order=order)
        ]
        trade_list = list([TradeFill.to_bounty_api_json(t) for t in trades])
        for t in trade_list:
            t['trade_timestamp'] = str(t['trade_timestamp'])
        return trade_list

    def test_mqtt_command_balance_limit(self):
        self.start_mqtt()

        topic = self.get_topic_for(self.BALANCE_LIMIT_URI)
        msg = {
            'exchange': 'binance',
            'asset': 'BTC-USD',
            'amount': '1.0',
        }

        self.fake_mqtt_broker.publish_to_subscription(topic, msg)
        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msg = "Limit for BTC-USD on binance exchange set to 1.0"
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    @patch("hummingbot.client.command.balance_command.BalanceCommand.balance")
    def test_mqtt_command_balance_limit_failure(
        self,
        balance_mock: MagicMock
    ):
        balance_mock.side_effect = self._create_exception_and_unlock_test_with_event
        self.start_mqtt()

        msg = {
            'exchange': 'binance',
            'asset': 'BTC-USD',
            'amount': '1.0',
        }

        self.fake_mqtt_broker.publish_to_subscription(self.get_topic_for(self.BALANCE_LIMIT_URI), msg)

        self.async_run_with_timeout(self.resume_test_event.wait())

        topic = f"test_reply/hbot/{self.instance_id}/balance/limit"
        msg = {'status': 400, 'msg': self.fake_err_msg, 'data': ''}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    def test_mqtt_command_balance_paper(self):
        self.start_mqtt()

        topic = self.get_topic_for(self.BALANCE_PAPER_URI)
        msg = {
            'exchange': 'binance',
            'asset': 'BTC-USD',
            'amount': '1.0',
        }

        self.fake_mqtt_broker.publish_to_subscription(topic, msg)
        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msg = "Paper balance for BTC-USD token set to 1.0"
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    @patch("hummingbot.client.command.balance_command.BalanceCommand.balance")
    def test_mqtt_command_balance_paper_failure(
        self,
        balance_mock: MagicMock
    ):
        balance_mock.side_effect = self._create_exception_and_unlock_test_with_event
        self.start_mqtt()

        msg = {
            'exchange': 'binance',
            'asset': 'BTC-USD',
            'amount': '1.0',
        }

        self.fake_mqtt_broker.publish_to_subscription(self.get_topic_for(self.BALANCE_PAPER_URI), msg)

        self.async_run_with_timeout(self.resume_test_event.wait())

        topic = f"test_reply/hbot/{self.instance_id}/balance/paper"
        msg = {'status': 400, 'msg': self.fake_err_msg, 'data': ''}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    def test_mqtt_command_command_shortcuts(self):
        self.start_mqtt()

        topic = self.get_topic_for(self.COMMAND_SHORTCUT_URI)
        shortcut_data = {"params": [["spreads", "4", "4"]]}

        self.fake_mqtt_broker.publish_to_subscription(topic, shortcut_data)
        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msgs = [
            "  >>> config bid_spread 4",
            "  >>> config ask_spread 4",
            "Invalid key, please choose from the list.",
        ]
        reply_topic = f"test_reply/hbot/{self.instance_id}/command_shortcuts"
        reply_data = {'success': [True], 'status': 200, 'msg': ''}
        self.async_run_with_timeout(self.wait_for_rcv(reply_topic, reply_data, msg_key='data'), timeout=10)
        for notify_msg in notify_msgs:
            self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
            self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication._handle_shortcut")
    def test_mqtt_command_command_shortcuts_failure(
        self,
        command_shortcuts_mock: MagicMock
    ):
        command_shortcuts_mock.side_effect = self._create_exception_and_unlock_test_with_event
        self.start_mqtt()

        topic = self.get_topic_for(self.COMMAND_SHORTCUT_URI)
        shortcut_data = {"params": [["spreads", "4", "4"]]}

        self.fake_mqtt_broker.publish_to_subscription(topic, shortcut_data)

        self.async_run_with_timeout(self.resume_test_event.wait())

        topic = f"test_reply/hbot/{self.instance_id}/command_shortcuts"
        msg = {'success': [], 'status': 400, 'msg': self.fake_err_msg}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    def test_mqtt_command_config(self):
        self.start_mqtt()

        topic = self.get_topic_for(self.CONFIG_URI)

        self.fake_mqtt_broker.publish_to_subscription(topic, {})
        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msg = "\nGlobal Configurations:"
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    def test_mqtt_command_config_map_changes(
        self,
        status_check_all_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock
    ):
        self.start_mqtt()
        topic = self.get_topic_for(self.CONFIG_URI)
        notify_topic = f"hbot/{self.instance_id}/notify"

        self._strategy_config_map = {}
        self.fake_mqtt_broker.publish_to_subscription(topic, {})
        notify_msg = "\nGlobal Configurations:"
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

        self.fake_mqtt_broker.publish_to_subscription(topic, {})
        notify_msg = "\nGlobal Configurations:"
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

        prev_cconfigmap = self.client_config_map
        self.client_config_map = {}
        self.fake_mqtt_broker.publish_to_subscription(topic, {})
        notify_msg = "\nGlobal Configurations:"
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))
        self.client_config_map = prev_cconfigmap

    def test_mqtt_command_config_updates_single_param(self):
        self.start_mqtt()

        topic = self.get_topic_for(self.CONFIG_URI)

        config_msg = {
            'params': [
                ('instance_id', self.instance_id),
            ]
        }

        self.fake_mqtt_broker.publish_to_subscription(topic, config_msg)
        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msg = "\nGlobal Configurations:"
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    @patch("hummingbot.client.command.config_command.ConfigCommand.config")
    def test_mqtt_command_config_updates_configurable_keys(
        self,
        config_mock: MagicMock
    ):
        config_mock.side_effect = self._create_exception_and_unlock_test_with_event
        self.start_mqtt()

        config_msg = {
            'params': [
                ('skata', 90),
            ]
        }

        self.fake_mqtt_broker.publish_to_subscription(
            self.get_topic_for(self.CONFIG_URI),
            config_msg
        )
        topic = f"test_reply/hbot/{self.instance_id}/config"
        msg = {'changes': [], 'config': {}, 'status': 400, 'msg': "Invalid param key(s): ['skata']"}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    def test_mqtt_command_config_updates_multiple_params(self):
        self.start_mqtt()
        topic = self.get_topic_for(self.CONFIG_URI)
        config_msg = {
            'params': [
                ('instance_id', self.instance_id),
                ('mqtt_bridge.mqtt_port', 1888),
            ]
        }
        self.fake_mqtt_broker.publish_to_subscription(topic, config_msg)
        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msg = "\nGlobal Configurations:"
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    @patch("hummingbot.client.command.config_command.ConfigCommand.config")
    def test_mqtt_command_config_failure(
        self,
        config_mock: MagicMock
    ):
        config_mock.side_effect = self._create_exception_and_unlock_test_with_event
        self.start_mqtt()

        self.fake_mqtt_broker.publish_to_subscription(self.get_topic_for(self.CONFIG_URI), {})

        self.async_run_with_timeout(self.resume_test_event.wait())

        topic = f"test_reply/hbot/{self.instance_id}/config"
        msg = {'changes': [], 'config': {}, 'status': 400, 'msg': self.fake_err_msg}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    @patch("hummingbot.client.command.history_command.HistoryCommand.get_history_trades_json")
    def test_mqtt_command_history(
        self,
        get_history_trades_mock: MagicMock
    ):
        fake_trades = self.build_fake_trades()
        get_history_trades_mock.return_value = fake_trades
        self.start_mqtt()

        topic = self.get_topic_for(self.HISTORY_URI)

        self.fake_mqtt_broker.publish_to_subscription(
            topic,
            {"async_backend": 0}
        )
        history_topic = f"test_reply/hbot/{self.instance_id}/history"
        history_msg = {'status': 200, 'msg': '', 'trades': fake_trades}
        self.async_run_with_timeout(self.wait_for_rcv(history_topic, history_msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(history_topic, history_msg, msg_key='data'))

        self.fake_mqtt_broker.publish_to_subscription(
            topic,
            {"async_backend": 1}
        )
        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msg = "\n  Please first import a strategy config file of which to show historical performance."
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))
        history_topic = f"test_reply/hbot/{self.instance_id}/history"
        history_msg = {'status': 200, 'msg': '', 'trades': []}
        self.async_run_with_timeout(self.wait_for_rcv(history_topic, history_msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(history_topic, history_msg, msg_key='data'))

    @patch("hummingbot.client.command.history_command.HistoryCommand.history")
    def test_mqtt_command_history_failure(
        self,
        history_mock: MagicMock
    ):
        history_mock.side_effect = self._create_exception_and_unlock_test_with_event
        self.start_mqtt()

        self.fake_mqtt_broker.publish_to_subscription(self.get_topic_for(self.HISTORY_URI), {})

        self.async_run_with_timeout(self.resume_test_event.wait())

        topic = f"test_reply/hbot/{self.instance_id}/history"
        msg = {'status': 400, 'msg': self.fake_err_msg, 'trades': []}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    def test_mqtt_command_import(
        self,
        status_check_all_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock
    ):
        self.start_mqtt()
        self.send_fake_import_cmd(status_check_all_mock=status_check_all_mock,
                                  load_strategy_config_map_from_file=load_strategy_config_map_from_file,
                                  invalid_strategy=False)

        notify_topic = f"hbot/{self.instance_id}/notify"
        start_msg = '\nEnter "start" to start market making.'
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, start_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, 'Configuration from avellaneda_market_making.yml file is imported.'))
        self.assertTrue(self.is_msg_received(notify_topic, start_msg))

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    @patch("hummingbot.client.command.import_command.ImportCommand.import_config_file", new_callable=AsyncMock)
    def test_mqtt_command_import_failure(
        self,
        import_mock: AsyncMock,
        status_check_all_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock
    ):
        import_mock.side_effect = self._create_exception_and_unlock_test_with_event_async
        self.start_mqtt()
        self.send_fake_import_cmd(status_check_all_mock=status_check_all_mock,
                                  load_strategy_config_map_from_file=load_strategy_config_map_from_file,
                                  invalid_strategy=False)

        topic = f"test_reply/hbot/{self.instance_id}/import"
        msg = {'status': 400, 'msg': 'Some error'}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    @patch("hummingbot.client.command.import_command.ImportCommand.import_config_file", new_callable=AsyncMock)
    def test_mqtt_command_import_empty_strategy(
        self,
        import_mock: AsyncMock,
        status_check_all_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock
    ):
        import_mock.side_effect = self._create_exception_and_unlock_test_with_event_async
        topic = f"test_reply/hbot/{self.instance_id}/import"
        msg = {'status': 400, 'msg': 'Empty strategy_name given!'}
        self.start_mqtt()
        self.send_fake_import_cmd(status_check_all_mock=status_check_all_mock,
                                  load_strategy_config_map_from_file=load_strategy_config_map_from_file,
                                  invalid_strategy=False,
                                  empty_name=True)
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.start_command.StartCommand._in_start_check")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    def test_mqtt_command_start_sync(
        self,
        status_check_all_mock: MagicMock,
        in_start_check_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock
    ):
        in_start_check_mock.return_value = True
        self.start_mqtt()

        self.send_fake_import_cmd(status_check_all_mock=status_check_all_mock,
                                  load_strategy_config_map_from_file=load_strategy_config_map_from_file,
                                  invalid_strategy=False)

        notify_topic = f"hbot/{self.instance_id}/notify"

        self.async_run_with_timeout(self.wait_for_rcv(
            notify_topic, '\nEnter "start" to start market making.'), timeout=10)

        self.fake_mqtt_broker.publish_to_subscription(
            self.get_topic_for(self.START_URI),
            {'async_backend': 0}
        )

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.start_command.StartCommand._in_start_check")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    def test_mqtt_command_start_async(
        self,
        status_check_all_mock: MagicMock,
        in_start_check_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock
    ):
        in_start_check_mock.return_value = True
        self.start_mqtt()

        self.send_fake_import_cmd(status_check_all_mock=status_check_all_mock,
                                  load_strategy_config_map_from_file=load_strategy_config_map_from_file,
                                  invalid_strategy=False)

        notify_topic = f"hbot/{self.instance_id}/notify"

        self.async_run_with_timeout(self.wait_for_rcv(
            notify_topic, '\nEnter "start" to start market making.'), timeout=10)

        self.fake_mqtt_broker.publish_to_subscription(
            self.get_topic_for(self.START_URI),
            {'async_backend': 1}
        )
        # start_msg = 'The bot is already running - please run "stop" first'
        # self.async_run_with_timeout(self.wait_for_rcv(notify_topic, start_msg))
        # self.assertTrue(self.is_msg_received(notify_topic, start_msg))

    @patch("hummingbot.client.command.start_command.init_logging")
    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.start_command.StartCommand.start_script_strategy")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    def test_mqtt_command_start_script(
        self,
        status_check_all_mock: MagicMock,
        start_script_strategy_mock: MagicMock,
        load_strategy_config_map_from_file: MagicMock,
        mock_init_logging: MagicMock
    ):
        start_script_strategy_mock.side_effect = self._create_exception_and_unlock_test_with_event_not_impl
        mock_init_logging.side_effect = lambda *args, **kwargs: None
        self.start_mqtt()

        notify_topic = f"hbot/{self.instance_id}/notify"
        notify_msg = "Invalid strategy. Start aborted."

        self.fake_mqtt_broker.publish_to_subscription(
            self.get_topic_for(self.START_URI),
            {'script': 'format_status_example.py'}
        )

        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, notify_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, notify_msg))

    # This test fails when executed individually
    # @patch("hummingbot.client.command.start_command.StartCommand.start")
    # def test_mqtt_command_start_failure(
    #     self,
    #     start_mock: MagicMock
    # ):
    #     start_mock.side_effect = self._create_exception_and_unlock_test_with_event
    #     self.start_mqtt()
    #     self.fake_mqtt_broker.publish_to_subscription(
    #         self.get_topic_for(self.START_URI),
    #         {}
    #     )
    #     topic = f"test_reply/hbot/{self.instance_id}/start"
    #     msg = {'status': 400, 'msg': self.fake_err_msg}
    #     self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
    #     self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))
    #
    #     self.hbapp.strategy_name = None
    #
    #     self.fake_mqtt_broker.publish_to_subscription(
    #         self.get_topic_for(self.START_URI),
    #         {'script': None}
    #     )
    #     topic = f"test_reply/hbot/{self.instance_id}/start"
    #     msg = {'status': 400, 'msg': self.fake_err_msg}
    #     self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
    #     self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))
    #
    #     self.fake_mqtt_broker.publish_to_subscription(
    #         self.get_topic_for(self.START_URI),
    #         {'script': 'format_status_example.py'}
    #     )
    #     topic = f"test_reply/hbot/{self.instance_id}/start"
    #     msg = {'status': 400, 'msg': self.fake_err_msg}
    #     self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
    #     self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))
    #
    #     prev_strategy = self.hbapp.strategy
    #     self.hbapp.strategy = {}
    #
    #     self.fake_mqtt_broker.publish_to_subscription(
    #         self.get_topic_for(self.START_URI),
    #         {'script': 'format_status_example.py'}
    #     )
    #     topic = f"test_reply/hbot/{self.instance_id}/start"
    #     msg = {
    #         'status': 400,
    #         'msg': 'The bot is already running - please run "stop" first'
    #     }
    #     self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
    #     self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))
    #
    #     self.fake_mqtt_broker.publish_to_subscription(
    #         self.get_topic_for(self.START_URI),
    #         {}
    #     )
    #     topic = f"test_reply/hbot/{self.instance_id}/start"
    #     msg = {
    #         'status': 400,
    #         'msg': 'Strategy check: Please import or create a strategy.'
    #     }
    #     self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
    #     self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))
    #     self.hbapp.strategy = prev_strategy

    @patch("hummingbot.client.command.status_command.StatusCommand.strategy_status", new_callable=AsyncMock)
    def test_mqtt_command_status_no_strategy_running(
        self,
        strategy_status_mock: AsyncMock
    ):
        strategy_status_mock.side_effect = self._create_exception_and_unlock_test_with_event_async
        self.start_mqtt()
        self.fake_mqtt_broker.publish_to_subscription(
            self.get_topic_for(self.STATUS_URI),
            {'async_backend': 0}
        )
        topic = f"test_reply/hbot/{self.instance_id}/status"
        msg = {'status': 400, 'msg': 'No strategy is currently running!', 'data': ''}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    @patch("hummingbot.client.command.status_command.StatusCommand.strategy_status", new_callable=AsyncMock)
    def test_mqtt_command_status_async(
        self,
        strategy_status_mock: AsyncMock
    ):
        strategy_status_mock.side_effect = self._create_exception_and_unlock_test_with_event_async
        self.hbapp.strategy = {}
        self.start_mqtt()
        self.fake_mqtt_broker.publish_to_subscription(
            self.get_topic_for(self.STATUS_URI),
            {'async_backend': 1}
        )
        topic = f"test_reply/hbot/{self.instance_id}/status"
        msg = {'status': 200, 'msg': '', 'data': ''}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))
        self.hbapp.strategy = None

    @patch("hummingbot.client.command.status_command.StatusCommand.strategy_status", new_callable=AsyncMock)
    def test_mqtt_command_status_sync(
        self,
        strategy_status_mock: AsyncMock
    ):
        strategy_status_mock.side_effect = self._create_exception_and_unlock_test_with_event_async
        self.hbapp.strategy = {}
        self.start_mqtt()
        self.fake_mqtt_broker.publish_to_subscription(
            self.get_topic_for(self.STATUS_URI),
            {'async_backend': 0}
        )
        topic = f"test_reply/hbot/{self.instance_id}/status"
        msg = {'status': 400, 'msg': 'Some error', 'data': ''}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))
        self.hbapp.strategy = None

    @patch("hummingbot.client.command.status_command.StatusCommand.strategy_status", new_callable=AsyncMock)
    def test_mqtt_command_status_failure(
        self,
        strategy_status_mock: AsyncMock
    ):
        strategy_status_mock.side_effect = self._create_exception_and_unlock_test_with_event_async
        self.start_mqtt()
        self.fake_mqtt_broker.publish_to_subscription(self.get_topic_for(self.STATUS_URI), {})
        topic = f"test_reply/hbot/{self.instance_id}/status"
        msg = {'status': 400, 'msg': 'No strategy is currently running!', 'data': ''}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    # This test freezes the process that runs the tests, and it never finishes
    # def test_mqtt_command_stop_sync(self):
    #     self.start_mqtt()
    #
    #     topic = self.get_topic_for(self.STOP_URI)
    #
    #     self.fake_mqtt_broker.publish_to_subscription(
    #         topic,
    #         {'async_backend': 0}
    #     )
    #     notify_topic = f"hbot/{self.instance_id}/notify"
    #     wind_down_msg = "\nWinding down..."
    #     canceling_msg = "Canceling outstanding orders..."
    #     stop_msg = "All outstanding orders canceled."
    #     self.async_run_with_timeout(self.wait_for_rcv(notify_topic, wind_down_msg), timeout=10)
    #     self.assertTrue(self.is_msg_received(notify_topic, wind_down_msg))
    #     self.async_run_with_timeout(self.wait_for_rcv(notify_topic, canceling_msg), timeout=10)
    #     self.assertTrue(self.is_msg_received(notify_topic, canceling_msg))
    #     self.async_run_with_timeout(self.wait_for_rcv(notify_topic, stop_msg), timeout=10)
    #     self.assertTrue(self.is_msg_received(notify_topic, stop_msg))

    def test_mqtt_command_stop_async(self):
        self.start_mqtt()

        topic = self.get_topic_for(self.STOP_URI)
        self.fake_mqtt_broker.publish_to_subscription(
            topic,
            {'async_backend': 1}
        )
        notify_topic = f"hbot/{self.instance_id}/notify"
        wind_down_msg = "\nWinding down..."
        canceling_msg = "Canceling outstanding orders..."
        stop_msg = "All outstanding orders canceled."
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, wind_down_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, wind_down_msg))
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, canceling_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, canceling_msg))
        self.async_run_with_timeout(self.wait_for_rcv(notify_topic, stop_msg), timeout=10)
        self.assertTrue(self.is_msg_received(notify_topic, stop_msg))

    @patch("hummingbot.client.command.stop_command.StopCommand.stop")
    def test_mqtt_command_stop_failure(
        self,
        stop_mock: MagicMock
    ):
        stop_mock.side_effect = self._create_exception_and_unlock_test_with_event
        self.start_mqtt()

        self.fake_mqtt_broker.publish_to_subscription(self.get_topic_for(self.STOP_URI), {})

        self.async_run_with_timeout(self.resume_test_event.wait())

        topic = f"test_reply/hbot/{self.instance_id}/stop"
        msg = {'status': 400, 'msg': self.fake_err_msg}
        self.async_run_with_timeout(self.wait_for_rcv(topic, msg, msg_key='data'), timeout=10)
        self.assertTrue(self.is_msg_received(topic, msg, msg_key='data'))

    def test_mqtt_event_buy_order_created(self):
        self.start_mqtt()

        order = LimitOrder(client_order_id="HBOT_1",
                           trading_pair="HBOT-USDT",
                           is_buy=True,
                           base_currency="HBOT",
                           quote_currency="USDT",
                           price=Decimal("100"),
                           quantity=Decimal("1.5")
                           )

        self.emit_order_created_event(self.test_market, order)

        events_topic = f"hbot/{self.instance_id}/events"

        evt_type = "BuyOrderCreated"
        self.async_run_with_timeout(self.wait_for_rcv(events_topic, evt_type, msg_key = 'type'), timeout=10)
        self.assertTrue(self.is_msg_received(events_topic, evt_type, msg_key = 'type'))

    def test_mqtt_event_sell_order_created(self):
        self.start_mqtt()

        order = LimitOrder(client_order_id="HBOT_1",
                           trading_pair="HBOT-USDT",
                           is_buy=False,
                           base_currency="HBOT",
                           quote_currency="USDT",
                           price=Decimal("100"),
                           quantity=Decimal("1.5")
                           )

        self.emit_order_created_event(self.test_market, order)

        events_topic = f"hbot/{self.instance_id}/events"

        evt_type = "SellOrderCreated"
        self.async_run_with_timeout(self.wait_for_rcv(events_topic, evt_type, msg_key = 'type'), timeout=10)
        self.assertTrue(self.is_msg_received(events_topic, evt_type, msg_key = 'type'))

    def test_mqtt_event_order_expired(self):
        self.start_mqtt()

        self.emit_order_expired_event(self.test_market)

        events_topic = f"hbot/{self.instance_id}/events"

        evt_type = "OrderExpired"
        self.async_run_with_timeout(self.wait_for_rcv(events_topic, evt_type, msg_key = 'type'), timeout=10)
        self.assertTrue(self.is_msg_received(events_topic, evt_type, msg_key = 'type'))

    def test_mqtt_subscribed_topics(self):
        self.start_mqtt()
        self.assertTrue(self.gateway is not None)
        subscribed_mqtt_topics = sorted(list([f"hbot/{self.instance_id}/{topic}"
                                              for topic in (self.command_topics + ['external/event/*'])]))
        self.assertEqual(subscribed_mqtt_topics, sorted(list(self.fake_mqtt_broker.subscriptions.keys())))

    @patch("hummingbot.remote_iface.mqtt.mqtts_logger", None)
    def test_mqtt_eventforwarder_logger(self):
        self.assertTrue(MQTTMarketEventForwarder.logger() is not None)
        self.start_mqtt()

    def test_mqtt_eventforwarder_unknown_events(self):
        self.start_mqtt()
        test_evt = {"unknown": "you don't know me"}
        self.gateway._market_events._send_mqtt_event(event_tag=999,
                                                     pubsub=None,
                                                     event=test_evt)

        events_topic = f"hbot/{self.instance_id}/events"

        evt_type = "Unknown"
        self.async_run_with_timeout(self.wait_for_rcv(events_topic, evt_type, msg_key = 'type'), timeout=10)
        self.assertTrue(self.is_msg_received(events_topic, evt_type, msg_key = 'type'))
        self.assertTrue(self.is_msg_received(events_topic, test_evt, msg_key = 'data'))

    def test_mqtt_eventforwarder_invalid_events(self):
        self.start_mqtt()
        self.gateway._market_events._send_mqtt_event(event_tag=999,
                                                     pubsub=None,
                                                     event="i feel empty")

        events_topic = f"hbot/{self.instance_id}/events"

        evt_type = "Unknown"
        self.async_run_with_timeout(
            self.wait_for_rcv(events_topic, evt_type, msg_key = 'type'), timeout=10)
        self.assertTrue(self.is_msg_received(events_topic, evt_type, msg_key = 'type'))
        self.assertTrue(self.is_msg_received(events_topic, {}, msg_key = 'data'))

    def test_mqtt_notifier_fakes(self):
        self.start_mqtt()
        self.assertEqual(self.gateway._notifier.start(), None)
        self.assertEqual(self.gateway._notifier.stop(), None)

    def test_mqtt_gateway_check_health(self):
        tmp = self.gateway._start_health_monitoring_loop
        self.gateway._start_health_monitoring_loop = lambda: None
        self.start_mqtt()
        self.assertTrue(self.gateway._check_connections())
        self.gateway._rpc_services[0]._transport._connected = False
        self.assertFalse(self.gateway._check_connections())
        self.gateway._rpc_services[0]._transport._connected = True
        s = self.gateway.create_subscriber(topic='TEST', on_message=lambda x: {})
        s.run()
        self.assertTrue(self.gateway._check_connections())
        s._transport._connected = False
        self.assertFalse(self.gateway._check_connections())
        prev_pub = self.gateway._publishers
        prev__sub = self.gateway._subscribers
        self.gateway._publishers = []
        self.gateway._subscribers = []
        self.gateway._rpc_services[0]._transport._connected = False
        self.assertFalse(self.gateway._check_connections())
        self.gateway._publishers = prev_pub
        self.gateway._subscribers = prev__sub
        self.gateway._start_health_monitoring_loop = tmp

    @patch("hummingbot.remote_iface.mqtt.MQTTGateway.health", new_callable=PropertyMock)
    def test_mqtt_gateway_check_health_restarts(
        self,
        health_mock: PropertyMock
    ):
        health_mock.return_value = True
        status_topic = f"hbot/{self.instance_id}/status_updates"
        self.start_mqtt()
        self.async_run_with_timeout(self.wait_for_logged("DEBUG", f"Started Heartbeat Publisher <hbot/{self.instance_id}/hb>"), timeout=10)
        self.async_run_with_timeout(self.wait_for_rcv(status_topic, 'online'), timeout=10)
        self.async_run_with_timeout(self.wait_for_logged("DEBUG", "Monitoring MQTT Gateway health for disconnections."), timeout=10)
        self.log_records.clear()
        health_mock.return_value = False
        self.restart_interval_mock.return_value = None
        self.async_run_with_timeout(self.wait_for_logged("WARNING", "MQTT Gateway is disconnected, attempting to reconnect."), timeout=10)
        fake_err = "'<=' not supported between instances of 'NoneType' and 'int'"
        self.async_run_with_timeout(self.wait_for_logged("ERROR", f"MQTT Gateway failed to reconnect: {fake_err}. Sleeping 10 seconds before retry."), timeout=10)
        self.assertFalse(
            self._is_logged(
                "WARNING",
                "MQTT Gateway successfully reconnected.",
            )
        )
        self.assertTrue(self.is_msg_received(status_topic, 'offline'))
        self.log_records.clear()
        self.restart_interval_mock.return_value = 0.0
        self.hbapp.strategy = True
        self.async_run_with_timeout(self.wait_for_logged("WARNING", "MQTT Gateway is disconnected, attempting to reconnect."), timeout=10)
        health_mock.return_value = True
        self.async_run_with_timeout(self.wait_for_logged("WARNING", "MQTT Gateway successfully reconnected."), timeout=10)
        self.assertTrue(
            self._is_logged(
                "WARNING",
                "MQTT Gateway successfully reconnected.",
            )
        )

    def test_mqtt_gateway_stop(self):
        self.start_mqtt()
        self.assertTrue(self.gateway._check_connections())
        self.gateway.stop()
        self.assertFalse(self.gateway._check_connections())

    def test_eevent_queue_factory(self):
        self.start_mqtt()
        from hummingbot.remote_iface.mqtt import EEventQueueFactory, ExternalEventFactory
        queue = ExternalEventFactory.create_queue('test')
        self.assertTrue(queue is not None)

        from collections import deque
        dq = deque()
        EEventQueueFactory._on_event(dq, {'a': 1}, 'testevent')
        self.assertTrue(1)

    def test_eevent_listener_factory(self):
        self.start_mqtt()
        from hummingbot.remote_iface.mqtt import ExternalEventFactory

        def clb(msg, event_name):
            pass

        ExternalEventFactory.create_async('test.a.b', clb)
        ExternalEventFactory.remove_listener('test.a.b', clb)
        try:
            MQTTGateway._instance = None
            ExternalEventFactory.create_async('test.a.b', clb)
            ExternalEventFactory.remove_listener('test.a.b', clb)
        except Exception:
            self.assertTrue(1)
        else:
            self.assertTrue(0)

    def test_etopic_queue_factory(self):
        self.start_mqtt()
        from hummingbot.remote_iface.mqtt import ETopicQueueFactory, ExternalTopicFactory
        queue = ExternalTopicFactory.create_queue('test/a/b')
        self.assertTrue(queue is not None)

        from collections import deque
        dq = deque()
        ETopicQueueFactory._on_message(dq, {'a': 1}, 'test/external')
        self.assertTrue(1)

    def test_etopic_listener_factory(self):
        self.start_mqtt()
        from hummingbot.remote_iface.mqtt import ExternalTopicFactory

        def clb(msg, topic):
            pass

        listener = ExternalTopicFactory.create_async('test/a/b', clb)
        self.assertTrue(listener is not None)
        ExternalTopicFactory.remove_listener(listener)

    def test_external_events_add_remove(self):
        self.start_mqtt()
        from hummingbot.remote_iface.mqtt import MQTTGateway

        def clb(msg, event_name):
            pass

        gw = MQTTGateway.main()
        self.assertTrue(len(gw._external_events._listeners.get('*')) == 0)
        gw.add_external_event_listener('*', clb)
        self.assertTrue(len(gw._external_events._listeners.get('*')) == 1)
        gw.remove_external_event_listener('*', clb)
        self.assertTrue(len(gw._external_events._listeners.get('*')) == 0)
        gw.add_external_event_listener('test.a.b', clb)
        self.assertTrue(len(gw._external_events._listeners.get('test.a.b')) == 1)
        gw.remove_external_event_listener('test.a.b', clb)
        self.assertTrue(len(gw._external_events._listeners.get('test.a.b')) == 0)

    def test_mqtt_log_handler(self):
        import logging

        from hummingbot.logger import HummingbotLogger
        from hummingbot.remote_iface.mqtt import MQTTLogHandler
        self.start_mqtt()

        handler = MQTTLogHandler(self.hbapp, self.gateway)
        handler.emit(logging.LogRecord('', 1, '', '', '', '', ''))
        self.assertTrue(1)

        logger = HummingbotLogger('testlogger')
        self.gateway.add_log_handler(logger)
        self.gateway.remove_log_handler(logger)
        logger = self.gateway._get_root_logger()
        self.assertTrue(logger is not None)
        self.gateway._remove_log_handlers()

    def test_market_events(self):
        self.start_mqtt()
        from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, DeductedFromReturnsTradeFee
        from hummingbot.remote_iface.mqtt import MQTTGateway

        gw = MQTTGateway.main()
        gw._market_events._make_event_payload({
            'a': 'a',
            'b': 1,
            'c': Decimal('1.0'),
            'd': DeductedFromReturnsTradeFee(),
            'e': AddedToCostTradeFee(),
            'f': {'a': 1},
            'type': 'TEST',
            'order_type': 'BUY',
            'trade_type': 'LIMIT',
        })
        self.assertTrue(1)

    def test_etopic_listener_class(self):
        from hummingbot.remote_iface.mqtt import ETopicListener

        def clb(msg, topic):
            pass

        listener = ETopicListener('test', clb, use_bot_prefix=False)
        self.assertTrue(listener is not None)
        listener = ETopicListener('test', clb, use_bot_prefix=True)
        self.assertTrue(listener is not None)

        self.start_mqtt()
        listener = ETopicListener('test', clb, use_bot_prefix=True)
        self.assertTrue(listener is not None)

        prev_gw = MQTTGateway.main()
        MQTTGateway._instance = None
        try:
            listener = ETopicListener('test', clb, use_bot_prefix=False)
        except Exception:
            self.assertTrue(1)
        else:
            self.assertFalse(1)
        MQTTGateway._instance = prev_gw

    def test_eevent_queue_factory_class(self):
        from hummingbot.remote_iface.mqtt import EEventQueueFactory
        self.start_mqtt()

        equeue = EEventQueueFactory.create(event_name='test', queue_size=2)
        self.assertTrue(equeue is not None)

        prev_gw = MQTTGateway.main()
        MQTTGateway._instance = None
        try:
            equeue = EEventQueueFactory.create(event_name='test', queue_size=2)
        except Exception:
            self.assertTrue(1)
        else:
            self.assertFalse(1)
        MQTTGateway._instance = prev_gw

    def test_eevent_listener_factory_class(self):
        from hummingbot.remote_iface.mqtt import EEventListenerFactory
        self.start_mqtt()

        def clb(msg, topic):
            pass

        EEventListenerFactory.create(event_name='test', callback=clb)
        prev_gw = MQTTGateway.main()
        MQTTGateway._instance = None
        try:
            EEventListenerFactory.create(event_name='test',
                                         callback=clb)
        except Exception:
            self.assertTrue(1)
        else:
            self.assertFalse(1)
        try:
            EEventListenerFactory.remove(event_name='test',
                                         callback=clb)
        except Exception:
            self.assertTrue(1)
        else:
            self.assertFalse(1)
        MQTTGateway._instance = prev_gw

    def test_mqtt_external_events_class(self):
        from hummingbot.remote_iface.messages import ExternalEventMessage
        from hummingbot.remote_iface.mqtt import MQTTExternalEvents

        self.start_mqtt()

        def clb(msg, topic):
            pass

        eevents = MQTTExternalEvents(self.hbapp, self.gateway)
        eevents.add_global_listener(clb)
        ename = eevents._event_uri_to_name('hbot/bot1/external/event/e1')
        self.assertTrue(ename == "e1")
        eevents.add_listener('e1', clb)
        eevents.add_listener('e1', clb)
        eevents._on_event_arrived(ExternalEventMessage(),
                                  'hbot/bot1/external/event/e1')
        self.assertTrue(len(eevents._listeners) == 2)
        self.assertTrue('*' in eevents._listeners)
        self.assertTrue('e1' in eevents._listeners)
        self.assertTrue(ename in eevents._listeners)

        eevents._listeners = {}
        eevents.add_global_listener(clb)
        eevents.remove_global_listener(clb)
        eevents.add_listener('test_event', clb)
        eevents.remove_listener('test_event', clb)
        eevents.add_listener('test_event', clb)
        eevents.add_listener('test_event', clb)
        eevents.remove_listener('test_event', clb)

    def test_mqtt_gateway_health(self):
        health = self.gateway.health
        self.assertFalse(health)

    def test_mqtt_gateway_namespace_wrong_lastchar(self):
        prev_ns = self.gateway._hb_app.client_config_map.mqtt_bridge.mqtt_namespace
        self.gateway._hb_app.client_config_map.mqtt_bridge.mqtt_namespace = 'test/'
        gw = MQTTGateway(self.hbapp)
        self.assertTrue(gw.namespace == 'test')
        gw.stop()
        del gw
        self.gateway._hb_app.client_config_map.mqtt_bridge.mqtt_namespace = prev_ns

    def test_etopic_publisher(self):
        self.start_mqtt()
        from hummingbot.remote_iface.mqtt import EMTopicPublisher, ETopicPublisher
        test_msg = {
            "a": "test",
            "b": 1,
            "c": False,
            "d": {},
            "e": []
        }
        pub = ETopicPublisher('test/a/b', use_bot_prefix=False)
        pub.send(test_msg)
        self.assertTrue(1)
        pub2 = EMTopicPublisher(use_bot_prefix=False)
        pub2.send("test/a/b", test_msg)
        pub2.send("test/c/d", test_msg)
        self.assertTrue(1)
