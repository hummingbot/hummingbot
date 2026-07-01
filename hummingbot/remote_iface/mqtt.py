#!/usr/bin/env python

import asyncio
import functools
import logging
import re
import threading
import time
from collections import deque
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import aiomqtt
import ujson

from hummingbot import get_logging_conf
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:  # pragma: no cover
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401
    from hummingbot.core.event.event_listener import EventListener  # noqa: F401

from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, DeductedFromReturnsTradeFee
from hummingbot.core.event import events
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.pubsub import PubSub
from hummingbot.core.utils.async_utils import call_sync, safe_ensure_future
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.remote_iface.messages import (
    MQTT_STATUS_CODE,
    BalanceLimitCommandMessage,
    BalancePaperCommandMessage,
    ConfigCommandMessage,
    ExternalEventMessage,
    HistoryCommandMessage,
    ImportCommandMessage,
    InternalEventMessage,
    LogMessage,
    NotifyMessage,
    StartCommandMessage,
    StatusCommandMessage,
    StatusUpdateMessage,
    StopCommandMessage,
)

mqtts_logger: HummingbotLogger = None


def _make_primitive(val: Any) -> Any:
    """Convert a value into JSON-serializable primitives.

    Faithful port of ``commlib.serializer.JSONSerializer.make_primitive_value``
    so the wire format is byte-compatible after dropping the commlib dependency
    (Decimals/floats -> float, non-digit/unknown values -> str, etc.).
    """
    if isinstance(val, dict):
        return {k: _make_primitive(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [_make_primitive(v) for v in val]
    elif isinstance(val, (Decimal, float)):
        return float(val)
    elif isinstance(val, int) and str(val).isdigit():
        return int(val)
    elif isinstance(val, bool):
        return bool(val)
    elif val is None:
        return None
    else:
        return str(val)


def mqtt_serialize(payload: Dict[str, Any]) -> str:
    """Serialize an MQTT payload exactly as commlib did (ujson + primitives)."""
    return ujson.dumps(_make_primitive(payload))


class CommandTopicSpecs:
    START: str = '/start'
    STOP: str = '/stop'
    CONFIG: str = '/config'
    IMPORT: str = '/import'
    STATUS: str = '/status'
    HISTORY: str = '/history'
    BALANCE_LIMIT: str = '/balance/limit'
    BALANCE_PAPER: str = '/balance/paper'


class TopicSpecs:
    PREFIX: str = '{namespace}/{instance_id}'
    COMMANDS: CommandTopicSpecs = CommandTopicSpecs()
    LOGS: str = '/log'
    INTERNAL_EVENTS: str = '/events'
    NOTIFICATIONS: str = '/notify'
    STATUS_UPDATES: str = '/status_updates'
    HEARTBEATS: str = '/hb'
    # MQTT multi-level wildcard ('#'); commlib used '*' and converted it internally.
    EXTERNAL_EVENTS: str = '/external/event/#'


class MQTTCommands:
    def __init__(self,
                 hb_app: "HummingbotApplication",
                 gateway: "MQTTGateway"):
        if threading.current_thread() != threading.main_thread():  # pragma: no cover
            raise EnvironmentError(
                "MQTTCommands can only be initialized from the main thread."
            )
        self._hb_app = hb_app
        self._gateway = gateway
        self.logger = self._hb_app.logger
        self._ev_loop: asyncio.AbstractEventLoop = self._hb_app.ev_loop

        topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._hb_app.instance_id
        )
        self._start_uri = f'{topic_prefix}{TopicSpecs.COMMANDS.START}'
        self._stop_uri = f'{topic_prefix}{TopicSpecs.COMMANDS.STOP}'
        self._config_uri = f'{topic_prefix}{TopicSpecs.COMMANDS.CONFIG}'
        self._import_uri = f'{topic_prefix}{TopicSpecs.COMMANDS.IMPORT}'
        self._status_uri = f'{topic_prefix}{TopicSpecs.COMMANDS.STATUS}'
        self._history_uri = f'{topic_prefix}{TopicSpecs.COMMANDS.HISTORY}'
        self._balance_limit_uri = f'{topic_prefix}{TopicSpecs.COMMANDS.BALANCE_LIMIT}'
        self._balance_paper_uri = f'{topic_prefix}{TopicSpecs.COMMANDS.BALANCE_PAPER}'

        self._init_commands()

    def _init_commands(self):
        self._gateway.register_command(
            self._start_uri, StartCommandMessage, self._on_cmd_start)
        self._gateway.register_command(
            self._stop_uri, StopCommandMessage, self._on_cmd_stop)
        self._gateway.register_command(
            self._config_uri, ConfigCommandMessage, self._on_cmd_config)
        self._gateway.register_command(
            self._import_uri, ImportCommandMessage, self._on_cmd_import)
        self._gateway.register_command(
            self._status_uri, StatusCommandMessage, self._on_cmd_status)
        self._gateway.register_command(
            self._history_uri, HistoryCommandMessage, self._on_cmd_history)
        self._gateway.register_command(
            self._balance_limit_uri, BalanceLimitCommandMessage, self._on_cmd_balance_limit)
        self._gateway.register_command(
            self._balance_paper_uri, BalancePaperCommandMessage, self._on_cmd_balance_paper)

    def _on_cmd_start(self, msg: StartCommandMessage.Request):
        response = StartCommandMessage.Response()
        timeout = 30
        try:
            if self._hb_app.strategy_name is None and msg.script is None:
                raise Exception('Strategy check: Please import or create a strategy.')
            if self._hb_app.strategy is not None:
                raise Exception('The bot is already running - please run "stop" first')
            if msg.async_backend:
                self._hb_app.start(
                    log_level=msg.log_level,
                    script=msg.script,
                    conf=msg.conf,
                    is_quickstart=msg.is_quickstart
                )
            else:
                res = call_sync(
                    self._hb_app.start_check(
                        log_level=msg.log_level,
                        script=msg.script,
                        conf=msg.conf,
                        is_quickstart=msg.is_quickstart
                    ),
                    loop=self._ev_loop,
                    timeout=timeout
                )
                response.msg = res if res is not None else ''
        except asyncio.exceptions.TimeoutError:
            response.msg = f'Hummingbot start command timed out after {timeout} seconds'
            response.status = MQTT_STATUS_CODE.ERROR
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_stop(self, msg: StopCommandMessage.Request):
        response = StopCommandMessage.Response()
        timeout = 30
        try:
            if msg.async_backend:
                self._hb_app.stop(
                    skip_order_cancellation=msg.skip_order_cancellation
                )
            else:
                res = call_sync(
                    self._hb_app.stop_loop(),
                    loop=self._ev_loop,
                    timeout=timeout
                )
                response.msg = res if res is not None else ''
        except asyncio.exceptions.TimeoutError:
            response.msg = f'Hummingbot start command timed out after {timeout} seconds'
            response.status = MQTT_STATUS_CODE.ERROR
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
                invalid_params = []
                for param in msg.params:
                    if param[0] in self._hb_app.configurable_keys():
                        self._ev_loop.call_soon_threadsafe(
                            self._hb_app.config,
                            param[0],
                            param[1]
                        )
                        response.changes.append((param[0], param[1]))
                    else:
                        invalid_params.append(param[0])
                if len(invalid_params):
                    raise ValueError(f'Invalid param key(s): {invalid_params}')
            strategy_config = {}
            client_config = {}
            if isinstance(self._hb_app.client_config_map, dict):  # pragma: no cover
                client_config = self._hb_app.client_config_map
                for key, value in client_config.items():
                    if isinstance(value, ConfigVar):
                        client_config[key] = value.value
                    else:
                        client_config[key] = value
            elif isinstance(self._hb_app.client_config_map,
                            ClientConfigAdapter):
                client_config = self._hb_app.client_config_map.dict()
            if isinstance(self._hb_app._strategy_config_map, dict):  # pragma: no cover
                for key, value in self._hb_app._strategy_config_map.items():
                    if isinstance(value, ConfigVar):
                        strategy_config[key] = value.value
                    else:
                        strategy_config[key] = value
            elif isinstance(self._hb_app._strategy_config_map,
                            ClientConfigAdapter):
                strategy_config = self._hb_app._strategy_config_map.dict()
            response.config = {
                "client": client_config,
                "strategy": strategy_config
            }
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
            self._hb_app.logger().error(e)
        return response

    def _on_cmd_import(self, msg: ImportCommandMessage.Request):
        response = ImportCommandMessage.Response()
        timeout = 30  # seconds
        strategy_name = msg.strategy
        if strategy_name in (None, ''):
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = 'Empty strategy_name given!'
            return response
        strategy_file_name = f'{strategy_name}.yml'
        try:
            res = call_sync(
                self._hb_app.import_config_file(strategy_file_name),
                loop=self._ev_loop,
                timeout=timeout
            )
            response.msg = res if res is not None else ''
        except asyncio.exceptions.TimeoutError:
            response.msg = f'Hummingbot import command timed out after {timeout} seconds'
            response.status = MQTT_STATUS_CODE.ERROR
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_status(self, msg: StatusCommandMessage.Request):
        response = StatusCommandMessage.Response()
        timeout = 30  # seconds
        try:
            if self._hb_app.strategy is None:
                response.status = MQTT_STATUS_CODE.ERROR
                response.msg = 'No strategy is currently running!'
                return response
            if msg.async_backend:
                self._ev_loop.call_soon_threadsafe(
                    self._hb_app.status
                )
            else:
                res = call_sync(
                    self._hb_app.strategy_status(),
                    loop=self._ev_loop,
                    timeout=timeout
                )
                response.msg = res if res is not None else ''
        except asyncio.exceptions.TimeoutError:
            response.msg = f'Hummingbot status command timed out after {timeout} seconds'
            response.status = MQTT_STATUS_CODE.ERROR
        except Exception as e:
            response.status = MQTT_STATUS_CODE.ERROR
            response.msg = str(e)
        return response

    def _on_cmd_history(self, msg: HistoryCommandMessage.Request):
        response = HistoryCommandMessage.Response()
        try:
            if msg.async_backend:
                self._hb_app.history(msg.days, msg.verbose, msg.precision)
            else:
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


class MQTTMarketEventForwarder:
    # Hoisted to a class attribute so it is built once, not per event (PERF-001).
    EVENT_TYPES: Dict[int, str] = {
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
        events.MarketEvent.RangePositionUpdateFailure.value: "RangePositionUpdateFailure",
    }

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global mqtts_logger
        if mqtts_logger is None:  # pragma: no cover
            mqtts_logger = HummingbotLogger(__name__)
        return mqtts_logger

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 gateway: "MQTTGateway"):
        if threading.current_thread() != threading.main_thread():  # pragma: no cover
            raise EnvironmentError(
                "MQTTMarketEventForwarder can only be initialized from the main thread."
            )
        self._hb_app = hb_app
        self._gateway = gateway
        self._ev_loop: asyncio.AbstractEventLoop = self._hb_app.ev_loop
        self._markets: List[ConnectorBase] = list(self._hb_app.markets.values())

        topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._hb_app.instance_id
        )
        self._topic = f'{topic_prefix}{TopicSpecs.INTERNAL_EVENTS}'

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
            (events.MarketEvent.RangePositionUpdateFailure, self._mqtt_fowarder),
        ]

        self._start_event_listeners()

    def _send_mqtt_event(self, event_tag: int, pubsub: PubSub, event):
        event_type = self.EVENT_TYPES.get(event_tag, "Unknown")

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

        event_data = self._make_event_payload(event_data)

        self._gateway.publish(
            self._topic,
            InternalEventMessage(
                timestamp=int(timestamp),
                type=event_type,
                data=event_data
            ).model_dump(),
            qos=0
        )

    def _make_event_payload(self, event_data):
        if 'type' in event_data:
            event_data['type'] = str(event_data['type'])
        if 'order_type' in event_data:
            event_data['order_type'] = str(event_data['order_type'])
        if 'trade_type' in event_data:
            event_data['trade_type'] = str(event_data['trade_type'])

        for key, val in event_data.items():
            event_data[key] = self._primitivize_event_value(val)
        return event_data

    def _primitivize_event_value(self, val):
        # Recurse through dicts and lists so nested Decimals/TradeFees are
        # converted too (CORR-007: the old version skipped list elements).
        if isinstance(val, dict):
            for key, inner in val.items():
                val[key] = self._primitivize_event_value(inner)
            return val
        elif isinstance(val, (list, tuple)):
            return [self._primitivize_event_value(v) for v in val]
        elif isinstance(val, Decimal):
            return float(val)
        elif isinstance(val, (DeductedFromReturnsTradeFee, AddedToCostTradeFee)):
            return self._primitivize_event_value(val.to_json())
        return val

    def _start_event_listeners(self):
        for market in self._markets:
            for event_pair in self._market_event_pairs:
                market.add_listener(event_pair[0], event_pair[1])
                self.logger().debug(
                    f'Created MQTT bridge for event: {event_pair[0]}, {event_pair[1]}'
                )

    def _stop_event_listeners(self):
        for market in self._markets:
            for event_pair in self._market_event_pairs:
                market.remove_listener(event_pair[0], event_pair[1])


