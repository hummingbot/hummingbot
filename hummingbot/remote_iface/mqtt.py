#!/usr/bin/env python

import asyncio
import logging
import threading
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import TYPE_CHECKING, List, Tuple

from hummingbot import get_logging_conf
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:  # pragma: no cover
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401
    from hummingbot.core.event.event_listener import EventListener  # noqa: F401

from commlib.node import Node
from commlib.transports.mqtt import ConnectionParameters as MQTTConnectionParameters

from hummingbot.core.event import events
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.pubsub import PubSub
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.remote_iface.messages import (
    MQTT_STATUS_CODE,
    BalanceLimitCommandMessage,
    BalancePaperCommandMessage,
    CommandShortcutMessage,
    ConfigCommandMessage,
    EventMessage,
    HistoryCommandMessage,
    ImportCommandMessage,
    LogMessage,
    NotifyMessage,
    StartCommandMessage,
    StatusCommandMessage,
    StopCommandMessage,
)

mqtts_logger: HummingbotLogger = None


class MQTTCommands:
    START_URI = '/$instance_id/start'
    STOP_URI = '/$instance_id/stop'
    CONFIG_URI = '/$instance_id/config'
    IMPORT_URI = '/$instance_id/import'
    STATUS_URI = '/$instance_id/status'
    HISTORY_URI = '/$instance_id/history'
    BALANCE_LIMIT_URI = '/$instance_id/balance/limit'
    BALANCE_PAPER_URI = '/$instance_id/balance/paper'
    COMMAND_SHORTCUT_URI = '/$instance_id/command_shortcuts'

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node):
        self._hb_app = hb_app
        self._mqtt_node = mqtt_node
        self.logger = self._hb_app.logger
        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        self.START_URI = self.START_URI.replace('$instance_id', hb_app.instance_id)
        self.START_URI = f'{self._mqtt_node.namespace}{self.START_URI}'
        self.STOP_URI = self.STOP_URI.replace('$instance_id', hb_app.instance_id)
        self.STOP_URI = f'{self._mqtt_node.namespace}{self.STOP_URI}'
        self.CONFIG_URI = self.CONFIG_URI.replace('$instance_id', hb_app.instance_id)
        self.CONFIG_URI = f'{self._mqtt_node.namespace}{self.CONFIG_URI}'
        self.IMPORT_URI = self.IMPORT_URI.replace('$instance_id', hb_app.instance_id)
        self.IMPORT_URI = f'{self._mqtt_node.namespace}{self.IMPORT_URI}'
        self.STATUS_URI = self.STATUS_URI.replace('$instance_id', hb_app.instance_id)
        self.STATUS_URI = f'{self._mqtt_node.namespace}{self.STATUS_URI}'
        self.HISTORY_URI = self.HISTORY_URI.replace('$instance_id', hb_app.instance_id)
        self.HISTORY_URI = f'{self._mqtt_node.namespace}{self.HISTORY_URI}'
        self.BALANCE_LIMIT_URI = self.BALANCE_LIMIT_URI.replace(
            '$instance_id', hb_app.instance_id)
        self.BALANCE_LIMIT_URI = f'{self._mqtt_node.namespace}{self.BALANCE_LIMIT_URI}'
        self.BALANCE_PAPER_URI = self.BALANCE_PAPER_URI.replace(
            '$instance_id', hb_app.instance_id)
        self.BALANCE_PAPER_URI = f'{self._mqtt_node.namespace}{self.BALANCE_PAPER_URI}'
        self.COMMAND_SHORTCUT_URI = self.COMMAND_SHORTCUT_URI.replace('$instance_id', hb_app.instance_id)
        self.COMMAND_SHORTCUT_URI = f'{self._mqtt_node.namespace}{self.COMMAND_SHORTCUT_URI}'
        self._init_commands()

    def _init_commands(self):
        self._mqtt_node.create_rpc(
            rpc_name=self.START_URI,
            msg_type=StartCommandMessage,
            on_request=self._on_cmd_start
        )
        self._mqtt_node.create_rpc(
            rpc_name=self.STOP_URI,
            msg_type=StopCommandMessage,
            on_request=self._on_cmd_stop
        )
        self._mqtt_node.create_rpc(
            rpc_name=self.CONFIG_URI,
            msg_type=ConfigCommandMessage,
            on_request=self._on_cmd_config
        )
        self._mqtt_node.create_rpc(
            rpc_name=self.IMPORT_URI,
            msg_type=ImportCommandMessage,
            on_request=self._on_cmd_import
        )
        self._mqtt_node.create_rpc(
            rpc_name=self.STATUS_URI,
            msg_type=StatusCommandMessage,
            on_request=self._on_cmd_status
        )
        self._mqtt_node.create_rpc(
            rpc_name=self.HISTORY_URI,
            msg_type=HistoryCommandMessage,
            on_request=self._on_cmd_history
        )
        self._mqtt_node.create_rpc(
            rpc_name=self.BALANCE_LIMIT_URI,
            msg_type=BalanceLimitCommandMessage,
            on_request=self._on_cmd_balance_limit
        )
        self._mqtt_node.create_rpc(
            rpc_name=self.BALANCE_PAPER_URI,
            msg_type=BalancePaperCommandMessage,
            on_request=self._on_cmd_balance_paper
        )
        self._mqtt_node.create_rpc(
            rpc_name=self.COMMAND_SHORTCUT_URI,
            msg_type=CommandShortcutMessage,
            on_request=self._on_cmd_command_shortcut
        )

    def _on_cmd_start(self, msg: StartCommandMessage.Request):
        response = StartCommandMessage.Response()
        try:
            self._hb_app.start(
                log_level=msg.log_level,
                restore=msg.restore,
                script=msg.script,
                is_quickstart=msg.is_quickstart
            )
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_stop(self, msg: StopCommandMessage.Request):
        response = StopCommandMessage.Response()
        try:
            self._hb_app.stop(
                skip_order_cancellation=msg.skip_order_cancellation
            )
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_config(self, msg: ConfigCommandMessage.Request):
        response = ConfigCommandMessage.Response()
        try:
            if len(msg.params) == 0:
                self._hb_app.config()
            else:
                for param in msg.params:
                    if param[0] in self._hb_app.configurable_keys():
                        self._hb_app.config(param[0], param[1])
                        response.changes.append((param[0], param[1]))
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_import(self, msg: ImportCommandMessage.Request):
        response = ImportCommandMessage.Response()
        strategy_name = msg.strategy
        if strategy_name is not None:
            strategy_file_name = f'{strategy_name}.yml'
            try:
                self._hb_app.import_command(strategy_file_name)
            except Exception as e:
                self._hb_app.notify(str(e))
                response.status = MQTT_STATUS_CODE.ERROR
                response.msg = str(e)
        return response

    def _on_cmd_status(self, msg: StatusCommandMessage.Request):
        response = StatusCommandMessage.Response()
        try:
            _status = self._ev_loop.run_until_complete(self._hb_app.strategy_status()).strip()
            response.data = _status
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_history(self, msg: HistoryCommandMessage.Request):
        response = HistoryCommandMessage.Response()
        try:
            self._hb_app.history(msg.days, msg.verbose, msg.precision)
            trades = self._hb_app.get_history_trades_json(msg.days)
            if trades:
                response.trades = trades
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_balance_limit(self, msg: BalanceLimitCommandMessage.Request):
        response = BalanceLimitCommandMessage.Response()
        try:
            data = self._hb_app.balance(
                'limit',
                [msg.exchange, msg.asset, msg.amount]
            )
            response.data = data
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_balance_paper(self, msg: BalancePaperCommandMessage.Request):
        response = BalancePaperCommandMessage.Response()
        try:
            data = self._hb_app.balance(
                'paper',
                [msg.asset, msg.amount]
            )
            response.data = data
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_command_shortcut(self, msg: CommandShortcutMessage.Request):
        response = CommandShortcutMessage.Response()
        try:
            for param in msg.params:
                response.success.append(self._hb_app._handle_shortcut(param))
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response


