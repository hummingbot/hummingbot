import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

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
    from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import (
        EvedexPerpetualDerivative,
    )


class EvedexPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
            self,
            trading_pairs: List[str],
            connector: "EvedexPerpetualDerivative",
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        response = await self._request_complete_funding_info(trading_pair)
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        
        funding_data = response.get("data", {})
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(funding_data.get("indexPrice", 0))),
            mark_price=Decimal(str(funding_data.get("markPrice", 0))),
            next_funding_utc_timestamp=self._next_funding_time(),
            rate=Decimal(str(funding_data.get("fundingRate", 0))),
        )
        return funding_info

    async def listen_for_funding_info(self, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    funding_info = await self.get_funding_info(trading_pair)
                    funding_info_update = FundingInfoUpdate(
                        trading_pair=trading_pair,
                        index_price=funding_info.index_price,
                        mark_price=funding_info.mark_price,
                        next_funding_utc_timestamp=funding_info.next_funding_utc_timestamp,
                        rate=funding_info.rate,
                    )
                    output.put_nowait(funding_info_update)
                await self._sleep(CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public funding info updates from exchange")
                await self._sleep(CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        symbol = web_utils.convert_to_exchange_trading_pair(ex_trading_pair)
        
        params = {
            "symbol": symbol,
            "limit": 100
        }

        data = await self._connector._api_get(
            path_url=CONSTANTS.MARKET_DEPTH_URL,
            params=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_data = snapshot_response.get("data", snapshot_response)
        
        snapshot_msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": int(snapshot_data.get("timestamp", time.time() * 1000)),
            "bids": [[float(bid[0]), float(bid[1])] for bid in snapshot_data.get("bids", [])],
            "asks": [[float(ask[0]), float(ask[1])] for ask in snapshot_data.get("asks", [])],
        }, timestamp=float(snapshot_data.get("timestamp", time.time() * 1000)) / 1000)
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                exchange_symbol = web_utils.convert_to_exchange_trading_pair(symbol)
                
                # Subscribe to orderbook channel using Centrifuge protocol
                orderbook_payload = {
                    "id": 1,
                    "method": 1,  # Subscribe method in Centrifuge
                    "params": {
                        "channel": f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:{exchange_symbol}"
                    }
                }
                subscribe_orderbook_request = WSJSONRequest(payload=orderbook_payload)

                # Subscribe to trades channel
                trades_payload = {
                    "id": 2,
                    "method": 1,
                    "params": {
                        "channel": f"{CONSTANTS.WS_TRADES_CHANNEL}:{exchange_symbol}"
                    }
                }
                subscribe_trade_request = WSJSONRequest(payload=trades_payload)

                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_trade_request)

                self.logger().info(f"Subscribed to public order book and trade channels for {trading_pair}")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" in event_message or "push" in event_message:
            push_data = event_message.get("push", {})
            channel_name = push_data.get("channel", "")
            
            if CONSTANTS.WS_ORDERBOOK_CHANNEL in channel_name:
                channel = self._snapshot_messages_queue_key
            elif CONSTANTS.WS_TRADES_CHANNEL in channel_name:
                channel = self._trade_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        push_data = raw_message.get("push", {})
        channel = push_data.get("channel", "")
        data = push_data.get("pub", {}).get("data", {})
        
        # Extract symbol from channel
        symbol = channel.split(":")[-1] if ":" in channel else ""
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            web_utils.convert_from_exchange_trading_pair(symbol))
        
        timestamp = float(data.get("timestamp", time.time() * 1000)) / 1000
        
        order_book_message = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "update_id": data.get("timestamp", int(time.time() * 1000)),
            "bids": [[float(bid[0]), float(bid[1])] for bid in data.get("bids", [])],
            "asks": [[float(ask[0]), float(ask[1])] for ask in data.get("asks", [])],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        await self._parse_order_book_diff_message(raw_message, message_queue)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        push_data = raw_message.get("push", {})
        channel = push_data.get("channel", "")
        trades = push_data.get("pub", {}).get("data", [])
        
        symbol = channel.split(":")[-1] if ":" in channel else ""
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            web_utils.convert_from_exchange_trading_pair(symbol))
        
        for trade_data in trades if isinstance(trades, list) else [trades]:
            trade_message = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade_data.get("side", "").lower() == "sell" else float(TradeType.BUY.value),
                "trade_id": trade_data.get("id", str(time.time())),
                "price": float(trade_data.get("price", 0)),
                "amount": float(trade_data.get("quantity", trade_data.get("size", 0)))
            }, timestamp=float(trade_data.get("timestamp", time.time() * 1000)) / 1000)
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    async def _request_complete_funding_info(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        symbol = web_utils.convert_to_exchange_trading_pair(ex_trading_pair)
        
        data = await self._connector._api_get(
            path_url=CONSTANTS.FUNDING_RATE_URL,
            params={"symbol": symbol})
        return data

    def _next_funding_time(self) -> int:
        # EVEDEX funding settlement typically occurs every 8 hours
        return int(((time.time() // 28800) + 1) * 28800)