class MQTTNotifier(NotifierBase):
    def __init__(self,
                 hb_app: "HummingbotApplication",
                 gateway: "MQTTGateway") -> None:
        super().__init__()
        self._gateway = gateway
        self._hb_app = hb_app
        self._ev_loop: asyncio.AbstractEventLoop = self._hb_app.ev_loop

        topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._hb_app.instance_id
        )
        self._topic = f'{topic_prefix}{TopicSpecs.NOTIFICATIONS}'

    def add_msg_to_queue(self, msg: str):
        self._gateway.publish(self._topic, NotifyMessage(msg=msg).model_dump(), qos=0)

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class MQTTStatusUpdates:
    def __init__(self,
                 hb_app: "HummingbotApplication",
                 gateway: "MQTTGateway") -> None:
        self._gateway = gateway
        self._hb_app = hb_app
        self._ev_loop: asyncio.AbstractEventLoop = self._hb_app.ev_loop

        topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._hb_app.instance_id
        )
        self._topic = f'{topic_prefix}{TopicSpecs.STATUS_UPDATES}'

    def add_msg_to_queue(self, msg: str, msg_type: str = 'hbapp'):
        self._gateway.publish(
            self._topic,
            StatusUpdateMessage(
                msg=msg,
                type=msg_type,
                timestamp=int(time.time() * 1e3)
            ).model_dump(),
            qos=0
        )

    def stop(self):
        return None


