#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
import pandas as pd
from typing import (
    List,
    Dict,
    Tuple)
import unittest
from hummingsim.backtest.binance_order_book_loader_v2 import BinanceOrderBookLoaderV2
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import Market, OrderType
from hummingsim.strategy.unit_test_strategy import UnitTestStrategy
from hummingbot.core.clock import (
    ClockMode,
    Clock
)
from hummingbot.core.event.events import (
    MarketEvent,
    OrderExpiredEvent,
)
from hummingbot.core.event.event_listener import EventListener


class OrderExpirationTestStrategy(UnitTestStrategy):
    """
    Makes expiring limit orders and record order expired events
    """

    class OrderFilledEventLogger(EventListener):
        def __init__(self, owner: "OrderExpirationTestStrategy"):
            self._owner: "OrderExpirationTestStrategy" = owner

        def __call__(self, order_expired_event: OrderExpiredEvent):
            self._owner.log_order_expired_event(order_expired_event)

    def __init__(self, market: Market, trades: Dict[str, Tuple[str, float]]):
        super().__init__(market)
        self.trades = trades
        self.tick_size = 5
        self._order_expired_event_timestamps: List[float] = []
        self._order_expired_events: List[OrderExpiredEvent] = []
        self._order_expired_logger: OrderExpirationTestStrategy.OrderFilledEventLogger = self.OrderFilledEventLogger(self)
        market.add_listener(MarketEvent.OrderExpired, self._order_expired_logger)

        self.start_printing = False

    def log_order_expired_event(self, evt: OrderExpiredEvent):
        self._order_expired_event_timestamps.append(self.current_timestamp)
        self._order_expired_events.append(evt)

    def process_tick(self):
        if self.current_timestamp in self.trades:
            for trade in self.trades[self.current_timestamp]:
                if trade[1] == "buy":
                    self.market.buy(trade[0], trade[2], order_type=OrderType.LIMIT, price=trade[3], kwargs=trade[4])
                elif trade[1] == "sell":
                    self.market.sell(trade[0], trade[2], order_type=OrderType.LIMIT, price=trade[3], kwargs=trade[4])
            self.start_printing = True
        if not self.start_printing:
            return
        # print(self.order_expired_events)
        # print(self.market.limit_orders)
        print(self.market.order_expirations)

    @property
    def order_expired_events(self) -> pd.DataFrame:
        retval: pd.DataFrame = pd.DataFrame(data=self._order_expired_events,
                                            columns=OrderExpiredEvent._fields,
                                            index=pd.Index(self._order_expired_event_timestamps, dtype="float64"))
        retval.index = (retval.index * 1e9).astype("int64").astype("datetime64[ns]")
        return retval


class OrderExpirationTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-24", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-26", tz="UTC")
    market_name = "ETHUSDT"
    quote = "ETH"
    base = "USDT"

    def setUp(self):
        # self.weth_dai_data = DDEXOrderBookLoader("WETH-DAI", "WETH", "DAI")
        self.pair_data = BinanceOrderBookLoaderV2(self.market_name, "ETH", "USDT")
        # self.pair_data = HuobiOrderBookLoader(self.market_name, "", "")
        self.clock = Clock(ClockMode.BACKTEST, 1.0, self.start.timestamp(), self.end.timestamp())
        self.market = BacktestMarket()
        # self.market.add_data(self.weth_dai_data)
        self.market.add_data(self.pair_data)
        self.market.set_balance(self.quote, 200.0)
        self.market.set_balance(self.base, 20000.0)
        self.clock.add_iterator(self.market)

    def tearDown(self):
        # self.weth_dai_data.close()
        # self.eth_usd_data.close()
        self.pair_data.close()

    def verify_expired_order_cleanup(self, order_expired_events, limit_orders):
        """
        Recorded order expired event should indicate that these orders are no longer in the limit orders
        """
        limit_order_dict = {o.client_order_id: o for o in limit_orders}

        for index, order_expired_event in order_expired_events.iterrows():
            self.assertTrue(order_expired_event.order_id not in limit_order_dict)

    def test_ask_order_expiration_clean_up(self):
        ts_1 = pd.Timestamp("2019-01-24 00:02:15+00:00").timestamp()
        ts_2 = pd.Timestamp("2019-01-24 00:02:20+00:00").timestamp()
        trades = {
            ts_1: [
                (self.market_name, "sell", 1302, 255, {"expiration_ts": ts_1 + 9})
            ],
            ts_2: [
                (self.market_name, "sell", 1302, 250, {"expiration_ts": ts_2 + 9})
            ]
        }
        strategy: OrderExpirationTestStrategy = OrderExpirationTestStrategy(self.market, trades)
        self.clock.add_iterator(strategy)

        # first limit order made
        self.clock.backtest_til(self.start.timestamp() + 60 * 2 + 15)
        first_order_id = self.market.limit_orders[0].client_order_id
        self.assertTrue(len(self.market.limit_orders) == 1)
        self.assertTrue(first_order_id in {o.order_id: o for o in self.market.order_expirations})

        # second limit order made
        self.clock.backtest_til(self.start.timestamp() + 60 * 2 + 20)
        self.assertTrue(len(self.market.limit_orders) == 2)

        # first limit order expired
        self.clock.backtest_til(self.start.timestamp() + 60 * 2 + 25)
        # check if order expired event is fired
        self.assertTrue(first_order_id in [evt.order_id for i, evt in strategy.order_expired_events.iterrows()])
        # check if the expired limit order is cleaned up
        self.verify_expired_order_cleanup(strategy.order_expired_events, self.market.limit_orders)

        self.assertTrue(len(self.market.limit_orders) == 1)
        second_order_id = self.market.limit_orders[0].client_order_id
        self.assertTrue(second_order_id in {o.order_id: o for o in self.market.order_expirations})

        # second limit order expired
        self.clock.backtest_til(self.start.timestamp() + 60 * 2 + 30)
        # check if order expired event is fired
        self.assertTrue(second_order_id in [evt.order_id for i, evt in strategy.order_expired_events.iterrows()])
        # check if the expired limit order is cleaned up
        self.verify_expired_order_cleanup(strategy.order_expired_events, self.market.limit_orders)

    def test_bid_order_expiration_clean_up(self):
        ts_1 = pd.Timestamp("2019-01-24 00:12:15+00:00").timestamp()
        ts_2 = pd.Timestamp("2019-01-24 00:12:20+00:00").timestamp()

        trades = {
            ts_1: [
                (self.market_name, "buy", 100, 55, {"expiration_ts": ts_1 + 9})

            ],
            ts_2: [
                (self.market_name, "buy", 100, 50, {"expiration_ts": ts_2 + 9}),
                (self.market_name, "buy", 100, 55, {"expiration_ts": ts_2 + 9})
            ]
        }
        strategy: OrderExpirationTestStrategy = OrderExpirationTestStrategy(self.market, trades)
        self.clock.add_iterator(strategy)

        # first limit order made
        self.clock.backtest_til(self.start.timestamp() + 60 * 12 + 15)
        first_order_id = self.market.limit_orders[0].client_order_id
        self.assertTrue(len(self.market.limit_orders) == 1)
        self.assertTrue(first_order_id in {o.order_id: o for o in self.market.order_expirations})

        # second limit order made
        self.clock.backtest_til(self.start.timestamp() + 60 * 12 + 20)
        self.assertTrue(len(self.market.limit_orders) == 3)

        # first limit order expired
        self.clock.backtest_til(self.start.timestamp() + 60 * 12 + 25)
        # check if order expired event is fired
        self.assertTrue(first_order_id in [evt.order_id for i, evt in strategy.order_expired_events.iterrows()])
        # check if the expired limit order is cleaned up
        self.verify_expired_order_cleanup(strategy.order_expired_events, self.market.limit_orders)

        self.assertTrue(len(self.market.limit_orders) == 2)
        second_order_id_1 = self.market.limit_orders[0].client_order_id
        second_order_id_2 = self.market.limit_orders[1].client_order_id

        self.assertTrue(second_order_id_1 in {o.order_id: o for o in self.market.order_expirations})
        self.assertTrue(second_order_id_2 in {o.order_id: o for o in self.market.order_expirations})

        # second limit order expired
        self.clock.backtest_til(self.start.timestamp() + 60 * 12 + 30)
        # check if order expired event is fired
        self.assertTrue(second_order_id_1 in [evt.order_id for i, evt in strategy.order_expired_events.iterrows()])
        self.assertTrue(second_order_id_2 in [evt.order_id for i, evt in strategy.order_expired_events.iterrows()])
        # check if the expired limit order is cleaned up
        self.verify_expired_order_cleanup(strategy.order_expired_events, self.market.limit_orders)


if __name__ == "__main__":
    unittest.main()
