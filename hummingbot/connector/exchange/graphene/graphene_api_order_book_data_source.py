# DISABLE SELECT PYLINT TESTS
# pylint: disable=bad-continuation, no-member, broad-except, no-name-in-module
# pylint: disable=arguments-differ
"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
~
forked from binance_api_order_book_data_source v1.0.0
~
"""
# STANDARD MODULES
import asyncio
import logging
import time
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

# METANODE MODULES
from metanode.graphene_metanode_client import GrapheneTrustlessClient

# HUMMINGBOT MODULES
from hummingbot.connector.exchange.graphene.graphene_constants import GrapheneConstants
from hummingbot.connector.exchange.graphene.graphene_order_book import GrapheneOrderBook
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger


class GrapheneAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    connect to metanode to get bid, ask, and market history updates
    """

    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
        self,
        domain: str,
        trading_pairs: List[str],
        **__,
    ):
        # ~ print("GrapheneAPIOrderBookDataSource")
        super().__init__(trading_pairs)
        # ~ self._order_book_create_function = lambda: OrderBook()
        self._order_book_create_function = OrderBook

        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

        self.domain = domain
        self.constants = GrapheneConstants(domain)
        self.metanode = GrapheneTrustlessClient(self.constants)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        """
        a classmethod for logging
        """
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @staticmethod
    async def get_last_traded_prices(
        domain: str,
        *_,
        **__,
    ) -> Dict[str, float]:
        """
        Return a dictionary the trading_pair as key and the current price as value
        for each trading pair passed as parameter
        :param trading_pairs: list of trading pairs to get the prices for
        :param domain: the name of the graphene blockchain
        :return: Dictionary of associations between token pair and its latest price
        """
        constants = GrapheneConstants(domain)
        metanode = GrapheneTrustlessClient(constants)
        metanode_pairs = metanode.pairs  # DISCRETE SQL QUERY
        return {k: v["last"] for k, v in metanode_pairs.items()}

    @staticmethod
    async def get_all_mid_prices(domain: str) -> Dict[str, Decimal]:
        """
        Returns the mid price of all trading pairs,
        obtaining the information from the exchange.
        This functionality is required by the market price strategy.
        :param domain: the name of the graphene blockchain
        :return: Dictionary with the trading pair as key, and the mid price as value
        """
        constants = GrapheneConstants(domain)
        metanode = GrapheneTrustlessClient(constants)
        metanode_pairs = metanode.pairs  # DISCRETE SQL QUERY
        ret = []
        for pair in metanode_pairs:
            ret[pair] = Decimal((pair["book"]["asks"][0] + pair["book"]["bids"][0]) / 2)
        return ret

    @staticmethod
    async def exchange_symbol_associated_to_pair(
        trading_pair: str,
        domain: str,
        **__,
    ) -> str:
        """
        1:1 mapping BASE-QUOTE
        :param trading_pair: BASE-QUOTE
        :param domain: the name of the graphene blockchain
        :return: BASE-QUOTE
        """
        symbol_map = await GrapheneAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain
        )

        return symbol_map.inverse[trading_pair]

    @staticmethod
    async def trading_pair_associated_to_exchange_symbol(
        symbol: str,
        domain: str,
        **__,
    ) -> str:
        """
        Used to translate a trading pair from exchange to client notation
        :param symbol: trading pair in exchange notation
        :param domain: the name of the graphene blockchain
        :return: trading pair in client notation
        """
        symbol_map = await GrapheneAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=domain
        )
        return symbol_map[symbol]

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Creates a local instance of the exchange order book for one pair
        :param trading_pair: BASE-QUOTE
        :return: a local copy of the current order book in the exchange
        """
        msg = await self.get_snapshot(trading_pair)
        snapshot: OrderBookMessage = GrapheneOrderBook.snapshot_message_from_exchange(
            msg=msg,
            timestamp=time.time(),
            metadata={
                "trading_pair": trading_pair,
                "blocktime": self.metanode.timing["blocktime"],
            },
        )
        book = self.order_book_create_function()
        book.apply_snapshot(snapshot.bids, snapshot.asks, snapshot.update_id)
        return book

    async def listen_for_trades(
        self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue
    ):
        """
        reads the trade events queue, for each event
            ~ creates a trade message instance
            ~ adds it to the output queue
        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created trade messages
        """
        # wait for metanode to intialize
        while not 0 < time.time() - self.metanode.timing["blocktime"] < 60:
            await self._sleep(1)
            continue  # SQL QUERY WHILE LOOP
        previous_history = {pair: [] for pair in self.constants.chain.PAIRS}
        while True:
            try:
                metanode_pairs = self.metanode.pairs
                for pair in self.constants.chain.PAIRS:
                    if str(previous_history[pair]) != str(
                        metanode_pairs[pair]["history"]
                    ):
                        new_trades = [
                            i
                            for i in metanode_pairs[pair]["history"]
                            if i not in previous_history[pair]
                        ]
                        for trade in new_trades:
                            # [unix, price, amount, trade_type, sequence]
                            trade_msg: OrderBookMessage = (
                                GrapheneOrderBook.trade_message_from_exchange(
                                    {
                                        "trading_pair": pair,
                                        "trade_type": trade[3],  # trade_type
                                        "trade_id": trade[4],  # sequence
                                        "update_id": trade[0],  # unix
                                        "price": trade[1],  # price
                                        "amount": trade[2],  # amount
                                    }
                                )
                            )
                            output.put_nowait(trade_msg)
                previous_history = {
                    pair: metanode_pairs[pair]["history"]
                    for pair in self.constants.chain.PAIRS
                }
                await self._sleep(3)
            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error when processing public trade updates from"
                    " exchange"
                )

    async def listen_for_order_book_diffs(
        self,
        *_,
        **__,
    ):
        """
        N/A
        """

    async def listen_for_order_book_snapshots(
        self,
        ev_loop: asyncio.AbstractEventLoop,
        output: asyncio.Queue,
    ):
        """
        This method runs continuously and requests the full order book content
        from the exchange every 3 seconds via SQL query to the metanode database
        It then creates a snapshot messages that are added to the output queue
        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created snapshot messages
        """
        while True:
            try:
                for trading_pair in self.constants.chain.PAIRS:
                    try:
                        snapshot: Dict[str, Any] = await self.get_snapshot(
                            trading_pair=trading_pair
                        )
                        snapshot_timestamp: float = time.time()
                        snapshot_msg: OrderBookMessage = (
                            GrapheneOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={
                                    "trading_pair": trading_pair,
                                    "blocktime": self.metanode.timing["blocktime"],
                                },
                            )
                        )
                        output.put_nowait(snapshot_msg)
                        msg = f"Saved order book snapshot for {trading_pair}"
                        self.logger().debug(msg)
                    except asyncio.CancelledError:
                        msg = f"asyncio.CancelledError {__name__}"
                        self.logger().exception(msg)
                        raise
                    except Exception:
                        msg = (
                            "Unexpected error fetching order book snapshot for"
                            f" {trading_pair}."
                        )
                        self.logger().error(msg, exc_info=True)
                        await self._sleep(5.0)
                await self._sleep(3)
            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await self._sleep(5.0)

    async def listen_for_subscriptions(self):
        """
        Graphene does not use this
        """

    async def get_snapshot(
        self,
        trading_pair: str,
        **__,
    ) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for one pair.
        :param trading_pair: BASE-QUOTE
        :param limit: the depth of the order book to retrieve
        :return: the response from the exchange (JSON dictionary)
        """
        metanode = GrapheneTrustlessClient(self.constants)
        return metanode.pairs[trading_pair]["book"]  # Discrete SQL Query

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler([])  # self.constants.RATE_LIMITS)

    @classmethod
    def trade_message_from_exchange(
        cls, msg: Dict[str, any], metadata: Optional[Dict] = None
    ):
        """
        Creates a trade message with info from each trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": (
                    float(TradeType.SELL.value)
                    if msg["trade_type"] == "SELL"
                    else float(TradeType.BUY.value)
                ),
                "trade_id": msg["trade_id"],
                "update_id": msg["update_id"],
                "price": msg["price"],
                "amount": msg["amount"],
            },
            timestamp=int(time.time() * 1e-3),
        )

    @classmethod
    async def _get_last_traded_price(
        cls,
        trading_pair: str,
        domain: str,
        **__,
    ) -> float:
        """
        Return a dictionary the trading_pair as key and the current price as value
        for each trading pair passed as parameter
        :param trading_pairs: list of trading pairs to get the prices for
        :param domain: the name of the graphene blockchain
        :param api_factory: N/A
        :param throttler: N/A
        :return: Dictionary of associations between token pair and its latest price
        """

        constants = GrapheneConstants(domain)
        metanode = GrapheneTrustlessClient(constants)
        return float(metanode.pairs[trading_pair]["last"])  # Discrete SQL Query