class MQTTGateway:
    NODE_NAME: str = 'hbot.$instance_id'
    _instance: Optional["MQTTGateway"] = None

    _QOS_COMMAND: int = 1
    _QOS_PUBSUB: int = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global mqtts_logger
        if mqtts_logger is None:  # pragma: no cover
            mqtts_logger = logging.getLogger(__name__)
        return mqtts_logger

    @classmethod
    def main(cls) -> "MQTTGateway":
        return cls._instance

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 *args, **kwargs
                 ):
        self._notifier: MQTTNotifier = None
        self._status_updates: MQTTStatusUpdates = None
        self._market_events: MQTTMarketEventForwarder = None
        self._commands: MQTTCommands = None
        self._logh: MQTTLogHandler = None
        self._external_events: MQTTExternalEvents = None
        self._hb_app: "HummingbotApplication" = hb_app
        self._ev_loop = self._hb_app.ev_loop

        self._heartbeat_interval: float = 10.0
        self._reconnect_interval: float = 5.0

        # aiomqtt connection state (all MQTT I/O lives on hb_app.ev_loop).
        self._client: Optional[aiomqtt.Client] = None
        self._connected: bool = False
        self._stopped: asyncio.Event = asyncio.Event()
        self._run_task: Optional[asyncio.Task] = None
        self._outgoing: "asyncio.Queue[Tuple[str, Dict[str, Any], int]]" = asyncio.Queue()
        # RPC handlers keyed by exact command topic.
        self._command_table: Dict[str, Tuple[Any, Callable]] = {}
        # Pub/Sub callbacks keyed by topic pattern (supports +/# wildcards).
        self._sub_callbacks: Dict[str, List[Callable[[str, Dict[str, Any]], None]]] = {}

        self._read_mqtt_params_from_conf()
        self.namespace = self._hb_app.client_config_map.mqtt_bridge.mqtt_namespace
        if self.namespace[-1] in ('/', '.'):
            self.namespace = self.namespace[:-1]

        self._topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self.namespace,
            instance_id=self._hb_app.instance_id
        )
        self._hb_topic = f'{self._topic_prefix}{TopicSpecs.HEARTBEATS}'
        self._node_name = self.NODE_NAME.replace('$instance_id', hb_app.instance_id)

        MQTTGateway._instance = self

    @property
    def health(self):
        return self._connected

    # ------------------------------------------------------------------ #
    # Connection params
    # ------------------------------------------------------------------ #
    def _read_mqtt_params_from_conf(self):
        cfg = self._hb_app.client_config_map.mqtt_bridge
        self._host = cfg.mqtt_host
        self._port = int(cfg.mqtt_port)
        self._username = cfg.mqtt_username
        self._password = cfg.mqtt_password
        self._use_ssl = bool(cfg.mqtt_ssl)

    def _create_client(self) -> aiomqtt.Client:
        # Seam: tests patch this to inject a fake client.
        tls_params = aiomqtt.TLSParameters() if self._use_ssl else None
        return aiomqtt.Client(
            hostname=self._host,
            port=self._port,
            username=self._username or None,
            password=self._password or None,
            identifier=self._node_name,
            tls_params=tls_params,
            keepalive=60,
        )

    # ------------------------------------------------------------------ #
    # Connection / reconnection loop
    # ------------------------------------------------------------------ #
    async def _run(self):
        while not self._stopped.is_set():
            tasks: List[asyncio.Task] = []
            try:
                async with self._create_client() as client:
                    self._client = client
                    self._connected = True
                    for topic, qos in self._desired_subscriptions().items():
                        await client.subscribe(topic, qos=qos)
                    self._hb_app.logger().debug(
                        f'Started Heartbeat Publisher <{self._hb_topic}>')
                    self.broadcast_status_update("online", msg_type="availability")
                    tasks = [
                        asyncio.create_task(self._drain_outgoing(client)),
                        asyncio.create_task(self._heartbeat_loop(client)),
                        asyncio.create_task(self._dispatch_incoming(client)),
                    ]
                    done, _ = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_EXCEPTION)
                    for t in done:
                        exc = t.exception()
                        if exc is not None:
                            raise exc
            except asyncio.CancelledError:
                raise
            except aiomqtt.MqttError as e:
                self._hb_app.logger().warning(
                    f'MQTT bridge disconnected: {e}. '
                    f'Reconnecting in {self._reconnect_interval}s.')
            except Exception as e:  # pragma: no cover
                self._hb_app.logger().error(
                    f'MQTT bridge error: {e}. '
                    f'Reconnecting in {self._reconnect_interval}s.', exc_info=True)
            finally:
                self._connected = False
                self._client = None
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            if self._stopped.is_set():
                break
            await asyncio.sleep(self._reconnect_interval)

    async def _drain_outgoing(self, client: aiomqtt.Client):
        while True:
            topic, payload, qos = await self._outgoing.get()
            # A publish failure bubbles up to _run to force a reconnect.
            await client.publish(topic, payload=mqtt_serialize(payload), qos=qos)

    async def _heartbeat_loop(self, client: aiomqtt.Client):
        while True:
            ts = int((time.time() + 0.5) * 1000000)
            await client.publish(
                self._hb_topic, payload=mqtt_serialize({"ts": ts}), qos=self._QOS_PUBSUB)
            await asyncio.sleep(self._heartbeat_interval)

    async def _dispatch_incoming(self, client: aiomqtt.Client):
        async for message in client.messages:
            topic = str(message.topic)
            try:
                payload = ujson.loads(message.payload)
            except (ValueError, TypeError):  # pragma: no cover
                continue
            if topic in self._command_table:
                self._ev_loop.run_in_executor(None, self._dispatch_rpc, topic, payload)
                continue
            for pattern in list(self._sub_callbacks.keys()):
                if self._topic_matches(pattern, topic):
                    for cb in list(self._sub_callbacks.get(pattern, [])):
                        try:
                            cb(topic, payload)
                        except Exception:  # pragma: no cover
                            self._hb_app.logger().error(
                                f'Error handling MQTT message on {topic}', exc_info=True)

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        p_parts = pattern.split('/')
        t_parts = topic.split('/')
        for i, seg in enumerate(p_parts):
            if seg == '#':
                return True
            if i >= len(t_parts):
                return False
            if seg != '+' and seg != t_parts[i]:
                return False
        return len(p_parts) == len(t_parts)

    # ------------------------------------------------------------------ #
    # RPC server
    # ------------------------------------------------------------------ #
    def _dispatch_rpc(self, topic: str, payload: Dict[str, Any]):
        # Runs in a thread-pool executor (not the event loop) because the
        # command handlers use call_sync(), which blocks on the loop.
        try:
            msg_type, handler = self._command_table[topic]
        except KeyError:  # pragma: no cover
            return
        header = payload.get("header", {}) if isinstance(payload, dict) else {}
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        reply_to = header.get("reply_to") if isinstance(header, dict) else None
        try:
            request = msg_type.Request(**(data or {}))
            response = handler(request)
        except Exception:  # pragma: no cover
            self._hb_app.logger().error(
                f'Error processing MQTT command {topic}', exc_info=True)
            return
        if reply_to:
            self.publish(reply_to, self._wrap_response(response), qos=self._QOS_COMMAND)

    def _wrap_response(self, response) -> Dict[str, Any]:
        # Mirrors commlib RPCService reply envelope byte-for-byte.
        return {
            "header": {
                "reply_to": "",
                "timestamp": int(time.time() * 1000),
                "content_type": "json",
                "encoding": "utf8",
                "agent": "commlib",
            },
            "data": response.model_dump(),
        }

    def register_command(self, topic: str, msg_type: Any, handler: Callable):
        self._command_table[topic] = (msg_type, handler)

    # ------------------------------------------------------------------ #
    # Publish / Subscribe primitives
    # ------------------------------------------------------------------ #
    def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0):
        """Enqueue a publish from any thread; drained on the event loop."""
        try:
            self._ev_loop.call_soon_threadsafe(
                self._outgoing.put_nowait, (topic, payload, qos))
        except RuntimeError:  # pragma: no cover - loop already closed
            pass

    def subscribe(self, topic: str, callback: Callable[[str, Dict[str, Any]], None]):
        self._sub_callbacks.setdefault(topic, [])
        self._sub_callbacks[topic].append(callback)
        self._schedule_subscribe(topic, self._QOS_PUBSUB)

    def unsubscribe(self,
                    topic: str,
                    callback: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        cbs = self._sub_callbacks.get(topic)
        if cbs is None:
            return
        if callback is None:
            cbs.clear()
        elif callback in cbs:
            cbs.remove(callback)
        if not cbs:
            self._sub_callbacks.pop(topic, None)
            self._schedule_unsubscribe(topic)

    def _desired_subscriptions(self) -> Dict[str, int]:
        subs = {topic: self._QOS_COMMAND for topic in self._command_table}
        for topic in self._sub_callbacks:
            subs.setdefault(topic, self._QOS_PUBSUB)
        return subs

    def _schedule_subscribe(self, topic: str, qos: int):
        if not self._connected or self._client is None:
            return
        client = self._client

        async def _do():
            try:
                await client.subscribe(topic, qos=qos)
            except aiomqtt.MqttError:  # pragma: no cover
                pass
        self._ev_loop.call_soon_threadsafe(
            lambda: safe_ensure_future(_do(), loop=self._ev_loop))

    def _schedule_unsubscribe(self, topic: str):
        if not self._connected or self._client is None:
            return
        client = self._client

        async def _do():
            try:
                await client.unsubscribe(topic)
            except aiomqtt.MqttError:  # pragma: no cover
                pass
        self._ev_loop.call_soon_threadsafe(
            lambda: safe_ensure_future(_do(), loop=self._ev_loop))

    # ------------------------------------------------------------------ #
    # Logging handler patching
    # ------------------------------------------------------------------ #
    def _safe_get_log_handlers(self, max_tries=3):  # pragma: no cover
        current_try = 0
        while current_try < max_tries:
            try:
                return list([logging.getLogger(name) for name in logging.root.manager.loggerDict])
            except RuntimeError:
                current_try += 1

        log_keys = logging.root.manager.loggerDict.keys()
        return list([logging.getLogger(name) for name in log_keys])

    def _remove_log_handlers(self):  # pragma: no cover
        loggers = self._safe_get_log_handlers()
        log_conf = get_logging_conf()

        if 'loggers' not in log_conf:
            return

        logs = [key for key, val in log_conf.get('loggers').items()]
        for logger in loggers:
            if 'hummingbot' in logger.name:
                for log in logs:
                    if log in logger.name:
                        self.remove_log_handler(logger)

        self._logh = None

    def _init_logger(self):
        self._logh = MQTTLogHandler(self._hb_app, self)
        self.patch_loggers()

    def patch_loggers(self):  # pragma: no cover
        loggers = self._safe_get_log_handlers()

        log_conf = get_logging_conf()
        if 'root' in log_conf:
            if log_conf.get('root').get('mqtt'):
                self.remove_log_handler(self._get_root_logger())
                self.add_log_handler(self._get_root_logger())

        if 'loggers' not in log_conf:
            return

        log_conf_names = [key for key, val in log_conf.get('loggers').items()]
        loggers_filtered = [logger for logger in loggers if
                            logger.name in log_conf_names]
        loggers_filtered = [logger for logger in loggers_filtered if
                            log_conf.get('loggers').get(logger.name).get('mqtt', False)]

        for logger in loggers_filtered:
            self.remove_log_handler(logger)
            self.add_log_handler(logger)

    def _get_root_logger(self):
        return logging.getLogger()

    def remove_log_handler(self, logger: HummingbotLogger):
        logger.removeHandler(self._logh)

    def add_log_handler(self, logger: HummingbotLogger):
        logger.addHandler(self._logh)

    # ------------------------------------------------------------------ #
    # Sub-component lifecycle
    # ------------------------------------------------------------------ #
    def _init_notifier(self):
        if self._hb_app.client_config_map.mqtt_bridge.mqtt_notifier:
            self._notifier = MQTTNotifier(self._hb_app, self)
            self._hb_app.notifiers.append(self._notifier)

    def _remove_notifier(self):
        self._hb_app.notifiers.remove(self._notifier) if self._notifier \
            in self._hb_app.notifiers else None

    def _init_status_updates(self):
        self._status_updates = MQTTStatusUpdates(self._hb_app, self)

    def _remove_status_updates(self):
        if self._status_updates is not None:
            self._status_updates.stop()
            self._status_updates = None

    def broadcast_status_update(self, *args, **kwargs):
        if self._status_updates is not None:
            self._status_updates.add_msg_to_queue(*args, **kwargs)

    def _init_commands(self):
        if self._hb_app.client_config_map.mqtt_bridge.mqtt_commands:
            self._commands = MQTTCommands(self._hb_app, self)

    def start_market_events_fw(self):
        # Must be called after loading the strategy.
        # Markets must be initialized via TradingCore before calling this method
        if self._hb_app.client_config_map.mqtt_bridge.mqtt_events:
            self._market_events = MQTTMarketEventForwarder(self._hb_app, self)

    def _remove_market_event_listeners(self):
        if self._market_events is not None:
            self._market_events._stop_event_listeners()

    def _init_external_events(self):
        if self._hb_app.client_config_map.mqtt_bridge.mqtt_external_events:
            self._external_events = MQTTExternalEvents(self._hb_app, self)

    def add_external_event_listener(self,
                                    event_name: str,
                                    callback: Callable[[ExternalEventMessage, str], None]):
        if event_name == '*':
            self._external_events.add_global_listener(callback)
        else:
            self._external_events.add_listener(event_name, callback)

    def remove_external_event_listener(self,
                                       event_name: str,
                                       callback: Callable[[ExternalEventMessage, str], None]):
        if event_name == '*':
            self._external_events.remove_global_listener(callback)
        else:
            self._external_events.remove_listener(event_name, callback)

    # ------------------------------------------------------------------ #
    # Start / Stop
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self._stopped.clear()
        self._init_logger()
        self._init_notifier()
        self._init_status_updates()
        self._init_commands()
        self._init_external_events()
        self._run_task = safe_ensure_future(self._run(), loop=self._ev_loop)

    def stop(self):
        # Best-effort offline notice (may not flush if we are mid-disconnect).
        self.broadcast_status_update("offline", msg_type="availability")
        self._stopped.set()
        self._connected = False
        if self._run_task is not None:
            self._run_task.cancel()
            self._run_task = None
        self._remove_status_updates()
        self._remove_notifier()
        self._remove_log_handlers()
        self._remove_market_event_listeners()


class MQTTLogHandler(logging.Handler):
    def __init__(self,
                 hb_app: "HummingbotApplication",
                 gateway: "MQTTGateway"):
        if threading.current_thread() != threading.main_thread():  # pragma: no cover
            raise EnvironmentError(
                "MQTTLogHandler can only be initialized from the main thread."
            )
        self._hb_app = hb_app
        self._gateway = gateway
        self._ev_loop: asyncio.AbstractEventLoop = self._hb_app.ev_loop

        topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._hb_app.instance_id
        )
        self._topic = f'{topic_prefix}{TopicSpecs.LOGS}'

        super().__init__()
        self.name = self.__class__.__name__

    def emit(self, record: logging.LogRecord):
        msg_str = self.format(record)
        msg = LogMessage(
            timestamp=time.time(),
            msg=msg_str,
            level_no=record.levelno,
            level_name=record.levelname,
            logger_name=record.name

        )
        self._gateway.publish(self._topic, msg.model_dump(), qos=self._gateway._QOS_PUBSUB)


