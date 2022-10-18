#!/usr/bin/env python

import asyncio
import threading
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from logging import Handler, LogRecord
from typing import TYPE_CHECKING, List, Tuple

# from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication
    from hummingbot.core.event.event_listener import EventListener

from commlib.msg import PubSubMessage
from commlib.node import Node
from commlib.transports.mqtt import ConnectionParameters as MQTTConnectionParameters

from hummingbot.core.event import events
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.pubsub import PubSub
from hummingbot.notifier.notifier_base import NotifierBase

mqtts_logger: HummingbotLogger = None


class NotifyMessage(PubSubMessage):
    seq: int = 0
    timestamp: int = -1
    msg: str = ''


class EventMessage(PubSubMessage):
    timestamp: int = -1
    type: str = 'Unknown'
    data: dict = {}


class MQTTCommands(Node):
    START_URI = 'hbot/$UID/start'
    STOP_URI = 'hbot/$UID/stop'
    RESTART_URI = 'hbot/$UID/restart'
    CONFIG_URI = 'hbot/$UID/config'
    IMPORT_URI = 'hbot/$UID/import'
    STATUS_URI = 'hbot/$UID/status'

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node):
        self._hb_app = hb_app
        self.node = mqtt_node
        self.logger = self._hb_app.logger

        self.START_URI = self.START_URI.replace('$UID', hb_app.uid())
        self.STOP_URI = self.STOP_URI.replace('$UID', hb_app.uid())
        self.RESTART_URI = self.RESTART_URI.replace('$UID', hb_app.uid())
        self.CONFIG_URI = self.CONFIG_URI.replace('$UID', hb_app.uid())
        self.IMPORT_URI = self.IMPORT_URI.replace('$UID', hb_app.uid())
        self.STATUS_URI = self.STATUS_URI.replace('$UID', hb_app.uid())

        self._init_commands()

    def _init_commands(self):
        self.node.create_rpc(
            rpc_name=self.START_URI,
            on_request=self._on_cmd_start
        )
        self.node.create_rpc(
            rpc_name=self.STOP_URI,
            on_request=self._on_cmd_stop
        )
        self.node.create_rpc(
            rpc_name=self.RESTART_URI,
            on_request=self._on_cmd_restart
        )
        self.node.create_rpc(
            rpc_name=self.CONFIG_URI,
            on_request=self._on_cmd_config
        )
        self.node.create_rpc(
            rpc_name=self.IMPORT_URI,
            on_request=self._on_cmd_import
        )
        self.node.create_rpc(
            rpc_name=self.STATUS_URI,
            on_request=self._on_cmd_status
        )

    def _on_cmd_start(self, msg):
        # self.node.logger().info(f"MQTT <Start> Command Received! msg = {msg}")
        self._hb_app.start()
        return {}

    def _on_cmd_stop(self, msg):
        # self.node.logger().info(f"MQTT <Stop> Command Received! msg = {msg}")
        self._hb_app.stop()
        return {}

    def _on_cmd_restart(self, msg):
        # self.node.logger().info(f"MQTT <Start> Command Received! msg = {msg}")
        self._hb_app.restart()
        return {}

    def _on_cmd_config(self, msg):
        # self.node.logger().info(f"MQTT <Config> Command Received! msg = {msg}")
        if len(msg) == 0:
            self._hb_app.config()
        else:
            for key, val in msg.items():
                if key in self._hb_app.config_able_keys():
                    self._hb_app.config(key, val)
        response = self._hb_app.get_config()
        return response

    def _on_cmd_import(self, msg):
        strategy_name = msg.get("strategy")
        response = {
            'status': 200,
            'msg': ''
        }
        if strategy_name is not None:
            strategy_file_name = f'{strategy_name}.yml'
            try:
                self._hb_app.import_command(strategy_file_name)
            except Exception as e:
                self._hb_app.notify(str(e))
                response['status'] = 400
                response['msg'] = str(e)
        return response

    def _on_cmd_status(self, msg):
        self._hb_app.status()
        _response = {}
        try:
            _response['msg'] = asyncio.run(self._hb_app.strategy_status()).strip()
        except AttributeError:
            _response['msg'] = "The strategy is not running."
        return _response

    def _on_get_market_data(self, msg):
        stat_data = self._hb_app.strategy.market_status_df()
        print(stat_data)


