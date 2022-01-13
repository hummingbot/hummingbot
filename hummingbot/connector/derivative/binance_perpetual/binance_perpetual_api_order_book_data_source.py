import asyncio
import copy
import logging
import time

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

from bidict import bidict, ValueDuplicationError

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils
import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_order_book import BinancePerpetualOrderBook
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTRequest,
    RESTResponse,
    WSRequest,
    WSResponse,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BinancePerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
        self,
        trading_pairs: List[str] = None,
        domain: str = CONSTANTS.DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
        api_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__(trading_pairs)
        self._api_factory: WebAssistantsFactory = api_factory or utils.build_api_factory()
        self._ws_assistant: Optional[WSAssistant] = None
        self._order_book_create_function = lambda: OrderBook()
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()
        self._funding_info: Dict[str, FundingInfo] = {}

        self._message_queue: Dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)

    @property
    def funding_info(self) -> Dict[str, FundingInfo]:
        return copy.deepcopy(self._funding_info)

    def is_funding_info_initialized(self) -> bool:
        return all(trading_pair in self._funding_info for trading_pair in self._trading_pairs)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobds_logger is None:
            cls._bpobds_logger = logging.getLogger(__name__)
        return cls._bpobds_logger

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    @classmethod
    async def get_last_traded_prices(cls,
                                     trading_pairs: List[str],
                                     domain: str = CONSTANTS.DOMAIN) -> Dict[str, float]:
        tasks = [cls.get_last_traded_price(t_pair, domain) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls,
                                    trading_pair: str,
                                    domain: str = CONSTANTS.DOMAIN,
                                    api_factory: WebAssistantsFactory = None) -> float:
        api_factory = api_factory or utils.build_api_factory()
        rest_assistant = await api_factory.get_rest_assistant()

        throttler = cls._get_throttler_instance()

        url = utils.rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL, domain=domain)
        params = {"symbol": await cls.convert_to_exchange_trading_pair(
            hb_trading_pair=trading_pair,
            domain=domain,
            throttler=throttler)}

        async with throttler.execute_task(CONSTANTS.TICKER_PRICE_CHANGE_URL):
            request = RESTRequest(
                method=RESTMethod.GET,
                url=url,
                params=params,
            )
            resp = await rest_assistant.call(request=request)
            resp_json = await resp.json()
            return float(resp_json["lastPrice"])

    @classmethod
    def trading_pair_symbol_map_ready(cls, domain: str = CONSTANTS.DOMAIN):
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized
        :param domain: the domain of the exchange being used
        :return: True if the mapping has been initialized, False otherwise
        """
        return domain in cls._trading_pair_symbol_map and len(cls._trading_pair_symbol_map[domain]) > 0

    @classmethod
    async def trading_pair_symbol_map(
            cls,
            domain: Optional[str] = CONSTANTS.DOMAIN,
            throttler: Optional[AsyncThrottler] = None,
            api_factory: WebAssistantsFactory = None
    ) -> Mapping[str, str]:
        if not cls.trading_pair_symbol_map_ready(domain=domain):
            async with cls._mapping_initialization_lock:
                # Check condition again (could have been initialized while waiting for the lock to be released)
                if not cls.trading_pair_symbol_map_ready(domain=domain):
                    await cls.init_trading_pair_symbols(domain, throttler, api_factory)

        return cls._trading_pair_symbol_map[domain]

    @classmethod
    async def init_trading_pair_symbols(
        cls,
        domain: str = CONSTANTS.DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
        api_factory: WebAssistantsFactory = None
    ):
        """Initialize _trading_pair_symbol_map class variable"""
        mapping = bidict()

        api_factory = api_factory or utils.build_api_factory()
        rest_assistant = await api_factory.get_rest_assistant()

        url = utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=domain)
        throttler = throttler or cls._get_throttler_instance()

        try:
            async with throttler.execute_task(limit_id=CONSTANTS.EXCHANGE_INFO_URL):
                request = RESTRequest(
                    method=RESTMethod.GET,
                    url=url,
                )
                response = await rest_assistant.call(request=request, timeout=10)

                if response.status == 200:
                    data = await response.json()
                    # fetch d["pair"] for binance perpetual
                    for symbol_data in filter(utils.is_exchange_information_valid, data["symbols"]):
                        try:
                            mapping[symbol_data["pair"]] = combine_to_hb_trading_pair(
                                symbol_data["baseAsset"],
                                symbol_data["quoteAsset"])
                        except ValueDuplicationError:
                            continue
        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")

        cls._trading_pair_symbol_map[domain] = mapping

    @staticmethod
    async def fetch_trading_pairs(
        domain: str = CONSTANTS.DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
        api_factory: WebAssistantsFactory = None
    ) -> List[str]:
        ob_source_cls = BinancePerpetualAPIOrderBookDataSource
        trading_pair_list: List[str] = []
        symbols_map = await ob_source_cls.trading_pair_symbol_map(domain=domain, throttler=throttler, api_factory=api_factory)
        trading_pair_list.extend(list(symbols_map.values()))

        return trading_pair_list

    @classmethod
    async def convert_from_exchange_trading_pair(
            cls,
            exchange_trading_pair: str,
            domain: str = CONSTANTS.DOMAIN,
            throttler: Optional[AsyncThrottler] = None) -> str:

        symbol_map = await cls.trading_pair_symbol_map(
            domain=domain,
            throttler=throttler)
        try:
            pair = symbol_map[exchange_trading_pair]
        except KeyError:
            raise ValueError(f"There is no symbol mapping for exchange trading pair {exchange_trading_pair}")

        return pair

    @classmethod
    async def convert_to_exchange_trading_pair(
            cls,
            hb_trading_pair: str,
            domain = CONSTANTS.DOMAIN,
            throttler: Optional[AsyncThrottler] = None) -> str:

        symbol_map = await cls.trading_pair_symbol_map(
            domain=domain,
            throttler=throttler)
        try:
            symbol = symbol_map.inverse[hb_trading_pair]
        except KeyError:
            raise ValueError(f"There is no symbol mapping for trading pair {hb_trading_pair}")

        return symbol

    @staticmethod
    async def get_snapshot(
            trading_pair: str,
            limit: int = 1000,
            domain: str = CONSTANTS.DOMAIN,
            throttler: Optional[AsyncThrottler] = None,
            api_factory: WebAssistantsFactory = None
    ) -> Dict[str, Any]:
        ob_source_cls = BinancePerpetualAPIOrderBookDataSource
        try:
            api_factory = api_factory or utils.build_api_factory()
            rest_assistant = await api_factory.get_rest_assistant()

            params = {"symbol": await ob_source_cls.convert_to_exchange_trading_pair(
                hb_trading_pair=trading_pair,
                domain=domain,
                throttler=throttler)}
            if limit != 0:
                params.update({"limit": str(limit)})
            url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain)
            throttler = throttler or ob_source_cls._get_throttler_instance()
            async with throttler.execute_task(limit_id=CONSTANTS.SNAPSHOT_REST_URL):
                request = RESTRequest(
                    method=RESTMethod.GET,
                    url=url,
                    params=params,
                )
                response = await rest_assistant.call(request=request)
                if response.status != 200:
                    raise IOError(f"Error fetching Binance market snapshot for {trading_pair}.")
                data: Dict[str, Any] = await response.json()
                return data
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair, 1000, self._domain, self._throttler, self._api_factory)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
            snapshot, snapshot_timestamp, metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def _get_funding_info_from_exchange(self, trading_pair: str) -> FundingInfo:
        """
        Fetches the funding information of the given trading pair from the exchange REST API. Parses and returns the
        respsonse as a FundingInfo data object.

        :param trading_pair: Trading pair of which its Funding Info is to be fetched
        :type trading_pair: str
        :return: Funding Information of the given trading pair
        :rtype: FundingInfo
        """
        rest_assistant = await self._api_factory.get_rest_assistant()

        params = {"symbol": await self.convert_to_exchange_trading_pair(
            hb_trading_pair=trading_pair,
            domain=self._domain,
            throttler=self._throttler)}

        async with self._get_throttler_instance().execute_task(limit_id=CONSTANTS.MARK_PRICE_URL):
            url = utils.rest_url(CONSTANTS.MARK_PRICE_URL, self._domain)
            request: RESTRequest = RESTRequest(method=RESTMethod.GET, url=url, params=params)
            response: RESTResponse = await rest_assistant.call(request)

            if response.status != 200:
                error_response = await response.json()
                self.logger().error(
                    f"Unable to fetch FundingInfo for {trading_pair}. Error: {error_response}", exc_info=True
                )
                return None

            data: Dict[str, Any] = await response.json()
            funding_info = FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal(data["indexPrice"]),
                mark_price=Decimal(data["markPrice"]),
                next_funding_utc_timestamp=int(data["nextFundingTime"]),
                rate=Decimal(data["lastFundingRate"]),
            )

        return funding_info

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Returns the FundingInfo of the specified trading pair. If it does not exist, it will query the REST API.
        """
        if trading_pair not in self._funding_info:
            self._funding_info[trading_pair] = await self._get_funding_info_from_exchange(trading_pair)
        return self._funding_info[trading_pair]

    async def _subscribe_to_order_book_streams(self) -> WSAssistant:
        url = f"{utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain)}"
        ws: WSAssistant = await self._get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)

        stream_id_channel_pairs = [
            (CONSTANTS.DIFF_STREAM_ID, "@depth"),
            (CONSTANTS.TRADE_STREAM_ID, "@aggTrade"),
            (CONSTANTS.FUNDING_INFO_STREAM_ID, "@markPrice"),
        ]
        for stream_id, channel in stream_id_channel_pairs:
            params = []
            for trading_pair in self._trading_pairs:
                symbol = await self.convert_to_exchange_trading_pair(
                    hb_trading_pair=trading_pair,
                    domain=self._domain,
                    throttler=self._throttler)
                params.append(f"{symbol.lower()}{channel}")
            payload = {
                "method": "SUBSCRIBE",
                "params": params,
                "id": stream_id,
            }
            subscribe_request: WSRequest = WSRequest(payload)
            await ws.send(subscribe_request)

        return ws

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws = await self._subscribe_to_order_book_streams()

                async for msg in ws.iter_messages():
                    if "result" in msg.data:
                        continue
                    if "@depth" in msg.data["stream"]:
                        self._message_queue[CONSTANTS.DIFF_STREAM_ID].put_nowait(msg)
                    elif "@aggTrade" in msg.data["stream"]:
                        self._message_queue[CONSTANTS.TRADE_STREAM_ID].put_nowait(msg)
                    elif "@markPrice" in msg.data["stream"]:
                        self._message_queue[CONSTANTS.FUNDING_INFO_STREAM_ID].put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Websocket connection. Retrying after 30 seconds...", exc_info=True
                )
                await self._sleep(30.0)
            finally:
                ws and await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            msg = await self._message_queue[CONSTANTS.DIFF_STREAM_ID].get()
            timestamp: float = time.time()
            msg.data["data"]["s"] = await self.convert_from_exchange_trading_pair(
                exchange_trading_pair=msg.data["data"]["s"],
                domain=self._domain,
                throttler=self._throttler)
            order_book_message: OrderBookMessage = BinancePerpetualOrderBook.diff_message_from_exchange(
                msg.data, timestamp
            )
            output.put_nowait(order_book_message)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            msg = await self._message_queue[CONSTANTS.TRADE_STREAM_ID].get()
            msg.data["data"]["s"] = await self.convert_from_exchange_trading_pair(
                exchange_trading_pair=msg.data["data"]["s"],
                domain=self._domain,
                throttler=self._throttler)
            trade_message: OrderBookMessage = BinancePerpetualOrderBook.trade_message_from_exchange(msg.data)
            output.put_nowait(trade_message)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot: Dict[str, Any] = await self.get_snapshot(
                        trading_pair, domain=self._domain, throttler=self._throttler, api_factory=self._api_factory
                    )
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
                        snapshot, snapshot_timestamp, metadata={"trading_pair": trading_pair}
                    )
                    output.put_nowait(snapshot_msg)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                delta = CONSTANTS.ONE_HOUR - time.time() % CONSTANTS.ONE_HOUR
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds...", exc_info=True
                )
                await self._sleep(5.0)

    async def listen_for_funding_info(self):
        """
        Listen for funding information events received through the websocket channel to update the respective
        FundingInfo for all active trading pairs.
        """
        while True:
            try:
                funding_info_message: WSResponse = await self._message_queue[CONSTANTS.FUNDING_INFO_STREAM_ID].get()
                data: Dict[str, Any] = funding_info_message.data["data"]

                trading_pair: str = await self.convert_from_exchange_trading_pair(
                    exchange_trading_pair=data["s"],
                    domain=self._domain,
                    throttler=self._throttler)

                if trading_pair not in self._trading_pairs:
                    continue

                self._funding_info.update(
                    {
                        trading_pair: FundingInfo(
                            trading_pair=trading_pair,
                            index_price=Decimal(data["i"]),
                            mark_price=Decimal(data["p"]),
                            next_funding_utc_timestamp=int(data["T"]),
                            rate=Decimal(data["r"]),
                        )
                    }
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error occured updating funding information. Retrying in 5 seconds... Error: {str(e)}",
                    exc_info=True,
                )
                await self._sleep(5.0)
