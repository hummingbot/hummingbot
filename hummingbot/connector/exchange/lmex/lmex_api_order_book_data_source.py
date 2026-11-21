import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.lmex import lmex_constants as CONSTANTS
from hummingbot.connector.exchange.lmex import lmex_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

# WebSocket streaming can be added once LMEX publishes WS API docs.

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lmex.lmex_exchange import LmexExchange


class LmexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    REST-polling order book data source for LMEX spot.

    LMEX does not currently publish WebSocket API documentation for the spot market,
    so this implementation polls the REST endpoints for snapshots and trades.
    _connected_websocket_assistant raises NotImplementedError until WS docs are available.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "LmexExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = float(snapshot_response.get("timestamp", self._time())) / 1e3

        # LMEX orderbook L2 response:
        # {symbol, buyQuote: [{price, size}], sellQuote: [{price, size}], timestamp, depth}
        raw_bids = snapshot_response.get("buyQuote", [])
        raw_asks = snapshot_response.get("sellQuote", [])

        bids = [[entry["price"], entry["size"]] for entry in raw_bids]
        asks = [[entry["price"], entry["size"]] for entry in raw_asks]

        snapshot_msg = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": snapshot_response.get("timestamp", int(self._time() * 1e3)),
                "bids": bids,
                "asks": asks,
            },
            timestamp=snapshot_timestamp,
        )
        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a full order book snapshot from LMEX for a given trading pair.

        GET /api/v3.2/orderbook/L2?symbol=<symbol>&depth=50
        """
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "symbol": symbol,
            "depth": 50,
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url=web_utils.public_rest_url(
                endpoint=CONSTANTS.ORDER_BOOK_PATH_URL, domain=self._domain
            ),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
        )

    async def _parse_trade_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        """
        Parses a REST trade record into an OrderBookMessage and puts it on the queue.

        LMEX trade object: {price, size, side (BUY/SELL), symbol, serialId, timestamp}
        """
        trade_timestamp: float = float(raw_message.get("timestamp", self._time() * 1e3)) / 1e3
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            symbol=raw_message["symbol"]
        )
        message_content = {
            "trading_pair": trading_pair,
            "trade_type": (
                float(TradeType.SELL.value)
                if raw_message.get("side", "").upper() == "SELL"
                else float(TradeType.BUY.value)
            ),
            "trade_id": raw_message.get("serialId", trade_timestamp),
            "update_id": trade_timestamp,
            "price": str(raw_message["price"]),
            "amount": str(raw_message["size"]),
        }
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=message_content,
            timestamp=trade_timestamp,
        )
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        # LMEX REST polling only delivers full snapshots, not diffs.
        # This method is a no-op; _order_book_snapshot handles updates.
        pass

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        WebSocket channel subscription is not implemented — LMEX WS docs are not yet public.
        The connector operates in REST-polling mode only.
        """
        raise NotImplementedError(
            "TODO: implement WebSocket channel subscription once LMEX publishes WS API docs."
        )

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        # Not used in REST-polling mode.
        return ""

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        WebSocket streaming is not yet implemented.
        TODO: implement once LMEX publishes WS API docs.
        """
        raise NotImplementedError(
            "TODO: WebSocket streaming can be added once LMEX publishes WS API docs."
        )

    async def _fetch_trades(self, trading_pair: str) -> List[Dict[str, Any]]:
        """
        Retrieves recent public trades for a trading pair.

        GET /api/v3.2/trades?symbol=<symbol>
        """
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"symbol": symbol}

        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url=web_utils.public_rest_url(
                endpoint=CONSTANTS.TRADES_PATH_URL, domain=self._domain
            ),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TRADES_PATH_URL,
        )
