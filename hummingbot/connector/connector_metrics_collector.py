import asyncio
import json
import logging
import platform
from abc import ABC, abstractmethod
from decimal import Decimal
from os.path import dirname, join, realpath
from typing import List, Tuple, TYPE_CHECKING

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.log_server_client import LogServerClient

if TYPE_CHECKING:
    from hummingbot.connector.connector_base import ConnectorBase

with open(realpath(join(dirname(__file__), '../VERSION'))) as version_file:
    CLIENT_VERSION = version_file.read().strip()


class MetricsCollector(ABC):

    DEFAULT_METRICS_SERVER_URL = "https://api.coinalpha.com/reporting-proxy-v2"
    DEFAULT_ACTIVATION_INTERVAL_MINUTES = 15

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        raise NotImplementedError

    @abstractmethod
    def process_tick(self, timestamp: float):
        raise NotImplementedError


class DummyMetricsCollector(MetricsCollector):

    def start(self):
        # Nothing is required
        pass

    def stop(self):
        # Nothing is required
        pass

    def process_tick(self, timestamp: float):
        # Nothing is required
        pass


class TradeVolumeMetricCollector(MetricsCollector):

    _logger = None

    METRIC_NAME = "filled_usdt_volume"

    def __init__(self,
                 connector: 'ConnectorBase',
                 activation_interval: float,
                 metrics_dispatcher: LogServerClient,
                 rate_provider: RateOracle,
                 instance_id: str,
                 client_version: str,
                 valuation_token: str = "USDT"):
        super().__init__()
        self._connector = connector
        self._activation_interval = activation_interval
        self._dispatcher = metrics_dispatcher
        self._rate_provider = rate_provider
        self._instance_id = instance_id
        self._client_version = client_version
        self._valuation_token = valuation_token
        self._last_process_tick_timestamp = 0
        self._last_executed_collection_process = None
        self._collected_events = []

        self._fill_event_forwarder = EventForwarder(self._register_fill_event)

        self._event_pairs: List[Tuple[MarketEvent, EventForwarder]] = [
            (MarketEvent.OrderFilled, self._fill_event_forwarder),
        ]

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def from_configuration(cls, connector: 'ConnectorBase', rate_provider: RateOracle, valuation_token: str = "USDT"):
        instance = DummyMetricsCollector()

        anonymized_metrics_enabled = global_config_map.get("anonymized_metrics_enabled")
        if anonymized_metrics_enabled is not None and anonymized_metrics_enabled.value:
            dispatcher_url = global_config_map.get("log_server_url")
            if dispatcher_url is None:
                dispatcher_url = cls.DEFAULT_METRICS_SERVER_URL
            else:
                dispatcher_url = dispatcher_url.value
            dispatcher = LogServerClient(log_server_url=dispatcher_url)

            activation_interval = global_config_map.get("anonymized_metrics_interval_min")
            if activation_interval is None:
                activation_interval = cls.DEFAULT_ACTIVATION_INTERVAL_MINUTES * 60
            else:
                activation_interval = float(activation_interval.value) * 60

            instance_id = global_config_map.get("instance_id")
            if instance_id is None:
                instance_id = ""
            else:
                instance_id = instance_id.value

            instance = cls(
                connector=connector,
                activation_interval=activation_interval,
                metrics_dispatcher=dispatcher,
                rate_provider=rate_provider,
                instance_id=instance_id,
                client_version=CLIENT_VERSION,
                valuation_token=valuation_token)

        return instance

    def start(self):
        self._dispatcher.start()
        for event_pair in self._event_pairs:
            self._connector.add_listener(event_pair[0], event_pair[1])

    def stop(self):
        self.trigger_metrics_collection_process()
        for event_pair in self._event_pairs:
            self._connector.remove_listener(event_pair[0], event_pair[1])
        self._dispatcher.stop()

    def process_tick(self, timestamp: float):
        inactivity_time = timestamp - self._last_process_tick_timestamp
        if inactivity_time >= self._activation_interval:
            self._last_process_tick_timestamp = timestamp
            self.trigger_metrics_collection_process()

    def trigger_metrics_collection_process(self):
        events_to_process = self._collected_events
        self._collected_events = []
        self._last_executed_collection_process = safe_ensure_future(
            self.collect_metrics(events=events_to_process))

    async def collect_metrics(self, events: List[OrderFilledEvent]):
        try:
            total_volume = Decimal("0")

            for fill_event in events:
                trade_base, trade_quote = split_hb_trading_pair(fill_event.trading_pair)
                from_quote_conversion_pair = combine_to_hb_trading_pair(base=trade_quote, quote=self._valuation_token)
                rate = await self._rate_provider.stored_or_live_rate(from_quote_conversion_pair)

                if rate is not None:
                    total_volume += fill_event.amount * fill_event.price * rate
                else:
                    from_base_conversion_pair = combine_to_hb_trading_pair(base=trade_base, quote=self._valuation_token)
                    rate = await self._rate_provider.stored_or_live_rate(from_base_conversion_pair)
                    if rate is not None:
                        total_volume += fill_event.amount * rate
                    else:
                        self.logger().debug(f"Could not find a conversion rate rate using Rate Oracle for any of "
                                            f"the pairs {from_quote_conversion_pair} or {from_base_conversion_pair}")

            if total_volume > Decimal("0"):
                self._dispatch_trade_volume(total_volume)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._collected_events.extend(events)

    def _dispatch_trade_volume(self, volume: Decimal):
        metric_request = {
            "url": f"{self._dispatcher.log_server_url}/client_metrics",
            "method": "POST",
            "request_obj": {
                "headers": {
                    'Content-Type': "application/json"
                },
                "data": json.dumps({
                    "source": "hummingbot",
                    "name": self.METRIC_NAME,
                    "instance_id": self._instance_id,
                    "exchange": self._connector.name,
                    "version": self._client_version,
                    "system": f"{platform.system()} {platform.release()}({platform.platform()})",
                    "value": str(volume)}),
                "params": {"ddtags": f"instance_id:{self._instance_id},"
                                     f"client_version:{self._client_version},"
                                     f"type:metrics",
                           "ddsource": "hummingbot-client"}
            }
        }

        self._dispatcher.request(metric_request)

    def _register_fill_event(self, event: OrderFilledEvent):
        self._collected_events.append(event)
