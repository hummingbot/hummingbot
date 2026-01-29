import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.architect_perpetual.architect_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.architect_perpetual.architect_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
        ArchitectPerpetualDerivative,
    )


class ArchitectPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'ArchitectPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._funding_info_messages_queue_key = "funding_info"
        self._snapshot_messages_queue_key = "order_book_snapshot"
        self._l1_subscription_tasks: Dict[str, asyncio.Task] = {}
        self._l2_subscription_tasks: Dict[str, asyncio.Task] = {}

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        try:
            client = await self._connector._get_architect_client()
            ticker = await client.get_ticker(symbol=trading_pair, venue="AX")

            mark_price = Decimal(str(ticker.mark_price)) if hasattr(ticker, 'mark_price') else Decimal("0")
            index_price = Decimal(str(ticker.index_price)) if hasattr(ticker, 'index_price') else mark_price
            funding_rate = Decimal(str(ticker.funding_rate)) if hasattr(ticker, 'funding_rate') else Decimal("0")

            return FundingInfo(
                trading_pair=trading_pair,
                index_price=index_price,
                mark_price=mark_price,
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=funding_rate,
            )
        except Exception:
            self.logger().exception(f"Error fetching funding info for {trading_pair}")
            return FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal("0"),
                mark_price=Decimal("0"),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal("0"),
            )

    def _next_funding_time(self) -> int:
        current_time = int(time.time())
        funding_interval = 8 * 3600
        return ((current_time // funding_interval) + 1) * funding_interval

    async def listen_for_funding_info(self, output: asyncio.Queue):
        message_queue = self._message_queue[self._funding_info_messages_queue_key]
        while True:
            try:
                funding_info_event = await message_queue.get()
                await self._parse_funding_info_message(funding_info_event, output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public funding info updates from exchange")
                await self._sleep(5)

    async def _parse_funding_info_message(self, msg: Dict[str, Any], output: asyncio.Queue):
        try:
            trading_pair = msg.get("trading_pair")
            if trading_pair:
                funding_info_update = FundingInfoUpdate(
                    trading_pair=trading_pair,
                    index_price=Decimal(str(msg.get("index_price", "0"))),
                    mark_price=Decimal(str(msg.get("mark_price", "0"))),
                    next_funding_utc_timestamp=msg.get("next_funding_timestamp", self._next_funding_time()),
                    rate=Decimal(str(msg.get("funding_rate", "0"))),
                )
                output.put_nowait(funding_info_update)
        except Exception:
            self.logger().exception(f"Error parsing funding info message: {msg}")

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        client = await self._connector._get_architect_client()
        snapshot = await client.get_l2_book_snapshot(symbol=trading_pair, venue="AX")
        return {
            "trading_pair": trading_pair,
            "bids": [(float(level.price), float(level.quantity)) for level in snapshot.bids] if snapshot.bids else [],
            "asks": [(float(level.price), float(level.quantity)) for level in snapshot.asks] if snapshot.asks else [],
            "timestamp": int(time.time() * 1000),
        }

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": snapshot_response["trading_pair"],
                "update_id": snapshot_response["timestamp"],
                "bids": snapshot_response["bids"],
                "asks": snapshot_response["asks"],
            },
            timestamp=snapshot_response["timestamp"]
        )
        return snapshot_msg

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                client = await self._connector._get_architect_client()
                for trading_pair in self._trading_pairs:
                    if trading_pair not in self._l2_subscription_tasks:
                        task = asyncio.create_task(
                            self._subscribe_to_l2_book(client, trading_pair)
                        )
                        self._l2_subscription_tasks[trading_pair] = task
                await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in subscriptions")
                await self._sleep(5)

    async def _subscribe_to_l2_book(self, client, trading_pair: str):
        try:
            async for update in client.stream_l2_book_updates(symbol=trading_pair, venue="AX"):
                message = {
                    "trading_pair": trading_pair,
                    "bids": [(float(level.price), float(level.quantity)) for level in update.bids] if update.bids else [],
                    "asks": [(float(level.price), float(level.quantity)) for level in update.asks] if update.asks else [],
                    "timestamp": int(time.time() * 1000),
                }
                self._message_queue[self._snapshot_messages_queue_key].put_nowait(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error in L2 book subscription for {trading_pair}")

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        message_queue = self._message_queue[self._snapshot_messages_queue_key]
        while True:
            try:
                diff_msg = await message_queue.get()
                order_book_message = OrderBookMessage(
                    OrderBookMessageType.DIFF,
                    {
                        "trading_pair": diff_msg["trading_pair"],
                        "update_id": diff_msg["timestamp"],
                        "bids": diff_msg["bids"],
                        "asks": diff_msg["asks"],
                    },
                    timestamp=diff_msg["timestamp"]
                )
                output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing order book diffs")
                await self._sleep(5)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot_msg = await self._order_book_snapshot(trading_pair)
                    output.put_nowait(snapshot_msg)
                await self._sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when fetching order book snapshots")
                await self._sleep(5)

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            try:
                client = await self._connector._get_architect_client()
                for trading_pair in self._trading_pairs:
                    async for trade in client.stream_trades(symbol=trading_pair, venue="AX"):
                        trade_msg = OrderBookMessage(
                            OrderBookMessageType.TRADE,
                            {
                                "trading_pair": trading_pair,
                                "trade_type": float(TradeType.BUY.value) if trade.side == "buy" else float(TradeType.SELL.value),
                                "trade_id": str(trade.id) if hasattr(trade, 'id') else str(int(time.time() * 1000)),
                                "price": float(trade.price),
                                "amount": float(trade.quantity),
                            },
                            timestamp=int(trade.timestamp * 1000) if hasattr(trade, 'timestamp') else int(time.time() * 1000)
                        )
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when listening for trades")
                await self._sleep(5)

    async def _sleep(self, seconds: float):
        await asyncio.sleep(seconds)
