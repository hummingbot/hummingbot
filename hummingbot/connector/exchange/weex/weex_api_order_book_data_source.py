import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.weex import weex_constants as CONSTANTS, weex_web_utils as web_utils
from hummingbot.connector.exchange.weex.weex_order_book import WeexOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange


class WeexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'WeexExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "type": "step0",
            "limit": "15"
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_SNAPSHOT_LIMIT_ID,
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trade_payload = {
                    "event": "subscribe",
                    "channel": f"trades.{symbol}"
                }
                depth_payload = {
                    "event": "subscribe",
                    "channel": f"depth.{symbol}.15"
                }
                await ws.send(WSJSONRequest(payload=trade_payload))
                await ws.send(WSJSONRequest(payload=depth_payload))

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _send_ping(self, ws: WSAssistant):
        """Send periodic ping to keep public WebSocket connection alive"""
        while True:
            try:
                await asyncio.sleep(20)  # Ping every 20s (WEEX times out at ~30s)
                ping_payload = {"event": "ping", "time": int(time.time() * 1000)}
                await ws.send(WSJSONRequest(payload=ping_payload))
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger().warning(f"Error sending ping on public WS: {e}")
                break

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.ws_public_url(self._domain),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
                         ws_headers={"User-Agent": "hummingbot"})
        return ws

    async def listen_for_subscriptions(self):
        """
        Override to add periodic ping for WEEX public WebSocket
        """
        ws: Optional[WSAssistant] = None
        ping_task = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant()
                self._ws_assistant = ws
                await self._subscribe_channels(ws)

                # Start periodic ping to keep connection alive
                ping_task = asyncio.create_task(self._send_ping(ws))

                await self._process_websocket_messages(websocket_assistant=ws)
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
                if ping_task is not None:
                    ping_task.cancel()
                    ping_task = None
                self._ws_assistant = None
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = WeexOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if raw_message.get("event") != "payload" or "data" not in raw_message:
            return

        channel = raw_message.get("channel", "")
        if not channel.startswith("trades."):
            return

        symbol = channel.split(".", 1)[1]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        for trade in raw_message.get("data", []):
            trade_message = WeexOrderBook.trade_message_from_exchange(
                trade, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if raw_message.get("event") != "payload" or "data" not in raw_message:
            return

        channel = raw_message.get("channel", "")
        if not channel.startswith("depth."):
            return

        for depth_update in raw_message.get("data", []):
            symbol = depth_update.get("symbol")
            if symbol is None:
                continue
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
            order_book_message: OrderBookMessage = WeexOrderBook.diff_message_from_exchange(
                depth_update, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if event_message.get("event") == "payload":
            ws_channel = event_message.get("channel", "")
            if ws_channel.startswith("depth."):
                channel = self._diff_messages_queue_key
            elif ws_channel.startswith("trades."):
                channel = self._trade_messages_queue_key
        return channel

    async def _subscribe_from_trading_pair(self, ws: WSAssistant, trading_pair: str):
        """
        Subscribe to a single trading pair's channels (for dynamic trading pair updates).
        """
        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            # Subscribe to trades
            trade_payload = {
                "event": "subscribe",
                "channel": f"trades.{symbol}"
            }
            await ws.send(WSJSONRequest(payload=trade_payload))

            # Subscribe to order book depth
            depth_payload = {
                "event": "subscribe",
                "channel": f"depth.{symbol}.15"
            }
            await ws.send(WSJSONRequest(payload=depth_payload))

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Unexpected error occurred subscribing to {trading_pair}...",
                exc_info=True
            )
            raise

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """
        Subscribes to order book and trade channels for a single trading pair on the
        existing WebSocket connection.

        :param trading_pair: the trading pair to subscribe to
        :return: True if subscription was successful, False otherwise
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot subscribe to {trading_pair}: WebSocket not connected"
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            # Subscribe to trade stream
            trade_payload = {
                "event": "subscribe",
                "channel": f"trades.{symbol}"
            }
            await self._ws_assistant.send(WSJSONRequest(payload=trade_payload))

            # Subscribe to depth stream
            depth_payload = {
                "event": "subscribe",
                "channel": f"depth.{symbol}.15"
            }
            await self._ws_assistant.send(WSJSONRequest(payload=depth_payload))

            # Add to trading pairs list
            self.add_trading_pair(trading_pair)

            self.logger().info(f"Subscribed to {trading_pair} order book and trade channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                f"Unexpected error subscribing to {trading_pair} channels"
            )
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """
        Unsubscribes from order book and trade channels for a single trading pair on the
        existing WebSocket connection.

        :param trading_pair: the trading pair to unsubscribe from
        :return: True if unsubscription was successful, False otherwise
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected"
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            # Unsubscribe from both trade and depth streams
            unsubscribe_trade_payload = {
                "event": "unsubscribe",
                "channel": f"trades.{symbol}"
            }
            unsubscribe_depth_payload = {
                "event": "unsubscribe",
                "channel": f"depth.{symbol}.15"
            }
            await self._ws_assistant.send(WSJSONRequest(payload=unsubscribe_trade_payload))
            await self._ws_assistant.send(WSJSONRequest(payload=unsubscribe_depth_payload))

            # Remove from trading pairs list
            self.remove_trading_pair(trading_pair)

            self.logger().info(f"Unsubscribed from {trading_pair} order book and trade channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                f"Unexpected error unsubscribing from {trading_pair} channels"
            )
            return False
