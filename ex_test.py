import time
import logging
import asyncio
from typing import Awaitable

from decimal import Decimal
from bidict import bidict

from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    #    BuyOrderCompletedEvent,
    #    BuyOrderCreatedEvent,
    #    MarketOrderFailureEvent,
    #    OrderCancelledEvent,
    #    OrderFilledEvent,
)
import hummingbot.core.utils
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
import hummingbot.logger.logger
from hummingbot.logger.logger import HummingbotLogger

import creds


class DisableTPF(TradingPairFetcher):
    async def fetch_all(self):
        return None


class TestingHL(HummingbotLogger):
    @staticmethod
    def is_testing_mode() -> bool:
        return True


hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher = DisableTPF
hummingbot.logger.logger.HummingbotLogger = TestingHL

logging.getLogger().setLevel(logging.DEBUG)


def get_binance(trading_pair):
    return BinanceExchange(
        binance_api_key=creds.k,
        binance_api_secret=creds.s,
        trading_pairs=[trading_pair],
    )


def get_gate_io(trading_pair):
    return GateIoExchange(
        gate_io_api_key=creds.k,
        gate_io_secret_key=creds.s,
        trading_pairs=[trading_pair],
    )


class ExchangeClient(object):
    # the level is required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        self.log_records = []
        self.test_task = None  # : Optional[asyncio.Task] = None

        self.base_asset = "COINALPHA"
        self.quote_asset = "HBOTX"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.exchange_trading_pair = f"{self.base_asset}{self.quote_asset}"
        self.symbol = f"{self.base_asset}{self.quote_asset}"

        # self.exchange = get_binance(self.trading_pair)
        self.exchange = get_gate_io(self.trading_pair)
        self.exchange.ORDERBOOK_DS_CLASS._trading_pair_symbol_map = {
            "com": bidict(
                {f"{self.base_asset}{self.quote_asset}": self.trading_pair})
        }
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)

        # logging init
        self.exchange.logger().setLevel(self.level)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.logger().setLevel(self.level)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(self.level)
        self.exchange._order_tracker.logger().addHandler(self)
        self._initialize_event_loggers()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.00001)),
                min_price_increment=Decimal(str(0.00001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def handle(self, log):
        self.log_records.append(log)

    def test(self):
        self._simulate_trading_rules_initialized()
        asyncio.run(self.tests())

    async def tests(self):
        # await self.update_balances()
        await self.test_order()

    async def update_balances(self):
        awt = asyncio.create_task(self.exchange._update_balances())
        r = await asyncio.gather(*[awt])
        print(r)

    async def test_order(self):
        ts = int(time.time())
        print(ts)  # ts = 123
        self.exchange._set_current_timestamp(ts)
        self.task = asyncio.create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("0.00001"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        r = await asyncio.gather(*[self.task])
        print(r)


if __name__ == '__main__':
    ec = ExchangeClient()
    ec.setUp()
    ec.test()
