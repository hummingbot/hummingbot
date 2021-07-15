
import aiohttp
import asyncio
import logging
import time

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS

from hummingbot.connector.exchange.ndax.ndax_order_book import NdaxOrderBook
from hummingbot.connector.exchange.ndax.ndax_order_book_message import NdaxOrderBookEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger.logger import HummingbotLogger


class NdaxAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_id_map: Dict[str, int] = {}

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)
        # TODO: Fetch trading pair to instrument id pairing when first initialized.

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    async def init_trading_pair_ids(cls):
        """Initialize _trading_pair_id_map class variable
        """
        cls._trading_pair_id_map.clear()

        results = {}
        params = {
            "OMSId": 1
        }
        async with aiohttp.ClientSession() as client:
            async with client.get(CONSTANTS.MARKETS_URL, params=params) as response:
                if response.status == 200:
                    resp_json: Dict[str, Any] = await response.json()

                    for instrument in resp_json:
                        results.update({
                            f"{instrument['Product1Symbol']}-{instrument['Product2Symbol']}": int(instrument["InstrumentId"])
                        })
        cls._trading_pair_id_map = results

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        """Fetches the Last Traded Price of the specified trading pairs.

        Args:
            trading_pairs (List[str]): List of trading pairs(in Hummingbot base-quote format i.e. BTC-CAD)

        Returns:
            Dict[str, float]: Dictionary of trading pairs to its last traded price in float
        """
        results = {}

        # Fetches and populates trading pair instrument IDs
        await cls.init_trading_pair_ids()

        async with aiohttp.ClientSession() as client:

            for trading_pair in trading_pairs:
                params = {
                    "OMSId": 1,
                    "InstrumentId": cls._trading_pair_id_map[trading_pair],
                    "Depth": 1,
                }
                async with client.get(f"{CONSTANTS.ORDER_BOOK_URL}", params=params) as response:
                    if response.status == 200:
                        resp_json: Dict[str, Any] = await response.json()
                        entry = resp_json[0]

                        results.update({
                            trading_pair: float(entry[4])
                        })

        return results

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        """Fetches and formats all supported trading pairs.

        Returns:
            List[str]: List of supported trading pairs in Hummingbot's format. (i.e. BASE-QUOTE)
        """
        async with aiohttp.ClientSession() as client:
            params = {
                "OMSId": 1
            }
            async with client.get(CONSTANTS.MARKETS_URL, params=params) as response:
                if response.status == 200:
                    resp_json: Dict[str, Any] = await response.json()
                    return [f"{instrument['Product1Symbol']}-{instrument['Product2Symbol']}" for instrument in resp_json]
                return []

    @classmethod
    async def get_order_book_data(cls, trading_pair: str) -> Dict[str, any]:
        """Retrieves entire orderbook snapshot of the specified trading pair via the REST API.

        Args:
            trading_pair (str): Trading pair of the particular orderbook.

        Returns:
            Dict[str, any]: Parsed API Response.
        """
        await cls.init_trading_pair_ids()
        params = {
            "OMSId": 1,
            "InstrumentId": cls._trading_pair_id_map[trading_pair],
            "Depth": 999999,
        }
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{CONSTANTS.ORDER_BOOK_URL}", params=params) as response:
                if response.status != 200:
                    raise IOError(
                        f"Error fetching OrderBook for {trading_pair} at {CONSTANTS.ORDER_BOOK_URL}. "
                        f"HTTP {response.status}. Response: {await response.json()}"
                    )

                response = await response.json()
                orderbook_entries: List[NdaxOrderBookEntry] = [NdaxOrderBookEntry(*entry) for entry in response]
                return {"data": orderbook_entries}

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: int = int(time.time() * 1e3)

        snapshot_msg: OrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
            msg=snapshot,
            timestamp=snapshot_timestamp,
        )
        order_book = self.order_book_create_function()

        bids, asks = snapshot_msg.bids, snapshot_msg.asks
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

        return order_book

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str: Any] = await self.get_new_order_book(trading_pair)
                        metadata = {
                            "trading_pair": trading_pair,
                            "instrument_id": self._trading_pair_id_map.get(trading_pair, None)
                        }
                        snapshot_timestamp: int = int(time.time() * 1e3)
                        snapshot_message: OrderBookMessage = NdaxOrderBook.snapshot_message_from_exchange(
                            msg=snapshot,
                            timestamp=snapshot_timestamp,
                            metadata=metadata
                        )
                        output.put_nowait(snapshot_message)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection."
                        )
                        await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error occured listening for orderbook snapshots. Retrying in 5 secs...",
                                    exc_info=True)
                await asyncio.sleep(5.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
