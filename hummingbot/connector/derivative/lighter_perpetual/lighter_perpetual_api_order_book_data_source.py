import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
        LighterPerpetualDerivative,
    )


class LighterPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "LighterPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._message_queue: Dict[str, asyncio.Queue] = {
            self._snapshot_messages_queue_key: asyncio.Queue(),
            self._diff_messages_queue_key: asyncio.Queue(),
            self._trade_messages_queue_key: asyncio.Queue(),
            self._funding_info_messages_queue_key: asyncio.Queue(),
        }

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobds_logger is None:
            cls._bpobds_logger = HummingbotLogger(
                "LighterPerpetualAPIOrderBookDataSource"
            )
        return cls._bpobds_logger

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        market_data = await self._request_markets_metadata()
        market_id = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair
        )
        market_info = market_data.get(market_id)
        if market_info is None:
            raise IOError(f"No funding info for {trading_pair}")

        mark_price = Decimal(market_info["mark_price"])
        index_price = Decimal(market_info["index_price"])
        funding_rate = Decimal(market_info["current_funding_rate"])
        next_funding_ts = int(market_info.get("funding_timestamp", 0))

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=index_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=next_funding_ts,
            rate=funding_rate,
        )

    async def listen_for_funding_info(self, output: asyncio.Queue):
        while True:
            try:
                message_queue = self._message_queue[
                    self._funding_info_messages_queue_key
                ]
                raw_message = await message_queue.get()
                await self._parse_funding_info_message(raw_message, output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error when processing public funding info updates from exchange"
                )
                await self._sleep(CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND)

    def _next_funding_time(self) -> int:
        """
        Funding settlement occurs every hour as described in Lighter docs.
        """
        return int(((time.time() // 3600) + 1) * 3600)

    async def _request_markets_metadata(self) -> Dict[str, Dict[str, Any]]:
        url = web_utils.public_rest_url(CONSTANTS.MARKETS_URL, self._domain)
        request = RESTRequest(method=RESTMethod.GET, url=url)
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.call(request=request)
        data = await response.json()
        markets: Dict[str, Dict[str, Any]] = {}
        for market in data.get("markets", []):
            market_id = str(market["market_id"])
            markets[market_id] = market
        return markets

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        market_id = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair
        )
        url = web_utils.public_rest_url(CONSTANTS.ORDERBOOK_SNAPSHOT_URL, self._domain)
        params = {"market_id": market_id, "limit": 200}
        request = RESTRequest(method=RESTMethod.GET, url=url, params=params)
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.call(request=request)
        data = await response.json()
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(
            trading_pair
        )
        update_id = int(
            snapshot_response.get("update_id") or snapshot_response.get("timestamp", 0)
        )
        bids = [
            [Decimal(level["price"]), Decimal(level["size"])]
            for level in snapshot_response.get("bids", [])
        ]
        asks = [
            [Decimal(level["price"]), Decimal(level["size"])]
            for level in snapshot_response.get("asks", [])
        ]
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=float(snapshot_response.get("timestamp", 0)),
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws_url = web_utils.wss_url(self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                market_id = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair
                )
                subscriptions = [
                    CONSTANTS.PUBLIC_WS_ORDER_BOOK_CHANNEL.format(market_id=market_id),
                    CONSTANTS.PUBLIC_WS_TRADES_CHANNEL.format(market_id=market_id),
                    CONSTANTS.PUBLIC_WS_MARKET_STATS_CHANNEL.format(
                        market_id=market_id
                    ),
                ]
                for channel in subscriptions:
                    payload = {"type": "subscribe", "channel": channel}
                    request = WSJSONRequest(payload=payload)
                    await ws.send(request)
            self.logger().info(
                "Subscribed to public order book, trade, and funding channels..."
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book data streams."
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = event_message.get("channel", "")
        if channel.startswith("order_book"):
            return self._diff_messages_queue_key
        if channel.startswith("trade"):
            return self._trade_messages_queue_key
        if channel.startswith("market_stats"):
            return self._funding_info_messages_queue_key
        return ""

    async def _parse_order_book_diff_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        order_book = raw_message.get("order_book", {})
        market_id = self._market_id_from_event(raw_message, order_book)
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            market_id
        )
        update_id = int(
            order_book.get("offset")
            or order_book.get("timestamp")
            or raw_message.get("offset", 0)
        )
        bids = [
            [Decimal(entry["price"]), Decimal(entry["size"])]
            for entry in order_book.get("bids", [])
        ]
        asks = [
            [Decimal(entry["price"]), Decimal(entry["size"])]
            for entry in order_book.get("asks", [])
        ]
        message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=float(
                order_book.get("timestamp", raw_message.get("timestamp", 0))
            ),
        )
        message_queue.put_nowait(message)

    async def _parse_order_book_snapshot_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        order_book = raw_message.get("order_book", {})
        market_id = self._market_id_from_event(raw_message, order_book)
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            market_id
        )
        bids = [
            [Decimal(entry["price"]), Decimal(entry["size"])]
            for entry in order_book.get("bids", [])
        ]
        asks = [
            [Decimal(entry["price"]), Decimal(entry["size"])]
            for entry in order_book.get("asks", [])
        ]
        update_id = int(
            order_book.get("offset")
            or order_book.get("timestamp")
            or raw_message.get("offset", 0)
        )
        message = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=float(
                order_book.get("timestamp", raw_message.get("timestamp", 0))
            ),
        )
        message_queue.put_nowait(message)

    async def _parse_trade_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        trades = raw_message.get("trades", [])
        channel_market = self._market_id_from_event(raw_message)
        for trade in trades:
            market_id = str(trade.get("market_id") or channel_market)
            trading_pair = (
                await self._connector.trading_pair_associated_to_exchange_symbol(
                    market_id
                )
            )
            trade_type = (
                TradeType.BUY if bool(trade.get("is_maker_ask")) else TradeType.SELL
            )
            message = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content={
                    "trading_pair": trading_pair,
                    "trade_type": float(trade_type.value),
                    "trade_id": str(trade.get("trade_id")),
                    "price": Decimal(str(trade.get("price", "0"))),
                    "amount": Decimal(str(trade.get("size", "0"))),
                },
                timestamp=float(
                    trade.get("timestamp", raw_message.get("timestamp", 0))
                ),
            )
            message_queue.put_nowait(message)

    async def _parse_funding_info_message(
        self, raw_message: Dict[str, Any], output: asyncio.Queue
    ):
        stats = raw_message.get("market_stats", {})
        market_id = self._market_id_from_event(raw_message, stats)
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            market_id
        )
        funding_rate = Decimal(str(stats.get("current_funding_rate", "0")))
        mark_price = Decimal(
            str(stats.get("mark_price", stats.get("index_price", "0")))
        )
        index_price = Decimal(str(stats.get("index_price", mark_price)))
        next_funding = int(stats.get("funding_timestamp", 0))
        funding_update = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=index_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=next_funding,
            rate=funding_rate,
        )
        output.put_nowait(funding_update)

    async def listen_for_subscriptions(self):
        ws = None
        try:
            ws = await self._connected_websocket_assistant()
            await self._subscribe_channels(ws)
            while True:
                try:
                    event = await ws.receive_json()
                    channel = self._channel_originating_message(event)
                    if channel:
                        message_queue = self._message_queue[channel]
                        message_queue.put_nowait(event)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.logger().exception(
                        "Unexpected error when processing public messages."
                    )
        finally:
            if ws is not None:
                safe_ensure_future(ws.disconnect())

    @staticmethod
    def _market_id_from_channel(channel: str) -> Optional[str]:
        if not channel:
            return None
        delimiter = ":" if ":" in channel else "/"
        parts = channel.split(delimiter)
        return parts[-1] if parts else None

    def _market_id_from_event(
        self, message: Dict[str, Any], payload: Optional[Dict[str, Any]] = None
    ) -> str:
        payload = payload or {}
        market_id = payload.get("market_id")
        if market_id is None:
            market_id = self._market_id_from_channel(message.get("channel", ""))
        if market_id is None:
            raise ValueError("Market id could not be determined from message.")
        return str(market_id)
