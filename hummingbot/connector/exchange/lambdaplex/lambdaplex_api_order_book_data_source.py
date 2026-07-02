import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.lambdaplex import (
    lambdaplex_constants as CONSTANTS,
    lambdaplex_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lambdaplex.lambdaplex_exchange import LambdaplexExchange


class LambdaplexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _next_ws_message_id: int = 1

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'LambdaplexExchange',
        api_factory: WebAssistantsFactory,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._api_factory = api_factory
        self._next_message_id = 1

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        exchange_pairs = await safe_gather(
            *[
                self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in trading_pairs
            ]
        )
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.LAST_PRICE_URL),
            params={"symbols": ",".join(exchange_pairs)},
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.LAST_PRICE_MULTI_LIMIT,
        )
        response = {
            await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=entry["symbol"]
            ): float(entry["price"])
            for entry in data
        }
        return response

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "limit": "1000",
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_THOUSAND_LIMIT,
        )

        return data

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        success = True

        if self._ws_assistant is None:
            self.logger().warning(f"Cannot subscribe to {trading_pair}: WebSocket not connected")
            success = False
        elif trading_pair in self._trading_pairs:
            self.logger().warning(f"{trading_pair} already subscribed. Ignoring request.")
        else:
            try:
                await self._subscribe_to_trading_pairs(ws=self._ws_assistant, trading_pairs=[trading_pair])
                self.add_trading_pair(trading_pair)
            except asyncio.CancelledError:
                raise
            except Exception:
                success = False

        return success

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        success = True

        if self._ws_assistant is None:
            self.logger().warning(f"Cannot unsubscribe from {trading_pair}: WebSocket not connected")
            success = False
        elif trading_pair not in self._trading_pairs:
            self.logger().warning(f"{trading_pair} not subscribed. Ignoring request.")
        else:
            try:
                await self._unsubscribe_from_trading_pairs(ws=self._ws_assistant, trading_pairs=[trading_pair])
                self.remove_trading_pair(trading_pair)
            except asyncio.CancelledError:
                raise
            except Exception:
                success = False

        return success

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair: str = await self._connector.trading_pair_associated_to_exchange_symbol(raw_message["s"])
        ts = raw_message["E"]
        message_content = {
            "trade_id": raw_message["t"],
            "trading_pair": trading_pair,
            "trade_type": float(TradeType.SELL.value) if raw_message["m"] else float(TradeType.BUY.value),
            "update_id": ts,
            "price": raw_message["p"],
            "amount": raw_message["q"]
        }
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=message_content,
            timestamp=ts * 1e-3,
        )
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["s"])
            order_book_message = OrderBookMessage(
                OrderBookMessageType.DIFF, {
                    "trading_pair": trading_pair,
                    "first_update_id": raw_message["U"],
                    "update_id": raw_message["u"],
                    "bids": raw_message["b"],
                    "asks": raw_message["a"]
                },
                timestamp=self._time(),
            )
            message_queue.put_nowait(order_book_message)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp = self._time()
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": snapshot["lastUpdateId"],
                "bids": snapshot["bids"],
                "asks": snapshot["asks"],
            },
            timestamp=snapshot_timestamp,
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_URL.format(CONSTANTS.API_VERSION),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        await self._subscribe_to_trading_pairs(ws=ws, trading_pairs=self._trading_pairs)

    async def _subscribe_to_trading_pairs(self, ws: WSAssistant, trading_pairs: list[str]):
        try:
            await self._send_sub_unsub_for_trading_pairs(ws=ws, trading_pairs=trading_pairs, subscribe=True)
            self.logger().info(
                f"Subscribed to public order book and trade channels for {', '.join(trading_pairs)}..."
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Unexpected error occurred subscribing to order book trading and delta streams for"
                f" {', '.join(trading_pairs)}...",
                exc_info=True
            )
            raise

    async def _unsubscribe_from_trading_pairs(self, ws: WSAssistant, trading_pairs: list[str]):
        try:
            await self._send_sub_unsub_for_trading_pairs(ws=ws, trading_pairs=trading_pairs, subscribe=False)
            self.logger().info(
                f"Unsubscribed from public order book and trade channels for {', '.join(trading_pairs)}..."
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Unexpected error occurred unsubscribing from order book trading and delta streams for"
                f" {', '.join(trading_pairs)}.",
                exc_info=True
            )
            raise

    async def _send_sub_unsub_for_trading_pairs(self, ws: WSAssistant, trading_pairs: list[str], subscribe: bool):
        trade_params = []
        depth_params = []
        for trading_pair in trading_pairs:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            trade_params.append(f"{symbol}@trade")
            depth_params.append(f"{symbol}@depth@100ms")
        payload = {
            "method": "subscribe" if subscribe else "unsubscribe",
            "params": trade_params,
            "id": self._get_next_ws_message_id(),
        }
        trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

        payload = {
            "method": "subscribe" if subscribe else "unsubscribe",
            "params": depth_params,
            "id": self._get_next_ws_message_id(),
        }
        orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

        await ws.send(trade_request)
        await ws.send(orderbook_request)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            event_type = event_message.get("e")
            channel = None
            if event_type == CONSTANTS.DIFF_EVENT_TYPE:
                channel = self._diff_messages_queue_key
            elif event_type == CONSTANTS.TRADE_EVENT_TYPE:
                channel = self._trade_messages_queue_key
        return channel

    @classmethod
    def _get_next_ws_message_id(cls) -> int:
        current_id = cls._next_ws_message_id
        cls._next_ws_message_id += 1
        return current_id
