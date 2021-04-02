#!/usr/bin/env python

import asyncio
from collections import deque, defaultdict
import logging
import time
from typing import (
    Deque,
    Dict,
    List,
    Optional
)
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_api_order_book_data_source import BambooRelayAPIOrderBookDataSource
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_order_book_message import BambooRelayOrderBookMessage
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessageType,
    OrderBookMessage
)
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_order_book import BambooRelayOrderBook
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_active_order_tracker import BambooRelayActiveOrderTracker
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_constants import (
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
                 trading_pairs: List[str],
                 chain: EthereumChain = EthereumChain.MAIN_NET):
        super().__init__(data_source=BambooRelayAPIOrderBookDataSource(trading_pairs, chain),
                         trading_pairs=trading_pairs)
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, BambooRelayOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[BambooRelayOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, BambooRelayActiveOrderTracker] = defaultdict(BambooRelayActiveOrderTracker)
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
    def exchange_name(self) -> str:
        return "bamboo_relay"

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
                    self.logger().debug(f"Diff messages processed: {messages_accepted}, "
                                        f"rejected: {messages_rejected}, queued: {messages_queued}")
                    messages_accepted = 0
                    messages_rejected = 0
                    messages_queued = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f'{"Unexpected error routing order book messages."}',
                    exc_info=True,
                    app_warning_msg=f'{"Unexpected error routing order book messages. Retrying after 5 seconds."}'
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

                    self.logger().debug(f"Processed order book snapshot for {trading_pair}.")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error tracking order book for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg=f'{"Unexpected error tracking order book. Retrying after 5 seconds."}'
                )
                await asyncio.sleep(5.0)
