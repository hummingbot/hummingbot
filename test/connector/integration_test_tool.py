import asyncio
import functools
import logging
import sys
import time
from decimal import Decimal
from distutils.util import strtobool

import aiohttp

import hummingbot.core.web_assistant.connections.rest_connection
import hummingbot.logger.logger
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger.logger import HummingbotLogger

from certs import creds  # isort: skip <- this module with the dictionary inside has to be created to provide the keys

this_loop = asyncio.get_event_loop()


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


class PrintingQueue(asyncio.Queue):
    def _get(self):
        elem = self._queue.popleft()
        print(f"\nPrintingQueue _user_stream_event_listener event_message: {elem}")
        return elem


class TestingHL(HummingbotLogger):
    @staticmethod
    def is_testing_mode() -> bool:
        return True


ENABLE_CONNECTION_TRACING = False


class RESTConnection(hummingbot.core.web_assistant.connections.rest_connection.RESTConnection):
    def __init__(self, aiohttp_client_session: aiohttp.ClientSession):
        if ENABLE_CONNECTION_TRACING:
            request_tracing = aiohttp.TraceConfig()
            request_tracing.on_request_start.append(self.on_request_start)
            request_tracing.on_request_end.append(self.on_request_end)
            request_tracing.on_request_chunk_sent.append(self.chunk_sent)
            aiohttp_client_session = aiohttp.ClientSession(trace_configs=[request_tracing])
        self._client_session = aiohttp_client_session

    @staticmethod
    async def on_request_start(session, trace_config_ctx, params):
        print("\non_request_start %s %s %s" % (params.method, params.url, params.headers))

    @staticmethod
    async def on_request_end(session, trace_config_ctx, params):
        print("\non_request_end %s %s %s" % (params.method, params.url, params.headers))

    @staticmethod
    async def chunk_sent(session, trace_config_ctx, params):
        print("\nchunk_sent %s %s" % (params.url, params.chunk))


# To add connection tracing
hummingbot.core.web_assistant.connections.rest_connection.RESTConnection = RESTConnection

# To disable triggering of Application instantiation
hummingbot.logger.logger.HummingbotLogger = TestingHL
logging.getLogger().setLevel(logging.DEBUG)


from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange  # noqa: E402
from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange  # noqa: E402

# Has to be after connection tracing override of RESTConnection
from hummingbot.connector.trading_rule import TradingRule  # noqa: E402
from hummingbot.core.data_type.common import OrderType  # noqa: E402
from hummingbot.core.event.event_logger import EventLogger  # noqa: E402


async def sleep_yes_no(question):
    await asyncio.sleep(3)
    while True:
        try:
            answer = await async_input("\n--> " + question + " [y/n] ")
            print("\n")
            answer = strtobool(answer.lower())
            if not answer:
                print("\n--> " + 'sleep for 5\n')
                await asyncio.sleep(5)
            else:
                return answer
        except ValueError:
            pass


async def proceed(question):
    while True:
        try:
            answer = await async_input("\n--> " + question + " [y/n] ")
            print("\n")
            return strtobool(answer.lower())
        except ValueError:
            pass


def get_binance(ec):
    exchange = BinanceExchange(
        binance_api_key=creds.k,
        binance_api_secret=creds.s,
        trading_pairs=[ec.pair],
    )
    return exchange


def get_gate_io(ec):
    exchange = GateIoExchange(
        gate_io_api_key=creds.k,
        gate_io_secret_key=creds.s,
        trading_pairs=[ec.pair],
    )
    return exchange