class MQTTEventForwarder:
    EVENT_URI = 'hbot/$UID/events'

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node):

        if threading.current_thread() != threading.main_thread():
            raise EnvironmentError(
                "MQTTEventForwarder can only be initialized from the main thread."
            )

        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._hb_app = hb_app
        self._node = mqtt_node
        self._markets: List[ConnectorBase] = list(self._hb_app.markets.values())

        self._topic = self.EVENT_URI.replace('$UID', self._hb_app.uid())

        self._mqtt_fowarder: SourceInfoEventForwarder = \
            SourceInfoEventForwarder(self._send_mqtt_event)
        self._market_event_pairs: List[Tuple[int, EventListener]] = [
            (events.MarketEvent.BuyOrderCreated, self._mqtt_fowarder),
            (events.MarketEvent.BuyOrderCompleted, self._mqtt_fowarder),
            (events.MarketEvent.SellOrderCreated, self._mqtt_fowarder),
            (events.MarketEvent.SellOrderCompleted, self._mqtt_fowarder),
            (events.MarketEvent.OrderFilled, self._mqtt_fowarder),
            (events.MarketEvent.OrderFailure, self._mqtt_fowarder),
            (events.MarketEvent.OrderCancelled, self._mqtt_fowarder),
            (events.MarketEvent.OrderExpired, self._mqtt_fowarder),
        ]
        self._app_event_pairs: List[Tuple[int, EventListener]] = []
        # self._app_event_pairs: List[Tuple[int, EventListener]] = [
        #     (events.CustomEvent.KillSwitchTriggered, self._mqtt_fowarder),
        #     (events.CustomEvent.MarketInitialized, self._mqtt_fowarder),
        # ]

        self.event_fw_pub = self._node.create_publisher(
            topic=self._topic, msg_type=EventMessage
        )
        self.start_event_listener()

    def _send_mqtt_event(self, event_tag: int, pubsub: PubSub, event):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._send_mqtt_event, event_tag, pubsub, event)
            return

        try:
            event_types = {
                events.MarketEvent.BuyOrderCreated.value: "BuyOrderCreated",
                events.MarketEvent.BuyOrderCompleted.value: "BuyOrderCompleted",
                events.MarketEvent.SellOrderCreated.value: "SellOrderCreated",
                events.MarketEvent.SellOrderCompleted.value: "SellOrderCompleted",
                events.MarketEvent.OrderFilled.value: "OrderFilled",
                events.MarketEvent.OrderCancelled.value: "OrderCancelled",
                events.MarketEvent.OrderExpired.value: "OrderExpired",
                events.MarketEvent.OrderFailure.value: "OrderFailure",
                # events.CustomEvent.KillSwitchTriggered.value: "KillSwitchTriggered",
                # events.CustomEvent.MarketInitialized.value: "MarketInitialized",
            }
            event_type = event_types[event_tag]
        except KeyError:
            event_type = "Unknown"

        if is_dataclass(event):
            event_data = asdict(event)
        elif isinstance(event, tuple) and hasattr(event, '_fields'):
            event_data = event._asdict()
        else:
            try:
                event_data = dict(event)
            except (TypeError, ValueError):
                event_data = {}

        try:
            timestamp = event_data.pop('timestamp')
        except KeyError:
            timestamp = datetime.now().timestamp()

        self.event_fw_pub.publish(
            EventMessage(
                timestamp=int(timestamp),
                type=event_type,
                data=event_data
            )
        )

    def start_event_listener(self):
        for market in self._markets:
            for event_pair in self._market_event_pairs:
                market.add_listener(event_pair[0], event_pair[1])
        for event_pair in self._app_event_pairs:
            self._hb_app.app.add_listener(event_pair[0], event_pair[1])

    def stop_event_listener(self):
        for market in self._markets:
            for event_pair in self._market_event_pairs:
                market.remove_listener(event_pair[0], event_pair[1])
        for event_pair in self._app_event_pairs:
            self._hb_app.app.remove_listener(event_pair[0], event_pair[1])


class MQTTNotifier(NotifierBase):
    NOTIFY_URI = 'hbot/$UID/notify'

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node,
                 topic: str = '') -> None:
        super().__init__()
        if topic in (None, ''):
            topic = self.NOTIFY_URI.replace('$UID', hb_app.uid())
        self._topic = topic
        self._node = mqtt_node
        self._hb_app = hb_app
        self.notify_pub = self._node.create_publisher(topic=self._topic,
                                                      msg_type=NotifyMessage)

    def add_msg_to_queue(self, msg: str):
        self.notify_pub.publish(NotifyMessage(msg=msg))

    def start(self):
        pass

    def stop(self):
        pass


class MQTTGateway(Node):
    NODE_NAME = 'hbot.$UID'
    HEARTBEAT_URI = 'hbot/$UID/hb'

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global mqtts_logger
        if mqtts_logger is None:
            mqtts_logger = HummingbotLogger(__name__)
        return mqtts_logger

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 *args, **kwargs):
        self.hb_app = hb_app
        self.HEARTBEAT_URI = self.HEARTBEAT_URI.replace('$UID', hb_app.uid())

        self._params = self._create_mqtt_params_from_conf()

        super().__init__(
            node_name=self.NODE_NAME.replace('$UID', hb_app.uid()),
            connection_params=self._params,
            heartbeat_uri=self.HEARTBEAT_URI,
            *args,
            **kwargs
        )

    def _init_features(self):
        if self.hb_app.client_config_map.mqtt_broker.mqtt_commands:
            self._commands = MQTTCommands(self.hb_app, self)
        if self.hb_app.client_config_map.mqtt_broker.mqtt_notifier:
            self._notifier = MQTTNotifier(self.hb_app, self)
            self.hb_app.notifiers.append(self._notifier)
        if self.hb_app.client_config_map.mqtt_broker.mqtt_events:
            self.mqtt_event_forwarder = MQTTEventForwarder(self.hb_app, self)

    def _create_mqtt_params_from_conf(self):
        host = self.hb_app.client_config_map.mqtt_broker.mqtt_host
        port = self.hb_app.client_config_map.mqtt_broker.mqtt_port
        username = self.hb_app.client_config_map.mqtt_broker.mqtt_username
        password = self.hb_app.client_config_map.mqtt_broker.mqtt_password
        conn_params = MQTTConnectionParameters(
            host=host,
            port=int(port),
            username=username,
            password=password
        )
        return conn_params

    def run(self):
        self._init_features()
        super().run()


class LogMessage(PubSubMessage):
    timestamp: float = 0.0
    msg: str = ''
    level_no: int = 0
    level_name: str = ''
    logger_name: str = ''


class MQTTHandler(Handler):
    MQTT_URI = 'hbot/$UID/log'

    def __init__(self,
                 mqtt_params: MQTTConnectionParameters = None,
                 mqtt_topic: str = ''):
        super().__init__()

    def emit(self, record: LogRecord):
        msg_str = self.format(record)
        msg = LogMessage(
            timestamp=time.time(),
            msg=msg_str,
            level_no=record.levelno,
            level_name=record.levelname,
            logger_name=record.name

        )
        return msg
