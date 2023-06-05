import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import MagicMock, PropertyMock

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.smart_components.smart_component_base import SmartComponentBase, SmartComponentStatus
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestSmartComponentBase(unittest.TestCase):
    def setUp(self):
        self.strategy = self.create_mock_strategy
        self.component = SmartComponentBase(self.strategy, ["connector1"], update_interval=0.5)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @property
    def create_mock_strategy(self):
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=ScriptStrategyBase)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        strategy.connectors = {
            "connector1": MagicMock(spec=ConnectorBase),
        }
        return strategy

    def test_constructor(self):
        component = SmartComponentBase(self.strategy, ["connector1"], update_interval=0.5)
        self.assertEqual(component._strategy, self.strategy)
        self.assertEqual(component.update_interval, 0.5)
        self.assertEqual(len(component.connectors), 1)
        self.assertEqual(component._status, SmartComponentStatus.NOT_STARTED)
        self.assertEqual(component._states, [])
        self.assertIsInstance(component._create_buy_order_forwarder, SourceInfoEventForwarder)

    def test_control_loop(self):
        self.component.control_task = MagicMock()
        self.component.terminated.set()
        self.async_run_with_timeout(self.component.control_loop())
        self.assertEqual(self.component._status, SmartComponentStatus.TERMINATED)

    def test_terminate_control_loop(self):
        self.component.control_task = MagicMock()
        self.component.terminate_control_loop()
        self.async_run_with_timeout(self.component.control_loop())
        self.assertEqual(self.component.status, SmartComponentStatus.TERMINATED)

    def test_process_order_completed_event(self):
        event_tag = 1
        market = MagicMock()
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=Decimal("1.0"),
            quote_asset_amount=Decimal("1.0") * Decimal("1000.0"),
            order_type=OrderType.LIMIT,
            exchange_order_id="ED140"
        )
        self.component.process_order_completed_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_completed_event(event_tag, market, event))

    def test_process_order_created_event(self):
        event_tag = 1
        market = MagicMock()
        event = BuyOrderCreatedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            trading_pair="ETH-USDT",
            amount=Decimal("1.0"),
            type=OrderType.LIMIT,
            price=Decimal("1000.0"),
            exchange_order_id="ED140",
            creation_timestamp=1234567890
        )
        self.component.process_order_created_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_created_event(event_tag, market, event))

    def test_process_order_canceled_event(self):
        event_tag = 1
        market = MagicMock()
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            exchange_order_id="ED140",
        )
        self.component.process_order_canceled_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_canceled_event(event_tag, market, event))

    def test_process_order_filled_event(self):
        event_tag = 1
        market = MagicMock()
        event = OrderFilledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            exchange_order_id="ED140",
            trading_pair="ETH-USDT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
            trade_fee=AddedToCostTradeFee(percent=Decimal("0.001")),
        )
        self.component.process_order_filled_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_filled_event(event_tag, market, event))

    def test_process_order_failed_event(self):
        event_tag = 1
        market = MagicMock()
        event = MarketOrderFailureEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            order_type=OrderType.LIMIT,
        )
        self.component.process_order_failed_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_failed_event(event_tag, market, event))

    def test_place_buy_order(self):
        buy_order_id = self.component.place_order(
            connector_name="connector1",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            side=TradeType.BUY,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
        )
        self.assertEqual(buy_order_id, "OID-BUY-1")

    def test_place_sell_order(self):
        sell_order_id = self.component.place_order(
            connector_name="connector1",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            side=TradeType.SELL,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
        )
        self.assertEqual(sell_order_id, "OID-SELL-1")
