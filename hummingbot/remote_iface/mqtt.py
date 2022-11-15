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


def get_timestamp(days_ago: float = 0.) -> float:
    return time.time() - (60. * 60. * 24. * days_ago)


class NotifyMessage(PubSubMessage):
    seq: int = 0
    timestamp: int = -1
    msg: str = ''


class EventMessage(PubSubMessage):
    timestamp: int = -1
    type: str = 'Unknown'
    data: dict = {}


class MQTTCommands:
    START_URI = 'hbot/$UID/start'
    STOP_URI = 'hbot/$UID/stop'
    RESTART_URI = 'hbot/$UID/restart'
    CONFIG_URI = 'hbot/$UID/config'
    IMPORT_URI = 'hbot/$UID/import'
    STATUS_URI = 'hbot/$UID/status'
    HISTORY_URI = 'hbot/$UID/history'
    BALANCE_LIMIT_URI = 'hbot/$UID/balance_limit'

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node):
        self._hb_app = hb_app
        self.node = mqtt_node
        self.logger = self._hb_app.logger

        self.START_URI = self.START_URI.replace('$UID', hb_app.uid)
        self.STOP_URI = self.STOP_URI.replace('$UID', hb_app.uid)
        self.RESTART_URI = self.RESTART_URI.replace('$UID', hb_app.uid)
        self.CONFIG_URI = self.CONFIG_URI.replace('$UID', hb_app.uid)
        self.IMPORT_URI = self.IMPORT_URI.replace('$UID', hb_app.uid)
        self.STATUS_URI = self.STATUS_URI.replace('$UID', hb_app.uid)
        self.HISTORY_URI = self.HISTORY_URI.replace('$UID', hb_app.uid)
        self.BALANCE_LIMIT_URI = self.BALANCE_LIMIT_URI.replace('$UID', hb_app.uid)

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
        self.node.create_rpc(
            rpc_name=self.HISTORY_URI,
            on_request=self._on_cmd_history
        )
        self.node.create_rpc(
            rpc_name=self.BALANCE_LIMIT_URI,
            on_request=self._on_cmd_balancelimit
        )

    def _on_cmd_start(self, msg):
        self._hb_app.start()
        return {}

    def _on_cmd_stop(self, msg):
        self._hb_app.stop()
        return {}

    def _on_cmd_restart(self, msg):
        self._hb_app.restart()
        return {}

    def _on_cmd_config(self, msg):
        if len(msg) == 0:
            self._hb_app.config()
        else:
            for key, val in msg.items():
                if key in self._hb_app.config_able_keys():
                    self._hb_app.config(key, val)
        response = self._hb_app.get_config()
        return response

    def _on_cmd_import(self, msg):
        _response = {
            'status': 200,
            'msg': ''
        }
        strategy_name = msg.get("strategy")
        if strategy_name is not None:
            strategy_file_name = f'{strategy_name}.yml'
            try:
                self._hb_app.import_command(strategy_file_name)
            except Exception as e:
                self._hb_app.notify(str(e))
                _response['status'] = 400
                _response['msg'] = str(e)
        return _response

    def _on_cmd_status(self, msg):
        _response = {
            'status': 200,
            'msg': '',
            'data': {}
        }
        try:
            _status = asyncio.run(self._hb_app.strategy_status()).strip()
            _response['data'] = _status
        except Exception as e:
            _response['status'] = 400
            _response['msg'] = str(e)
        return _response

    def _on_cmd_history(self, msg):
        _response = {
            'status': 200,
            'msg': '',
            'trades': []
        }
        try:
            _days = msg.get('days', 0)
            _verbose = msg.get('verbose')
            _precision = msg.get('precision')
            self._hb_app.history(_days, _verbose, _precision)
            _trades = self._hb_app.get_history_trades(_days)
            _response['trades'] = _trades.to_dict()
        except Exception as e:
            _response['status'] = 400
            _response['msg'] = str(e)
        return _response

    def _on_cmd_balancelimit(self, msg):
        _response = {
            'status': 200,
            'msg': ''
        }
        try:
            _exchange = msg.get("exchange")
            _asset = msg.get("asset")
            _amount = msg.get("amount")
            _response['msg'] = self._hb_app.balance('limit', [_exchange, _asset,
                                                              _amount])
        except Exception as e:
            _response['msg'] = str(e)
            _response['status'] = 400
        return _response

    def _on_get_market_data(self, msg):
        _response = {
            'status': 200,
            'msg': '',
            'market_data': {}
        }
        try:
            market_data = self._hb_app.strategy.market_status_df()
            _response['market_data'] = market_data
        except Exception as e:
            _response['msg'] = str(e)
            _response['status'] = 400
        return _response