class MQTTExternalEvents:
    # Regex pattern for validating event names: alphanumeric, dots, underscores, and wildcard
    EVENT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9._*]+$')

    def __init__(self,
                 hb_app: "HummingbotApplication",
                 gateway: "MQTTGateway"
                 ):
        self._gateway: "MQTTGateway" = gateway
        self._hb_app: 'HummingbotApplication' = hb_app
        self._ev_loop: asyncio.AbstractEventLoop = self._hb_app.ev_loop

        topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._hb_app.instance_id
        )
        self._topic = f'{topic_prefix}{TopicSpecs.EXTERNAL_EVENTS}'

        self._gateway.subscribe(self._topic, self._on_message)
        self._listeners: Dict[
            str,
            List[Callable[[ExternalEventMessage], str], None]
        ] = {'*': []}

    def _on_message(self, topic: str, payload: Dict[str, Any]) -> None:
        # Reconstruct the ExternalEventMessage so listeners keep receiving an
        # object with a `.data` attribute (commlib msg_type behaviour).
        try:
            msg = ExternalEventMessage(**payload) if isinstance(payload, dict) \
                else ExternalEventMessage()
        except Exception:  # pragma: no cover
            msg = ExternalEventMessage()
        self._on_event_arrived(msg, topic)

    def _event_uri_to_name(self, topic: str) -> str:
        return topic.split('event/')[1].replace('/', '.')

    def _on_event_arrived(self,
                          msg: ExternalEventMessage,
                          topic: str
                          ) -> None:
        event_name = self._event_uri_to_name(topic)
        self._hb_app.logger().debug(
            f'Received external event {event_name} -> {msg} - '
            'Broadcasting to listeners...'
        )
        if event_name in self._listeners:
            for fenc in self._listeners[event_name]:
                fenc(msg, event_name)
        for fenc in self._listeners['*']:
            fenc(msg, event_name)

    def _validate_event_name(self, event_name: str) -> None:
        """Validate event name format using regex pattern."""
        if not self.EVENT_NAME_PATTERN.match(event_name):
            raise ValueError(
                f"Invalid event name '{event_name}'. "
                "Event names must only contain alphanumeric characters, dots, underscores, or wildcards (*)"
            )

    def add_listener(self,
                     event_name: str,
                     callback: Callable[[ExternalEventMessage, str], None]
                     ) -> None:
        self._validate_event_name(event_name)
        if event_name in self._listeners:
            self._listeners.get(event_name).append(callback)
        else:
            self._listeners[event_name] = [callback]

    def remove_listener(self,
                        event_name: str,
                        callback: Callable[[ExternalEventMessage, str], None]
                        ):
        self._validate_event_name(event_name)
        if event_name in self._listeners:
            self._listeners.get(event_name).remove(callback)

    def add_global_listener(self,
                            callback: Callable[[ExternalEventMessage, str], None]
                            ):
        if '*' in self._listeners:
            self._listeners.get('*').append(callback)
        else:
            self._listeners['*'] = [callback]

    def remove_global_listener(self,
                               callback: Callable[[ExternalEventMessage, str], None]
                               ):
        if '*' in self._listeners:
            self._listeners.get('*').remove(callback)


