import asyncio
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
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'AevoPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
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
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        funding = await self._connector._api_get(
            path_url=CONSTANTS.FUNDING_PATH_URL,
            params={"instrument_name": ex_trading_pair},
        )
        instrument = await self._connector._api_get(
            path_url=f"{CONSTANTS.INSTRUMENT_PATH_URL}/{ex_trading_pair}",
            limit_id=CONSTANTS.INSTRUMENT_PATH_URL,
        )
        next_epoch_ns = int(funding.get("next_epoch", "0"))
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(instrument.get("index_price", "0")),
            mark_price=Decimal(instrument.get("mark_price", "0")),
            next_funding_utc_timestamp=int(next_epoch_ns * 1e-9),
            rate=Decimal(funding.get("funding_rate", "0")),
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
                await self._sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public funding info updates from exchange")
                await self._sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=CONSTANTS.ORDERBOOK_PATH_URL,
            params={"instrument_name": ex_trading_pair},
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        timestamp = int(snapshot_response["last_updated"]) * 1e-9
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": int(snapshot_response["last_updated"]),
            "bids": [[float(i[0]), float(i[1])] for i in snapshot_response.get("bids", [])],
            "asks": [[float(i[0]), float(i[1])] for i in snapshot_response.get("asks", [])],
        }, timestamp=timestamp)
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                trades_payload = {
                    "op": "subscribe",
                    "data": [f"{CONSTANTS.WS_TRADE_CHANNEL}:{symbol}"],
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

                order_book_payload = {
                    "op": "subscribe",
                    "data": [f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:{symbol}"],
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

                await ws.send(subscribe_trade_request)
                await ws.send(subscribe_orderbook_request)

                self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "channel" in event_message:
            stream_name = event_message.get("channel")
            if stream_name.startswith(f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:"):
                msg_type = event_message.get("data", {}).get("type")
                if msg_type == "snapshot":
                    channel = self._snapshot_messages_queue_key
                else:
                    channel = self._diff_messages_queue_key
            elif stream_name.startswith(f"{CONSTANTS.WS_TRADE_CHANNEL}:"):
                channel = self._trade_messages_queue_key
            else:
                self.logger().warning(f"Unknown WS channel received: {stream_name}")
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message["data"]
        timestamp = int(data["last_updated"]) * 1e-9
        instrument_name = raw_message["data"]["instrument_name"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(instrument_name)
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "update_id": int(data["last_updated"]),
            "bids": [[float(i[0]), float(i[1])] for i in data.get("bids", [])],
            "asks": [[float(i[0]), float(i[1])] for i in data.get("asks", [])],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message["data"]
        timestamp = int(data["last_updated"]) * 1e-9
        instrument_name = raw_message["data"]["instrument_name"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(instrument_name)
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": int(data["last_updated"]),
            "bids": [[float(i[0]), float(i[1])] for i in data.get("bids", [])],
            "asks": [[float(i[0]), float(i[1])] for i in data.get("asks", [])],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message["data"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            data["instrument_name"])
        timestamp = int(data.get("created_timestamp", "0")) * 1e-9
        trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": trading_pair,
            "trade_type": float(TradeType.BUY.value) if data["side"] == "buy" else float(TradeType.SELL.value),
            "trade_id": str(data["trade_id"]),
            "price": float(data["price"]),
            "amount": float(data["amount"]),
        }, timestamp=timestamp)
        message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot subscribe to {trading_pair}: WebSocket connection not established."
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            trades_payload = {
                "op": "subscribe",
                "data": [f"{CONSTANTS.WS_TRADE_CHANNEL}:{symbol}"],
            }
            order_book_payload = {
                "op": "subscribe",
                "data": [f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:{symbol}"],
            }

            await self._ws_assistant.send(WSJSONRequest(payload=trades_payload))
            await self._ws_assistant.send(WSJSONRequest(payload=order_book_payload))

            self.add_trading_pair(trading_pair)
            self.logger().info(f"Successfully subscribed to {trading_pair}")
            return True
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error subscribing to {trading_pair}: {e}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket connection not established."
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            trades_payload = {
                "op": "unsubscribe",
                "data": [f"{CONSTANTS.WS_TRADE_CHANNEL}:{symbol}"],
            }
            order_book_payload = {
                "op": "unsubscribe",
                "data": [f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:{symbol}"],
            }

            await self._ws_assistant.send(WSJSONRequest(payload=trades_payload))
            await self._ws_assistant.send(WSJSONRequest(payload=order_book_payload))

            self.remove_trading_pair(trading_pair)
            self.logger().info(f"Successfully unsubscribed from {trading_pair}")
            return True
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error unsubscribing from {trading_pair}: {e}")
            return False
