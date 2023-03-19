import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_derivative import BitComPerpetualDerivative


class BitComPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'BitComPerpetualDerivative',
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
        symbol_info: Dict[str, Any] = await self._request_complete_funding_info(trading_pair)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(symbol_info["data"]["index_price"]),
            mark_price=Decimal(symbol_info["data"]["mark_price"]),
            next_funding_utc_timestamp=int(symbol_info["data"]["time"]) + CONSTANTS.FUNDING_RATE_INTERNAL_MIL_SECOND,
            rate=Decimal(symbol_info["data"]["funding_rate"]),
        )
        return funding_info

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        params = {
            "instrument_id": ex_trading_pair,
            "level": "50"
        }

        data = await self._connector._api_get(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            params=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_response.update({"trading_pair": trading_pair})
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": snapshot_response["trading_pair"],
            "update_id": int(snapshot_response['data']["timestamp"]),
            "bids": snapshot_response['data']["bids"],
            "asks": snapshot_response['data']["asks"]
        }, timestamp=int(snapshot_response['data']["timestamp"]))
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trades_payload = {
                    "type": "subscribe",
                    "instruments": [symbol],
                    "channels": [CONSTANTS.TRADES_ENDPOINT_NAME],
                    "interval": "raw",
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

                order_book_payload = {
                    "type": "subscribe",
                    "instruments": [symbol],
                    "channels": [CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME],
                    "interval": "raw",
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

                funding_rate_payload = {
                    "type": "subscribe",
                    "instruments": [symbol],
                    "channels": [CONSTANTS.FUNDING_INFO_STREAM_NAME],
                    "interval": "100ms",
                }
                subscribe_fundingrate_request: WSJSONRequest = WSJSONRequest(payload=funding_rate_payload)

                await ws.send(subscribe_trade_request)
                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_fundingrate_request)

                self.logger().info("Subscribed to public order book, trade and fundingrate channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            stream_name = event_message.get("channel")
            if "depth" in stream_name:
                if event_message["data"]["type"] == "update":
                    channel = self._diff_messages_queue_key
                elif event_message["data"]["type"] == "snapshot":
                    channel = self._snapshot_messages_queue_key
            elif "trade" in stream_name:
                channel = self._trade_messages_queue_key
            elif "ticker" in stream_name:
                channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = raw_message["timestamp"] * 1e-3
        raw_message["data"]["instrument_id"] = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["data"]["instrument_id"])
        data = raw_message["data"]
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": data["instrument_id"],
            "update_id": data["sequence"],
            "bids": [[i[1], i[2]] for i in data["changes"] if i[0] == 'buy'],
            "asks": [[i[1], i[2]] for i in data["changes"] if i[0] == 'sell'],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = raw_message["timestamp"] * 1e-3
        raw_message["data"]["instrument_id"] = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["data"]["instrument_id"])
        data = raw_message["data"]
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": data["instrument_id"],
            "update_id": data["sequence"],
            "bids": data["bids"],
            "asks": data["asks"]
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = raw_message["timestamp"] * 1e-3

        data = raw_message["data"]
        for trade_data in data:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(trade_data["instrument_id"])
            trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade_data["side"] == "sell" else float(
                    TradeType.BUY.value),
                "trade_id": trade_data["trade_id"],
                "price": trade_data["price"],
                "amount": trade_data["qty"]
            }, timestamp=timestamp)

            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):

        data: Dict[str, Any] = raw_message["data"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(data["instrument_id"])

        if trading_pair not in self._trading_pairs:
            return
        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            mark_price=Decimal(data["mark_price"]),
            next_funding_utc_timestamp=(int(data["time"] / CONSTANTS.FUNDING_RATE_INTERNAL_MIL_SECOND) + 1) *
            CONSTANTS.FUNDING_RATE_INTERNAL_MIL_SECOND,
            rate=Decimal(data["funding_rate"]),
        )

        message_queue.put_nowait(funding_info)

    async def _request_complete_funding_info(self, trading_pair: str):
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL,
            params={"instrument_id": ex_trading_pair})
        return data
