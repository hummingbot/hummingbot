import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
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
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

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
        self._trade_messages_queue_key = "trade"
        self._diff_messages_queue_key = "order_book_diff"
        self._funding_info_messages_queue_key = "funding_info"
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _exchange_symbol_for_pair(self, trading_pair: str) -> str:
        resolver = getattr(self._connector, "exchange_symbol_for_trading_pair", None)
        if callable(resolver):
            return await resolver(trading_pair=trading_pair)
        return await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol_info: Dict[str, Any] = await self._request_complete_funding_info(trading_pair)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(symbol_info.get("index_price", "0"))),
            mark_price=Decimal(str(symbol_info.get("mark_price", "0"))),
            next_funding_utc_timestamp=int(int(symbol_info.get("next_funding_time", "0")) / 1e9),
            rate=Decimal(str(symbol_info.get("funding_rate", "0"))),
        )
        return funding_info

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._exchange_symbol_for_pair(trading_pair=trading_pair)

        params = {
            "instrument": ex_trading_pair,
            "depth": 100,
        }

        data = await self._connector._api_post(
            path_url=CONSTANTS.ORDERBOOK_URL,
            data=params,
            is_auth_required=False,
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()

        bids = []
        asks = []

        # GRVT order book response: lists of {"price": "...", "size": "..."}
        for bid in snapshot_response.get("bids", []):
            bids.append([bid.get("price", "0"), bid.get("size", "0")])
        for ask in snapshot_response.get("asks", []):
            asks.append([ask.get("price", "0"), ask.get("size", "0")])

        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(snapshot_response.get("event_time", int(time.time() * 1e9))),
                "bids": bids,
                "asks": asks,
            },
            timestamp=snapshot_timestamp,
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.wss_url(domain=self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events, order book, and funding info via GRVT JSONRPC.
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._exchange_symbol_for_pair(trading_pair=trading_pair)

                # Subscribe to order book snapshots (100-level, 500ms interval)
                book_payload = {
                    "jsonrpc": "2.0",
                    "method": "subscribe",
                    "params": {
                        "stream": CONSTANTS.WS_ORDER_BOOK_SNAP_STREAM,
                        "selectors": [f"{symbol}@500-100"],
                    },
                    "id": CONSTANTS.DIFF_STREAM_ID,
                }
                await ws.send(WSJSONRequest(book_payload))

                # Subscribe to trades (500ms interval)
                trade_payload = {
                    "jsonrpc": "2.0",
                    "method": "subscribe",
                    "params": {
                        "stream": CONSTANTS.WS_TRADE_STREAM,
                        "selectors": [f"{symbol}@500"],
                    },
                    "id": CONSTANTS.TRADE_STREAM_ID,
                }
                await ws.send(WSJSONRequest(trade_payload))

                # Subscribe to mini ticker for funding info (500ms interval)
                ticker_payload = {
                    "jsonrpc": "2.0",
                    "method": "subscribe",
                    "params": {
                        "stream": CONSTANTS.WS_MINI_TICKER_SNAP_STREAM,
                        "selectors": [f"{symbol}@500"],
                    },
                    "id": CONSTANTS.FUNDING_INFO_STREAM_ID,
                }
                await ws.send(WSJSONRequest(ticker_payload))

            self.logger().info(
                "Subscribed to public order book, trade, and funding info channels..."
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                "Unexpected error occurred subscribing to order book trading and delta streams..."
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        stream = event_message.get("stream", "")
        if stream in (CONSTANTS.WS_ORDER_BOOK_SNAP_STREAM, CONSTANTS.WS_ORDER_BOOK_DELTA_STREAM):
            channel = self._diff_messages_queue_key
        elif stream == CONSTANTS.WS_TRADE_STREAM:
            channel = self._trade_messages_queue_key
        elif stream in (CONSTANTS.WS_MINI_TICKER_SNAP_STREAM, CONSTANTS.WS_TICKER_SNAP_STREAM):
            channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        timestamp: float = time.time()
        feed = raw_message.get("feed", {})
        selector = raw_message.get("selector", "")

        # Extract instrument from selector (e.g. "BTC_USDT_Perp@500-100")
        instrument = selector.split("@")[0] if "@" in selector else selector
        trading_pair = web_utils.convert_from_exchange_trading_pair(instrument)

        bids = []
        asks = []
        for bid in feed.get("bids", []):
            bids.append([bid.get("price", "0"), bid.get("size", "0")])
        for ask in feed.get("asks", []):
            asks.append([ask.get("price", "0"), ask.get("size", "0")])

        order_book_message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": trading_pair,
                "update_id": int(feed.get("event_time", int(time.time() * 1e9))),
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp,
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        feed = raw_message.get("feed", {})
        selector = raw_message.get("selector", "")

        instrument = selector.split("@")[0] if "@" in selector else selector
        trading_pair = web_utils.convert_from_exchange_trading_pair(instrument)

        # GRVT trade feed contains a "trades" list
        trades = feed.get("trades", [])
        for trade_data in trades:
            trade_timestamp = int(trade_data.get("event_time", int(time.time() * 1e9))) / 1e9
            is_buyer_maker = trade_data.get("is_buyer_maker", False)
            trade_message: OrderBookMessage = OrderBookMessage(
                OrderBookMessageType.TRADE,
                {
                    "trading_pair": trading_pair,
                    "trade_type": float(TradeType.SELL.value) if is_buyer_maker else float(TradeType.BUY.value),
                    "trade_id": trade_data.get("trade_id", str(int(time.time() * 1e6))),
                    "update_id": int(trade_data.get("event_time", int(time.time() * 1e9))),
                    "price": trade_data.get("price", "0"),
                    "amount": trade_data.get("size", "0"),
                },
                timestamp=trade_timestamp,
            )
            message_queue.put_nowait(trade_message)

    async def listen_for_order_book_snapshots(
        self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue
    ):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot_msg: OrderBookMessage = await self._order_book_snapshot(trading_pair)
                    output.put_nowait(snapshot_msg)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                delta = CONSTANTS.ONE_HOUR - time.time() % CONSTANTS.ONE_HOUR
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds...",
                    exc_info=True,
                )
                await self._sleep(5.0)

    async def _parse_funding_info_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        feed = raw_message.get("feed", {})
        selector = raw_message.get("selector", "")

        instrument = selector.split("@")[0] if "@" in selector else selector
        trading_pair = web_utils.convert_from_exchange_trading_pair(instrument)

        if trading_pair not in self._trading_pairs:
            return

        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(str(feed.get("index_price", "0"))),
            mark_price=Decimal(str(feed.get("mark_price", "0"))),
            next_funding_utc_timestamp=int(int(feed.get("next_funding_time", "0")) / 1e9),
            rate=Decimal(str(feed.get("funding_rate", "0"))),
        )
        message_queue.put_nowait(funding_info)

    async def _request_complete_funding_info(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._exchange_symbol_for_pair(trading_pair=trading_pair)
        data = await self._connector._api_post(
            path_url=CONSTANTS.MINI_TICKER_URL,
            data={"instrument": ex_trading_pair},
            is_auth_required=False,
        )
        return data
