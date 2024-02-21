import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from dateutil.parser import parse as dateparse

import hummingbot.connector.exchange.btc_markets.btc_markets_constants as CONSTANTS
from hummingbot.connector.exchange.btc_markets import btc_markets_web_utils as web_utils
from hummingbot.connector.exchange.btc_markets.btc_markets_order_book import BtcMarketsOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.btc_markets.btc_markets_exchange import BtcMarketsExchange


class BtcMarketsAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'BtcMarketsExchange',
            api_factory: WebAssistantsFactory
    ):
        super().__init__(trading_pairs)
        self._connector: BtcMarketsExchange = connector
        self._domain = CONSTANTS.DEFAULT_DOMAIN
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange

        :return: an instance of WSAssistant connected to the exchange
        """
        websocket_assistant: WSAssistant = await self._api_factory.get_ws_assistant()

        await websocket_assistant.connect(
            ws_url=CONSTANTS.WSS_V1_PUBLIC_URL[self._domain],
            ping_timeout=CONSTANTS.WS_PING_TIMEOUT)

        return websocket_assistant

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        self.logger().info("Subscribing ...")
        try:
            marketIds = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                marketIds.append(symbol)

            subscription_payload = {
                "messageType": "subscribe",
                "marketIds": marketIds,
                "channels": [CONSTANTS.DIFF_EVENT_TYPE, CONSTANTS.SNAPSHOT_EVENT_TYPE, CONSTANTS.TRADE_EVENT_TYPE, CONSTANTS.HEARTBEAT]
            }

            subscription_request: WSJSONRequest = WSJSONRequest(payload=subscription_payload)

            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIPTION_LIMIT_ID):
                await websocket_assistant.send(subscription_request)

            self.logger().info("Subscribed to public order book and trade channels for all trading pairs ...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Identifies the channel for a particular event message. Used to find the correct queue to add the message in

        :param event_message: the event received through the websocket connection

        :return: the message channel
        """

        event_type = event_message["messageType"]
        if event_type == CONSTANTS.DIFF_EVENT_TYPE:
            return self._diff_messages_queue_key
        elif event_type == CONSTANTS.SNAPSHOT_EVENT_TYPE:
            return self._snapshot_messages_queue_key
        elif event_type == CONSTANTS.TRADE_EVENT_TYPE:
            return self._trade_messages_queue_key

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data

            channel: str = self._channel_originating_message(event_message=data)
            if channel in [self._diff_messages_queue_key, self._trade_messages_queue_key, self._snapshot_messages_queue_key]:
                self._message_queue[channel].put_nowait(data)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Create an instance of OrderBookMessage of type OrderBookMessageType.TRADE

        :param raw_message: the JSON dictionary of the public trade event
        :param message_queue: queue where the parsed messages should be stored in
        """
        try:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(raw_message["marketId"])
            timestamp: float = float(dateparse(raw_message["timestamp"]).timestamp())

            trade_message: Optional[OrderBookMessage] = BtcMarketsOrderBook.trade_message_from_exchange(
                raw_message, timestamp, {"marketId": trading_pair})

            message_queue.put_nowait(trade_message)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error when processing public trade updates from exchange")

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Create an instance of OrderBookMessage of type OrderBookMessageType.DIFF

        :param raw_message: the JSON dictionary of the public trade event
        :param message_queue: queue where the parsed messages should be stored in
        """
        try:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(raw_message["marketId"])
            timestamp: float = float(dateparse(raw_message["timestamp"]).timestamp())

            diff_message: Optional[OrderBookMessage] = BtcMarketsOrderBook.diff_message_from_exchange(
                raw_message, timestamp, {"marketId": trading_pair})

            message_queue.put_nowait(diff_message)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error when processing public order book updates from exchange")

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        try:
            marketId = raw_message["marketId"]

            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(marketId)
            timestamp: float = float(dateparse(raw_message["timestamp"]).timestamp())

            snapshot_message: Optional[OrderBookMessage] = BtcMarketsOrderBook.snapshot_message_from_exchange_rest(
                raw_message, timestamp, {"marketId": trading_pair})

            message_queue.put_nowait(snapshot_message)

        except asyncio.CancelledError:
            raise
        except Exception:
            marketId = raw_message["marketId"]
            self.logger().error(f"Unexpected error fetching order book snapshot for {marketId}.", exc_info=True)
            await self._sleep(5.0)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        try:
            snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair=trading_pair)
            snapshot_timestamp: float = float(snapshot["snapshotId"])

            return BtcMarketsOrderBook.snapshot_message_from_exchange_rest(
                snapshot,
                snapshot_timestamp,
                metadata={"marketId": trading_pair}
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Unexpected error fetching order book snapshot for {trading_pair}.", exc_info=True)
            await self._sleep(5.0)

    async def get_snapshot(
            self,
            trading_pair: str,
            limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.
        :param trading_pair: the trading pair for which the order book will be retrieved
        :param limit: the depth of the order book to retrieve
        :return: the response from the exchange (JSON dictionary)
        """
        params = {}
        if limit != 0:
            params["limit"] = str(limit)

        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=f"{CONSTANTS.MARKETS_URL}/{ex_trading_pair}/orderbook"),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.MARKETS_URL,
        )

        return data
