import asyncio
import time
from collections import defaultdict, namedtuple
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_web_utils as web_utils
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_derivative import PhemexPerpetualDerivative


TradeStructure = namedtuple("Trade", "timestamp side price amount")


class PhemexPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "PhemexPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
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
        self.pong_received_event = asyncio.Event()

    def _get_messages_queue_keys(self) -> List[str]:
        return [self._funding_info_messages_queue_key, self._diff_messages_queue_key, self._trade_messages_queue_key]

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
            timestamp=snapshot_response["timestamp"] * 1e-9,
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WSS_CONNECTION_LIMIT_ID):
            await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT)
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
                    "params": params if stream_method is not CONSTANTS.FUNDING_INFO_STREAM_METHOD else [],
                }
                subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WSS_MESSAGE_LIMIT_ID):
                    await ws.send(subscribe_request)
            self.logger().info("Subscribed to public order book, trade and funding info channels...")
            safe_ensure_future(self.ping_loop(ws=ws))
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
        elif event_message.get("method", None) == self._funding_info_messages_queue_key:
            channel = self._funding_info_messages_queue_key
        return channel

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        if event_message.get("result", None) == "pong":
            self.pong_received_event.set()

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
                timestamp=mapped_trade.timestamp * 1e-9,
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
        if raw_message["type"] == "snapshot":
            fields = raw_message.get("fields", [])
            self.index_price_index = fields.index("indexRp")
            self.mark_price_index = fields.index("markRp")
            self.symbol_index = fields.index("symbol")
            self.funding_rate_index = fields.index("fundingRateRr")

        for data in raw_message.get("data", []):
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(data[self.symbol_index])

            if trading_pair not in self._trading_pairs:
                continue
            funding_info = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(data[self.index_price_index]),
                mark_price=Decimal(data[self.mark_price_index]),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal(data[self.funding_rate_index]),
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

    async def ping_loop(self, ws: WSAssistant):
        count = 0
        while ws._connection.connected:
            ping_request: WSJSONRequest = WSJSONRequest({"id": 0, "method": "server.ping", "params": []})
            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WSS_MESSAGE_LIMIT_ID):
                await ws.send(ping_request)
            try:
                await asyncio.wait_for(self.pong_received_event.wait(), timeout=5)
                self.pong_received_event.clear()
                count = 0
                await self._sleep(5.0)
            except asyncio.TimeoutError:
                count += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                await ws._connection.disconnect()
            finally:
                if count == 3:
                    await ws._connection.disconnect()
