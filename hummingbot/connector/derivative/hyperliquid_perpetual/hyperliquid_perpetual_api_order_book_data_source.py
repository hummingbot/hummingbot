import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_derivative import (
        HyperliquidPerpetualDerivative,
    )


class HyperliquidPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    _DYNAMIC_SUBSCRIBE_ID_START = 100
    _next_subscribe_id: int = _DYNAMIC_SUBSCRIBE_ID_START

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'HyperliquidPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._dex_markets = []
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._funding_info_messages_queue_key = "funding_info"
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        # Check if this is a HIP-3 market (contains ":")
        if ":" in ex_trading_pair:
            # HIP-3 markets: Use REST API with dex parameter
            dex_name = ex_trading_pair.split(':')[0]
            try:
                response = await self._connector._api_post(
                    path_url=CONSTANTS.EXCHANGE_INFO_URL,
                    data={"type": "metaAndAssetCtxs", "dex": dex_name})

                universe = response[0]["universe"]
                asset_ctxs = response[1]

                for meta, ctx in zip(universe, asset_ctxs):
                    if meta.get("name") == ex_trading_pair:
                        return FundingInfo(
                            trading_pair=trading_pair,
                            index_price=Decimal(str(ctx.get("oraclePx", "0"))),
                            mark_price=Decimal(str(ctx.get("markPx", "0"))),
                            next_funding_utc_timestamp=self._next_funding_time(),
                            rate=Decimal(str(ctx.get("funding", "0"))),
                        )
            except Exception:
                self.logger().exception(f"Error fetching funding info for HIP-3 market {trading_pair}")

            # If not found, return placeholder
            return FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal('0'),
                mark_price=Decimal('0'),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal('0'),
            )
        else:
            # Base perpetual market: Use REST API
            response: List = await self._request_complete_funding_info(trading_pair)

            for index, i in enumerate(response[0]['universe']):
                if i['name'] == ex_trading_pair:
                    funding_info = FundingInfo(
                        trading_pair=trading_pair,
                        index_price=Decimal(response[1][index]['oraclePx']),
                        mark_price=Decimal(response[1][index]['markPx']),
                        next_funding_utc_timestamp=self._next_funding_time(),
                        rate=Decimal(response[1][index]['funding']),
                    )
                    return funding_info

            # Base market not found, return placeholder
            return FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal('0'),
                mark_price=Decimal('0'),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal('0'),
            )

    async def listen_for_funding_info(self, output: asyncio.Queue):
        """
        Reads the funding info events from WebSocket queue and updates the local funding info information.
        """
        message_queue = self._message_queue[self._funding_info_messages_queue_key]
        while True:
            try:
                funding_info_event = await message_queue.get()
                await self._parse_funding_info_message(funding_info_event, output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public funding info updates from exchange")
                await self._sleep(5)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "type": 'l2Book',
            "coin": ex_trading_pair
        }

        data = await self._connector._api_post(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            data=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_response.update({"trading_pair": trading_pair})
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": snapshot_response["trading_pair"],
            "update_id": int(snapshot_response['time']),
            "bids": [[float(i['px']), float(i['sz'])] for i in snapshot_response['levels'][0]],
            "asks": [[float(i['px']), float(i['sz'])] for i in snapshot_response['levels'][1]],
        }, timestamp=int(snapshot_response['time']))
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
                    "method": "subscribe",
                    "subscription": {
                        "type": CONSTANTS.TRADES_ENDPOINT_NAME,
                        "coin": symbol,
                    }
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

                order_book_payload = {
                    "method": "subscribe",
                    "subscription": {
                        "type": CONSTANTS.DEPTH_ENDPOINT_NAME,
                        "coin": symbol,
                    }
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

                funding_info_payload = {
                    "method": "subscribe",
                    "subscription": {
                        "type": CONSTANTS.FUNDING_INFO_ENDPOINT_NAME,
                        "coin": symbol,
                    }
                }
                subscribe_funding_info_request: WSJSONRequest = WSJSONRequest(payload=funding_info_payload)

                await ws.send(subscribe_trade_request)
                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_funding_info_request)

                self.logger().info("Subscribed to public order book, trade, and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            stream_name = event_message.get("channel")
            if "l2Book" in stream_name:
                channel = self._snapshot_messages_queue_key
            elif "trades" in stream_name:
                channel = self._trade_messages_queue_key
            elif "activeAssetCtx" in stream_name:
                channel = self._funding_info_messages_queue_key
        return channel

    def parse_symbol(self, raw_message) -> str:
        if isinstance(raw_message["data"], list) and len(raw_message["data"]) > 0:
            exchange_symbol = raw_message["data"][0]["coin"]
        else:
            exchange_symbol = raw_message["data"]["coin"]
        return exchange_symbol

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        exchange_symbol = self.parse_symbol(raw_message)
        timestamp: float = raw_message["data"]["time"] * 1e-3
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            exchange_symbol)
        data = raw_message["data"]
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "update_id": data["time"],
            "bids": [[float(i['px']), float(i['sz'])] for i in data["levels"][0]],
            "asks": [[float(i['px']), float(i['sz'])] for i in data["levels"][1]],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        exchange_symbol = self.parse_symbol(raw_message)
        timestamp: float = raw_message["data"]["time"] * 1e-3
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            exchange_symbol)
        data = raw_message["data"]
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": data["time"],
            "bids": [[float(i['px']), float(i['sz'])] for i in data["levels"][0]],
            "asks": [[float(i['px']), float(i['sz'])] for i in data["levels"][1]],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        exchange_symbol = self.parse_symbol(raw_message)
        data = raw_message["data"]
        for trade_data in data:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                exchange_symbol)
            trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade_data["side"] == "A" else float(
                    TradeType.BUY.value),
                "trade_id": trade_data["hash"],
                "price": float(trade_data["px"]),
                "amount": float(trade_data["sz"])
            }, timestamp=trade_data["time"] * 1e-3)

            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        try:
            data: Dict[str, Any] = raw_message["data"]
            # ticker_slim.ETH-PERP.1000

            symbol = data["coin"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

            if trading_pair not in self._trading_pairs:
                return

            # Handle both regular and HIP-3 market formats
            ctx = data.get("ctx", data)  # Fallback to data itself if ctx doesn't exist
            funding_info = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(str(ctx.get("oraclePx", "0"))),
                mark_price=Decimal(str(ctx.get("markPx", "0"))),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal(str(ctx.get("openInterest", ctx.get("funding", "0")))),
            )

            message_queue.put_nowait(funding_info)
        except Exception as e:
            self.logger().debug(f"Error parsing funding info message: {e}")

    async def _request_complete_funding_info(self, trading_pair: str):

        data = await self._connector._api_post(path_url=CONSTANTS.EXCHANGE_INFO_URL,
                                               data={"type": CONSTANTS.ASSET_CONTEXT_TYPE})
        return data

    def _next_funding_time(self) -> int:
        """
        Funding settlement occurs every 1 hours as mentioned in https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
        """
        return int(((time.time() // 3600) + 1) * 3600)

    @classmethod
    def _get_next_subscribe_id(cls) -> int:
        """Get the next subscription ID and increment the counter."""
        subscribe_id = cls._next_subscribe_id
        cls._next_subscribe_id += 1
        return subscribe_id

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """
        Subscribe to order book channels for a single trading pair dynamically.

        :param trading_pair: The trading pair to subscribe to.
        :return: True if subscription was successful, False otherwise.
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot subscribe to {trading_pair}: WebSocket connection not established."
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            coin = symbol.split("-")[0]

            trades_payload = {
                "method": "subscribe",
                "subscription": {
                    "type": CONSTANTS.TRADES_ENDPOINT_NAME,
                    "coin": coin,
                }
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

            order_book_payload = {
                "method": "subscribe",
                "subscription": {
                    "type": CONSTANTS.DEPTH_ENDPOINT_NAME,
                    "coin": coin,
                }
            }
            subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

            await self._ws_assistant.send(subscribe_trade_request)
            await self._ws_assistant.send(subscribe_orderbook_request)

            self.add_trading_pair(trading_pair)
            self.logger().info(f"Successfully subscribed to {trading_pair}")
            return True

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error subscribing to {trading_pair}: {e}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """
        Unsubscribe from order book channels for a single trading pair dynamically.

        :param trading_pair: The trading pair to unsubscribe from.
        :return: True if unsubscription was successful, False otherwise.
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket connection not established."
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            coin = symbol.split("-")[0]

            trades_payload = {
                "method": "unsubscribe",
                "subscription": {
                    "type": CONSTANTS.TRADES_ENDPOINT_NAME,
                    "coin": coin,
                }
            }
            unsubscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

            order_book_payload = {
                "method": "unsubscribe",
                "subscription": {
                    "type": CONSTANTS.DEPTH_ENDPOINT_NAME,
                    "coin": coin,
                }
            }
            unsubscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

            await self._ws_assistant.send(unsubscribe_trade_request)
            await self._ws_assistant.send(unsubscribe_orderbook_request)

            self.remove_trading_pair(trading_pair)
            self.logger().info(f"Successfully unsubscribed from {trading_pair}")
            return True

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error unsubscribing from {trading_pair}: {e}")
            return False
