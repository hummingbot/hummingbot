import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative import AevoPerpetualDerivative


class AevoPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'AevoPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._trade_messages_queue_key = CONSTANTS.TRADE_STREAM_ID
        self._diff_messages_queue_key = CONSTANTS.DIFF_STREAM_ID
        self._funding_info_messages_queue_key = CONSTANTS.FUNDING_INFO_STREAM_ID
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol_info = await self._request_complete_funding_info(trading_pair)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(symbol_info.get("index_price", "0"))),
            mark_price=Decimal(str(symbol_info.get("mark_price", "0"))),
            next_funding_utc_timestamp=int(symbol_info.get("next_funding_time", 0)),
            rate=Decimal(str(symbol_info.get("funding_rate", "0"))),
        )
        return funding_info

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"instrument_name": ex_trading_pair}
        data = await self._connector._api_get(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            params=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp = time.time()
        snapshot_response["trading_pair"] = trading_pair
        bids = [[str(b[0]), str(b[1])] for b in snapshot_response.get("bids", [])]
        asks = [[str(a[0]), str(a[1])] for a in snapshot_response.get("asks", [])]
        snapshot_msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": snapshot_response.get("timestamp", int(time.time() * 1000)),
            "bids": bids,
            "asks": asks
        }, timestamp=snapshot_timestamp)
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.wss_url(self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                orderbook_payload = {
                    "op": "subscribe",
                    "data": [f"orderbook:{symbol}"]
                }
                subscribe_orderbook = WSJSONRequest(payload=orderbook_payload)
                await ws.send(subscribe_orderbook)

                trades_payload = {
                    "op": "subscribe",
                    "data": [f"trades:{symbol}"]
                }
                subscribe_trades = WSJSONRequest(payload=trades_payload)
                await ws.send(subscribe_trades)

                ticker_payload = {
                    "op": "subscribe",
                    "data": [f"ticker:{symbol}"]
                }
                subscribe_ticker = WSJSONRequest(payload=ticker_payload)
                await ws.send(subscribe_ticker)

            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        channel_name = event_message.get("channel", "")
        if "orderbook" in channel_name:
            channel = self._diff_messages_queue_key
        elif "trades" in channel_name:
            channel = self._trade_messages_queue_key
        elif "ticker" in channel_name:
            channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp = time.time()
        data = raw_message.get("data", {})
        channel = raw_message.get("channel", "")
        symbol = channel.split(":")[-1] if ":" in channel else ""
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        bids = [[str(b[0]), str(b[1])] for b in data.get("bids", [])]
        asks = [[str(a[0]), str(a[1])] for a in data.get("asks", [])]

        order_book_message = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "update_id": data.get("timestamp", int(time.time() * 1000)),
            "bids": bids,
            "asks": asks
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        channel = raw_message.get("channel", "")
        symbol = channel.split(":")[-1] if ":" in channel else ""
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        trades = data if isinstance(data, list) else [data]
        for trade in trades:
            trade_type = TradeType.SELL if trade.get("side", "").lower() == "sell" else TradeType.BUY
            trade_message = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(trade_type.value),
                "trade_id": trade.get("trade_id", str(int(time.time() * 1000))),
                "update_id": trade.get("timestamp", int(time.time() * 1000)),
                "price": str(trade.get("price", "0")),
                "amount": str(trade.get("amount", "0"))
            }, timestamp=float(trade.get("timestamp", time.time() * 1000)) / 1000)
            message_queue.put_nowait(trade_message)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot_msg = await self._order_book_snapshot(trading_pair)
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
        data = raw_message.get("data", {})
        channel = raw_message.get("channel", "")
        symbol = channel.split(":")[-1] if ":" in channel else ""
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        if trading_pair not in self._trading_pairs:
            return

        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(str(data.get("index_price", "0"))),
            mark_price=Decimal(str(data.get("mark_price", "0"))),
            next_funding_utc_timestamp=int(data.get("next_funding_time", 0)),
            rate=Decimal(str(data.get("funding_rate", "0"))),
        )
        message_queue.put_nowait(funding_info)

    async def _request_complete_funding_info(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=CONSTANTS.TICKER_PRICE_URL,
            params={"instrument_name": ex_trading_pair})
        return data
