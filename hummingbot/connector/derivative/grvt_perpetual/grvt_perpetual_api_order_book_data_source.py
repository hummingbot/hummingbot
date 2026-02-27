import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import (
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GrvtPerpetualDerivative


class GrvtPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "GrvtPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        ex_pair = convert_to_exchange_trading_pair(trading_pair)
        try:
            resp = await self._connector._api_get(
                path_url=CONSTANTS.GET_FUNDING_PATH,
                params={"instrument": ex_pair},
                is_auth_required=False,
            )
            entries = resp.get("fundingRates", [])
            if entries:
                entry = entries[0]
                return FundingInfo(
                    trading_pair=trading_pair,
                    index_price=Decimal(str(entry.get("indexPrice", "0"))),
                    mark_price=Decimal(str(entry.get("markPrice", "0"))),
                    next_funding_utc_timestamp=int(entry.get("nextFundingTime", time.time() + 3600)),
                    rate=Decimal(str(entry.get("fundingRate", "0"))),
                )
        except Exception:
            self.logger().exception(f"Error fetching funding info for {trading_pair}")
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal("0"),
            mark_price=Decimal("0"),
            next_funding_utc_timestamp=int(time.time()) + 3600,
            rate=Decimal("0"),
        )

    async def get_new_order_book(self, trading_pair: str) -> Any:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        snapshot_msg = self.snapshot_message_from_exchange(snapshot, time.time(), {"trading_pair": trading_pair})
        order_book = self._connector.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_pair = convert_to_exchange_trading_pair(trading_pair)
        resp = await self._connector._api_get(
            path_url=CONSTANTS.GET_ORDER_BOOK_PATH,
            params={"instrument": ex_pair},
            is_auth_required=False,
        )
        return resp

    def snapshot_message_from_exchange(
        self,
        msg: Dict[str, Any],
        timestamp: float,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        trading_pair = metadata.get("trading_pair", "") if metadata else ""
        bids = [[Decimal(str(b["price"])), Decimal(str(b["size"]))] for b in msg.get("bids", [])]
        asks = [[Decimal(str(a["price"])), Decimal(str(a["size"]))] for a in msg.get("asks", [])]
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {"trading_pair": trading_pair, "bids": bids, "asks": asks, "update_id": int(timestamp * 1e3)},
            timestamp=timestamp,
        )

    def trade_message_from_exchange(
        self,
        msg: Dict[str, Any],
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        trading_pair = metadata.get("trading_pair", "") if metadata else ""
        ts = int(msg.get("eventTime", time.time() * 1e9)) / 1e9
        trade_type = TradeType.BUY if msg.get("isBuyingBase", True) else TradeType.SELL
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": trading_pair,
                "trade_type": float(trade_type.value),
                "trade_id": msg.get("tradeId", str(ts)),
                "price": msg.get("price", "0"),
                "amount": msg.get("size", "0"),
            },
            timestamp=ts,
        )

    async def _subscribe_channels(self, ws: WSAssistant):
        for trading_pair in self._trading_pairs:
            ex_pair = convert_to_exchange_trading_pair(trading_pair)
            # Subscribe to order book snapshots
            await ws.send(WSJSONRequest(payload={
                "op": "subscribe",
                "channel": CONSTANTS.WS_BOOK_SNAPSHOT,
                "instrument": ex_pair,
            }))
            # Subscribe to public trades
            await ws.send(WSJSONRequest(payload={
                "op": "subscribe",
                "channel": CONSTANTS.WS_TRADE,
                "instrument": ex_pair,
            }))
            # Subscribe to funding info
            await ws.send(WSJSONRequest(payload={
                "op": "subscribe",
                "channel": CONSTANTS.WS_CANDLE,
                "instrument": ex_pair,
                "interval": "1d",
            }))

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.wss_market_url(self._domain),
            ping_timeout=30,
        )
        return ws

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if not isinstance(data, dict):
                continue
            channel = data.get("channel", "")
            feed = data.get("feed", {})
            instrument = data.get("instrument", "")
            trading_pair = convert_from_exchange_trading_pair(instrument)

            if channel == CONSTANTS.WS_BOOK_SNAPSHOT:
                msg = self.snapshot_message_from_exchange(feed, time.time(), {"trading_pair": trading_pair})
                self._message_queue[self._snapshot_messages_queue_key].put_nowait(msg)
            elif channel == CONSTANTS.WS_BOOK_DELTA:
                # Apply delta as a diff message
                bids = [[Decimal(str(b["price"])), Decimal(str(b["size"]))] for b in feed.get("bids", [])]
                asks = [[Decimal(str(a["price"])), Decimal(str(a["size"]))] for a in feed.get("asks", [])]
                msg = OrderBookMessage(
                    OrderBookMessageType.DIFF,
                    {
                        "trading_pair": trading_pair,
                        "bids": bids,
                        "asks": asks,
                        "update_id": int(time.time() * 1e3),
                    },
                    timestamp=time.time(),
                )
                self._message_queue[self._diff_messages_queue_key].put_nowait(msg)
            elif channel == CONSTANTS.WS_TRADE:
                trades = feed if isinstance(feed, list) else [feed]
                for trade in trades:
                    msg = self.trade_message_from_exchange(trade, {"trading_pair": trading_pair})
                    self._message_queue[self._trade_messages_queue_key].put_nowait(msg)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in order book snapshot listener. Reconnecting...")
                await asyncio.sleep(5)

    async def listen_for_subscriptions(self):
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in order book subscription listener. Reconnecting...")
                await asyncio.sleep(5)

    async def listen_for_funding_info(self, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    funding_info = await self.get_funding_info(trading_pair)
                    output.put_nowait(FundingInfoUpdate(
                        trading_pair=funding_info.trading_pair,
                        index_price=funding_info.index_price,
                        mark_price=funding_info.mark_price,
                        next_funding_utc_timestamp=funding_info.next_funding_utc_timestamp,
                        rate=funding_info.rate,
                    ))
                await asyncio.sleep(CONSTANTS.FUNDING_RATE_UPDATE_INTERVAL_SECOND)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in funding info listener.")
                await asyncio.sleep(30)
