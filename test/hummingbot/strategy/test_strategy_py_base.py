#!/usr/bin/env python
import unittest
import asyncio
import time

from collections import deque
from decimal import Decimal
from typing import Union
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.event.events import (
    MarketEvent,
    OrderType,
    TradeType,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderFilledEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    FundingPaymentCompletedEvent,
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from test.mock.mock_paper_exchange import MockPaperExchange


class MockPyStrategy(StrategyPyBase):

    def __init__(self):
        super().__init__()

        # Used the check the events are recorded
        self.events_queue = deque()

    def did_create_buy_order(self, order_created_event: BuyOrderCreatedEvent):
        self.events_queue.append(order_created_event)

    def did_create_sell_order(self, order_created_event: SellOrderCreatedEvent):
        self.events_queue.append(order_created_event)

    def did_fill_order(self, order_filled_event: OrderFilledEvent):
        self.events_queue.append(order_filled_event)

    def did_fail_order(self, order_failed_event: MarketOrderFailureEvent):
        self.events_queue.append(order_failed_event)

    def did_cancel_order(self, cancelled_event: OrderCancelledEvent):
        self.events_queue.append(cancelled_event)

    def did_expire_order(self, expired_event: OrderExpiredEvent):
        self.events_queue.append(expired_event)

    def did_complete_buy_order(self, order_completed_event: BuyOrderCompletedEvent):
        self.events_queue.append(order_completed_event)

    def did_complete_sell_order(self, order_completed_event: SellOrderCompletedEvent):
        self.events_queue.append(order_completed_event)

    def did_complete_funding_payment(self, funding_payment_completed_event: FundingPaymentCompletedEvent):
        self.events_queue.append(funding_payment_completed_event)


class StrategyPyBaseUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.trading_pair = "COINALPHA-HBOT"

    def setUp(self):
        self.market: MockPaperExchange = MockPaperExchange()
        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.market, self.trading_pair, *self.trading_pair.split("-")
        )

        self.strategy: StrategyPyBase = MockPyStrategy()
        self.strategy.add_markets([self.market])

    @staticmethod
    def simulate_order_created(market_info: MarketTradingPairTuple, order: Union[LimitOrder, MarketOrder]):
        event_tag = MarketEvent.BuyOrderCreated if order.is_buy else MarketEvent.SellOrderCreated
        event_class = BuyOrderCreatedEvent if order.is_buy else SellOrderCreatedEvent

        market_info.market.trigger_event(
            event_tag,
            event_class(
                int(time.time() * 1e3),
                OrderType.LIMIT if isinstance(order, LimitOrder) else OrderType.MARKET,
                order.trading_pair,
                order.quantity if isinstance(order, LimitOrder) else order.amount,
                order.price,
                order.client_order_id if isinstance(order, LimitOrder) else order.order_id
            )
        )

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

    @staticmethod
    def simulate_order_failed(market_info: MarketTradingPairTuple, order: Union[LimitOrder, MarketOrder]):
        market_info.market.trigger_event(
            MarketEvent.OrderFailure,
            MarketOrderFailureEvent(
                int(time.time() * 1e3),
                order.client_order_id if isinstance(order, LimitOrder) else order.order_id,
                OrderType.LIMIT if isinstance(order, LimitOrder) else OrderType.MARKET
            )
        )

    @staticmethod
    def simulate_cancel_order(market_info: MarketTradingPairTuple, order: Union[LimitOrder, MarketOrder]):
        market_info.market.trigger_event(
            MarketEvent.OrderCancelled,
            OrderCancelledEvent(
                int(time.time() * 1e3),
                order.client_order_id if isinstance(order, LimitOrder) else order.order_id,
            )
        )

    @staticmethod
    def simulate_order_expired(market_info: MarketTradingPairTuple, order: Union[LimitOrder, MarketOrder]):
        market_info.market.trigger_event(
            MarketEvent.OrderExpired,
            OrderExpiredEvent(
                int(time.time() * 1e3),
                order.client_order_id if isinstance(order, LimitOrder) else order.order_id,
            )
        )

    @staticmethod
    def simulate_order_completed(market_info: MarketTradingPairTuple, order: Union[LimitOrder, MarketOrder]):
        event_tag = MarketEvent.BuyOrderCompleted if order.is_buy else MarketEvent.SellOrderCompleted
        event_class = BuyOrderCompletedEvent if order.is_buy else SellOrderCompletedEvent

        market_info.market.trigger_event(
            event_tag,
            event_class(
                int(time.time() * 1e3),
                order.client_order_id if isinstance(order, LimitOrder) else order.order_id,
                order.trading_pair.split("-")[0],
                order.trading_pair.split("-")[1],
                order.trading_pair.split("-")[0] if order.is_buy else order.trading_pair.split("-")[1],
                Decimal("1") if order.is_buy else Decimal("0"),
                Decimal("0") if order.is_buy else Decimal("1"),
                Decimal("0") if order.is_buy else Decimal("1"),
                OrderType.LIMIT if isinstance(order, LimitOrder) else OrderType.MARKET,
            )
        )

    @staticmethod
    def simulate_funding_payment_completed(market_info: MarketTradingPairTuple):

        example_rate: Decimal = Decimal("100")

        # Example API response for funding payment details
        response = {
            "symbol": "BTCUSDT",
            "incomeType": "COMMISSION",
            "income": "-0.01000000",
            "asset": "USDT",
            "info": "COMMISSION",
            "time": 1570636800000,
            "tranId": "9689322392",
            "tradeId": "2059192"
        }

        market_info.market.trigger_event(
            MarketEvent.FundingPaymentCompleted,
            FundingPaymentCompletedEvent(
                response["time"],
                market_info.market.name,
                example_rate,
                response["symbol"],
                response["income"]
            )
        )

    def test_did_create_buy_order(self):
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=True,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("100"),
                                             quantity=Decimal("50"))
        self.simulate_order_created(self.market_info, limit_order)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, BuyOrderCreatedEvent)

    def test_did_create_sell_order(self):
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=False,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("100"),
                                             quantity=Decimal("50"))

        self.simulate_order_created(self.market_info, limit_order)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, SellOrderCreatedEvent)

    def test_did_fill_order(self):
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=False,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("100"),
                                             quantity=Decimal("50"))

        self.simulate_order_filled(self.market_info, limit_order)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, OrderFilledEvent)

    def test_did_cancel_order(self):
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=True,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("100"),
                                             quantity=Decimal("50"))

        self.simulate_cancel_order(self.market_info, limit_order)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, OrderCancelledEvent)

    def test_did_fail_order(self):
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=False,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("100"),
                                             quantity=Decimal("50"))

        self.simulate_order_failed(self.market_info, limit_order)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, MarketOrderFailureEvent)

    def test_did_expire_order(self):
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=False,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("100"),
                                             quantity=Decimal("50"))

        self.simulate_order_expired(self.market_info, limit_order)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, OrderExpiredEvent)

    def test_did_complete_buy_order(self):
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=True,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("100"),
                                             quantity=Decimal("50"))

        self.simulate_order_completed(self.market_info, limit_order)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, BuyOrderCompletedEvent)

    def test_did_complete_sell_order(self):
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=False,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("100"),
                                             quantity=Decimal("50"))

        self.simulate_order_completed(self.market_info, limit_order)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, SellOrderCompletedEvent)

    def test_did_complete_funding_payment(self):
        self.simulate_funding_payment_completed(self.market_info)

        event = self.strategy.events_queue.popleft()

        self.assertIsInstance(event, FundingPaymentCompletedEvent)
