import asyncio
import logging
import time

from collections import defaultdict
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
)

import aiohttp
import pandas as pd
from bidict import bidict

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
from hummingbot.connector.exchange.binance import binance_utils
from hummingbot.connector.exchange.binance.binance_order_book import BinanceOrderBook
from hummingbot.connector.utils import build_api_factory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTMethod, RESTResponse, WSRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BinanceAPIOrderBookDataSource(OrderBookTrackerDataSource):

    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    DIFF_EVENT_TYPE = "depthUpdate"
    TRADE_EVENT_TYPE = "trade"

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}

    def __init__(self,
                 trading_pairs: List[str],
                 domain="com",
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory()
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    async def get_last_traded_prices(cls,
                                     trading_pairs: List[str],
                                     domain: str = "com",
                                     api_factory: Optional[WebAssistantsFactory] = None,
                                     throttler: Optional[AsyncThrottler] = None) -> Dict[str, float]:
        """
        Return a dictionary the trading_pair as key and the current price as value for each trading pair passed as
        parameter
        :param trading_pairs: list of trading pairs to get the prices for
        :param domain: which Binance domain we are connecting to (the default value is 'com')
        :param api_factory: the instance of the web assistant factory to be used when doing requests to the server.
        If no instance is provided then a new one will be created.
        :param throttler: the instance of the throttler to use to limit request to the server. If it is not specified
        the function will create a new one.
        :return: Dictionary of associations between token pair and its latest price
        """
        local_api_factory = api_factory or build_api_factory()
        rest_assistant = await local_api_factory.get_rest_assistant()
        local_throttler = throttler or cls._get_throttler_instance()
        tasks = [cls._get_last_traded_price(t_pair, domain, rest_assistant, local_throttler) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @staticmethod
    @async_ttl_cache(ttl=2, maxsize=1)
    async def get_all_mid_prices(domain="com") -> Optional[Decimal]:
        local_api_factory = build_api_factory()
        rest_assistant = await local_api_factory.get_rest_assistant()
        throttler = BinanceAPIOrderBookDataSource._get_throttler_instance()

        url = binance_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain)
        request = RESTRequest(method=RESTMethod.GET, url=url)

        async with throttler.execute_task(limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL):
            resp: RESTResponse = await rest_assistant.call(request=request)
            resp_json = await resp.json()

        ret_val = {}
        for record in resp_json:
            pair = await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                symbol=record["symbol"],
                domain=domain)
            ret_val[pair] = (Decimal(record.get("bidPrice", "0")) + Decimal(record.get("askPrice", "0"))) / Decimal("2")
        return ret_val

    @classmethod
    async def trading_pair_symbol_map(
            cls,
            domain: str = "com",
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None
    ):
        if domain not in cls._trading_pair_symbol_map or not cls._trading_pair_symbol_map[domain]:
            await cls._init_trading_pair_symbols(domain, api_factory, throttler)

        return cls._trading_pair_symbol_map[domain]

    @staticmethod
    async def exchange_symbol_associated_to_pair(
            trading_pair: str,
            domain="com",
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
    ) -> str:
        symbol_map = await BinanceAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            api_factory=api_factory,
            throttler=throttler)
        return symbol_map.inverse[trading_pair]

    @staticmethod
    async def trading_pair_associated_to_exchange_symbol(
            symbol: str,
            domain="com",
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None) -> str:

        symbol_map = await BinanceAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain,
            api_factory=api_factory,
            throttler=throttler)
        return symbol_map[symbol]

    @staticmethod
    async def fetch_trading_pairs(domain="com") -> List[str]:
        mapping = await BinanceAPIOrderBookDataSource.trading_pair_symbol_map(domain=domain)
        return list(mapping.values())

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair, 1000)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        message_queue = self._message_queue[self.TRADE_EVENT_TYPE]
        while True:
            try:
                json_msg = await message_queue.get()

                if "result" in json_msg:
                    continue
                trade_msg: OrderBookMessage = BinanceOrderBook.trade_message_from_exchange(json_msg)
                output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public trade updates from exchange")

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        message_queue = self._message_queue[self.DIFF_EVENT_TYPE]
        while True:
            try:
                json_msg = await message_queue.get()
                if "result" in json_msg:
                    continue
                order_book_message: OrderBookMessage = BinanceOrderBook.diff_message_from_exchange(
                    json_msg, time.time())
                output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public order book updates from exchange")

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair=trading_pair)
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().error(f"Unexpected error fetching order book snapshot for {trading_pair}.",
                                            exc_info=True)
                        await self._sleep(5.0)
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await self._sleep(5.0)

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.WSS_URL.format(self._domain),
                                 ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                await self._subscribe_channels(ws)

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if "result" in data:
                        continue
                    event_type = data.get("e")
                    if event_type in [self.DIFF_EVENT_TYPE, self.TRADE_EVENT_TYPE]:
                        self._message_queue[event_type].put_nowait(data)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def get_snapshot(
            self,
            trading_pair: str,
            limit: int = 1000) -> Dict[str, Any]:

        rest_assistant = await self._get_rest_assistant()
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair)
        }
        if limit != 0:
            params["limit"] = str(limit)

        url = binance_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain)
        request = RESTRequest(method=RESTMethod.GET, url=url, params=params)

        async with self._throttler.execute_task(limit_id=CONSTANTS.SNAPSHOT_PATH_URL):
            response: RESTResponse = await rest_assistant.call(request=request)
            if response.status != 200:
                raise IOError(f"Error fetching market snapshot for {trading_pair}. "
                              f"Response: {response}.")
            data = await response.json()

        return data

    async def _create_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize WebSocket client for APIOrderBookDataSource
        """
        try:
            return await aiohttp.ClientSession().ws_connect(url=CONSTANTS.WSS_URL.format(self._domain),
                                                            heartbeat=self.HEARTBEAT_TIME_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occurred when connecting to WebSocket server. "
                                  f"Error: {e}")
            raise

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            payload = {
                "method": "SUBSCRIBE",
                "params":
                    [f"{(await self.exchange_symbol_associated_to_pair(trading_pair)).lower()}@trade"
                        for trading_pair in self._trading_pairs],
                "id": 1
            }
            subscribe_trade_request: WSRequest = WSRequest(payload=payload)

            payload = {
                "method": "SUBSCRIBE",
                "params":
                    [
                        f"{(await self.exchange_symbol_associated_to_pair(trading_pair)).lower()}@depth@100ms"
                        for trading_pair in self._trading_pairs
                    ],
                "id": 2
            }
            subscribe_orderbook_request: WSRequest = WSRequest(payload=payload)

            await ws.send(subscribe_trade_request)
            await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @classmethod
    async def _get_last_traded_price(cls,
                                     trading_pair: str,
                                     domain: str,
                                     rest_assistant: RESTAssistant,
                                     throttler: AsyncThrottler) -> float:

        url = binance_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain)
        request = RESTRequest(
            method=RESTMethod.GET,
            url=f"{url}?symbol={binance_utils.convert_to_exchange_trading_pair(trading_pair)}")

        async with throttler.execute_task(limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL):
            resp: RESTResponse = await rest_assistant.call(request=request)
            if resp.status == 200:
                resp_json = await resp.json()
                return float(resp_json["lastPrice"])

    @classmethod
    async def _init_trading_pair_symbols(
            cls,
            domain: str = "com",
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None):
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation

        """
        mapping = bidict()
        cls._trading_pair_symbol_map[domain] = mapping

        local_api_factory = api_factory or build_api_factory()
        rest_assistant = await local_api_factory.get_rest_assistant()
        local_throttler = throttler or cls._get_throttler_instance()
        url = binance_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=domain)
        request = RESTRequest(method=RESTMethod.GET, url=url)

        try:
            async with local_throttler.execute_task(limit_id=CONSTANTS.EXCHANGE_INFO_PATH_URL):
                response: RESTResponse = await rest_assistant.call(request=request)
                if response.status == 200:
                    data = await response.json()
                    for symbol_data in data["symbols"]:
                        if symbol_data["status"] == "TRADING" and "SPOT" in symbol_data["permissions"]:
                            mapping[symbol_data["symbol"]] = f"{symbol_data['baseAsset']}-{symbol_data['quoteAsset']}"
        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange infor ({str(ex)})")

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
