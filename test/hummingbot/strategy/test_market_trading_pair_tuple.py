#!/usr/bin/env python
import unittest
import math
import pandas as pd
import time
from decimal import Decimal
from typing import List
from hummingbot.core.clock import (
    Clock,
    ClockMode,
)
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    OrderBookTradeEvent,
    OrderFilledEvent,
    OrderType,
    PriceType,
    SellOrderCompletedEvent,
    TradeType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange

s_decimal_0 = Decimal(0)


class MarketTradingPairTupleUnitTest(unittest.TestCase):

    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair: str = "COINALPHA-HBOT"
    base_asset, quote_asset = trading_pair.split("-")
    base_balance: int = 500
    quote_balance: int = 5000
    initial_mid_price: int = 100
    clock_tick_size = 10

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: MockPaperExchange = MockPaperExchange()
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=100,
                                            min_price=50,
                                            max_price=150,
                                            price_step_size=1,
                                            volume_step_size=10)
        self.market.set_balance("COINALPHA", self.base_balance)
        self.market.set_balance("HBOT", self.quote_balance)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )

        self.market_info = MarketTradingPairTuple(self.market, self.trading_pair, self.base_asset, self.quote_asset)

    @staticmethod
    def simulate_limit_order_fill(market: MockPaperExchange, limit_order: LimitOrder, timestamp: float = 0):
        quote_currency_traded: Decimal = limit_order.price * limit_order.quantity
        base_currency_traded: Decimal = limit_order.quantity
        quote_currency: str = limit_order.quote_currency
        base_currency: str = limit_order.base_currency

        trade_event: OrderBookTradeEvent = OrderBookTradeEvent(
            trading_pair=limit_order.trading_pair,
            timestamp=timestamp,
            type=TradeType.BUY if limit_order.is_buy else TradeType.SELL,
            price=limit_order.price,
            amount=limit_order.quantity
        )

        market.get_order_book(limit_order.trading_pair).apply_trade(trade_event)

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
                quote_currency,
                base_currency_traded,
                quote_currency_traded,
                Decimal(0.0),
                OrderType.LIMIT
            ))
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
                quote_currency,
                base_currency_traded,
                quote_currency_traded,
                Decimal(0.0),
                OrderType.LIMIT
            ))

    @staticmethod
    def simulate_order_book_update(market_info: MarketTradingPairTuple, n: int, is_bid: bool):
        # Removes first n bid/ask entries
        update_id = int(time.time())

        if is_bid:
            new_bids: List[OrderBookRow] = [
                OrderBookRow(row.price, 0, row.update_id + 1)
                for i, row in enumerate(market_info.order_book.bid_entries())
                if i < n
            ]
            new_asks = []
        else:
            new_asks: List[OrderBookRow] = [
                OrderBookRow(row.price, 0, row.update_id + 1)
                for i, row in enumerate(market_info.order_book.ask_entries())
                if i < n
            ]
            new_bids = []

        market_info.order_book.apply_diffs(new_bids, new_asks, update_id)

    def test_order_book(self):
        # Calculate expected OrderBook volume
        expected_bid_volume: Decimal = Decimal("0")
        expected_ask_volume: Decimal = Decimal("0")

        # Calculate bid volume
        current_price = 100 - 1 / 2
        current_size = 10
        while current_price >= 50:
            expected_bid_volume += Decimal(str(current_size))
            current_price -= 1
            current_size += 10

        # Calculate ask volume
        current_price = 100 + 1 / 2
        current_size = 10
        while current_price <= 150:
            expected_ask_volume += Decimal(str(current_size))
            current_price += 1
            current_size += 10

        # Check order book by comparing the total volume
        # TODO: Determine a better approach to comparing orderbooks
        current_bid_volume: Decimal = sum([Decimal(entry.amount) for entry in self.market_info.order_book.bid_entries()])
        current_ask_volume: Decimal = sum([Decimal(entry.amount) for entry in self.market_info.order_book.ask_entries()])

        self.assertEqual(expected_bid_volume, current_bid_volume)
        self.assertEqual(expected_ask_volume, current_ask_volume)

    def test_quote_balance(self):
        # Check initial balance
        expected_quote_balance = self.quote_balance
        self.assertEqual(self.quote_balance, self.market_info.quote_balance)

        # Simulate an order fill
        fill_order: LimitOrder = LimitOrder(client_order_id="test",
                                            trading_pair=self.trading_pair,
                                            is_buy=True,
                                            base_currency=self.base_asset,
                                            quote_currency=self.quote_asset,
                                            price=Decimal("101.0"),
                                            quantity=Decimal("10"))
        self.simulate_limit_order_fill(self.market_info.market, fill_order)

        # Updates expected quote balance
        expected_quote_balance = self.quote_balance - (fill_order.price * fill_order.quantity)
        self.assertNotEqual(self.quote_balance, self.market_info.quote_balance)
        self.assertEqual(expected_quote_balance, self.market_info.quote_balance)

    def test_base_balance(self):
        # Check initial balance
        expected_base_balance = self.base_balance
        self.assertEqual(self.base_balance, self.market_info.base_balance)

        # Simulate order fill
        fill_order: LimitOrder = LimitOrder(client_order_id="test",
                                            trading_pair=self.trading_pair,
                                            is_buy=True,
                                            base_currency=self.base_asset,
                                            quote_currency=self.quote_asset,
                                            price=Decimal("101.0"),
                                            quantity=Decimal("10"))
        self.simulate_limit_order_fill(self.market_info.market, fill_order)

        # Updates expected base balance
        expected_base_balance = self.base_balance + fill_order.quantity
        self.assertNotEqual(self.base_balance, self.market_info.base_balance)
        self.assertEqual(expected_base_balance, self.market_info.base_balance)

    def test_get_mid_price(self):
        # Check initial mid price
        self.assertIs
        self.assertEqual(Decimal(str(self.initial_mid_price)), self.market_info.get_mid_price())

        # Calculate new mid price after removing first n bid entries in orderbook
        n_entires: int = 10
        bid_entries, ask_entries = self.market_info.order_book.snapshot
        best_bid: Decimal = Decimal(bid_entries.drop(list(range(n_entires))).iloc[1]["price"])
        best_ask: Decimal = Decimal(ask_entries.iloc[1]["price"])

        expected_mid_price = (best_bid + best_ask) / Decimal("2")

        # Simulate n bid entries being removed
        self.simulate_order_book_update(self.market_info, n_entires, True)

        self.assertNotEqual(Decimal(str(self.initial_mid_price)), self.market_info.get_mid_price())
        self.assertEqual(expected_mid_price, self.market_info.get_mid_price())

    def test_get_price(self):
        # Check buy price
        expected_buy_price: Decimal = min([entry.price for entry in self.market.order_book_ask_entries(self.trading_pair)])
        self.assertEqual(expected_buy_price, self.market_info.get_price(is_buy=True))

        # Check sell price
        expected_sell_price: Decimal = max([entry.price for entry in self.market.order_book_bid_entries(self.trading_pair)])
        self.assertEqual(expected_sell_price, self.market_info.get_price(is_buy=False))

    def test_get_price_by_type(self):
        # Check PriceType.BestAsk
        expected_best_ask: Decimal = max([entry.price for entry in self.market.order_book_bid_entries(self.trading_pair)])
        self.assertEqual(expected_best_ask, self.market_info.get_price_by_type(PriceType.BestBid))

        # Check PriceType.BestAsk
        expected_best_ask: Decimal = min([entry.price for entry in self.market.order_book_ask_entries(self.trading_pair)])
        self.assertEqual(expected_best_ask, self.market_info.get_price_by_type(PriceType.BestAsk))

        # Check PriceType.MidPrice
        expected_mid_price: Decimal = Decimal(self.initial_mid_price)
        self.assertEqual(expected_mid_price, self.market_info.get_price_by_type(PriceType.MidPrice))

        # Check initial PriceType.LastTrade
        self.assertTrue(math.isnan(self.market_info.get_price_by_type(PriceType.LastTrade)))

        # Simulate fill buy order
        expected_trade_price = Decimal("101.0")
        fill_order: LimitOrder = LimitOrder(client_order_id="test",
                                            trading_pair=self.trading_pair,
                                            is_buy=True,
                                            base_currency=self.base_asset,
                                            quote_currency=self.quote_asset,
                                            price=expected_trade_price,
                                            quantity=Decimal("10"))
        self.simulate_limit_order_fill(self.market_info.market, fill_order)

        # Check for updated trade price
        self.assertEqual(expected_trade_price, self.market_info.get_price_by_type(PriceType.LastTrade))

    def test_vwap_for_volume(self):
        # Check VWAP on BUY sell
        order_volume: Decimal = Decimal("15")
        filled_orders: List[OrderBookRow] = self.market.get_order_book(self.trading_pair).simulate_buy(order_volume)
        expected_vwap: Decimal = sum([Decimal(o.price) * Decimal(o.amount) for o in filled_orders]) / order_volume

        self.assertAlmostEqual(expected_vwap, self.market_info.get_vwap_for_volume(True, order_volume).result_price, 3)

        # Check VWAP on SELL side
        order_volume: Decimal = Decimal("15")
        filled_orders: List[OrderBookRow] = self.market.get_order_book(self.trading_pair).simulate_sell(order_volume)
        expected_vwap: Decimal = sum([Decimal(o.price) * Decimal(o.amount) for o in filled_orders]) / order_volume

        self.assertAlmostEqual(expected_vwap, self.market_info.get_vwap_for_volume(False, order_volume).result_price, 3)

    def test_get_price_for_volume(self):
        # Check price on BUY sell
        order_volume: Decimal = Decimal("15")
        filled_orders: List[OrderBookRow] = self.market.get_order_book(self.trading_pair).simulate_buy(order_volume)
        expected_buy_price: Decimal = max([Decimal(o.price) for o in filled_orders])

        self.assertAlmostEqual(expected_buy_price, self.market_info.get_price_for_volume(True, order_volume).result_price, 3)

        # Check price on SELL side
        order_volume: Decimal = Decimal("15")
        filled_orders: List[OrderBookRow] = self.market.get_order_book(self.trading_pair).simulate_sell(order_volume)
        expected_sell_price: Decimal = min([Decimal(o.price) for o in filled_orders])

        self.assertAlmostEqual(expected_sell_price, self.market_info.get_price_for_volume(False, order_volume).result_price, 3)

    def test_order_book_bid_entries(self):
        # Check all entries.
        order_book: OrderBook = self.market.get_order_book(self.trading_pair)
        bid_entries: List[OrderBookRow] = order_book.bid_entries()

        self.assertTrue(set(bid_entries).intersection(set(self.market_info.order_book_bid_entries())))

    def test_order_book_ask_entries(self):
        # Check all entries.
        order_book: OrderBook = self.market.get_order_book(self.trading_pair)
        ask_entries: List[OrderBookRow] = order_book.ask_entries()

        self.assertTrue(set(ask_entries).intersection(set(self.market_info.order_book_ask_entries())))
