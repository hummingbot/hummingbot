#!/usr/bin/env python

import asyncio
import logging
import pandas as pd
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.logger import HummingbotLogger
from hummingbot.market.stablecoinswap.stablecoinswap_order_book import StablecoinswapOrderBook
from hummingbot.market.market_base import MarketBase
import hummingbot.market.stablecoinswap.stablecoinswap_contracts as stablecoinswap_contracts


class StablecoinswapBlockchainOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _stlaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._stlaobds_logger is None:
            cls._stlaobds_logger = logging.getLogger(__name__)
        return cls._stlaobds_logger

    def __init__(self,
                 stl_contract: stablecoinswap_contracts.Stablecoinswap,
                 symbols: Optional[List[str]] = None):
        super().__init__()
        self._symbols: Optional[List[str]] = symbols
        self._stl_cont = stl_contract

    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        pass

    async def get_trading_pairs(self) -> List[str]:
        if not self._symbols:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._symbols = active_markets.index.tolist()
            except Exception:
                self._symbols = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg=f"Error getting active exchange information. Check network connection."
                )
        return self._symbols

    async def get_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        base_asset, quote_asset = MarketBase. \
            split_symbol(trading_pair)

        exchange_rate = await self._stl_cont.get_exchange_rate(base_asset,
                                                               quote_asset)

        base_asset_token = self._stl_cont.get_token(base_asset)
        quote_asset_token = self._stl_cont.get_token(quote_asset)
        base_asset_decimals = await base_asset_token.get_decimals()
        quote_asset_decimals = await quote_asset_token.get_decimals()
        base_asset_balance = base_asset_token._contract.functions.balanceOf(
            stablecoinswap_contracts.STABLECOINSWAP_ADDRESS).call() \
            / 10 ** base_asset_decimals
        quote_asset_balance = quote_asset_token._contract.functions.balanceOf(
            stablecoinswap_contracts.STABLECOINSWAP_ADDRESS).call() \
            / 10 ** quote_asset_decimals

        snapshot: Dict[str, Any] = {
            "bids": [[
                exchange_rate,
                quote_asset_balance / float(exchange_rate)
            ]],
            "asks": [[
                exchange_rate,
                base_asset_balance
            ]],
        }

        return snapshot

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        trading_pairs: List[str] = await self.get_trading_pairs()
        retval: Dict[str, OrderBookTrackerEntry] = {}

        number_of_pairs: int = len(trading_pairs)
        for index, trading_pair in enumerate(trading_pairs):
            try:
                snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair)
                snapshot_msg: OrderBookMessage = StablecoinswapOrderBook.snapshot_message_from_exchange(
                    snapshot,
                    metadata={"symbol": trading_pair},
                    timestamp=time.time()
                )
                order_book: OrderBook = self.order_book_create_function()
                order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                retval[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_msg.timestamp, order_book)
                self.logger().info(f"Initialized order book for {trading_pair}. "
                                   f"{index + 1}/{number_of_pairs} completed.")
                await asyncio.sleep(10.0)
            except Exception:
                self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                await asyncio.sleep(5)

        return retval

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()

                for trading_pair in trading_pairs:
                    try:
                        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair)
                        snapshot_message: OrderBookMessage = StablecoinswapOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            metadata={"symbol": trading_pair},
                            timestamp=time.time()
                        )
                        output.put_nowait(snapshot_message)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        await asyncio.sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().error("Unexpected error.", exc_info=True)
                        await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
