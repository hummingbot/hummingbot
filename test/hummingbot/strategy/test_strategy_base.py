import asyncio
import logging
import time
import unittest
import unittest.mock
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple, Union

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.delayed_market_order import DelayedMarketOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.strategy.strategy_base import StrategyBase

ms_logger = None


class ExtendedMockPaperExchange(MockPaperExchange):

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__(client_config_map)

        self._in_flight_orders = {}

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values() if in_flight_order.order_type == OrderType.LIMIT
        ]

    @property
    def delayed_market_orders(self) -> List[DelayedMarketOrder]:
        return [
            in_flight_order.to_delayed_market_order()
            for in_flight_order in self._in_flight_orders.values() if (
                in_flight_order.order_type == OrderType.STOP_LOSS
                or in_flight_order.order_type == OrderType.TAKE_PROFIT
                or in_flight_order.order_type == OrderType.TRAILING_STOP
            )
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
        self.market: ExtendedMockPaperExchange = ExtendedMockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
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
        self.strategy.order_tracker._set_current_timestamp(1640001112.223)

    @staticmethod
    def simulate_order_filled(market_info: MarketTradingPairTuple, order: Union[LimitOrder, MarketOrder, DelayedMarketOrder]):

        if isinstance(order, LimitOrder):
            order_type = OrderType.LIMIT
            quantity = order.quantity
            price = order.price
        elif isinstance(order, MarketOrder):
            order_type = OrderType.MARKET
            quantity = order.amount
            price = None
        elif isinstance(order, DelayedMarketOrder):
            order_type = OrderType.STOP_LOSS
            quantity = order.amount
            price = order.trigger_price

        market_info.market.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                time.time(),
                order.client_order_id if isinstance(order, LimitOrder) else order.order_id,
                order.trading_pair,
                TradeType.BUY if order.is_buy else TradeType.SELL,
                order_type,
                price,
                quantity,
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

        new_market: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
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

        stop_loss_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="stop_loss_test",
            order_type=OrderType.STOP_LOSS.value,
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("90"),
            trigger_price=Decimal("100"),
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        stop_loss_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.STOP_LOSS,
            amount=stop_loss_order.amount,
            reference_price=stop_loss_order.reference_price,
            trigger_price=stop_loss_order.trigger_price,
        )

        tracked_stop_loss_order: DelayedMarketOrder = self.strategy.order_tracker.get_delayed_market_order(self.market_info, stop_loss_order_id)

        # Note: order_id generate here is random
        self.assertIsNotNone(stop_loss_order_id)

        self.assertEqual(stop_loss_order.is_buy, tracked_stop_loss_order.is_buy)
        self.assertEqual(stop_loss_order.trading_pair, tracked_stop_loss_order.trading_pair)
        self.assertEqual(stop_loss_order.amount, tracked_stop_loss_order.amount)
        self.assertEqual(stop_loss_order.reference_price, tracked_stop_loss_order.reference_price)
        self.assertEqual(stop_loss_order.trigger_price, tracked_stop_loss_order.trigger_price)

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

        stop_loss_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="market_test",
            order_type=OrderType.STOP_LOSS.value,
            trading_pair=self.trading_pair,
            is_buy=False,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("100"),
            trigger_price=Decimal("90"),
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        stop_loss_order_id: str = self.strategy.sell_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.STOP_LOSS,
            amount=stop_loss_order.amount,
            reference_price=stop_loss_order.reference_price,
            trigger_price=stop_loss_order.trigger_price,
        )

        tracked_stop_loss_order: DelayedMarketOrder = self.strategy.order_tracker.get_delayed_market_order(self.market_info, stop_loss_order_id)

        # Note: order_id generate here is random
        self.assertIsNotNone(stop_loss_order_id)

        self.assertEqual(stop_loss_order.is_buy, tracked_stop_loss_order.is_buy)
        self.assertEqual(stop_loss_order.trading_pair, tracked_stop_loss_order.trading_pair)
        self.assertEqual(stop_loss_order.amount, tracked_stop_loss_order.amount)
        self.assertEqual(stop_loss_order.reference_price, tracked_stop_loss_order.reference_price)
        self.assertEqual(stop_loss_order.trigger_price, tracked_stop_loss_order.trigger_price)

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

        stop_loss_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="stop_loss_test",
            order_type=OrderType.STOP_LOSS.value,
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("90"),
            trigger_price=Decimal("100"),
            amount=Decimal("50"),
            timestamp =int(time.time() * 1e3))

        stop_loss_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.STOP_LOSS,
            reference_price=stop_loss_order.reference_price,
            trigger_price=stop_loss_order.trigger_price,
            amount=stop_loss_order.quantity,
        )

        self.strategy.cancel_order(self.market_info, stop_loss_order_id)
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
        self.assertEqual(1, len(self.strategy.order_tracker.shadow_limit_orders))

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
        self.assertEqual(1, len(self.strategy.order_tracker.shadow_limit_orders))

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

    def test_start_tracking_delayed_market_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

        delayed_market_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="stop_loss_test",
            order_type=OrderType.STOP_LOSS.value,
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("90"),
            trigger_price=Decimal("100"),
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3),
        )

        # Note: order_id generate here is random
        self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.STOP_LOSS,
            amount=delayed_market_order.amount,
            reference_price=delayed_market_order.reference_price,
            trigger_price=delayed_market_order.trigger_price
        )

        self.assertEqual(1, len(self.strategy.order_tracker.tracked_delayed_market_orders))
        self.assertEqual(1, len(self.strategy.order_tracker.shadow_delayed_market_orders))

    def test_stop_tracking_delayed_market_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

        delayed_market_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="stop_loss_test",
            order_type=OrderType.STOP_LOSS.value,
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("90"),
            trigger_price=Decimal("100"),
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        delayed_market_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.STOP_LOSS,
            amount=delayed_market_order.amount,
            reference_price=delayed_market_order.reference_price,
            trigger_price=delayed_market_order.trigger_price
        )

        self.assertEqual(1, len(self.strategy.order_tracker.tracked_delayed_market_orders))
        self.assertEqual(1, len(self.strategy.order_tracker.shadow_delayed_market_orders))

        self.strategy.cancel_order(self.market_info, delayed_market_order_id)
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

    def test_start_tracking_take_profit_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

        take_profit_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="take_profit_test",
            order_type=OrderType.TAKE_PROFIT.value,
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("90"),
            trigger_price=Decimal("100"),
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3),
        )

        # Note: order_id generate here is random
        self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.TAKE_PROFIT,
            amount=take_profit_order.amount,
            reference_price=take_profit_order.reference_price,
            trigger_price=take_profit_order.trigger_price
        )

        self.assertEqual(1, len(self.strategy.order_tracker.tracked_delayed_market_orders))
        self.assertEqual(1, len(self.strategy.order_tracker.shadow_delayed_market_orders))

    def test_stop_tracking_take_profit_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

        take_profit_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="take_profit_test",
            order_type=OrderType.TAKE_PROFIT.value,
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("90"),
            trigger_price=Decimal("100"),
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        take_profit_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.TAKE_PROFIT,
            amount=take_profit_order.amount,
            reference_price=take_profit_order.reference_price,
            trigger_price=take_profit_order.trigger_price
        )
        self.assertEqual(1, len(self.strategy.order_tracker.tracked_delayed_market_orders))
        self.assertEqual(1, len(self.strategy.order_tracker.shadow_delayed_market_orders))

        self.strategy.cancel_order(self.market_info, take_profit_order_id)
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

    def test_start_tracking_trailing_stop_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

        trailing_stop_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="trailing_stop_test",
            order_type=OrderType.TRAILING_STOP.value,
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("90"),
            trigger_price=Decimal("100"),
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3),
        )

        # Note: order_id generate here is random
        self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.TRAILING_STOP,
            amount=trailing_stop_order.amount,
            reference_price=trailing_stop_order.reference_price,
            trigger_price=trailing_stop_order.trigger_price
        )

        self.assertEqual(1, len(self.strategy.order_tracker.tracked_delayed_market_orders))
        self.assertEqual(1, len(self.strategy.order_tracker.shadow_delayed_market_orders))

    def test_stop_tracking_trailing_stop_order(self):
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

        trailing_stop_order: DelayedMarketOrder = DelayedMarketOrder(
            order_id="trailing_stop_test",
            order_type=OrderType.TRAILING_STOP.value,
            trading_pair=self.trading_pair,
            is_buy=True,
            base_asset=self.trading_pair.split("-")[0],
            quote_asset=self.trading_pair.split("-")[1],
            reference_price=Decimal("90"),
            trigger_price=Decimal("100"),
            amount=Decimal("100"),
            timestamp =int(time.time() * 1e3)
        )

        # Note: order_id generate here is random
        trailing_stop_order_id: str = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            order_type=OrderType.TRAILING_STOP,
            amount=trailing_stop_order.amount,
            reference_price=trailing_stop_order.reference_price,
            trigger_price=trailing_stop_order.trigger_price
        )
        self.assertEqual(1, len(self.strategy.order_tracker.tracked_delayed_market_orders))
        self.assertEqual(1, len(self.strategy.order_tracker.shadow_delayed_market_orders))

        self.strategy.cancel_order(self.market_info, trailing_stop_order_id)
        self.assertEqual(0, len(self.strategy.order_tracker.tracked_delayed_market_orders))

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
                creation_timestamp=1640001112.0,
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
