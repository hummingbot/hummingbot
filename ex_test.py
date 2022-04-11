import sys
import time
import logging
import asyncio
from distutils.util import strtobool
import functools

from decimal import Decimal
from bidict import bidict
# from async_timeout import timeout

from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType  # , TradeType
from hummingbot.core.event.event_logger import EventLogger
import hummingbot.logger.logger
from hummingbot.logger.logger import HummingbotLogger
import hummingbot.core.pubsub

from certs import creds


class Prompt:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.q = asyncio.Queue()
        self.loop.add_reader(sys.stdin, self.got_input)

    def got_input(self):
        asyncio.ensure_future(self.q.put(sys.stdin.readline()), loop=self.loop)

    async def __call__(self, msg, end='\n', flush=False):
        print(msg, end=end, flush=flush)
        return (await self.q.get()).rstrip('\n')


async_input = None


class TestingHL(HummingbotLogger):
    @staticmethod
    def is_testing_mode() -> bool:
        return True


# disable triggering of Application instantiation
hummingbot.logger.logger.HummingbotLogger = TestingHL

logging.getLogger().setLevel(logging.DEBUG)


async def sleep_yes_no(question):
    await asyncio.sleep(3)
    while True:
        try:
            answer = await async_input("\n--> " + question + " [y/n]")
            print("\n")
            answer = strtobool(answer.lower())
            if not answer:
                print('sleep for 5')
                await asyncio.sleep(5)
            else:
                return answer
        except ValueError:
            pass


async def proceed(question):
    while True:
        try:
            answer = await async_input("\n--> " + question + " [y/n]")
            print("\n")
            return strtobool(answer.lower())
        except ValueError:
            pass


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
    log_records = []

    def handle(self, log):
        print('handle ', log)
        self.log_records.append(log)

    def _initialize_event_loggers(self):
        self.event_logger = EventLogger()
        # TODO subscribe to other events?
        for event in self.exchange.MARKET_EVENTS:
            self.exchange.add_listener(event, self.event_logger)
            print(event)

    def set_trading_pair(self, base, quote):
        self.base_asset = base
        self.quote_asset = quote
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.exchange_trading_pair = f"{self.base_asset}{self.quote_asset}"
        self.symbol = f"{self.base_asset}{self.quote_asset}"

    async def start(self) -> None:
        self.base = "ETH"
        self.quote = "USDT"
        self.pair = f"{self.base}-{self.quote}"
        self.set_trading_pair(self.base, self.quote)
        self.exchange = get_gate_io(self.trading_pair)
        # self.exchange = get_binance(self.trading_pair)
        # TODO
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

        tasks = [
            self.loop_clock(),
            self.tests()
        ]
        await asyncio.gather(*tasks)

    async def loop_clock(self):
        while True:
            ts = time.time()
            # print(f'ticking {ts}')
            self.exchange.tick(ts)
            await asyncio.sleep(1)

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.00001)),
                min_price_increment=Decimal(str(0.00001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    async def tests(self):
        self._simulate_trading_rules_initialized()
        # TODO Unclosed client session
        await self.exchange.start_network()

        r = await self.exchange._update_balances()
        print(r)
        r = await self.exchange.check_network()
        print(r)

        global async_input
        prompt = Prompt()
        async_input = functools.partial(prompt, end='', flush=True)
        await asyncio.sleep(3)

        if await proceed("run two failed orders?"):
            # this one will fail for the 1% margin:
            # "Add 1% as a safety factor in case the prices changed while making the order."
            order_id = self.exchange.buy(self.pair, amount=Decimal(0.1), price=Decimal(1), order_type=OrderType.LIMIT)
            order_id = self.exchange.buy(self.pair, amount=Decimal(1000000), price=Decimal(1), order_type=OrderType.LIMIT)
            await sleep_yes_no("Two order should have failed.")

        if await proceed("run buy succeeeds then cancel?"):
            order_id = self.exchange.buy(self.pair, amount=Decimal(1.5), price=Decimal(1.5), order_type=OrderType.LIMIT)
            await sleep_yes_no(f"LIMIT buy {order_id} should have succeeded")
            order_id = self.exchange.cancel(self.pair, order_id)
            await sleep_yes_no(f"{order_id} should have been canceled")

        if await proceed("run buy and cancel via web?"):
            order_id = self.exchange.buy(self.pair, amount=Decimal(1.1), price=Decimal(1.1), order_type=OrderType.LIMIT)
            await sleep_yes_no(f"{order_id} should have been placed")
            if await proceed("did you delete it via web?"):
                await sleep_yes_no(f"{order_id} should have been cancelled")

        return

        # multiple orders +
        if await proceed("run buy and cancel via web?"):
            pass  # cancellations = await self.exchange.cancel_all(10)

        # check ws create order update and balance update
        if await proceed("run buy and cancel via web?"):
            pass

        # ws order book and make sure updates are received

        # to check no methods were left untested, run test pure mm strategy


if __name__ == '__main__':
    ec = ExchangeClient()
    try:
        asyncio.run(ec.start())
    except KeyboardInterrupt as e:
        print(e)
