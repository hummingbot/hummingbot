#!/usr/bin/env python

import asyncio
from collections import deque, defaultdict
import logging
import time
from typing import (
    Deque,
    Dict,
    List,
    Optional,
    Set
)
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTracker,
    OrderBookTrackerDataSourceType
)
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.market.bamboo_relay.bamboo_relay_api_order_book_data_source import BambooRelayAPIOrderBookDataSource
from hummingbot.market.bamboo_relay.bamboo_relay_order_book_message import BambooRelayOrderBookMessage
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessageType,
    OrderBookMessage
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.market.bamboo_relay.bamboo_relay_order_book_tracker_entry import BambooRelayOrderBookTrackerEntry
from hummingbot.market.bamboo_relay.bamboo_relay_order_book import BambooRelayOrderBook
from hummingbot.market.bamboo_relay.bamboo_relay_active_order_tracker import BambooRelayActiveOrderTracker
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.market.bamboo_relay.bamboo_relay_constants import (
    BAMBOO_RELAY_REST_ENDPOINT,
    BAMBOO_RELAY_TEST_ENDPOINT
)


class BambooRelayOrderBookTracker(OrderBookTracker):
    _brobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._brobt_logger is None:
            cls._brobt_logger = logging.getLogger(__name__)
        return cls._brobt_logger

    def __init__(self,
                 data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 chain: EthereumChain = EthereumChain.MAIN_NET):
        super().__init__(data_source_type=data_source_type)

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[OrderBookTrackerDataSource] = None
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, BambooRelayOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[BambooRelayOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, BambooRelayActiveOrderTracker] = defaultdict(BambooRelayActiveOrderTracker)
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._chain = chain
        if chain is EthereumChain.ROPSTEN:
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "ropsten/0x"
            self._network_id = 3
        elif chain is EthereumChain.RINKEBY:
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "rinkeby/0x"
            self._network_id = 4
        elif chain is EthereumChain.KOVAN:
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "kovan/0x"
            self._network_id = 42
        elif chain is EthereumChain.ZEROEX_TEST:
            self._api_endpoint = BAMBOO_RELAY_TEST_ENDPOINT
            self._api_prefix = "testrpc/0x"
            self._network_id = 1337
        else:
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "main/0x"
            self._network_id = 1

    def get_active_order_tracker(self, trading_pair: str) -> BambooRelayActiveOrderTracker:
        if trading_pair not in self._active_order_trackers:
            raise ValueError(f"{trading_pair} is not being actively tracked.")
        return self._active_order_trackers[trading_pair]

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.EXCHANGE_API:
                self._data_source = BambooRelayAPIOrderBookDataSource(trading_pairs=self._trading_pairs, chain=self._chain)
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "bamboo_relay"

    async def start(self):
        await super().start()
        self._order_book_diff_listener_task = safe_ensure_future(
            self.data_source.listen_for_order_book_diffs(self._ev_loop, self._order_book_diff_stream)
        )
        self._order_book_snapshot_listener_task = safe_ensure_future(
            self.data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
        self._refresh_tracking_task = safe_ensure_future(
            self._refresh_tracking_loop()
        )
        self._order_book_diff_router_task = safe_ensure_future(
            self._order_book_diff_router()
        )
        self._order_book_snapshot_router_task = safe_ensure_future(
            self._order_book_snapshot_router()
        )

    async def _refresh_tracking_tasks(self):
        """
        Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.
        """
        tracking_trading_pairs: Set[str] = set([key for key in self._tracking_tasks.keys()
                                               if not self._tracking_tasks[key].done()])
        available_pairs: Dict[str, BambooRelayOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
        available_trading_pairs: Set[str] = set(available_pairs.keys())
        new_trading_pairs: Set[str] = available_trading_pairs - tracking_trading_pairs
        deleted_trading_pairs: Set[str] = tracking_trading_pairs - available_trading_pairs

        for trading_pair in new_trading_pairs:
            order_book_tracker_entry: BambooRelayOrderBookTrackerEntry = available_pairs[trading_pair]
            self._active_order_trackers[trading_pair] = order_book_tracker_entry.active_order_tracker
            self._order_books[trading_pair] = order_book_tracker_entry.order_book
            self._tracking_message_queues[trading_pair] = asyncio.Queue()
            self._tracking_tasks[trading_pair] = safe_ensure_future(self._track_single_book(trading_pair))
            self.logger().info("Started order book tracking for %s.", trading_pair)

        for trading_pair in deleted_trading_pairs:
            self._tracking_tasks[trading_pair].cancel()
            del self._tracking_tasks[trading_pair]
            del self._order_books[trading_pair]
            del self._active_order_trackers[trading_pair]
            del self._tracking_message_queues[trading_pair]
            self.logger().info("Stopped order book tracking for %s.", trading_pair)

    async def _order_book_diff_router(self):
        """
        Route the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        messages_queued: int = 0
        messages_accepted: int = 0
        messages_rejected: int = 0
        address_token_map: Dict[str, any] = await self._data_source.get_all_token_info(self._api_endpoint, self._api_prefix)
        while True:
            try:
                ob_message: BambooRelayOrderBookMessage = await self._order_book_diff_stream.get()
                base_token_address: str = ob_message.content["actions"][0]["event"]["baseTokenAddress"]
                quote_token_address: str = ob_message.content["actions"][0]["event"]["quoteTokenAddress"]
                base_token_asset: str = address_token_map[base_token_address]["symbol"]
                quote_token_asset: str = address_token_map[quote_token_address]["symbol"]
                trading_pair: str = f"{base_token_asset}-{quote_token_asset}"

                if trading_pair not in self._tracking_message_queues:
                    messages_queued += 1
                    # Save diff messages received before snapshots are ready
                    self._saved_message_queues[trading_pair].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: BambooRelayOrderBook = self._order_books[trading_pair]

                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)

                for action in ob_message.content["actions"]:
                    if action["action"] == "FILL":  # put FILL messages to trade queue
                        trade_type = float(TradeType.BUY.value) if action["event"]["type"] == "BUY" \
                            else float(TradeType.SELL.value)
                        self._order_book_trade_stream.put_nowait(OrderBookMessage(OrderBookMessageType.TRADE, {
                            "trading_pair": trading_pair,
                            "trade_type": trade_type,
                            "trade_id": ob_message.update_id,
                            "update_id": ob_message.timestamp,
                            "price": action["event"]["order"]["price"],
                            "amount": action["event"]["filledBaseTokenAmount"]
                        }, timestamp=ob_message.timestamp))

                messages_accepted += 1

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug("Diff messages processed: %d, rejected: %d, queued: %d",
                                        messages_accepted,
                                        messages_rejected,
                                        messages_queued)
                    messages_accepted = 0
                    messages_rejected = 0
                    messages_queued = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error routing order book messages.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error routing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    async def _track_single_book(self, trading_pair: str):
        past_diffs_window: Deque[BambooRelayOrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: BambooRelayOrderBook = self._order_books[trading_pair]
        active_order_tracker: BambooRelayActiveOrderTracker = self._active_order_trackers[trading_pair]

        while True:
            try:
                message: BambooRelayOrderBookMessage = None
                saved_messages: Deque[BambooRelayOrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    # Diff message just refreshes the entire snapshot
                    bids, asks = active_order_tracker.convert_diff_message_to_order_book_row(message)
                    order_book.apply_snapshot(bids, asks, message.update_id)
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    s_bids, s_asks = active_order_tracker.convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)

                    self.logger().debug("Processed order book snapshot for %s.", trading_pair)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error tracking order book for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error tracking order book. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)
