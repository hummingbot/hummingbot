import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_utils
from hummingbot.connector.exchange.ndax.ndax_order_book import NdaxOrderBook
from hummingbot.connector.exchange.ndax.ndax_order_book_message import NdaxOrderBookEntry, NdaxOrderBookMessage
from hummingbot.connector.exchange.ndax.ndax_utils import convert_to_exchange_trading_pair
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger.logger import HummingbotLogger


class NdaxAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _ORDER_BOOK_SNAPSHOT_DELAY = 60 * 60  # expressed in seconds

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_id_map: Dict[str, int] = {}
    _last_traded_prices: Dict[str, float] = {}

    def __init__(
        self,
        throttler: Optional[AsyncThrottler] = None,
        shared_client: Optional[aiohttp.ClientSession] = None,
        trading_pairs: Optional[List[str]] = None,
        domain: Optional[str] = None,
    ):
        super().__init__(trading_pairs)
        self._shared_client = shared_client or self._get_session_instance()
        self._throttler = throttler or self._get_throttler_instance()
        self._domain: Optional[str] = domain

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @classmethod
    async def init_trading_pair_ids(cls, domain: Optional[str] = None, throttler: Optional[AsyncThrottler] = None, shared_client: Optional[aiohttp.ClientSession] = None):
        """Initialize _trading_pair_id_map class variable
        """
        cls._trading_pair_id_map.clear()

        shared_client = shared_client or cls._get_session_instance()

        params = {
            "OMSId": 1
        }

        throttler = throttler or cls._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.MARKETS_URL):
            async with shared_client.get(
                f"{ndax_utils.rest_api_url(domain) + CONSTANTS.MARKETS_URL}", params=params
            ) as response:
                if response.status == 200:
                    resp_json: Dict[str, Any] = await response.json()

                    results = {
                        f"{instrument['Product1Symbol']}-{instrument['Product2Symbol']}": int(
                            instrument["InstrumentId"])
                        for instrument in resp_json
                        if instrument["SessionStatus"] == "Running"
                    }

                    cls._trading_pair_id_map = results

    @classmethod
    async def get_last_traded_prices(
        cls, trading_pairs: List[str], domain: Optional[str] = None, throttler: Optional[AsyncThrottler] = None, shared_client: Optional[aiohttp.ClientSession] = None
    ) -> Dict[str, float]:
        """Fetches the Last Traded Price of the specified trading pairs.

        :params: List[str] trading_pairs: List of trading pairs(in Hummingbot base-quote format i.e. BTC-CAD)
        :return: Dict[str, float]: Dictionary of the trading pairs mapped to its last traded price in float
        """
        if not len(cls._trading_pair_id_map) > 0:
            await cls.init_trading_pair_ids(domain)

        shared_client = shared_client or cls._get_session_instance()

        results = {}

        for trading_pair in trading_pairs:
            if trading_pair in cls._last_traded_prices:
                results[trading_pair] = cls._last_traded_prices[trading_pair]
            else:
                params = {
                    "OMSId": 1,
                    "InstrumentId": cls._trading_pair_id_map[trading_pair],
                }
                throttler = throttler or cls._get_throttler_instance()
                async with throttler.execute_task(CONSTANTS.LAST_TRADE_PRICE_URL):
                    async with shared_client.get(
                        f"{ndax_utils.rest_api_url(domain) + CONSTANTS.LAST_TRADE_PRICE_URL}", params=params
                    ) as response:
                        if response.status == 200:
                            resp_json: Dict[str, Any] = await response.json()

                            results.update({
                                trading_pair: float(resp_json["LastTradedPx"])
                            })

        return results

    @staticmethod
    async def fetch_trading_pairs(domain: str = None, throttler: Optional[AsyncThrottler] = None) -> List[str]:
        """Fetches and formats all supported trading pairs.

        Returns:
            List[str]: List of supported trading pairs in Hummingbot's format. (i.e. BASE-QUOTE)
        """
        async with aiohttp.ClientSession() as client:
            params = {
                "OMSId": 1
            }
            throttler = throttler or NdaxAPIOrderBookDataSource._get_throttler_instance()
            async with throttler.execute_task(CONSTANTS.MARKETS_URL):
                async with client.get(
                    f"{ndax_utils.rest_api_url(domain) + CONSTANTS.MARKETS_URL}", params=params
                ) as response:
                    if response.status == 200:
                        resp_json: Dict[str, Any] = await response.json()
                        return [f"{instrument['Product1Symbol']}-{instrument['Product2Symbol']}"
                                for instrument in resp_json
                                if instrument["SessionStatus"] == "Running"]
                    return []

    async def get_order_book_data(
        self, trading_pair: str, domain: Optional[str] = None, throttler: Optional[AsyncThrottler] = None
    ) -> Dict[str, any]:
        """Retrieves entire orderbook snapshot of the specified trading pair via the REST API.

        Args:
            trading_pair (str): Trading pair of the particular orderbook.
            domain (str): The label of the variant of the connector that is being used.
            throttler (AsyncThrottler): API-requests throttler to use.

        Returns:
            Dict[str, any]: Parsed API Response.
        """
        if not len(self._trading_pair_id_map) > 0:
            await self.init_trading_pair_ids(domain)
        params = {
            "OMSId": 1,
            "InstrumentId": self._trading_pair_id_map[trading_pair],
            "Depth": 200,
        }

        throttler = throttler or self._get_throttler_instance()
        async with throttler.execute_task(CONSTANTS.ORDER_BOOK_URL):
            async with self._shared_client.get(
                f"{ndax_utils.rest_api_url(domain) + CONSTANTS.ORDER_BOOK_URL}", params=params
            ) as response:
                status = response.status
                if status != 200:
                    raise IOError(
                        f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.ORDER_BOOK_URL}. "
                        f"HTTP {status}. Response: {await response.json()}"
                    )

                response_ls: List[Any] = await response.json()
                orderbook_entries: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry) for entry in response_ls]
                return {"data": orderbook_entries,
                        "timestamp": int(time.time() * 1e3)}

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair, self._domain)

        snapshot_msg: NdaxOrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
            msg=snapshot,
            timestamp=snapshot["timestamp"],
        )
        order_book = self.order_book_create_function()

        bids, asks = snapshot_msg.bids, snapshot_msg.asks
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

        return order_book

    async def get_instrument_ids(self) -> Dict[str, int]:
        if not len(self._trading_pair_id_map) > 0:
            await self.init_trading_pair_ids(self._domain, self._throttler, self._shared_client)
        return self._trading_pair_id_map

    async def _create_websocket_connection(self) -> NdaxWebSocketAdaptor:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            ws = await self._shared_client.ws_connect(ndax_utils.wss_url(self._domain))
            return NdaxWebSocketAdaptor(throttler=self._throttler, websocket=ws)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network(f"Unexpected error occurred during {CONSTANTS.EXCHANGE_NAME} WebSocket Connection "
                                  f"({ex})")
            raise

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Periodically polls for orderbook snapshots using the REST API.
        """
        if not len(self._trading_pair_id_map) > 0:
            await self.init_trading_pair_ids(self._domain, self._throttler, self._shared_client)
        while True:
            await self._sleep(self._ORDER_BOOK_SNAPSHOT_DELAY)
            try:
                for trading_pair in self._trading_pairs:
                    snapshot: Dict[str: Any] = await self.get_order_book_data(trading_pair, domain=self._domain)
                    metadata = {
                        "trading_pair": trading_pair,
                        "instrument_id": self._trading_pair_id_map.get(trading_pair, None)
                    }
                    snapshot_message: NdaxOrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
                        msg=snapshot,
                        timestamp=snapshot["timestamp"],
                        metadata=metadata
                    )
                    output.put_nowait(snapshot_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error occured listening for orderbook snapshots. Retrying in 5 secs...",
                                    exc_info=True)
                await self._sleep(5.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using WebSocket API.
        """
        if not len(self._trading_pair_id_map) > 0:
            await self.init_trading_pair_ids(self._domain, self._throttler, self._shared_client)

        while True:
            try:
                ws_adaptor: NdaxWebSocketAdaptor = await self._create_websocket_connection()
                for trading_pair in self._trading_pairs:
                    payload = {
                        "OMSId": 1,
                        "Symbol": convert_to_exchange_trading_pair(trading_pair),
                        "Depth": 200
                    }
                    async with self._throttler.execute_task(CONSTANTS.WS_ORDER_BOOK_CHANNEL):
                        await ws_adaptor.send_request(endpoint_name=CONSTANTS.WS_ORDER_BOOK_CHANNEL,
                                                      payload=payload)
                async for raw_msg in ws_adaptor.iter_messages():
                    payload = NdaxWebSocketAdaptor.payload_from_raw_message(raw_msg)
                    msg_event: str = NdaxWebSocketAdaptor.endpoint_from_raw_message(raw_msg)
                    if msg_event in [CONSTANTS.WS_ORDER_BOOK_CHANNEL, CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT]:
                        msg_data: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry)
                                                              for entry in payload]
                        msg_timestamp: int = int(time.time() * 1e3)
                        msg_product_code: int = msg_data[0].productPairCode

                        content = {"data": msg_data}
                        msg_trading_pair: Optional[str] = None

                        for trading_pair, instrument_id in self._trading_pair_id_map.items():
                            if msg_product_code == instrument_id:
                                msg_trading_pair = trading_pair
                                break

                        if msg_trading_pair:
                            metadata = {
                                "trading_pair": msg_trading_pair,
                                "instrument_id": msg_product_code,
                            }

                            order_book_message = None
                            if msg_event == CONSTANTS.WS_ORDER_BOOK_CHANNEL:
                                order_book_message: NdaxOrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
                                    msg=content,
                                    timestamp=msg_timestamp,
                                    metadata=metadata)
                            elif msg_event == CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT:
                                order_book_message: NdaxOrderBookMessage = NdaxOrderBook.diff_message_from_exchange(
                                    msg=content,
                                    timestamp=msg_timestamp,
                                    metadata=metadata)
                            self._last_traded_prices[
                                order_book_message.trading_pair] = order_book_message.last_traded_price
                            await output.put(order_book_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                if ws_adaptor:
                    await ws_adaptor.close()
                await self._sleep(30.0)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # NDAX does not have a public orderbook trade channel, rather it can be inferred from the Level2UpdateEvent when
        # subscribed to the SubscribeLevel2 channel
        pass

    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        # This connector does not use this base class method and needs a refactoring
        pass
