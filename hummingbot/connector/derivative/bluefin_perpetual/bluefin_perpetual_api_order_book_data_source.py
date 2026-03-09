"""
Order book data source for Bluefin Perpetual connector.

This data source consumes market events from the Bluefin SDK wrapper and
adapts them to Hummingbot order book and funding info messages.
"""
import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.bluefin_perpetual import bluefin_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bluefin_perpetual.data_sources.bluefin_data_source import BluefinDataSource
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative import (
        BluefinPerpetualDerivative,
    )


class BluefinPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    """Order book data source for Bluefin Perpetual."""

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "BluefinPerpetualDerivative",
        data_source: BluefinDataSource,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._data_source = data_source
        self._domain = domain

        # Funding info cache keyed by HB trading pair
        self._last_funding_info: Dict[str, FundingInfo] = {}
        self._last_oracle_prices: Dict[str, Decimal] = {}
        self._last_mark_prices: Dict[str, Decimal] = {}

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        del domain
        prices: Dict[str, float] = {}
        for trading_pair in trading_pairs:
            ticker = await self._data_source.get_market_ticker(trading_pair)
            prices[trading_pair] = float(self._data_source.from_e9(getattr(ticker, "last_trade_price_e9", "0")))
        return prices

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        try:
            ticker = await self._data_source.get_market_ticker(trading_pair)
            funding_info = FundingInfo(
                trading_pair=trading_pair,
                index_price=self._data_source.from_e9(getattr(ticker, "oracle_price_e9", "0")),
                mark_price=self._data_source.from_e9(getattr(ticker, "mark_price_e9", "0")),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=self._data_source.from_e9(getattr(ticker, "predicted_funding_rate_e9", "0")),
            )
            self._last_funding_info[trading_pair] = funding_info
            return funding_info
        except (AttributeError, TypeError, ValueError, ArithmeticError):
            return self._last_funding_info.get(
                trading_pair,
                FundingInfo(
                    trading_pair=trading_pair,
                    index_price=Decimal("0"),
                    mark_price=Decimal("0"),
                    next_funding_utc_timestamp=self._next_funding_time(),
                    rate=Decimal("0"),
                ),
            )

    async def listen_for_funding_info(self, output: asyncio.Queue[Any]):
        while True:
            try:
                event = await self._data_source.get_market_funding_event()
                await self._parse_funding_info_message(raw_message=event, message_queue=output)
            except (AttributeError, TypeError, ValueError):
                self.logger().exception("Error processing funding info from Bluefin stream")
                await asyncio.sleep(5)

    async def _parse_funding_info_message(self, raw_message: Any, message_queue: asyncio.Queue[Any]):
        symbol = self._data_source.bluefin_to_hb_symbol(getattr(raw_message, "symbol", ""))
        if not symbol:
            return

        oracle_price_e9 = getattr(raw_message, "oracle_price_e9", None)
        mark_price_e9 = getattr(raw_message, "mark_price_e9", None)

        if oracle_price_e9 is not None:
            self._last_oracle_prices[symbol] = self._data_source.from_e9(oracle_price_e9)
        if mark_price_e9 is not None:
            self._last_mark_prices[symbol] = self._data_source.from_e9(mark_price_e9)

        if symbol in self._last_oracle_prices and symbol in self._last_mark_prices:
            funding_info = FundingInfo(
                trading_pair=symbol,
                index_price=self._last_oracle_prices[symbol],
                mark_price=self._last_mark_prices[symbol],
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal("0"),
            )
            self._last_funding_info[symbol] = funding_info
            message_queue.put_nowait(
                FundingInfoUpdate(
                    trading_pair=symbol,
                    index_price=funding_info.index_price,
                    mark_price=funding_info.mark_price,
                    next_funding_utc_timestamp=funding_info.next_funding_utc_timestamp,
                    rate=funding_info.rate,
                )
            )

    async def _parse_trade_message(self, raw_message: Any, message_queue: asyncio.Queue[Any]):
        trades = getattr(raw_message, "trades", None)
        if not trades:
            return

        for trade in trades:
            trading_pair = self._data_source.bluefin_to_hb_symbol(getattr(trade, "symbol", ""))
            if not trading_pair:
                continue

            side = str(getattr(getattr(trade, "side", None), "value", getattr(trade, "side", ""))).upper()
            trade_type = float(TradeType.BUY.value) if side == "LONG" else float(TradeType.SELL.value)
            price = self._data_source.from_e9(getattr(trade, "price_e9", "0"))
            amount = self._data_source.from_e9(getattr(trade, "quantity_e9", "0"))
            ts_ms = int(getattr(trade, "executed_at_millis", int(time.time() * 1000)))

            message_queue.put_nowait(
                OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content={
                        "trade_id": str(getattr(trade, "id", ts_ms)),
                        "trading_pair": trading_pair,
                        "trade_type": trade_type,
                        "amount": str(amount),
                        "price": str(price),
                    },
                    timestamp=ts_ms * 1e-3,
                )
            )

    async def _parse_order_book_diff_message(self, raw_message: Any, message_queue: asyncio.Queue[Any]):
        bids_e9 = getattr(raw_message, "bids_e9", None)
        asks_e9 = getattr(raw_message, "asks_e9", None)
        symbol = getattr(raw_message, "symbol", None)
        if bids_e9 is None or asks_e9 is None or symbol is None:
            return

        trading_pair = self._data_source.bluefin_to_hb_symbol(symbol)
        update_id = int(getattr(raw_message, "last_update_id", getattr(raw_message, "updated_at_millis", 0)))
        timestamp_ms = int(getattr(raw_message, "updated_at_millis", int(time.time() * 1000)))

        message_queue.put_nowait(
            OrderBookMessage(
                OrderBookMessageType.DIFF,
                {
                    "trading_pair": trading_pair,
                    "update_id": update_id,
                    "bids": self._convert_levels_from_e9(bids_e9),
                    "asks": self._convert_levels_from_e9(asks_e9),
                },
                timestamp=timestamp_ms * 1e-3,
            )
        )

    async def _parse_order_book_snapshot_message(self, raw_message: Any, message_queue: asyncio.Queue[Any]):
        bids_e9 = getattr(raw_message, "bids_e9", None)
        asks_e9 = getattr(raw_message, "asks_e9", None)
        symbol = getattr(raw_message, "symbol", None)
        if bids_e9 is None or asks_e9 is None or symbol is None:
            return

        trading_pair = self._data_source.bluefin_to_hb_symbol(symbol)
        update_id = int(getattr(raw_message, "orderbook_update_id", getattr(raw_message, "updated_at_millis", 0)))
        timestamp_ms = int(getattr(raw_message, "updated_at_millis", int(time.time() * 1000)))

        message_queue.put_nowait(
            OrderBookMessage(
                OrderBookMessageType.SNAPSHOT,
                {
                    "trading_pair": trading_pair,
                    "update_id": update_id,
                    "bids": self._convert_levels_from_e9(bids_e9),
                    "asks": self._convert_levels_from_e9(asks_e9),
                },
                timestamp=timestamp_ms * 1e-3,
            )
        )

    async def _request_order_book_snapshot(self, trading_pair: str) -> Any:
        return await self._data_source.get_orderbook(trading_pair)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        update_id = int(getattr(snapshot_response, "last_update_id", getattr(snapshot_response, "updated_at_millis", 0)))
        timestamp_ms = int(getattr(snapshot_response, "updated_at_millis", int(time.time() * 1000)))

        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": self._convert_levels_from_e9(getattr(snapshot_response, "bids_e9", [])),
                "asks": self._convert_levels_from_e9(getattr(snapshot_response, "asks_e9", [])),
            },
            timestamp=timestamp_ms * 1e-3,
        )

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue[Any]):
        while True:
            try:
                event = await self._data_source.get_market_order_book_event()
                event_name = type(event).__name__
                if event_name == "OrderbookDiffDepthUpdate":
                    await self._parse_order_book_diff_message(event, output)
                elif event_name == "OrderbookPartialDepthUpdate":
                    await self._parse_order_book_snapshot_message(event, output)
            except (AttributeError, TypeError, ValueError):
                self.logger().exception("Error processing order book/trade updates from Bluefin stream")
                await asyncio.sleep(5)

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue[Any]):
        while True:
            try:
                event = await self._data_source.get_market_trade_event()
                await self._parse_trade_message(event, output)
            except (AttributeError, TypeError, ValueError):
                self.logger().exception("Error processing trade updates from Bluefin stream")
                await asyncio.sleep(5)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue[Any]):
        while True:
            await asyncio.sleep(60)

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if trading_pair not in self._trading_pairs:
            self._trading_pairs.append(trading_pair)
        # The underlying SDK listener currently uses connection-level subscription setup.
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if trading_pair in self._trading_pairs:
            self._trading_pairs.remove(trading_pair)
        # The SDK listener does not expose per-pair unsubscribe yet.
        return True

    def _next_funding_time(self) -> int:
        current_time = int(time.time())
        return ((current_time // 3600) + 1) * 3600

    def _convert_levels_from_e9(self, levels_e9: List[List[str]]) -> List[List[Decimal]]:
        converted: List[List[Decimal]] = []
        for level in levels_e9:
            if len(level) < 2:
                continue
            converted.append([
                self._data_source.from_e9(level[0]),
                self._data_source.from_e9(level[1]),
            ])
        return converted
