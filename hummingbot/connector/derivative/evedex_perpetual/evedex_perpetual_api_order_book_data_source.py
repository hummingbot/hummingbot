import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import EvedexPerpetualDerivative


class EvedexPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'EvedexPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._trade_messages_queue_key = "trades"
        self._diff_messages_queue_key = "orderbook"
        self._funding_info_messages_queue_key = "funding"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        response = await self._connector._api_get(
            path_url=CONSTANTS.MARK_PRICE_URL,
            params={"market": symbol})
        data = response.get("data", response)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(data.get("indexPrice", 0))),
            mark_price=Decimal(str(data.get("markPrice", 0))),
            next_funding_utc_timestamp=int(data.get("nextFundingTime", 0)),
            rate=Decimal(str(data.get("fundingRate", 0))),
        )
        return funding_info

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"market": symbol, "limit": 100}
        data = await self._connector._api_get(path_url=CONSTANTS.SNAPSHOT_REST_URL, params=params)
        return data.get("data", data)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp = time.time()
        snapshot_msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": snapshot_response.get("sequence", int(snapshot_timestamp * 1000)),
            "bids": [[bid["price"], bid["quantity"]] for bid in snapshot_response.get("bids", [])],
            "asks": [[ask["price"], ask["quantity"]] for ask in snapshot_response.get("asks", [])],
        }, timestamp=snapshot_timestamp)
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain), ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                orderbook_payload = {
                    "id": 1,
                    "method": "subscribe",
                    "params": {"channel": f"orderbook:{symbol}"}
                }
                trades_payload = {
                    "id": 2,
                    "method": "subscribe",
                    "params": {"channel": f"trades:{symbol}"}
                }
                funding_payload = {
                    "id": 3,
                    "method": "subscribe",
                    "params": {"channel": f"funding:{symbol}"}
                }
                await ws.send(WSJSONRequest(payload=orderbook_payload))
                await ws.send(WSJSONRequest(payload=trades_payload))
                await ws.send(WSJSONRequest(payload=funding_payload))
            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to channels...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "channel" in event_message:
            ch = event_message.get("channel", "")
            if "orderbook" in ch:
                channel = self._diff_messages_queue_key
            elif "trades" in ch:
                channel = self._trade_messages_queue_key
            elif "funding" in ch:
                channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        channel = raw_message.get("channel", "")
        symbol = channel.split(":")[1] if ":" in channel else ""
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        timestamp = time.time()
        order_book_message = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "update_id": data.get("sequence", int(timestamp * 1000)),
            "bids": [[bid["price"], bid["quantity"]] for bid in data.get("bids", [])],
            "asks": [[ask["price"], ask["quantity"]] for ask in data.get("asks", [])],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        channel = raw_message.get("channel", "")
        symbol = channel.split(":")[1] if ":" in channel else ""
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        for trade in data.get("trades", [data]):
            trade_message = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade.get("side", "").upper() == "SELL" else float(TradeType.BUY.value),
                "trade_id": trade.get("id", str(int(time.time() * 1000))),
                "update_id": trade.get("sequence", int(time.time() * 1000)),
                "price": trade.get("price"),
                "amount": trade.get("quantity")
            }, timestamp=trade.get("timestamp", time.time()) / 1000 if trade.get("timestamp", 0) > 1e10 else trade.get("timestamp", time.time()))
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        channel = raw_message.get("channel", "")
        symbol = channel.split(":")[1] if ":" in channel else ""
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        if trading_pair not in self._trading_pairs:
            return
        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(str(data.get("indexPrice", 0))),
            mark_price=Decimal(str(data.get("markPrice", 0))),
            next_funding_utc_timestamp=int(data.get("nextFundingTime", 0)),
            rate=Decimal(str(data.get("fundingRate", 0))),
        )
        message_queue.put_nowait(funding_info)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot_msg = await self._order_book_snapshot(trading_pair)
                    output.put_nowait(snapshot_msg)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                await self._sleep(3600)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error fetching orderbook snapshots.", exc_info=True)
                await self._sleep(5.0)