class MQTTEventForwarder:
    EVENT_URI = '/$instance_id/events'

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global mqtts_logger
        if mqtts_logger is None:
            mqtts_logger = HummingbotLogger("MQTTGateway")
        return mqtts_logger

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node):

        if threading.current_thread() != threading.main_thread():  # pragma: no cover
            raise EnvironmentError(
                "MQTTEventForwarder can only be initialized from the main thread."
            )

        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._hb_app = hb_app
        self._mqtt_node = mqtt_node
        self._markets: List[ConnectorBase] = list(self._hb_app.markets.values())

        self.EVENT_URI = self.EVENT_URI.replace('$instance_id', self._hb_app.instance_id)
        self.EVENT_URI = f'{self._mqtt_node.namespace}{self.EVENT_URI}'

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

        self.event_fw_pub = self._mqtt_node.create_publisher(
            topic=self.EVENT_URI, msg_type=EventMessage
        )
        self.start_event_listener()

    def _send_mqtt_event(self, event_tag: int, pubsub: PubSub, event):
        if threading.current_thread() != threading.main_thread():  # pragma: no cover
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
    NOTIFY_URI = '/$instance_id/notify'

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node,
                 topic: str = '') -> None:
        super().__init__()
        self._mqtt_node = mqtt_node
        self._hb_app = hb_app
        if topic in (None, ''):
            self.NOTIFY_URI = self.NOTIFY_URI.replace('$instance_id', hb_app.instance_id)
            self.NOTIFY_URI = f'{self._mqtt_node.namespace}{self.NOTIFY_URI}'
        self.notify_pub = self._mqtt_node.create_publisher(topic=self.NOTIFY_URI,
                                                           msg_type=NotifyMessage)

    def add_msg_to_queue(self, msg: str):
        self.notify_pub.publish(NotifyMessage(msg=msg))

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class MQTTGateway(Node):
    NODE_NAME = 'hbot.$instance_id'
    HEARTBEAT_URI = '/$instance_id/hb'

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global mqtts_logger
        if mqtts_logger is None:
            mqtts_logger = HummingbotLogger("MQTTGateway")
        return mqtts_logger

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 *args, **kwargs):
        self._notifier: MQTTNotifier = None
        self._event_forwarder: MQTTEventForwarder = None
        self._commands: MQTTCommands = None
        self._logh: MQTTLogHandler = None
        self._hb_app = hb_app
        self._params = self._create_mqtt_params_from_conf()
        self.namespace = self._hb_app.client_config_map.mqtt_bridge.mqtt_namespace
        if self.namespace[-1] in ('/', '.'):
            self.namespace = self.namespace[:-1]
        self.HEARTBEAT_URI = self.HEARTBEAT_URI.replace('$instance_id', hb_app.instance_id)
        self.HEARTBEAT_URI = f'{self.namespace}{self.HEARTBEAT_URI}'

        super().__init__(
            node_name=self.NODE_NAME.replace('$instance_id', hb_app.instance_id),
            connection_params=self._params,
            heartbeat_uri=self.HEARTBEAT_URI,
            debug=True,
            *args,
            **kwargs
        )

    def stop_logger(self):
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        log_conf = get_logging_conf()
        if 'loggers' not in log_conf:
            return
        logs = [key for key, val in log_conf.get('loggers').items()]
        for logger in loggers:
            if 'hummingbot' in logger.name:
                for log in logs:
                    if log in logger.name:
                        self.remove_log_handler(logger)

    def start_logger(self):
        self._logh = MQTTLogHandler(self._hb_app, self)
        self.patch_loggers()

    def patch_loggers(self):
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        log_conf = get_logging_conf()

        if 'root' not in log_conf:
            return
        if log_conf.get('root').get('mqtt'):
            self.add_log_handler(self._get_root_logger())

        if 'loggers' not in log_conf:
            return
        log_conf_names = [key for key, val in log_conf.get('loggers').items()]
        loggers_filtered = [logger for logger in loggers if logger.name in log_conf_names]
        loggers_filtered = [logger for logger in loggers_filtered if
                            log_conf.get('loggers').get(logger.name).get('mqtt', False)]

        for logger in loggers_filtered:
            self.remove_log_handler(logger)
            self.add_log_handler(logger)

    def _get_root_logger(self):
        return logging.getLogger()

    def remove_log_handler(self, logger):
        logger.removeHandler(self._logh)

    def add_log_handler(self, logger):
        logger.addHandler(self._logh)

    def add_log_handler_to_strategy(self):
        loggers = [logging.getLogger(name) for name in
                   logging.root.manager.loggerDict if 'strategy' in name]
        self._hb_app.logger().info(loggers)
        for logger in loggers:
            self.add_log_handler(logger)

    def start_notifier(self):
        if self._hb_app.client_config_map.mqtt_bridge.mqtt_notifier:
            self.logger().info('Starting MQTT Notifier')
            self._notifier = MQTTNotifier(self._hb_app, self)
            self._hb_app.notifiers.append(self._notifier)

    def start_commands(self):
        if self._hb_app.client_config_map.mqtt_bridge.mqtt_commands:
            self.logger().info('Starting MQTT Remote Commands')
            self._commands = MQTTCommands(self._hb_app, self)

    def start_event_fw(self):
        if self._hb_app.client_config_map.mqtt_bridge.mqtt_events:
            self.logger().info('Starting MQTT Remote Events')
            self._event_forwarder = MQTTEventForwarder(self._hb_app, self)

    def _create_mqtt_params_from_conf(self):
        host = self._hb_app.client_config_map.mqtt_bridge.mqtt_host
        port = self._hb_app.client_config_map.mqtt_bridge.mqtt_port
        username = self._hb_app.client_config_map.mqtt_bridge.mqtt_username
        password = self._hb_app.client_config_map.mqtt_bridge.mqtt_password
        ssl = self._hb_app.client_config_map.mqtt_bridge.mqtt_ssl
        conn_params = MQTTConnectionParameters(
            host=host,
            port=int(port),
            username=username,
            password=password,
            ssl=ssl
        )
        return conn_params

    def check_health(self) -> bool:
        for c in self._subscribers:
            if not c._transport.is_connected:
                return False
        for c in self._publishers:
            if not c._transport.is_connected:
                return False
        for c in self._rpc_services:
            if not c._transport.is_connected:
                return False
        for c in self._rpc_clients:
            if not c._transport.is_connected:
                return False
        return True

    def start(self) -> None:
        self.start_logger()
        self.start_notifier()
        self.start_commands()
        self.start_event_fw()
        self.run()

    def stop(self):
        super().stop()
        self.stop_logger()


class MQTTLogHandler(logging.Handler):
    MQTT_URI = '/$instance_id/log'

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 mqtt_node: Node,
                 mqtt_topic: str = ''):
        self._hb_app = hb_app
        self._mqtt_node = mqtt_node
        if mqtt_topic in ('', None):
            self.MQTT_URI = self.MQTT_URI.replace('$instance_id',
                                                  self._hb_app.instance_id)
            self.MQTT_URI = f'{self._mqtt_node.namespace}{self.MQTT_URI}'
        super().__init__()
        self.log_pub = self._mqtt_node.create_publisher(topic=self.MQTT_URI,
                                                        msg_type=LogMessage)

    def emit(self, record: logging.LogRecord):
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
