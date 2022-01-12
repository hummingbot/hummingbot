import unittest
import pandas as pd

from decimal import Decimal
from typing import List
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.exchange.paper_trade.market_config import MarketConfig, AssetType
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import (
    MarketEvent,
    TradeType,
    OrderType,
    OrderFilledEvent,
    OrderBookTradeEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    PriceType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.strategy.dev_2_perform_trade import PerformTradeStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from test.mock.mock_paper_exchange import MockPaperExchange


class Dev2PerformTradeUnitTest(unittest.TestCase):

    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair: str = "COINALPHA-WETH"
    base_asset, quote_asset = trading_pair.split("-")
    clock_tick_size = 10
    spread: Decimal = Decimal("3.0")

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.mid_price = 100
        self.time_delay = 15
        self.cancel_order_wait_time = 45

        self.market: MockPaperExchange = MockPaperExchange()
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.mid_price, min_price=1,
                                            max_price=200, price_step_size=1, volume_step_size=10)

        self.market.set_balance("COINALPHA", 500)
        self.market.set_balance("WETH", 5000)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )

        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.market, self.trading_pair, self.base_asset, self.quote_asset
        )

        # Define strategies to test
        self.buy_mid_price_strategy: PerformTradeStrategy = PerformTradeStrategy(
            exchange=self.market,
            trading_pair=self.trading_pair,
            is_buy=True,
            spread=self.spread,
            order_amount=Decimal("1.0"),
            price_type=PriceType.MidPrice
        )

        self.sell_mid_price_strategy: PerformTradeStrategy = PerformTradeStrategy(
            exchange=self.market,
            trading_pair=self.trading_pair,
            is_buy=False,
            spread=self.spread,
            order_amount=Decimal("1.0"),
            price_type=PriceType.MidPrice
        )

        self.buy_last_price_strategy: PerformTradeStrategy = PerformTradeStrategy(
            exchange=self.market,
            trading_pair=self.trading_pair,
            is_buy=True,
            spread=self.spread,
            order_amount=Decimal("1.0"),
            price_type=PriceType.LastTrade
        )

        self.sell_last_price_strategy: PerformTradeStrategy = PerformTradeStrategy(
            exchange=self.market,
            trading_pair=self.trading_pair,
            is_buy=False,
            spread=self.spread,
            order_amount=Decimal("1.0"),
            price_type=PriceType.LastTrade
        )

        self.buy_last_own_trade_price_strategy: PerformTradeStrategy = PerformTradeStrategy(
            exchange=self.market,
            trading_pair=self.trading_pair,
            is_buy=True,
            spread=self.spread,
            order_amount=Decimal("1.0"),
            price_type=PriceType.LastOwnTrade
        )

        self.sell_last_own_trade_price_strategy: PerformTradeStrategy = PerformTradeStrategy(
            exchange=self.market,
            trading_pair=self.trading_pair,
            is_buy=False,
            spread=self.spread,
            order_amount=Decimal("1.0"),
            price_type=PriceType.LastOwnTrade
        )

        self.clock.add_iterator(self.market)
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.buy_order_completed_logger: EventLogger = EventLogger()
        self.sell_order_completed_logger: EventLogger = EventLogger()

        self.market.add_listener(MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger)
        self.market.add_listener(MarketEvent.SellOrderCompleted, self.sell_order_completed_logger)
        self.market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    @staticmethod
    def simulate_limit_order_fill(market: MockPaperExchange, limit_order: LimitOrder, timestamp: float):
        quote_currency_traded: Decimal = limit_order.price * limit_order.quantity
        base_currency_traded: Decimal = limit_order.quantity
        quote_currency: str = limit_order.quote_currency
        base_currency: str = limit_order.base_currency
        config: MarketConfig = market.config

        trade_event = OrderBookTradeEvent(
            trading_pair=limit_order.trading_pair,
            timestamp=timestamp,
            type=TradeType.BUY if limit_order.is_buy else TradeType.SELL,
            price=limit_order.price,
            amount=limit_order.quantity,
        )

        if limit_order.is_buy:
            market.set_balance(quote_currency, market.get_balance(quote_currency) - quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) + base_currency_traded)
            market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                limit_order.trading_pair,
                TradeType.BUY,
                OrderType.LIMIT,
                limit_order.price,
                limit_order.quantity,
                AddedToCostTradeFee(Decimal(0.0))
            ))
            market.trigger_event(MarketEvent.BuyOrderCompleted, BuyOrderCompletedEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                base_currency,
                quote_currency,
                base_currency if config.buy_fees_asset is AssetType.BASE_CURRENCY else quote_currency,
                base_currency_traded,
                quote_currency_traded,
                Decimal(0.0),
                OrderType.LIMIT
            ))
            market.order_books[limit_order.trading_pair].apply_trade(trade_event)
        else:
            market.set_balance(quote_currency, market.get_balance(quote_currency) + quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) - base_currency_traded)
            market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                limit_order.trading_pair,
                TradeType.SELL,
                OrderType.LIMIT,
                limit_order.price,
                limit_order.quantity,
                AddedToCostTradeFee(Decimal(0.0))
            ))
            market.trigger_event(MarketEvent.SellOrderCompleted, SellOrderCompletedEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                base_currency,
                quote_currency,
                base_currency if config.sell_fees_asset is AssetType.BASE_CURRENCY else quote_currency,
                base_currency_traded,
                quote_currency_traded,
                Decimal(0.0),
                OrderType.LIMIT
            ))
            market.order_books[limit_order.trading_pair].apply_trade(trade_event)

    def test_buy_mid_price_place_order(self):
        self.clock.add_iterator(self.buy_mid_price_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + self.time_delay)

        mid_price: Decimal = self.market.get_mid_price(self.trading_pair)
        expected_order_price: Decimal = mid_price * (Decimal('1') - (self.spread / Decimal("100")))

        bid_orders: List[LimitOrder] = [o for o in self.buy_mid_price_strategy.active_orders if o.is_buy]
        self.assertEqual(1, len(bid_orders))
        bid_order: LimitOrder = bid_orders[0]
        self.assertEqual(expected_order_price, bid_order.price)
        self.assertEqual(1, bid_order.quantity)

    def test_sell_mid_price_place_order(self):
        self.clock.add_iterator(self.sell_mid_price_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + self.time_delay)

        mid_price: Decimal = self.market.get_mid_price(self.trading_pair)
        expected_order_price: Decimal = mid_price * (Decimal('1') + (self.spread / Decimal("100")))

        ask_orders: List[LimitOrder] = [o for o in self.sell_mid_price_strategy.active_orders if not o.is_buy]
        self.assertEqual(1, len(ask_orders))
        ask_order: LimitOrder = ask_orders[0]
        self.assertEqual(expected_order_price, ask_order.price)
        self.assertEqual(1, ask_order.quantity)

    def test_buy_last_price_place_order(self):
        self.clock.add_iterator(self.buy_last_price_strategy)

        filled_order: LimitOrder = LimitOrder(client_order_id="test",
                                              trading_pair=self.trading_pair,
                                              is_buy=True,
                                              base_currency=self.base_asset,
                                              quote_currency=self.quote_asset,
                                              price=Decimal("101.0"),
                                              quantity=Decimal("10"))
        self.simulate_limit_order_fill(self.market, filled_order, self.start_timestamp)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + self.time_delay)

        last_trade_price = filled_order.price
        expected_order_price: Decimal = last_trade_price * (Decimal('1') - (self.spread / Decimal("100")))

        bid_orders: List[LimitOrder] = [o for o in self.buy_last_price_strategy.active_orders if o.is_buy]
        self.assertEqual(1, len(bid_orders))
        bid_order: LimitOrder = bid_orders[0]
        self.assertEqual(expected_order_price, bid_order.price)
        self.assertEqual(1, bid_order.quantity)

    def test_sell_last_price_place_order(self):
        self.clock.add_iterator(self.sell_last_price_strategy)

        filled_order: LimitOrder = LimitOrder(client_order_id="test",
                                              trading_pair=self.trading_pair,
                                              is_buy=True,
                                              base_currency=self.base_asset,
                                              quote_currency=self.quote_asset,
                                              price=Decimal("101.0"),
                                              quantity=Decimal("10"))
        self.simulate_limit_order_fill(self.market, filled_order, self.start_timestamp)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + self.time_delay)

        last_trade_price = filled_order.price
        expected_order_price: Decimal = last_trade_price * (Decimal('1') + (self.spread / Decimal("100")))

        ask_orders: List[LimitOrder] = [o for o in self.sell_last_price_strategy.active_orders if not o.is_buy]
        self.assertEqual(1, len(ask_orders))
        ask_order: LimitOrder = ask_orders[0]
        self.assertEqual(expected_order_price, ask_order.price)
        self.assertEqual(1, ask_order.quantity)

    def test_buy_last_own_trade_price_place_order(self):
        self.clock.add_iterator(self.buy_last_own_trade_price_strategy)

        # Simulate a order being filled in the orderbook
        own_filled_order: LimitOrder = LimitOrder(client_order_id="myTrade",
                                                  trading_pair=self.trading_pair,
                                                  is_buy=True,
                                                  base_currency=self.base_asset,
                                                  quote_currency=self.quote_asset,
                                                  price=Decimal("102.0"),
                                                  quantity=Decimal("10"))
        self.buy_last_own_trade_price_strategy._tracked_order_ids.add("myTrade")
        self.simulate_limit_order_fill(self.market, own_filled_order, self.start_timestamp + 60)

        self.clock.backtest_til(self.start_timestamp + 120)

        last_own_traded_price = own_filled_order.price
        expected_order_price: Decimal = last_own_traded_price * (Decimal('1') - (self.spread / Decimal("100")))

        bid_orders: List[LimitOrder] = [o for o in self.buy_last_own_trade_price_strategy.active_orders if o.is_buy]
        self.assertEqual(1, len(bid_orders))
        bid_order: LimitOrder = bid_orders[0]
        self.assertEqual(expected_order_price, bid_order.price)
        self.assertEqual(1, bid_order.quantity)

    def test_sell_last_own_trade_price_place_order(self):
        self.clock.add_iterator(self.sell_last_own_trade_price_strategy)

        # Simulate a order being filled in the orderbook
        own_filled_order: LimitOrder = LimitOrder(client_order_id="myTrade",
                                                  trading_pair=self.trading_pair,
                                                  is_buy=True,
                                                  base_currency=self.base_asset,
                                                  quote_currency=self.quote_asset,
                                                  price=Decimal("102.0"),
                                                  quantity=Decimal("10"))
        self.sell_last_own_trade_price_strategy._tracked_order_ids.add("myTrade")
        self.simulate_limit_order_fill(self.market, own_filled_order, self.start_timestamp + 60)

        self.clock.backtest_til(self.start_timestamp + 120)

        last_own_traded_price = own_filled_order.price
        expected_order_price: Decimal = last_own_traded_price * (Decimal('1') + (self.spread / Decimal("100")))

        ask_orders: List[LimitOrder] = [o for o in self.sell_last_own_trade_price_strategy.active_orders if not o.is_buy]
        self.assertEqual(1, len(ask_orders))
        ask_order: LimitOrder = ask_orders[0]
        self.assertEqual(expected_order_price, ask_order.price)
        self.assertEqual(1, ask_order.quantity)

    def test_order_filled(self):
        self.clock.add_iterator(self.buy_mid_price_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + self.time_delay)

        bid_order = [o for o in self.buy_mid_price_strategy.active_orders if o.is_buy][0]
        self.simulate_limit_order_fill(self.market, bid_order, self.start_timestamp + 10)

        fill_events = self.maker_order_fill_logger.event_log
        self.assertEqual(1, len(fill_events))

        order_filled: OrderFilledEvent = fill_events[0]
        self.assertEqual(bid_order.client_order_id, order_filled.order_id)

    def test_mid_price_order_update(self):
        self.clock.add_iterator(self.buy_mid_price_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + self.time_delay)

        # Simulate mid price update
        expected_mid_price: Decimal = Decimal("105")
        expected_new_price: Decimal = expected_mid_price * (Decimal('1') - (self.spread / Decimal("100")))
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=expected_mid_price, min_price=1,
                                            max_price=200, price_step_size=1, volume_step_size=10)

        new_price: Decimal = self.buy_mid_price_strategy._recalculate_price_parameter()
        self.assertEqual(new_price, expected_new_price)

    def test_last_price_order_update(self):
        self.clock.add_iterator(self.buy_last_price_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + self.time_delay)

        # Simulate last traded price update
        expected_last_price: Decimal = Decimal("101.0")
        filled_order: LimitOrder = LimitOrder(client_order_id="test",
                                              trading_pair=self.trading_pair,
                                              is_buy=True,
                                              base_currency=self.base_asset,
                                              quote_currency=self.quote_asset,
                                              price=expected_last_price,
                                              quantity=Decimal("10"))
        self.simulate_limit_order_fill(self.market, filled_order, self.start_timestamp)
        expected_new_price: Decimal = expected_last_price * (Decimal('1') - (self.spread / Decimal("100")))

        new_price: Decimal = self.buy_last_price_strategy._recalculate_price_parameter()
        self.assertEqual(new_price, expected_new_price)

    def test_last_own_trade_price_order_update(self):
        self.clock.add_iterator(self.buy_last_own_trade_price_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + self.time_delay)

        # Simulate own order filled
        last_own_traded_price: Decimal = Decimal("102.0")
        filled_order: LimitOrder = LimitOrder(client_order_id="myTrade",
                                              trading_pair=self.trading_pair,
                                              is_buy=True,
                                              base_currency=self.base_asset,
                                              quote_currency=self.quote_asset,
                                              price=last_own_traded_price,
                                              quantity=Decimal("10"))
        self.buy_last_own_trade_price_strategy._tracked_order_ids.add("myTrade")
        self.simulate_limit_order_fill(self.market, filled_order, self.start_timestamp)

        market_filled_order: LimitOrder = LimitOrder(client_order_id="notMyTrade",
                                                     trading_pair=self.trading_pair,
                                                     is_buy=True,
                                                     base_currency=self.base_asset,
                                                     quote_currency=self.quote_asset,
                                                     price=Decimal("100"),
                                                     quantity=Decimal("10"))
        self.simulate_limit_order_fill(self.market, market_filled_order, self.start_timestamp)

        expected_new_price: Decimal = last_own_traded_price * (Decimal('1') - (self.spread / Decimal("100")))

        new_price: Decimal = self.buy_last_own_trade_price_strategy._recalculate_price_parameter()
        self.assertEqual(new_price, expected_new_price)
