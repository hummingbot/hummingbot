import asyncio
import time
from collections import defaultdict, namedtuple
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_web_utils as web_utils
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

# if TYPE_CHECKING:
#     from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_derivative import (
#         PhemexPerpetualDerivative,
#     )


TradeStructure = namedtuple("Trade", "timestamp side price amount")
PhemexPerpetualDerivative = ""  # To-do: cleanup. Just added so preliminaty commit is possible.


class PhemexPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "PhemexPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._trade_messages_queue_key = "trades_p"
        self._diff_messages_queue_key = "orderbook_p"
        self._funding_info_messages_queue_key = "perp_market24h_pack_p.update"
        self._snapshot_messages_queue_key = "snapshot"

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol_info: Dict[str, Any] = (await self._request_complete_funding_info(trading_pair))["result"]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(symbol_info["indexPriceRp"]),
            mark_price=Decimal(symbol_info["markPriceRp"]),
            next_funding_utc_timestamp=self._next_funding_time(),
            rate=Decimal(symbol_info["fundingRateRr"]),
        )
        return funding_info

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        params = {"symbol": ex_trading_pair}

        data = await self._connector._api_get(path_url=CONSTANTS.SNAPSHOT_REST_URL, params=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = (await self._request_order_book_snapshot(trading_pair))["result"]
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": snapshot_response["sequence"],
                "bids": snapshot_response[self._diff_messages_queue_key]["bids"],
                "asks": snapshot_response[self._diff_messages_queue_key]["asks"],
            },
            timestamp=snapshot_response["timestamp"] // 1e9,
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            stream_id_channel_pairs = [
                CONSTANTS.DIFF_STREAM_METHOD,
                CONSTANTS.TRADE_STREAM_METHOD,
                CONSTANTS.FUNDING_INFO_STREAM_METHOD,
            ]
            for stream_method in stream_id_channel_pairs:
                params = []
                for trading_pair in self._trading_pairs:
                    params.append(await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair))
                payload = {
                    "id": 0,
                    "method": stream_method,
                    "params": params,
                }
                subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                await ws.send(subscribe_request)
            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if self._diff_messages_queue_key in event_message:
            channel = self._diff_messages_queue_key
        elif self._trade_messages_queue_key in event_message:
            channel = self._trade_messages_queue_key
        elif event_message["method"] == self._funding_info_messages_queue_key:
            channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = time.time()
        raw_message["symbol"] = await self._connector.trading_pair_associated_to_exchange_symbol(raw_message["symbol"])
        if raw_message["type"] == "incremental":
            book = raw_message[self._diff_messages_queue_key]
            order_book_message: OrderBookMessage = OrderBookMessage(
                OrderBookMessageType.DIFF,
                {
                    "trading_pair": raw_message["symbol"],
                    "update_id": raw_message["sequence"],
                    "bids": book["bids"],
                    "asks": book["asks"],
                },
                timestamp=timestamp,
            )
            message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raw_message["symbol"] = await self._connector.trading_pair_associated_to_exchange_symbol(raw_message["symbol"])
        for trade in raw_message[self._trade_messages_queue_key]:
            mapped_trade = TradeStructure(*trade)
            trade_message: OrderBookMessage = OrderBookMessage(
                OrderBookMessageType.TRADE,
                {
                    "trading_pair": raw_message["symbol"],
                    "trade_type": mapped_trade.side.upper(),
                    "trade_id": mapped_trade.timestamp,
                    "update_id": raw_message["sequence"],
                    "price": mapped_trade.price,
                    "amount": mapped_trade.amount,
                },
                timestamp=mapped_trade.timestamp // 1e9,
            )

            message_queue.put_nowait(trade_message)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
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
                    "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds...", exc_info=True
                )
                await self._sleep(5.0)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        fields = raw_message.get("fields", [])
        index_price_index = fields.index("indexRp")
        mark_price_index = fields.index("markRp")
        symbol_index = fields.index("symbol")
        funding_rate_index = fields.index("fundingRateRr")

        for data in raw_message.get("data", []):
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(data[symbol_index])

            if trading_pair not in self._trading_pairs:
                return
            funding_info = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(data[index_price_index]),
                mark_price=Decimal(data[mark_price_index]),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal(data[funding_rate_index]),
            )

        message_queue.put_nowait(funding_info)

    async def _request_complete_funding_info(self, trading_pair: str):
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=CONSTANTS.MARK_PRICE_URL, params={"symbol": ex_trading_pair}, is_auth_required=False
        )
        return data

    def _next_funding_time(self) -> int:
        """
        Funding settlement occurs every 8 hours as mentioned in https://phemex.com/user-guides/funding-rate
        """
        return ((time.time() // 28800) + 1) * 28800
