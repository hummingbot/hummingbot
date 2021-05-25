#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import pandas as pd
# from typing import (
#    List,
#    Dict,
#    Tuple)
import unittest
# from hummingsim.backtest.backtest_market import BacktestMarket
# from hummingsim.backtest.ddex_order_book_loader import DDEXOrderBookLoader
# from hummingsim.backtest.market import Market
# from hummingsim.strategy.unit_test_strategy import UnitTestStrategy
from hummingbot.core.clock import (
    ClockMode,
    Clock
)
from hummingbot.core.event.events import (
    # MarketEvent,
    # OrderFilledEvent,
    TradeType,
)
# from hummingbot.core.event.event_listener import EventListener


# class CompositeOrderBookTestStrategy(UnitTestStrategy):
#     """
#     Makes market orders and record fill events
#     """
#
#     class OrderFilledEventLogger(EventListener):
#         def __init__(self, owner: "CompositeOrderBookTestStrategy"):
#             self._owner: "CompositeOrderBookTestStrategy" = owner
#
#         def __call__(self, order_filled_event: OrderFilledEvent):
#             self._owner.log_order_filled_event(order_filled_event)
#
#     def __init__(self, market: Market, trades: Dict[str, Tuple[str, float]]):
#         super().__init__(market)
#         self.trades = trades
#         self.tick_size = 5
#         self._order_filled_event_timestamps: List[float] = []
#         self._order_filled_events: List[OrderFilledEvent] = []
#         self._trade_logger: CompositeOrderBookTestStrategy.OrderFilledEventLogger = self.OrderFilledEventLogger(self)
#         market.add_listener(MarketEvent.OrderFilled, self._trade_logger)
#
#         self.start_printing = False
#
#     def log_order_filled_event(self, evt: OrderFilledEvent):
#         self._order_filled_event_timestamps.append(self.current_timestamp)
#         self._order_filled_events.append(evt)
#
#     def process_tick(self):
#         if self.current_timestamp in self.trades:
#             for trade in self.trades[self.current_timestamp]:
#                 if trade[1] == "buy":
#                     self.market.buy(trade[0], trade[2])
#                 elif trade[1] == "sell":
#                     self.market.sell(trade[0], trade[2])
#             self.start_printing = True
#
#         composite_ob = self.market.get_order_book("WETH-DAI")
#         composite_bids = list(composite_ob.bid_entries())
#         composite_asks = list(composite_ob.ask_entries())
#
#         if not self.start_printing:
#             return
#
#         original_bids = list(composite_ob.original_bid_entries())
#         original_asks = list(composite_ob.original_ask_entries())
#
#         filled_bids = list(composite_ob.traded_order_book.bid_entries())
#         filled_asks = list(composite_ob.traded_order_book.ask_entries())
#
#         order_books_top = [composite_bids[i] + composite_asks[i] + original_bids[i] + original_asks[i] for i in range(5)]
#
#         filled_order_books = []
#         for i in range(max(len(filled_bids), len(filled_asks))):
#             if i + 1 > len(filled_bids):
#                 fb = (None, None, None)
#             else:
#                 fb = filled_bids[i]
#             if i + 1 > len(filled_asks):
#                 fa = (None, None, None)
#             else:
#                 fa = filled_asks[i]
#             filled_order_books.append(fb + fa)
#
#         print(str(pd.Timestamp(self.current_timestamp, unit="s", tz="UTC")) + "\n" +
#               pd.DataFrame(data=filled_order_books,
#                            columns=['filled_bid_price', 'filled_bid_amount', 'uid',
#                                     'filled_ask_price', 'filled_ask_amount', 'uid'
#                                     ]
#                            ).to_string()
#               )
#
#         print(str(pd.Timestamp(self.current_timestamp, unit="s", tz="UTC")) + "\n" +
#               pd.DataFrame(data=order_books_top,
#                            columns=['composite_bid_price', 'composite_bid_amount', 'uid',
#                                     'composite_ask_price', 'composite_ask_amount', 'uid',
#                                     'original_bid_price', 'original_bid_amount', 'uid',
#                                     'original_ask_price', 'original_ask_amount', 'uid',
#                                     ]
#                            ).to_string()
#               )
#
#     @property
#     def order_filled_events(self) -> pd.DataFrame:
#         retval: pd.DataFrame = pd.DataFrame(data=self._order_filled_events,
#                                             columns=OrderFilledEvent._fields,
#                                             index=pd.Index(self._order_filled_event_timestamps, dtype="float64"))
#         retval.index = (retval.index * 1e9).astype("int64").astype("datetime64[ns]")
#         return retval

