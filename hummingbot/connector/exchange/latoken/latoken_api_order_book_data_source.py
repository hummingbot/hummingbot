import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import ujson

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
import hummingbot.connector.exchange.latoken.latoken_stomper as stomper
from hummingbot.connector.exchange.latoken import latoken_web_utils as web_utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.event.events import TradeType
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSPlainTextRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.latoken.latoken_exchange import LatokenExchange


class LatokenAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'LatokenExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str, limit: int = CONSTANTS.SNAPSHOT_LIMIT_SIZE) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved
        :param limit: the depth of the order book to retrieve

        :return: the response from the exchange (JSON dictionary)
        """
        params = {}
        if limit != 0:
            params["limit"] = str(limit)

        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=f"{CONSTANTS.SNAPSHOT_PATH_URL}/{symbol}", domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL
        )

        return data

    async def _subscribe_channels(self, client: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param client: the websocket assistant used to connect to the exchange
        """
        try:
            subscriptions = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                path_params = {'symbol': symbol}
                msg_subscribe_books = stomper.subscribe(CONSTANTS.BOOK_STREAM.format(**path_params),
                                                        f"{CONSTANTS.SUBSCRIPTION_ID_BOOKS}_{trading_pair}", ack="auto")
                msg_subscribe_trades = stomper.subscribe(CONSTANTS.TRADES_STREAM.format(**path_params),
                                                         f"{CONSTANTS.SUBSCRIPTION_ID_TRADES}_{trading_pair}",
                                                         ack="auto")

                subscriptions.append(client.subscribe(WSPlainTextRequest(payload=msg_subscribe_books)))
                subscriptions.append(client.subscribe(WSPlainTextRequest(payload=msg_subscribe_trades)))

            _ = await safe_gather(*subscriptions)
            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.ws_url(self._domain), ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        connect_request: WSPlainTextRequest = WSPlainTextRequest(payload=CONSTANTS.WS_CONNECT_MSG, is_auth_required=True)
        await ws.send(connect_request)
        _ = await ws.receive()
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        timestamp_seconds = snapshot_timestamp * 1e-9
        content = {
            "asks": web_utils.get_book_side(snapshot.pop("ask")),
            "bids": web_utils.get_book_side(snapshot.pop("bid")),
            "update_id": timestamp_seconds,
            "trading_pair": trading_pair}
        snapshot_msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp=timestamp_seconds)
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol = raw_message['headers']['destination'].replace('/v1/trade/', '')
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)

        body = ujson.loads(raw_message["body"])
        payload = body["payload"]
        timestamp = time.time_ns()
        for trade in payload:  # body_timestamp = body['timestamp']
            ts_seconds = timestamp * 1e-9
            trade_type = float(TradeType.BUY.value) if trade["makerBuyer"] else float(TradeType.SELL.value)
            content = {
                "trading_pair": trading_pair,
                "trade_type": trade_type,
                "trade_id": trade["timestamp"] * 1e-3,  # could also use msg['headers']['message-id'] ?
                "update_id": ts_seconds,  # do we need body_timestamp here???
                "price": trade["price"],
                "amount": trade["quantity"]}
            trade_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, content, ts_seconds)
            message_queue.put_nowait(trade_msg)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol = raw_message['headers']['destination'].replace('/v1/book/', '')
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        body = ujson.loads(raw_message["body"])
        payload = body["payload"]
        timestamp_ns = time.time_ns()
        timestamp_seconds = timestamp_ns * 1e-9
        content = {
            "trading_pair": trading_pair,
            "first_update_id": body["timestamp"],  # could also use msg['headers']['message-id'] ?
            "update_id": timestamp_seconds,
            "bids": web_utils.get_book_side(payload["bid"]),
            "asks": web_utils.get_book_side(payload["ask"])}
        order_book_message = OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp_seconds)
        message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        event_type = int(event_message['headers']['subscription'].split('_')[0])

        channel: str = ""
        if event_type == CONSTANTS.SUBSCRIPTION_ID_TRADES:
            channel = self._trade_messages_queue_key
        elif event_type == CONSTANTS.SUBSCRIPTION_ID_BOOKS:
            channel = self._diff_messages_queue_key
        else:
            self.logger().error(f"Unsubscribed id {event_type} packet received {event_message}")

        return channel
