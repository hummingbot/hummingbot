import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import (
        BinancePerpetualDerivative,
    )


class BinancePerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()
    _DYNAMIC_SUBSCRIBE_ID_START = 100
    _next_subscribe_id: int = _DYNAMIC_SUBSCRIBE_ID_START

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'BinancePerpetualDerivative',
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
        self._market_ws_assistant: Optional[WSAssistant] = None

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol_info: Dict[str, Any] = await self._request_complete_funding_info(trading_pair)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(symbol_info["indexPrice"]),
            mark_price=Decimal(symbol_info["markPrice"]),
            next_funding_utc_timestamp=int(float(symbol_info["nextFundingTime"]) * 1e-3),
            rate=Decimal(symbol_info["lastFundingRate"]),
        )
        return funding_info

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        params = {
            "symbol": ex_trading_pair,
            "limit": "1000"
        }

        data = await self._connector._api_get(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            params=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_response.update({"trading_pair": trading_pair})
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": snapshot_response["trading_pair"],
            "update_id": snapshot_response["lastUpdateId"],
            "bids": snapshot_response["bids"],
            "asks": snapshot_response["asks"]
        }, timestamp=snapshot_timestamp)
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _connected_market_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(CONSTANTS.MARKET_WS_ENDPOINT, self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_public_channels(self, ws: WSAssistant):
        try:
            params = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                params.append(f"{symbol.lower()}@depth")
            payload = {
                "method": "SUBSCRIBE",
                "params": params,
                "id": CONSTANTS.DIFF_STREAM_ID,
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload)
            await ws.send(subscribe_request)
            self.logger().info("Subscribed to public order book channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book streams...")
            raise

    async def _subscribe_market_channels(self, ws: WSAssistant):
        try:
            for stream_id, channel in [
                (CONSTANTS.TRADE_STREAM_ID, "@aggTrade"),
                (CONSTANTS.FUNDING_INFO_STREAM_ID, "@markPrice"),
            ]:
                params = []
                for trading_pair in self._trading_pairs:
                    symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                    params.append(f"{symbol.lower()}{channel}")
                payload = {
                    "method": "SUBSCRIBE",
                    "params": params,
                    "id": stream_id,
                }
                subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                await ws.send(subscribe_request)
            self.logger().info("Subscribed to market trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to market streams...")
            raise

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to depth channels on the public WS connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        await self._subscribe_public_channels(ws)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            stream_name = event_message.get("stream")
            if "@depth" in stream_name:
                channel = self._diff_messages_queue_key
            elif "@aggTrade" in stream_name:
                channel = self._trade_messages_queue_key
            elif "@markPrice" in stream_name:
                channel = self._funding_info_messages_queue_key
        return channel

    async def listen_for_subscriptions(self):
        public_ws: Optional[WSAssistant] = None
        market_ws: Optional[WSAssistant] = None
        while True:
            try:
                public_ws = await self._connected_websocket_assistant()
                self._ws_assistant = public_ws
                await self._subscribe_public_channels(public_ws)

                market_ws = await self._connected_market_websocket_assistant()
                self._market_ws_assistant = market_ws
                await self._subscribe_market_channels(market_ws)

                public_task = asyncio.ensure_future(
                    self._process_websocket_messages(websocket_assistant=public_ws))
                market_task = asyncio.ensure_future(
                    self._process_websocket_messages(websocket_assistant=market_ws))

                done, pending = await asyncio.wait(
                    [public_task, market_task],
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                for task in pending:
                    task.cancel()
                for task in done:
                    task.result()
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                )
                await self._sleep(1.0)
            finally:
                self._ws_assistant = None
                self._market_ws_assistant = None
                await self._on_order_stream_interruption(websocket_assistant=public_ws)
                if market_ws is not None:
                    await market_ws.disconnect()

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = time.time()
        raw_message["data"]["s"] = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["data"]["s"])
        data = raw_message["data"]
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": data["s"],
            "update_id": data["u"],
            "bids": data["b"],
            "asks": data["a"]
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raw_message["data"]["s"] = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["data"]["s"])
        data = raw_message["data"]
        trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": data["s"],
            "trade_type": float(TradeType.SELL.value) if data["m"] else float(TradeType.BUY.value),
            "trade_id": data["a"],
            "update_id": data["E"],
            "price": data["p"],
            "amount": data["q"]
        }, timestamp=data["E"] * 1e-3)

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

        data: Dict[str, Any] = raw_message["data"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(data["s"])

        if trading_pair not in self._trading_pairs:
            return
        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(data["i"]),
            mark_price=Decimal(data["p"]),
            next_funding_utc_timestamp=int(float(data["T"]) * 1e-3),
            rate=Decimal(data["r"]),
        )

        message_queue.put_nowait(funding_info)

    async def _request_complete_funding_info(self, trading_pair: str):
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=CONSTANTS.MARK_PRICE_URL,
            params={"symbol": ex_trading_pair},
            is_auth_required=True)
        return data

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """
        Subscribes to order book, trade, and funding info channels for a single trading pair
        on the existing WebSocket connections.

        :param trading_pair: the trading pair to subscribe to
        :return: True if subscription was successful, False otherwise
        """
        if self._ws_assistant is None or self._market_ws_assistant is None:
            self.logger().warning(
                f"Cannot subscribe to {trading_pair}: WebSocket not connected"
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            # Subscribe to @depth on public WS
            depth_payload = {
                "method": "SUBSCRIBE",
                "params": [f"{symbol.lower()}@depth"],
                "id": self._get_next_subscribe_id(),
            }
            await self._ws_assistant.send(WSJSONRequest(depth_payload))

            # Subscribe to @aggTrade and @markPrice on market WS
            for channel in ["@aggTrade", "@markPrice"]:
                market_payload = {
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol.lower()}{channel}"],
                    "id": self._get_next_subscribe_id(),
                }
                await self._market_ws_assistant.send(WSJSONRequest(market_payload))

            self.add_trading_pair(trading_pair)
            self.logger().info(f"Subscribed to {trading_pair} order book, trade and funding info channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error subscribing to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """
        Unsubscribes from order book, trade, and funding info channels for a single trading pair
        on the existing WebSocket connections.

        :param trading_pair: the trading pair to unsubscribe from
        :return: True if unsubscription was successful, False otherwise
        """
        if self._ws_assistant is None or self._market_ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected"
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            # Unsubscribe @depth from public WS
            depth_payload = {
                "method": "UNSUBSCRIBE",
                "params": [f"{symbol.lower()}@depth"],
                "id": self._get_next_subscribe_id(),
            }
            await self._ws_assistant.send(WSJSONRequest(depth_payload))

            # Unsubscribe @aggTrade and @markPrice from market WS
            market_payload = {
                "method": "UNSUBSCRIBE",
                "params": [
                    f"{symbol.lower()}@aggTrade",
                    f"{symbol.lower()}@markPrice",
                ],
                "id": self._get_next_subscribe_id(),
            }
            await self._market_ws_assistant.send(WSJSONRequest(market_payload))

            self.remove_trading_pair(trading_pair)
            self.logger().info(f"Unsubscribed from {trading_pair} order book, trade and funding info channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error unsubscribing from {trading_pair}")
            return False

    @classmethod
    def _get_next_subscribe_id(cls) -> int:
        """Returns the next subscription ID and increments the counter."""
        current_id = cls._next_subscribe_id
        cls._next_subscribe_id += 1
        return current_id
