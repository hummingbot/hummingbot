#!/usr/bin/env python
import unittest
import unittest.mock
import asyncio
import logging
import time

from datetime import datetime
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Union,
    Tuple,
)
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.event.events import (
    MarketEvent,
    OrderType,
    TradeType,
    OrderFilledEvent,
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange

ms_logger = None


class ExtendedMockPaperExchange(MockPaperExchange):

    def __init__(self):
        super().__init__()

        self._in_flight_orders = {}

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    def restored_market_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: value
            for key, value in saved_states.items()
        })


class MockStrategy(StrategyBase):

    @classmethod
    def logger(cls) -> logging.Logger:
        global ms_logger
        if ms_logger is None:
            ms_logger = logging.getLogger(__name__)
        return ms_logger


class StrategyBaseUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.trading_pair = "COINALPHA-HBOT"

    def setUp(self):
        self.market: ExtendedMockPaperExchange = ExtendedMockPaperExchange()
        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.market, self.trading_pair, *self.trading_pair.split("-")
        )

        self.mid_price = 100
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.mid_price, min_price=1,
                                            max_price=200, price_step_size=1, volume_step_size=10)
        self.market.set_balance("COINALPHA", 500)
        self.market.set_balance("WETH", 5000)
        self.market.set_balance("QETH", 500)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair.split("-")[0], 6, 6, 6, 6
            )
        )

        self.strategy: StrategyBase = MockStrategy()
        self.strategy.add_markets([self.market])

    @staticmethod
    def simulate_order_filled(market_info: MarketTradingPairTuple, order: Union[LimitOrder, MarketOrder]):

        market_info.market.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                int(time.time() * 1e3),
                order.client_order_id if isinstance(order, LimitOrder) else order.order_id,
                order.trading_pair,
                TradeType.BUY if order.is_buy else TradeType.SELL,
                OrderType.LIMIT if isinstance(order, LimitOrder) else OrderType.MARKET,
                order.price,
                order.quantity if isinstance(order, LimitOrder) else order.amount,
                Decimal("1")
            )
        )

    def test_active_markets(self):
        self.assertEqual(1, len(self.strategy.active_markets))

    def test_order_tracker(self):
        self.assertIsInstance(self.strategy.order_tracker, OrderTracker)

    def test_trades(self):
        self.assertEqual(0, len(self.strategy.trades))

        # Simulate order being placed and filled
        limit_order = LimitOrder(client_order_id="test",
                                 trading_pair=self.trading_pair,
                                 is_buy=False,
                                 base_currency=self.trading_pair.split("-")[0],
                                 quote_currency=self.trading_pair.split("-")[1],
                                 price=Decimal("100"),
                                 quantity=Decimal("50"))
        self.simulate_order_filled(self.market_info, limit_order)

        self.assertEqual(1, len(self.strategy.trades))

    def test_add_markets(self):

        self.assertEqual(1, len(self.strategy.active_markets))

        new_market: MockPaperExchange = MockPaperExchange()
        self.strategy.add_markets([new_market])

        self.assertEqual(2, len(self.strategy.active_markets))

    def test_remove_markets(self):
        self.assertEqual(1, len(self.strategy.active_markets))

        self.strategy.remove_markets([self.market])

        self.assertEqual(0, len(self.strategy.active_markets))

    def test_cum_flat_fees(self):

        fee_asset = self.trading_pair.split("-")[1]
        trades: List[Tuple[str, Decimal]] = [
            (fee_asset, Decimal(f"{i}"))
            for i in range(5)
        ]

        expected_total_fees = sum([Decimal(f"{i}") for i in range(5)])

        self.assertEqual(expected_total_fees, self.strategy.cum_flat_fees(fee_asset, trades))

    def test_buy_with_specific_market(self):
        limit_order: LimitOrder = LimitOrder(
            client_order_id="limit_test",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_currency=self.trading_pair.split("-")[0],
            quote_currency=self.trading_pair.split("-")[1],
            price=Decimal("100"),
            quantity=Decimal("50"))

        limit_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.LIMIT,
            price=limit_order.price,
            amount=limit_order.quantity,
        )

        tracked_limit_order: LimitOrder = self.strategy.order_tracker.get_limit_order(self.market_info, limit_order_id)

        # Note: order_id generate here is random
        self.assertIsNotNone(limit_order_id)

        self.assertEqual(limit_order.is_buy, tracked_limit_order.is_buy)
        self.assertEqual(limit_order.trading_pair, tracked_limit_order.trading_pair)
        self.assertEqual(limit_order.price, tracked_limit_order.price)
        self.assertEqual(limit_order.quantity, tracked_limit_order.quantity)

        market_order: MarketOrder = MarketOrder(
            order_id="market_test",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        market_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.MARKET,
            amount=market_order.amount
        )

        tracked_market_order: MarketOrder = self.strategy.order_tracker.get_market_order(self.market_info, market_order_id)

        # Note: order_id generate here is random
        self.assertIsNotNone(market_order_id)

        self.assertEqual(market_order.is_buy, tracked_market_order.is_buy)
        self.assertEqual(market_order.trading_pair, tracked_market_order.trading_pair)
        self.assertEqual(market_order.amount, tracked_market_order.amount)

    def test_sell_with_specific_market(self):
        limit_order: LimitOrder = LimitOrder(
            client_order_id="limit_test",
            trading_pair=self.trading_pair,
            is_buy=False,
            base_currency=self.trading_pair.split("-")[0],
            quote_currency=self.trading_pair.split("-")[1],
            price=Decimal("100"),
            quantity=Decimal("50"))

        limit_order_id: str = self.strategy.sell_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.LIMIT,
            price=limit_order.price,
            amount=limit_order.quantity,
        )

        tracked_limit_order: LimitOrder = self.strategy.order_tracker.get_limit_order(self.market_info, limit_order_id)

        # Note: order_id generate here is random
        self.assertIsNotNone(limit_order_id)

        self.assertEqual(limit_order.is_buy, tracked_limit_order.is_buy)
        self.assertEqual(limit_order.trading_pair, tracked_limit_order.trading_pair)
        self.assertEqual(limit_order.price, tracked_limit_order.price)
        self.assertEqual(limit_order.quantity, tracked_limit_order.quantity)

        market_order: MarketOrder = MarketOrder(
            order_id="market_test",
            trading_pair=self.trading_pair,
            is_buy=False,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        market_order_id: str = self.strategy.sell_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.MARKET,
            amount=market_order.amount
        )

        tracked_market_order: MarketOrder = self.strategy.order_tracker.get_market_order(self.market_info, market_order_id)

        # Note: order_id generate here is random
        self.assertIsNotNone(market_order_id)

        self.assertEqual(market_order.is_buy, tracked_market_order.is_buy)
        self.assertEqual(market_order.trading_pair, tracked_market_order.trading_pair)
        self.assertEqual(market_order.amount, tracked_market_order.amount)

    def test_cancel_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.in_flight_cancels))

        limit_order: LimitOrder = LimitOrder(
            client_order_id="limit_test",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_currency=self.trading_pair.split("-")[0],
            quote_currency=self.trading_pair.split("-")[1],
            price=Decimal("100"),
            quantity=Decimal("50"))

        limit_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.LIMIT,
            price=limit_order.price,
            amount=limit_order.quantity,
        )

        self.strategy.cancel_order(self.market_info, limit_order_id)
        self.assertEqual(0, len(self.strategy.order_tracker.in_flight_cancels))

    def test_start_tracking_limit_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_limit_orders))

        limit_order: LimitOrder = LimitOrder(
            client_order_id="limit_test",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_currency=self.trading_pair.split("-")[0],
            quote_currency=self.trading_pair.split("-")[1],
            price=Decimal("100"),
            quantity=Decimal("50"))

        self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.LIMIT,
            price=limit_order.price,
            amount=limit_order.quantity,
        )

        self.assertEqual(1, len(self.strategy.order_tracker.tracked_limit_orders))

    def test_stop_tracking_limit_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_limit_orders))

        limit_order: LimitOrder = LimitOrder(
            client_order_id="limit_test",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_currency=self.trading_pair.split("-")[0],
            quote_currency=self.trading_pair.split("-")[1],
            price=Decimal("100"),
            quantity=Decimal("50"))

        limit_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.LIMIT,
            price=limit_order.price,
            amount=limit_order.quantity,
        )

        self.assertEqual(1, len(self.strategy.order_tracker.tracked_limit_orders))

        self.strategy.cancel_order(self.market_info, limit_order_id)
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_limit_orders))

    def test_start_tracking_market_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_limit_orders))

        market_order: MarketOrder = MarketOrder(
            order_id="market_test",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.MARKET,
            amount=market_order.amount
        )

        self.assertEqual(1, len(self.strategy.order_tracker.tracked_market_orders))

    def test_stop_tracking_market_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_limit_orders))

        market_order: MarketOrder = MarketOrder(
            order_id="market_test",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        market_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.MARKET,
            amount=market_order.amount
        )
        self.strategy.cancel_order(self.market_info, market_order_id)
        # Note: MarketOrder is assumed to be filled once placed.
        self.assertEqual(1, len(self.strategy.order_tracker.tracked_market_orders))

    def test_track_restored_order(self):

        self.assertEqual(0, len(self.market.limit_orders))

        saved_states: Dict[str, Any] = {
            f"LIMIT_ORDER_ID_{i}": InFlightOrderBase(
                client_order_id=f"LIMIT_ORDER_ID_{i}",
                exchange_order_id=f"LIMIT_ORDER_ID_{i}",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal(f"{i+1}"),
                amount=Decimal(f"{10 * (i+1)}"),
                initial_state="OPEN"
            )
            for i in range(10)
        }

        self.market.restored_market_states(saved_states)

        self.assertEqual(10, len(self.strategy.track_restored_orders(self.market_info)))

    @unittest.mock.patch('hummingbot.client.hummingbot_application.HummingbotApplication.main_application')
    @unittest.mock.patch('hummingbot.client.hummingbot_application.HummingbotCLI')
    def test_notify_hb_app(self, cli_class_mock, main_application_function_mock):
        messages = []
        cli_logs = []

        cli_instance = cli_class_mock.return_value
        cli_instance.log.side_effect = lambda message: cli_logs.append(message)

        notifier_mock = unittest.mock.MagicMock()
        notifier_mock.add_msg_to_queue.side_effect = lambda message: messages.append(message)

        hummingbot_application = HummingbotApplication()
        hummingbot_application.notifiers.append(notifier_mock)
        main_application_function_mock.return_value = hummingbot_application

        self.strategy.notify_hb_app("Test message")

        self.assertIn("Test message", cli_logs)
        self.assertIn("Test message", messages)

    @unittest.mock.patch('hummingbot.client.hummingbot_application.HummingbotApplication.main_application')
    @unittest.mock.patch('hummingbot.client.hummingbot_application.HummingbotCLI')
    def test_notify_hb_app_with_timestamp(self, cli_class_mock, main_application_function_mock):
        messages = []
        cli_logs = []

        cli_instance = cli_class_mock.return_value
        cli_instance.log.side_effect = lambda message: cli_logs.append(message)

        notifier_mock = unittest.mock.MagicMock()
        notifier_mock.add_msg_to_queue.side_effect = lambda message: messages.append(message)

        hummingbot_application = HummingbotApplication()
        hummingbot_application.notifiers.append(notifier_mock)
        main_application_function_mock.return_value = hummingbot_application

        time_of_tick = datetime(year=2021, month=6, day=17, hour=0, minute=0, second=0, microsecond=0)

        self.strategy.tick(time_of_tick.timestamp())
        self.strategy.notify_hb_app_with_timestamp("Test message")

        self.assertIn("(2021-06-17 00:00:00) Test message", cli_logs)
        self.assertIn("(2021-06-17 00:00:00) Test message", messages)