class ETopicListener:
    def __init__(self,
                 topic: str,
                 on_message: Callable[[Dict[str, Any], str], None],
                 use_bot_prefix: Optional[bool] = True
                 ):
        self._gateway = MQTTGateway.main()
        if self._gateway is None:
            raise Exception('MQTT Gateway not yet initialized')
        topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._gateway._hb_app.instance_id
        )
        if use_bot_prefix:
            self._topic = f'{topic_prefix}/{topic}'
        else:
            self._topic = topic
        self._on_message = on_message
        self._gateway.subscribe(self._topic, self._on_message_wrapper)

    def _on_message_wrapper(self, topic: str, payload: Dict[str, Any]):
        self._on_message(payload, topic)

    def stop(self):
        self._gateway.unsubscribe(self._topic, self._on_message_wrapper)


class EEventQueueFactory:
    @classmethod
    def create(cls,
               event_name: str,
               queue_size: Optional[int] = 1000
               ) -> deque:
        gw = MQTTGateway.main()
        queue = deque(maxlen=queue_size)
        if gw is None:
            raise Exception('MQTTGateway is offline!')
        _on_event_clb = functools.partial(cls._on_event, queue)
        gw.add_external_event_listener(event_name, _on_event_clb)
        return queue

    @classmethod
    def _on_event(cls, queue: deque, msg: Dict[str, Any], name):
        queue.append((name, msg))


