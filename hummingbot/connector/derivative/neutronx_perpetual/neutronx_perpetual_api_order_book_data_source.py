import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from neutronx_sdk.indexer import (
    CHANNEL_ORDERBOOK,
    CHANNEL_TICKER,
    CHANNEL_TRADES,
    OrderbookV1,
    TickerV1,
    TradeV1,
    compact_pair,
)
from neutronx_sdk.indexer.api import orderbook_path

from hummingbot.connector.derivative.neutronx_perpetual import neutronx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.neutronx_perpetual.data_sources import indexer_stream, translators
from hummingbot.connector.derivative.neutronx_perpetual.data_sources.indexer_stream import Subscription
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_derivative import (
        NeutronxPerpetualDerivative,
    )

PAIR_CHANNELS = (CHANNEL_ORDERBOOK, CHANNEL_TRADES, CHANNEL_TICKER)


class NeutronxPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: "NeutronxPerpetualDerivative",
        api_factory: WebAssistantsFactory,
    ) -> None:
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._groups: List[List[Subscription]] = []
        self._sockets: Dict[int, WSAssistant] = {}
        self._group_tasks: List[asyncio.Task] = []
        self._update_ids: Dict[str, int] = {}
        self._queue_keys = {
            CHANNEL_ORDERBOOK: self._snapshot_messages_queue_key,
            CHANNEL_TRADES: self._trade_messages_queue_key,
            CHANNEL_TICKER: self._funding_info_messages_queue_key,
        }

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        tickers = await self._connector.tickers()
        prices = {}
        for trading_pair in trading_pairs:
            ticker = tickers.get(compact_pair(trading_pair))
            price = None if ticker is None else ticker.last_price or ticker.mark_price
            if price is not None:
                prices[trading_pair] = float(price)
        return prices

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        ticker = await self._connector.ticker(trading_pair)
        if ticker is None:
            raise IOError(f"the NeutronX indexer has no ticker for {trading_pair}")
        return translators.funding_info(ticker, trading_pair)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        await self._connector.trading_pair_symbol_map()
        raw = await self._connector.request_indexer(
            orderbook_path(translators.to_exchange_pair(trading_pair)),
            params={"depth": CONSTANTS.ORDER_BOOK_SNAPSHOT_DEPTH},
        )
        return self._snapshot(OrderbookV1.from_json(raw), trading_pair)

    async def listen_for_subscriptions(self):
        await self._connector.trading_pair_symbol_map()
        self._groups = indexer_stream.group(self._subscriptions(self._trading_pairs), self._connector.max_subscriptions)
        self._group_tasks = [asyncio.ensure_future(self._listen_group(index)) for index in range(len(self._groups))]
        try:
            await asyncio.gather(*self._group_tasks)
        finally:
            for task in self._group_tasks:
                task.cancel()
            self._group_tasks = []

    async def _listen_group(self, index: int) -> None:
        while True:
            ws: Optional[WSAssistant] = None
            try:
                ws = await indexer_stream.connect(self._api_factory, self._connector.network, self._connector.api_key)
                self._sockets[index] = ws
                await indexer_stream.subscribe(ws, self._groups[index])
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The NeutronX order book stream closed ({connection_exception})")
            except Exception:
                self.logger().exception("Unexpected error on the NeutronX order book stream. Retrying in 1 second...")
                await self._sleep(1.0)
            finally:
                self._sockets.pop(index, None)
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        return await indexer_stream.connect(self._api_factory, self._connector.network, self._connector.api_key)

    async def _subscribe_channels(self, ws: WSAssistant) -> None:
        await indexer_stream.subscribe(ws, self._subscriptions(self._trading_pairs))

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant) -> None:
        async with indexer_stream.heartbeat(websocket_assistant):
            await super()._process_websocket_messages(websocket_assistant)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        frame = indexer_stream.parse_frame(event_message, self.logger())
        if not frame.is_data or frame.channel is None:
            return ""
        if frame.channel == CHANNEL_TRADES and frame.is_snapshot:
            return ""
        return self._queue_keys.get(frame.channel, "")

    async def _parse_order_book_snapshot_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ) -> None:
        for row in indexer_stream.parse_frame(raw_message, self.logger()).rows():
            book = OrderbookV1.from_json(row)
            trading_pair = self._connector.trading_pair_for_indexer(book.pair)
            if trading_pair is not None:
                message_queue.put_nowait(self._snapshot(book, trading_pair))

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue) -> None:
        for row in indexer_stream.parse_frame(raw_message, self.logger()).rows():
            trade = TradeV1.from_json(row)
            trading_pair = self._connector.trading_pair_for_indexer(trade.pair)
            if trading_pair is not None:
                message_queue.put_nowait(translators.trade_message(trade, trading_pair, self._mid_price(trading_pair)))

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue) -> None:
        for row in indexer_stream.parse_frame(raw_message, self.logger()).rows():
            ticker = TickerV1.from_json(row)
            trading_pair = self._connector.trading_pair_for_indexer(ticker.pair)
            if trading_pair is not None:
                message_queue.put_nowait(translators.funding_info_update(ticker, trading_pair))

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        subscriptions = self._subscriptions([trading_pair])
        capacity = self._connector.max_subscriptions
        index = next(
            (i for i, group in enumerate(self._groups) if len(group) + len(subscriptions) <= capacity),
            None,
        )
        if index is None:
            self._groups.append(list(subscriptions))
            self._group_tasks.append(asyncio.ensure_future(self._listen_group(len(self._groups) - 1)))
            return True
        self._groups[index].extend(subscriptions)
        ws = self._sockets.get(index)
        if ws is not None:
            await indexer_stream.subscribe(ws, subscriptions)
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        subscriptions = set(self._subscriptions([trading_pair]))
        for index, group in enumerate(self._groups):
            removed = [subscription for subscription in group if subscription in subscriptions]
            if not removed:
                continue
            self._groups[index] = [subscription for subscription in group if subscription not in subscriptions]
            ws = self._sockets.get(index)
            if ws is not None:
                await indexer_stream.unsubscribe(ws, removed)
        return True

    @staticmethod
    def _subscriptions(trading_pairs: List[str]) -> List[Subscription]:
        return [
            (channel, translators.to_exchange_pair(trading_pair))
            for trading_pair in trading_pairs
            for channel in PAIR_CHANNELS
        ]

    def _snapshot(self, book: OrderbookV1, trading_pair: str) -> OrderBookMessage:
        update_id = translators.next_update_id(self._update_ids.get(trading_pair, 0))
        self._update_ids[trading_pair] = update_id
        return translators.snapshot_message(book, trading_pair, update_id, update_id * 1e-3)

    def _mid_price(self, trading_pair: str) -> Optional[Decimal]:
        try:
            mid = self._connector.get_mid_price(trading_pair)
        except Exception:
            return None
        return mid if mid is not None and mid.is_finite() else None
