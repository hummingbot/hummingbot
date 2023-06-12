import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.crypto_com import (
    crypto_com_constants as CONSTANTS,
    crypto_com_web_utils as web_utils,
)
from hummingbot.connector.exchange.crypto_com.crypto_com_order_book import CryptoComOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.crypto_com.crypto_com_exchange import CryptoComExchange


class CryptoComAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'CryptoComExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._trade_messages_queue_key = CONSTANTS.WS_TRADE_CHANNEL
        self._diff_messages_queue_key = CONSTANTS.WS_DIFF_CHANNEL
        self._snapshot_messages_queue_key = CONSTANTS.WS_SNAPSHOT_CHANNEL
        self._connector = connector
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
            "instrument_name": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "depth": "50"
        }

        params = self._connector.generate_crypto_com_request(method=CONSTANTS.SNAPSHOT_PATH_URL, params=params)

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

        order_book_data = data["result"]["data"][0]

        return order_book_data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            trade_channels = []
            depth_channels = []
            for trading_pair in self._trading_pairs:
                instrument_name = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trade_channels.append(f"trade.{instrument_name}")
                depth_channels.append(f"depth.{instrument_name}.50")

            trade_params = {
                "channels": trade_channels
            }
            depth_params = {
                "channels": depth_channels,
                "book_subscription_type": "SNAPSHOT_AND_UPDATE",
                "book_update_frequency": 10
            }

            trade_payload = self._connector.generate_crypto_com_request(method=CONSTANTS.WS_SUBSCRIBE, params=trade_params)
            trade_subscribe_request: WSJSONRequest = WSJSONRequest(payload=trade_payload)
            depth_payload = self._connector.generate_crypto_com_request(method=CONSTANTS.WS_SUBSCRIBE, params=depth_params)
            depth_subscribe_request: WSJSONRequest = WSJSONRequest(payload=depth_payload)

            await ws.send(trade_subscribe_request)
            await ws.send(depth_subscribe_request)

            self.logger().info("Subscribed to Crytp.com Public Order Book and Trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to Crytp.com Public Order Book and Trade channels...",
                exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_PUBLIC_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        self.logger().info("Connected to Cryto.com Public WebSocket.")

        await self._sleep(1.0)  # Sleep for 1 second before sending the requests, recommended by the exchange.
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = CryptoComOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        result = raw_message["result"]
        # extracting instrument_name from subscription string
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=result["subscription"].split(".")[1])
        for trade in result["data"]:
            trade_message: OrderBookMessage = CryptoComOrderBook.trade_message_from_exchange(
                trade, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        result = raw_message["result"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=result["instrument_name"])
        for diff in result["data"]:
            diff_message: OrderBookMessage = CryptoComOrderBook.diff_message_from_exchange(
                diff, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(diff_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        result = raw_message["result"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=result["instrument_name"])
        for snapshot in result["data"]:
            snapshot_message: OrderBookMessage = CryptoComOrderBook.snapshot_message_from_exchange(
                snapshot, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(snapshot_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" in event_message:
            channel = event_message["result"].get("channel")
        return channel

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data
            if data is not None:  # data will be None when the websocket is disconnected
                # deal with heartbeat messages
                if data.get("method", "") == CONSTANTS.WS_PING:
                    # respond to the heartbeat message
                    pong = {
                        "id": data.get("id"),
                        "method": CONSTANTS.WS_PONG,
                    }

                    respond_heartbeat: WSJSONRequest = WSJSONRequest(payload=pong)
                    await websocket_assistant.send(respond_heartbeat)

                    continue

                channel: str = self._channel_originating_message(event_message=data)
                valid_channels = self._get_messages_queue_keys()
                if channel in valid_channels:
                    self._message_queue[channel].put_nowait(data)
                else:
                    await self._process_message_for_unknown_channel(
                        event_message=data, websocket_assistant=websocket_assistant
                    )