class EEventListenerFactory:
    @classmethod
    def create(cls,
               event_name: str,
               callback: Callable[[Dict[str, Any], str], None],
               ) -> None:
        gw = MQTTGateway.main()
        if gw is None:
            raise Exception('MQTTGateway is offline!')
        gw.add_external_event_listener(event_name, callback)

    @classmethod
    def remove(cls,
               event_name: str,
               callback: Callable[[Dict[str, Any], str], None],
               ) -> None:
        gw = MQTTGateway.main()
        if gw is None:
            raise Exception('MQTTGateway is offline!')
        gw.remove_external_event_listener(event_name, callback)


class ETopicListenerFactory:
    @classmethod
    def create(cls,
               topic: str,
               callback: Callable[[Dict[str, Any], str], None],
               use_bot_prefix: Optional[bool] = True
               ) -> ETopicListener:
        listener = ETopicListener(
            topic=topic,
            on_message=callback,
            use_bot_prefix=use_bot_prefix
        )
        return listener

    @classmethod
    def remove(cls, listener):
        listener.stop()
        del listener


class ETopicQueueFactory:
    @classmethod
    def create(cls,
               topic: str,
               queue_size: Optional[int] = 1000,
               use_bot_prefix: Optional[bool] = True
               ) -> deque:
        queue = deque(maxlen=queue_size)
        on_msg = functools.partial(cls._on_message, queue)
        _ = ETopicListener(
            topic=topic,
            on_message=on_msg,
            use_bot_prefix=use_bot_prefix
        )
        return queue

    @classmethod
    def _on_message(cls, queue: deque, msg: Dict[str, Any], topic: str):
        queue.append((topic, msg))


