import time
import logging
import asyncio
from typing import Awaitable

from decimal import Decimal
from bidict import bidict
from async_timeout import timeout

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
import hummingbot.logger.logger
from hummingbot.logger.logger import HummingbotLogger

from certs import creds


class TestingHL(HummingbotLogger):
    @staticmethod
    def is_testing_mode() -> bool:
        return True


# disable triggering of Application instantiation
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

    def set_trading_pair(self, base, quote):
        self.base_asset = base
        self.quote_asset = quote
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.exchange_trading_pair = f"{self.base_asset}{self.quote_asset}"
        self.symbol = f"{self.base_asset}{self.quote_asset}"

    async def start(self) -> None:
        self.log_records = []
        self.test_task = None  # : Optional[asyncio.Task] = None

        self.set_trading_pair("COINALPHA", "HBOT")
        self.set_trading_pair("XRP", "USD")
        # self.exchange = get_binance(self.trading_pair)
        self.exchange = get_gate_io(self.trading_pair)
        self.exchange.ORDERBOOK_DS_CLASS._trading_pair_symbol_map = {
            "com": bidict(
                {f"{self.base_asset}{self.quote_asset}": self.trading_pair})
        }
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self._simulate_trading_rules_initialized()

        # logging init
        self.exchange.logger().setLevel(self.level)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.logger().setLevel(self.level)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(self.level)
        self.exchange._order_tracker.logger().addHandler(self)
        self._initialize_event_loggers()

        await self.tests()

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

    async def task_and_gather(self, f):
        ret = await asyncio.gather(*[
            asyncio.create_task(f)
        ])
        if ret:
            return ret[0]
        return ret

    async def get_msg_from_queue(self):
        try:
            async with timeout(5):
                try:
                    print('user stream ', await self.exchange._user_stream_tracker._user_stream.get())
                    print('ob snapshot stream ', await self.exchange._order_book_tracker._order_book_snapshot_stream.get())
                    print('ob trade stream', await self.exchange._order_book_tracker._order_book_trade_stream.get())
                except asyncio.queues.QueueEmpty:
                    pass
        except asyncio.exceptions.TimeoutError:
            pass

    async def tests(self):
        self.set_trading_pair("XRP", "USD")
        self._simulate_trading_rules_initialized()

        await self.exchange.start_network()

        balances = await self.update_balances()
        print(balances)

        order_id = "t-123456"
        ret = await self.create_buy_order(order_id)
        print('create_buy_order ret ', ret)

        await self.get_msg_from_queue()

        # 2/b check ws create order update and balance update

        tracked_order = self.exchange._order_tracker.fetch_tracked_order(order_id)
        assert tracked_order.client_order_id == order_id

        ret = await self.cancel_order(order_id, tracked_order)
        print('deleted order: ', ret)

        await self.get_msg_from_queue()

        # 4
        # make sure the canceled order event is received from websocket

        # 5
        # connect and update from websocket updates from trades

        # 6
        # sell order create
        # balance should change (locked balance for error)

        # 7
        # connect to ws order book
        # make sure 1 update is received

        # 8 run test pure mm strategy

    async def update_balances(self):
        return await self.task_and_gather(self.exchange._update_balances())

    async def create_buy_order(self, order_id):
        return await self.create_order(TradeType.BUY, order_id)

    async def create_order(self, trade_type, order_id):
        self.exchange._set_current_timestamp(int(time.time()))
        return await self.task_and_gather(
            self.exchange._create_order(trade_type=trade_type,
                                        order_id=order_id,
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("0.001"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("0.0001"))
        )

    async def cancel_order(self, order_id, tracked_order):
        self.exchange._set_current_timestamp(int(time.time()))
        return await self.task_and_gather(
            self.exchange._place_cancel(order_id, tracked_order)
        )

    async def list_orders(self, trading_pair):
        return await self.task_and_gather(
            # self.exchange._place_cancel(order_id, tracked_order)
        )


if __name__ == '__main__':
    ec = ExchangeClient()
    asyncio.run(ec.start())