class ExchangeClient(object):
    # level is required to receive logs from the data source logger
    level = 0
    log_records = []
    DEBUG = False

    def handle(self, record):
        fmt = '%(levelname)s\t[%(filename)s]\t[%(funcName)s] |\t%(message)s'
        formatter = logging.Formatter(fmt)
        print(formatter.format(record))

    def initialize_exchange_loggers(self):
        def config_logger(obj):
            obj.logger().setLevel(self.level)
            obj.logger().addHandler(self)
        objs = (
            self.exchange,
            self.exchange._time_synchronizer,
            self.exchange._order_tracker,
            self.exchange._user_stream_tracker,
            self.exchange._order_book_tracker,
            self.exchange._userstream_ds,
            self.exchange._orderbook_ds,
        )
        for obj in objs:
            config_logger(obj)

    def initialize_event_loggers(self):
        self.event_logger = EventLogger()
        # TODO subscribe to other events?
        for event in self.exchange.MARKET_EVENTS:
            self.exchange.add_listener(event, self.event_logger)
            print("subscribing event_logger to ", event)

    def set_trading_pair(self, base, quote):
        self.base = base
        self.quote = quote
        self.pair = f"{self.base}-{self.quote}"

    def debug(self, msg):
        if self.DEBUG:
            print(msg)

    async def loop_clock(self):
        """ This will trigger _status_polling_loop via self._poll_notifier.wait() """
        while True:
            ts = time.time()
            self.exchange.tick(ts)
            debug_msg = f"ticking {ts}\n" \
                        f"UST recv time: {self.exchange._user_stream_tracker.last_recv_time}\n" \
                        f"OBT recv time: {self.exchange._user_stream_tracker.last_recv_time}\n"
            self.debug(debug_msg)
            await asyncio.sleep(1)

    def set_test_trading_rules(self):
        self.exchange._trading_rules = {
            self.pair: TradingRule(
                trading_pair=self.pair,
                min_order_size=Decimal(str(0.000001)),
                min_price_increment=Decimal(str(0.000001)),
                min_base_amount_increment=Decimal(str(0.000001)),
                max_order_size=Decimal(str(0.001)),
            )
        }
        print("Trading rules: ", self.exchange._trading_rules)

    async def start(self):
        self.set_trading_pair("ETH", "USDT")

        self.exchange = get_gate_io(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._user_stream_tracker._user_stream = PrintingQueue()

        self.initialize_exchange_loggers()
        self.initialize_event_loggers()

        tasks = [
            self.loop_clock(),
            self.exchange.start_network(),
            self.tests()
        ]
        await asyncio.gather(*tasks)

    async def update_order_status(self):
        print("ORDERS: ", [o.to_json() for o in self.exchange.in_flight_orders.values()])
        await self.exchange._update_order_status()

    async def tests(self):
        global async_input
        prompt = Prompt()
        async_input = functools.partial(prompt, end='', flush=True)

        global ENABLE_CONNECTION_TRACING

        # wait for network init
        while True:
            await asyncio.sleep(5)

            r = await self.exchange.check_network()
            print(f'\n{r}')
            if r == NetworkStatus.CONNECTED:
                print("Exchange status: ", self.exchange.status_dict)
                # Can be used to test for invalid keys
                # api_keys = { "gate_io_api_key": creds.k, "gate_io_secret_key": creds.s, }
                # await UserBalances.instance().add_exchange(self.exchange.name, **api_keys)
                print('\n')
                break

        self.exchange.supported_order_types()

        if await proceed("run buy and cancel via web + update order status?"):
            order_id = self.exchange.buy(self.pair, amount=Decimal(1.5), price=Decimal(1.5), order_type=OrderType.LIMIT)
            await sleep_yes_no(f"{order_id} should have been placed")
            while await proceed("run update order status?"):
                await self.update_order_status()

        if await proceed("(will spend USDT) buy LIMIT with last_trade_price and run update order status?"):
            trade_price = self.exchange.get_order_book(self.pair).last_trade_price
            order_id = self.exchange.buy(
                self.pair,
                amount=Decimal(0.001),
                price=Decimal(trade_price),
                order_type=OrderType.LIMIT)
            while await proceed("run update order status?"):
                await self.update_order_status()

        if await proceed("run two failed orders?"):
            # this one will fail for:
            # "Add 1% as a safety factor in case the prices changed while making the order."
            order_id = self.exchange.buy(self.pair, amount=Decimal(0.1), price=Decimal(1), order_type=OrderType.LIMIT)
            order_id = self.exchange.buy(self.pair, amount=Decimal(1000000), price=Decimal(1), order_type=OrderType.LIMIT)
            await sleep_yes_no("Two order should have failed.")

        if await proceed("run buy succeeeds then cancel?"):
            order_id = self.exchange.buy(self.pair, amount=Decimal(1.5), price=Decimal(1.5), order_type=OrderType.LIMIT)
            await sleep_yes_no(f"LIMIT buy {order_id} should have succeeded")
            order_id = self.exchange.cancel(self.pair, order_id)
            await sleep_yes_no(f"{order_id} should have been canceled")

        if await proceed("3 orders and cancel_all?"):
            order_id = self.exchange.buy(self.pair, amount=Decimal(1.1), price=Decimal(1.1), order_type=OrderType.LIMIT)
            order_id = self.exchange.buy(self.pair, amount=Decimal(1.2), price=Decimal(1.2), order_type=OrderType.LIMIT)
            order_id = self.exchange.buy(self.pair, amount=Decimal(1.3), price=Decimal(1.3), order_type=OrderType.LIMIT)
            if await proceed("orders created?"):
                cancellations = await self.exchange.cancel_all(10)
                print(cancellations)


if __name__ == '__main__':
    ec = ExchangeClient()
    try:
        # asyncio.run(ec.start())
        this_loop.run_until_complete(ec.start())
    except KeyboardInterrupt as e:
        print(e)