class ExternalEventFactory:
    @classmethod
    def create_queue(cls,
                     event_name: str,
                     queue_size: Optional[int] = 1000
                     ) -> deque:
        return EEventQueueFactory.create(event_name, queue_size)

    @classmethod
    def create_async(cls,
                     event_name: str,
                     callback: Callable[[Dict[str, Any], str], None],
                     ) -> None:
        return EEventListenerFactory.create(event_name, callback)

    @classmethod
    def remove_listener(cls,
                        event_name: str,
                        callback: Callable[[Dict[str, Any], str], None],
                        ) -> None:
        EEventListenerFactory.remove(event_name, callback)


class ExternalTopicFactory:
    @classmethod
    def create_queue(cls,
                     topic: str,
                     queue_size: Optional[int] = 1000,
                     use_bot_prefix: Optional[bool] = True
                     ) -> deque:
        return ETopicQueueFactory.create(topic, queue_size, use_bot_prefix)

    @classmethod
    def create_async(cls,
                     topic: str,
                     callback: Callable[[Dict[str, Any], str], None],
                     use_bot_prefix: Optional[bool] = True
                     ) -> ETopicListener:
        return ETopicListenerFactory.create(topic, callback, use_bot_prefix)

    @classmethod
    def remove_listener(cls, listener):
        return ETopicListenerFactory.remove(listener)


