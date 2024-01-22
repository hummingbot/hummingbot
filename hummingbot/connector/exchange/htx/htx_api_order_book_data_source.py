import asyncio
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.exchange.htx.htx_constants as CONSTANTS
from hummingbot.connector.exchange.htx.htx_web_utils import public_rest_url
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.htx.htx_exchange import HtxExchange


class HtxAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'HtxExchange',
                 api_factory: WebAssistantsFactory,
                 ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._diff_messages_queue_key = CONSTANTS.ORDERBOOK_CHANNEL_SUFFIX
        self._trade_messages_queue_key = CONSTANTS.TRADE_CHANNEL_SUFFIX
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_PUBLIC_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

        return ws

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Suppressing call to this function as the orderbook snapshots are handled by
        listen_for_order_book_diffs() for Htx
        """
        pass

    def snapshot_message_from_exchange(self,
                                       msg: Dict[str, Any],
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:

        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
        msg_ts = msg["tick"]["ts"] * 1e-3
        content = {
            "trading_pair": msg["trading_pair"],
            "update_id": msg["tick"]["ts"],
            "bids": msg["tick"].get("bids", []),
            "asks": msg["tick"].get("asks", [])
        }

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp=msg_ts)

    def trade_message_from_exchange(self,
                                    msg: Dict[str, Any],
                                    metadata: Dict[str, Any] = None) -> OrderBookMessage:
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)

        msg_ts = int(round(msg["ts"] / 1e3))
        content = {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.BUY.value) if msg["direction"] == "buy" else float(TradeType.SELL.value),
            "trade_id": msg["id"],
            "update_id": msg["ts"],
            "amount": msg["amount"],
            "price": msg["price"]
        }
        return OrderBookMessage(OrderBookMessageType.TRADE, content, timestamp=msg_ts)

    async def _request_new_orderbook_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        url = public_rest_url(CONSTANTS.DEPTH_URL)
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        # when type is set to "step0", the default value of "depth" is 150
        params: Dict = {"symbol": exchange_symbol, "type": "step0"}
        snapshot_data = await rest_assistant.execute_request(
            url=url,
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.DEPTH_URL,
        )
        return snapshot_data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_new_orderbook_snapshot(trading_pair)
        snapshot_msg: OrderBookMessage = self.snapshot_message_from_exchange(
            msg=snapshot,
            metadata={"trading_pair": trading_pair},
        )

        return snapshot_msg

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest({
                    "sub": f"market.{exchange_symbol}.depth.step0",
                    "id": str(uuid.uuid4())
                })
                subscribe_trade_request: WSJSONRequest = WSJSONRequest({
                    "sub": f"market.{exchange_symbol}.trade.detail",
                    "id": str(uuid.uuid4())
                })
                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_trade_request)
            self.logger().info("Subscribed to public orderbook and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = event_message.get("ch", "")
        retval = ""
        if channel.endswith(self._trade_messages_queue_key):
            retval = self._trade_messages_queue_key
        if channel.endswith(self._diff_messages_queue_key):
            retval = self._diff_messages_queue_key

        return retval

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):

        ex_symbol = raw_message["ch"].split(".")[1]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=ex_symbol)
        for data in raw_message["tick"]["data"]:
            trade_message: OrderBookMessage = self.trade_message_from_exchange(
                msg=data,
                metadata={"trading_pair": trading_pair}
            )
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        msg_channel = raw_message["ch"]
        order_book_symbol = msg_channel.split(".")[1]
        snapshot_msg: OrderBookMessage = self.snapshot_message_from_exchange(
            msg=raw_message,
            metadata={
                "trading_pair": await self._connector.trading_pair_associated_to_exchange_symbol(order_book_symbol)
            }
        )
        message_queue.put_nowait(snapshot_msg)

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        if "ping" in event_message:
            pong_request = WSJSONRequest(payload={"pong": event_message["ping"]})
            await websocket_assistant.send(request=pong_request)