@unittest.skip("The test seems to be out of date. It requires the hummingsim component that is not present")
class CompositeOrderBookTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-25", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-26", tz="UTC")

    def setUp(self):
        # self.weth_dai_data = DDEXOrderBookLoader("WETH-DAI", "WETH", "DAI")
        self.clock = Clock(ClockMode.BACKTEST, 1.0, self.start.timestamp(), self.end.timestamp())
        # self.market = BacktestMarket()
        self.market.add_data(self.weth_dai_data)
        self.market.set_balance("WETH", 200.0)
        self.market.set_balance("DAI", 20000.0)
        self.clock.add_iterator(self.market)

    def tearDown(self):
        self.weth_dai_data.close()

    def verify_filled_order_recorded(self, recorded_filled_events, composite_order_book):
        bid_dict = {entry.price: (entry.amount, entry.update_id)
                    for entry in composite_order_book.traded_order_book.bid_entries()}
        ask_dict = {entry.price: (entry.amount, entry.update_id)
                    for entry in composite_order_book.traded_order_book.ask_entries()}
        for index, fill_event in recorded_filled_events.iterrows():
            if fill_event.trade_type is TradeType.SELL:
                self.assertTrue(fill_event.price in bid_dict)
                self.assertTrue(bid_dict[fill_event.price][0] == fill_event.amount)
                self.assertTrue(bid_dict[fill_event.price][1] == fill_event.timestamp)
            elif fill_event.trade_type is TradeType.BUY:
                self.assertTrue(fill_event.price in ask_dict)
                self.assertTrue(ask_dict[fill_event.price][0] == fill_event.amount)
                self.assertTrue(ask_dict[fill_event.price][1] == fill_event.timestamp)

    def verify_composite_order_book_correctness(self, composite_order_book):
        filled_bid_dict = {o.price: (o.amount, o.update_id)
                           for o in composite_order_book.traded_order_book.bid_entries()}
        filled_ask_dict = {o.price: (o.amount, o.update_id)
                           for o in composite_order_book.traded_order_book.ask_entries()}

        composite_bid_dict = {o.price: (o.amount, o.update_id) for o in composite_order_book.bid_entries()}
        composite_ask_dict = {o.price: (o.amount, o.update_id) for o in composite_order_book.ask_entries()}

        original_bid_dict = {o.price: (o.amount, o.update_id)
                             for o in composite_order_book.original_bid_entries()}
        original_ask_dict = {o.price: (o.amount, o.update_id)
                             for o in composite_order_book.original_ask_entries()}

        for filled_bid_price, filled_bid_amount in filled_bid_dict.items():
            if filled_bid_price in original_bid_dict:
                if (original_bid_dict[filled_bid_price] - filled_bid_amount) <= 0:
                    self.assertTrue(filled_bid_price not in composite_bid_dict)
                else:
                    self.assertTrue(composite_bid_dict[filled_bid_price] ==
                                    original_bid_dict[filled_bid_price] - filled_bid_amount)

        for filled_ask_price, filled_ask_amount in filled_ask_dict.items():
            if filled_ask_price in original_ask_dict:
                if (original_bid_dict[filled_ask_price] - filled_ask_amount) <= 0:
                    self.assertTrue(filled_ask_price not in composite_ask_dict)
                else:
                    self.assertTrue(composite_bid_dict[filled_ask_price] ==
                                    original_bid_dict[filled_ask_price] - filled_ask_amount)

    def verify_composite_order_book_cleanup(self, recorded_filled_events, composite_order_book):
        """
        Recorded fill order should be cleaned up when the original order book no longer contain that price entry
        """
        filled_bid_dict = {o.price: (o.amount, o.update_id)
                           for o in composite_order_book.traded_order_book.bid_entries()}
        filled_ask_dict = {o.price: (o.amount, o.update_id)
                           for o in composite_order_book.traded_order_book.ask_entries()}

        original_bid_dict = {o.price: (o.amount, o.update_id)
                             for o in composite_order_book.original_bid_entries()}
        original_ask_dict = {o.price: (o.amount, o.update_id)
                             for o in composite_order_book.original_ask_entries()}

        for index, fill_event in recorded_filled_events.iterrows():
            if fill_event.trade_type is TradeType.SELL:
                if fill_event.price not in original_bid_dict:
                    self.assertTrue(fill_event.price not in filled_bid_dict)

            elif fill_event.trade_type is TradeType.BUY:
                if fill_event.price not in original_ask_dict:
                    self.assertTrue(fill_event.price not in filled_ask_dict)

    def verify_composite_order_book_adjustment(self, composite_order_book):
        """
        Recorded fill order sohuld adjust it's amount to no larger than the original price entries' amount
        """
        filled_bid_dict = {o.price: (o.amount, o.update_id)
                           for o in composite_order_book.traded_order_book.bid_entries()}
        filled_ask_dict = {o.price: (o.amount, o.update_id)
                           for o in composite_order_book.traded_order_book.ask_entries()}

        original_bid_dict = {o.price: (o.amount, o.update_id)
                             for o in composite_order_book.original_bid_entries()}
        original_ask_dict = {o.price: (o.amount, o.update_id)
                             for o in composite_order_book.original_ask_entries()}

        for filled_bid_price, filled_bid_entry in filled_bid_dict.items():
            if filled_bid_price in original_bid_dict:
                self.assertTrue(original_bid_dict[filled_bid_price][0] >= filled_bid_entry[0])

        for filled_ask_price, filled_ask_entry in filled_ask_dict.items():
            if filled_ask_price in original_ask_dict:
                self.assertTrue(original_ask_dict[filled_ask_price][0] >= filled_ask_entry[0])

    # def test_market_order(self):
    #     trades = {
    #         pd.Timestamp("2019-01-25 00:00:10+00:00").timestamp(): [
    #             ("WETH-DAI", "buy", 5.0),
    #             ("WETH-DAI", "sell", 5.0)
    #         ]
    #     }
    #     strategy: CompositeOrderBookTestStrategy = CompositeOrderBookTestStrategy(self.market, trades)
    #     self.clock.add_iterator(strategy)
    #     self.clock.backtest_til(self.start.timestamp() + 10)
    #
    #     self.verify_filled_order_recorded(strategy.order_filled_events, self.market.get_order_book("WETH-DAI"))
    #     self.verify_composite_order_book_correctness(self.market.get_order_book("WETH-DAI"))
    #
    #     self.clock.backtest_til(self.start.timestamp() + 70)
    #
    #     self.verify_composite_order_book_cleanup(strategy.order_filled_events, self.market.get_order_book("WETH-DAI"))
    #
    # def test_composite_order_book_adjustment(self):
    #     trades = {
    #         pd.Timestamp("2019-01-25 00:02:15+00:00").timestamp(): [
    #             ("WETH-DAI", "sell", 93.53 + 23.65)
    #         ]
    #     }
    #     strategy: CompositeOrderBookTestStrategy = CompositeOrderBookTestStrategy(self.market, trades)
    #     self.clock.add_iterator(strategy)
    #     self.clock.backtest_til(self.start.timestamp() + 60 * 2 + 15)
    #     self.clock.backtest_til(self.start.timestamp() + 60 * 2 + 25)
    #     self.verify_composite_order_book_adjustment(self.market.get_order_book("WETH-DAI"))


if __name__ == "__main__":
    unittest.main()