class ETopicPublisher:
    def __init__(self,
                 topic: str,
                 use_bot_prefix: Optional[bool] = False):
        self._gateway = MQTTGateway.main()
        if self._gateway is None:
            raise Exception('MQTT Gateway not yet initialized')
        self._topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._gateway._hb_app.instance_id
        )
        if use_bot_prefix:
            self._topic = f'{self._topic_prefix}/{topic}'
        else:
            self._topic = topic

    def send(self, msg: Dict[str, Any]):
        self._gateway.publish(self._topic, msg, qos=self._gateway._QOS_PUBSUB)

    def __call__(self, msg: Dict[str, Any]):
        self.send(msg)


class EMTopicPublisher:
    def __init__(self,
                 use_bot_prefix: Optional[bool] = False):
        self._use_bot_prefix = use_bot_prefix
        self._gateway = MQTTGateway.main()
        if self._gateway is None:
            raise Exception('MQTT Gateway not yet initialized')
        self._topic_prefix = TopicSpecs.PREFIX.format(
            namespace=self._gateway.namespace,
            instance_id=self._gateway._hb_app.instance_id
        )

    def send(self, topic: str, msg: Dict[str, Any]):
        self._gateway.publish(self._make_topic(topic), msg, qos=self._gateway._QOS_PUBSUB)

    def _make_topic(self, topic: str):
        if self._use_bot_prefix:
            _topic = f'{self._topic_prefix}/{topic}'
        else:
            _topic = topic
        return _topic

    def __call__(self, topic: str, msg: Dict[str, Any]):
        self.send(topic, msg)
