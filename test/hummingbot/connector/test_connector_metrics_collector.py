import asyncio
import json
import platform
from copy import deepcopy
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import hummingbot.connector.connector_metrics_collector
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.connector_metrics_collector import DummyMetricsCollector, TradeVolumeMetricCollector
from hummingbot.core.data_type.common import TradeType, OrderType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import OrderFilledEvent, MarketEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle


class TradeVolumeMetricCollectorTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._global_config_backup = deepcopy(global_config_map)

        self.metrics_collector_url = "localhost"
        self.connector_name = "test_connector"
        self.instance_id = "test_instance_id"
        self.client_version = "0.1"
        self.rate_oracle = RateOracle()
        self.connector_mock = MagicMock()
        type(self.connector_mock).name = PropertyMock(return_value=self.connector_name)
        self.dispatcher_mock = MagicMock()
        type(self.dispatcher_mock).log_server_url = PropertyMock(return_value=self.metrics_collector_url)

        self.original_client_version = hummingbot.connector.connector_metrics_collector.CLIENT_VERSION
        hummingbot.connector.connector_metrics_collector.CLIENT_VERSION = self.client_version

        self.metrics_collector = TradeVolumeMetricCollector(
            connector=self.connector_mock,
            activation_interval=10,
            metrics_dispatcher=self.dispatcher_mock,
            rate_provider=self.rate_oracle,
            instance_id=self.instance_id,
            client_version=self.client_version)

    def tearDown(self) -> None:
        hummingbot.connector.connector_metrics_collector.CLIENT_VERSION = self.original_client_version
        self._reset_global_config()
        super().tearDown()

    def _reset_global_config(self):
        global_config_map.clear()
        for key, value in self._global_config_backup.items():
            global_config_map[key] = value

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_instance_creation_using_configuration_parameters(self):
        metrics_config = ConfigVar(key="anonymized_metrics_enabled", prompt="")
        metrics_config.value = True
        global_config_map["anonymized_metrics_enabled"] = metrics_config

        url_config = ConfigVar(key="log_server_url", prompt="")
        url_config.value = "localhost/reporting-proxy"
        global_config_map["log_server_url"] = url_config

        interval_config = ConfigVar(key="anonymized_metrics_interval_min", prompt="")
        interval_config.value = 5
        global_config_map["anonymized_metrics_interval_min"] = interval_config

        instance_id_config = ConfigVar(key="instance_id", prompt="")
        instance_id_config.value = self.instance_id
        global_config_map["instance_id"] = instance_id_config

        metrics_collector = TradeVolumeMetricCollector.from_configuration(
            connector=MagicMock(),
            rate_provider=self.rate_oracle,
            valuation_token="USDT")

        self.assertEqual(5 * 60, metrics_collector._activation_interval)
        self.assertEqual("localhost/reporting-proxy", metrics_collector._dispatcher.log_server_url)
        self.assertEqual(self.instance_id, metrics_collector._instance_id)
        self.assertEqual(self.client_version, metrics_collector._client_version)
        self.assertEqual("USDT", metrics_collector._valuation_token)

    def test_instance_creation_using_configuration_parameters_when_disabled(self):
        metrics_config = ConfigVar(key="anonymized_metrics_enabled", prompt="")
        metrics_config.value = False
        global_config_map["anonymized_metrics_enabled"] = metrics_config

        metrics_collector = TradeVolumeMetricCollector.from_configuration(
            connector=MagicMock(),
            rate_provider=self.rate_oracle,
            valuation_token="USDT")

        self.assertEqual(DummyMetricsCollector, type(metrics_collector))

        del (global_config_map["anonymized_metrics_enabled"])

        metrics_collector = TradeVolumeMetricCollector.from_configuration(
            connector=MagicMock(),
            rate_provider=self.rate_oracle,
            valuation_token="USDT")

        self.assertEqual(DummyMetricsCollector, type(metrics_collector))

    def test_start_and_stop_are_forwarded_to_dispatcher(self):
        self.metrics_collector.start()
        self.dispatcher_mock.start.assert_called()

        self.metrics_collector.stop()
        self.dispatcher_mock.stop.assert_called()

    def test_start_registers_to_order_fill_event(self):
        self.metrics_collector.start()
        self.connector_mock.add_listener.assert_called()
        self.assertEqual(MarketEvent.OrderFilled, self.connector_mock.add_listener.call_args[0][0])

    def test_stop_unregisters_from_order_fill_event(self):
        self.metrics_collector.stop()
        self.connector_mock.remove_listener.assert_called()
        self.assertEqual(MarketEvent.OrderFilled, self.connector_mock.remove_listener.call_args[0][0])

    def test_process_tick_does_not_collect_metrics_if_activation_interval_not_reached(self):
        event = OrderFilledEvent(
            timestamp=1000,
            order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(1000),
            amount=Decimal(1),
            trade_fee=AddedToCostTradeFee(),
        )
        self.metrics_collector._register_fill_event(event)

        last_process_tick_timestamp_copy = self.metrics_collector._last_process_tick_timestamp
        last_executed_collection_process = self.metrics_collector._last_executed_collection_process

        self.metrics_collector.process_tick(timestamp=5)

        self.assertEqual(last_process_tick_timestamp_copy, self.metrics_collector._last_process_tick_timestamp)
        self.assertEqual(last_executed_collection_process, self.metrics_collector._last_executed_collection_process)
        self.assertIn(event, self.metrics_collector._collected_events)

    def test_process_tick_starts_metrics_collection_if_activation_interval_reached(self):
        event = OrderFilledEvent(
            timestamp=1000,
            order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(1000),
            amount=Decimal(1),
            trade_fee=AddedToCostTradeFee(),
        )
        self.metrics_collector._register_fill_event(event)

        last_executed_collection_process = self.metrics_collector._last_executed_collection_process

        self.metrics_collector.process_tick(timestamp=15)

        self.assertEqual(15, self.metrics_collector._last_process_tick_timestamp)
        self.assertNotEqual(last_executed_collection_process, self.metrics_collector._last_executed_collection_process)
        self.assertNotIn(event, self.metrics_collector._collected_events)

    def test_collect_metrics_does_not_dispatch_anything_when_no_events_registered(self):
        self.async_run_with_timeout(self.metrics_collector.collect_metrics([]))
        self.dispatcher_mock.request.assert_not_called()

    def test_collect_metrics_for_single_event(self):
        self.rate_oracle._prices = {"HBOT-USDT": Decimal("100")}

        event = OrderFilledEvent(
            timestamp=1000,
            order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(1000),
            amount=Decimal(1),
            trade_fee=AddedToCostTradeFee(),
        )
        self.async_run_with_timeout(self.metrics_collector.collect_metrics([event]))

        expected_dispatch_request = {
            "url": f"{self.metrics_collector_url}/client_metrics",
            "method": "POST",
            "request_obj": {
                "headers": {
                    'Content-Type': "application/json"
                },
                "data": json.dumps({
                    "source": "hummingbot",
                    "name": TradeVolumeMetricCollector.METRIC_NAME,
                    "instance_id": self.instance_id,
                    "exchange": self.connector_name,
                    "version": self.client_version,
                    "system": f"{platform.system()} {platform.release()}({platform.platform()})",
                    "value": str(event.amount * event.price * 100)
                }),
                "params": {"ddtags": f"instance_id:{self.instance_id},"
                                     f"client_version:{self.client_version},"
                                     f"type:metrics",
                           "ddsource": "hummingbot-client"}
            }
        }

        self.dispatcher_mock.request.assert_called()
        dispatched_metric = self.dispatcher_mock.request.call_args[0][0]

        self.assertEqual(expected_dispatch_request, dispatched_metric)

    def test_metrics_not_collected_when_convertion_rate_to_volume_token_not_found(self):
        mock_rate_oracle = MagicMock()
        mock_rate_oracle.stored_or_live_rate = AsyncMock(return_value=None)

        local_collector = TradeVolumeMetricCollector(
            connector=self.connector_mock,
            activation_interval=10,
            metrics_dispatcher=self.dispatcher_mock,
            rate_provider=mock_rate_oracle,
            instance_id=self.instance_id,
            client_version=self.client_version)

        event = OrderFilledEvent(
            timestamp=1000,
            order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(1000),
            amount=Decimal(1),
            trade_fee=AddedToCostTradeFee(),
        )
        self.async_run_with_timeout(local_collector.collect_metrics([event]))

        self.dispatcher_mock.request.assert_not_called()

    def test_collect_metrics_uses_event_amount_when_only_base_token_convertion_rate_found(self):
        self.rate_oracle._prices = {
            "HBOT-USDT": Decimal("100"),
            "COINALPHA-USDT": Decimal("200"),
        }

        event_1 = OrderFilledEvent(
            timestamp=1000,
            order_id="OID1",
            trading_pair="COINALPHA-HBOT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(1000),
            amount=Decimal(1),
            trade_fee=AddedToCostTradeFee(),
        )
        event_2 = OrderFilledEvent(
            timestamp=1000,
            order_id="OID2",
            trading_pair="COINALPHA-ZZZ",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(500000),
            amount=Decimal(1),
            trade_fee=AddedToCostTradeFee(),
        )
        self.async_run_with_timeout(self.metrics_collector.collect_metrics([event_1, event_2]))

        expected_volume = Decimal("0")
        expected_volume += event_1.amount * event_1.price * Decimal("100")
        expected_volume += event_2.amount * Decimal("200")

        expected_dispatch_request = {
            "url": f"{self.metrics_collector_url}/client_metrics",
            "method": "POST",
            "request_obj": {
                "headers": {
                    'Content-Type': "application/json"
                },
                "data": json.dumps({
                    "source": "hummingbot",
                    "name": TradeVolumeMetricCollector.METRIC_NAME,
                    "instance_id": self.instance_id,
                    "exchange": self.connector_name,
                    "version": self.client_version,
                    "system": f"{platform.system()} {platform.release()}({platform.platform()})",
                    "value": str(expected_volume)
                }),
                "params": {"ddtags": f"instance_id:{self.instance_id},"
                                     f"client_version:{self.client_version},"
                                     f"type:metrics",
                           "ddsource": "hummingbot-client"}
            }
        }

        self.dispatcher_mock.request.assert_called()
        dispatched_metric = self.dispatcher_mock.request.call_args[0][0]

        self.assertEqual(expected_dispatch_request, dispatched_metric)
