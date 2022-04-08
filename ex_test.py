import sys
import logging
import asyncio
from enum import Enum
from distutils.util import strtobool

from decimal import Decimal
from bidict import bidict
from async_timeout import timeout

from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType  # , TradeType
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
import hummingbot.core.pubsub

from certs import creds


class TestingHL(HummingbotLogger):
    @staticmethod
    def is_testing_mode() -> bool:
        return True


# disable triggering of Application instantiation
hummingbot.logger.logger.HummingbotLogger = TestingHL

logging.getLogger().setLevel(logging.DEBUG)


class FixPubSub(hummingbot.core.pubsub.PubSub):
    def trigger_event(self, event_tag: Enum, message: any):
        print("EVENT ", event_tag, message)
        self.c_trigger_event(event_tag.value, message)


# KeyError: '__pyx_vtable__'
# hummingbot.core.pubsub.PubSub = FixPubSub


async def sleep_yes_no(question):
    await asyncio.sleep(5)
    sys.stdout.write('\n%s [y/n]\n' % question)
    while True:
        try:
            answer = strtobool(input().lower())
            if not answer:
                print('sleep for 5')
                await asyncio.sleep(5)
            else:
                return answer
        except ValueError:
            sys.stdout.write('Please respond with \'y\' or \'n\'.\n')


def proceed(question):
    sys.stdout.write('\n%s [y/n]\n' % question)
    while True:
        try:
            return strtobool(input().lower())
        except ValueError:
            sys.stdout.write('Please respond with \'y\' or \'n\'.\n')


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

        # TODO
        # subscribe to other events
        # use only 1 logger
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
        results = []
        try:
            async with timeout(5):
                tasks = [
                    self.exchange._order_book_tracker._order_book_snapshot_stream.get(),
                    self.exchange._order_book_tracker._order_book_trade_stream.get(),
                    # OK
                    self.exchange._user_stream_tracker._user_stream.get()
                ]
                results = await asyncio.gather(*tasks)
        except asyncio.exceptions.TimeoutError:
            pass
        print('msgs ', results)

    async def update_balances(self):
        return await self.task_and_gather(self.exchange._update_balances())

    async def tests(self):
        base = "ETH"
        quote = "USDT"
        pair = f"{base}-{quote}"
        self.set_trading_pair(base, quote)
        self._simulate_trading_rules_initialized()

        await self.exchange.start_network()
        await self.update_balances()

        if proceed("run two failed orders?"):
            order_id = self.exchange.buy(pair, amount=Decimal(0.1), price=Decimal(1), order_type=OrderType.LIMIT)
            order_id = self.exchange.buy(pair, amount=Decimal(1000000), price=Decimal(1), order_type=OrderType.LIMIT)
            await sleep_yes_no("Two order should have failed.")

        if proceed("run 1% safety?"):
            order_id = self.exchange.buy(pair, amount=Decimal(1), price=Decimal(1), order_type=OrderType.LIMIT)
            await sleep_yes_no(f"LIMIT buy {order_id} should have failed because of line 816 1% safety")

        if proceed("run buy succeeeds then cancel?"):
            order_id = self.exchange.buy(pair, amount=Decimal(1.5), price=Decimal(1.5), order_type=OrderType.LIMIT)
            await sleep_yes_no(f"LIMIT buy {order_id} should have succeeded")
            order_id = self.exchange.cancel(pair, order_id)
            await sleep_yes_no(f"{order_id} should have been canceled")

        if proceed("run buy and cancel via web?"):
            order_id = self.exchange.buy(pair, amount=Decimal(1.1), price=Decimal(1.1), order_type=OrderType.LIMIT)
            await sleep_yes_no(f"{order_id} should have been placed")
            if proceed("did you delete it via web?"):
                await sleep_yes_no(f"{order_id} should have been cancelled")

        return

        # multiple orders +
        # cancellations = await self.exchange.cancel_all(10)

        # check ws create order update and balance update

        # connect to ws order book and make sure 1 update is received

        # to check no methods were left untested, run test pure mm strategy


if __name__ == '__main__':
    ec = ExchangeClient()
    try:
        asyncio.run(ec.start())
    except KeyboardInterrupt as e:
        print(e)