class MQTTEventForwarder:
    EVENT_URI = 'hbot/$UID/events'

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global mqtts_logger
        if mqtts_logger is None:
            mqtts_logger = HummingbotLogger("MQTTGateway")
        return mqtts_logger

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

        self._topic = self.EVENT_URI.replace('$UID', self._hb_app.uid)

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
            (events.MarketEvent.FundingPaymentCompleted, self._mqtt_fowarder),
            (events.MarketEvent.RangePositionLiquidityAdded, self._mqtt_fowarder),
            (events.MarketEvent.RangePositionLiquidityRemoved, self._mqtt_fowarder),
            (events.MarketEvent.RangePositionUpdate, self._mqtt_fowarder),
            (events.MarketEvent.RangePositionUpdateFailure, self._mqtt_fowarder),
            (events.MarketEvent.RangePositionFeeCollected, self._mqtt_fowarder),
            (events.MarketEvent.RangePositionClosed, self._mqtt_fowarder),
        ]
        self._app_event_pairs: List[Tuple[int, EventListener]] = []

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
                events.MarketEvent.FundingPaymentCompleted.value: "FundingPaymentCompleted",
                events.MarketEvent.RangePositionLiquidityAdded.value: "RangePositionLiquidityAdded",
                events.MarketEvent.RangePositionLiquidityRemoved.value: "RangePositionLiquidityRemoved",
                events.MarketEvent.RangePositionUpdate.value: "RangePositionUpdate",
                events.MarketEvent.RangePositionUpdateFailure.value: "RangePositionUpdateFailure",
                events.MarketEvent.RangePositionFeeCollected.value: "RangePositionFeeCollected",
                events.MarketEvent.RangePositionClosed.value: "RangePositionClosed",
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
                self.logger().info(
                    f'Created MQTT bridge for event: {event_pair[0]}, {event_pair[1]}'
                )
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
            topic = self.NOTIFY_URI.replace('$UID', hb_app.uid)
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
            mqtts_logger = HummingbotLogger("MQTTGateway")
        return mqtts_logger

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 *args, **kwargs):
        self._hb_app = hb_app
        self.HEARTBEAT_URI = self.HEARTBEAT_URI.replace('$UID', hb_app.uid)

        self._params = self._create_mqtt_params_from_conf()

        super().__init__(
            node_name=self.NODE_NAME.replace('$UID', hb_app.uid),
            connection_params=self._params,
            heartbeat_uri=self.HEARTBEAT_URI,
            debug=True,
            *args,
            **kwargs
        )

    def patch_logger_class(self):
        HummingbotLogger._mqtt_handler = MQTTLogHandler(self._hb_app, self)

    def start_notifier(self):
        if self._hb_app.client_config_map.mqtt_broker.mqtt_notifier:
            self.logger().info('Starting MQTT Notifier')
            self._notifier = MQTTNotifier(self._hb_app, self)
            self._hb_app.notifiers.append(self._notifier)

    def start_commands(self):
        if self._hb_app.client_config_map.mqtt_broker.mqtt_commands:
            self.logger().info('Starting MQTT Remote Commands')
            self._commands = MQTTCommands(self._hb_app, self)

    def start_event_fw(self):
        if self._hb_app.client_config_map.mqtt_broker.mqtt_events:
            self.logger().info('Starting MQTT Remote Events')
            self.mqtt_event_forwarder = MQTTEventForwarder(self._hb_app, self)

    def _create_mqtt_params_from_conf(self):
        host = self._hb_app.client_config_map.mqtt_broker.mqtt_host
        port = self._hb_app.client_config_map.mqtt_broker.mqtt_port
        username = self._hb_app.client_config_map.mqtt_broker.mqtt_username
        password = self._hb_app.client_config_map.mqtt_broker.mqtt_password
        ssl = self._hb_app.client_config_map.mqtt_broker.mqtt_ssl
        conn_params = MQTTConnectionParameters(
            host=host,
            port=int(port),
            username=username,
            password=password,
            ssl=ssl
        )
        return conn_params


class LogMessage(PubSubMessage):
    timestamp: float = 0.0
    msg: str = ''
    level_no: int = 0
    level_name: str = ''
    logger_name: str = ''


class MQTTLogHandler(Handler):
    MQTT_URI = 'hbot/$UID/log'

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node,
                 mqtt_topic: str = ''):
        self._hb_app = hb_app
        self._node = mqtt_node
        if mqtt_topic in ('', None):
            mqtt_topic = self.MQTT_URI.replace('$UID', self._hb_app.uid)
        self._topic = mqtt_topic
        super().__init__()
        self.log_pub = self._node.create_publisher(topic=self._topic,
                                                   msg_type=LogMessage)

    def emit(self, record: LogRecord):
        msg_str = self.format(record)
        msg = LogMessage(
            timestamp=time.time(),
            msg=msg_str,
            level_no=record.levelno,
            level_name=record.levelname,
            logger_name=record.name

        )
        self.log_pub.publish(msg)
        return msg
