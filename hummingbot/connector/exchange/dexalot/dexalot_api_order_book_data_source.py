import asyncio
import math
import time
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.dexalot import dexalot_constants as CONSTANTS
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.dexalot.dexalot_exchange import DexalotExchange


class DexalotAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'DexalotExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        pass

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            if not self._connector._evm_params:
                await self._connector._update_trading_rules()
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                min_price_increment = self._connector.trading_rules[trading_pair].min_price_increment
                show_decimal = int(-math.log10(min_price_increment))
                payload = {
                    "data": symbol,
                    "pair": symbol,
                    "type": "subscribe",
                    "decimal": show_decimal
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)
                await ws.send(subscribe_orderbook_request)

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
        await ws.connect(ws_url=CONSTANTS.WSS_URL,
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        # snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = self._time()
        # snapshot_msg: OrderBookMessage = DexalotOrderBook.snapshot_message_from_exchange(
        #     snapshot,
        #     snapshot_timestamp,
        #     metadata={"trading_pair": trading_pair}
        # )
        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": snapshot_timestamp,
            "bids": [],
            "asks": [],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp)
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["pair"])
        for trade_data in raw_message["data"]:
            timestamp = int(datetime.strptime(trade_data['ts'], '%Y-%m-%dT%H:%M:%S.%fZ').timestamp())
            trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade_data["takerSide"] == 1 else float(
                    TradeType.BUY.value),
                "trade_id": trade_data["execId"],
                "price": trade_data["price"],
                "amount": trade_data["quantity"]
            }, timestamp=timestamp)

            message_queue.put_nowait(trade_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = time.time()

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["pair"])

        data = raw_message["data"]
        row_bids = [[price, amount] for price, amount in
                    zip(data["buyBook"][0]["prices"].split(','), data["buyBook"][0]["quantities"].split(','))]
        row_asks = [[price, amount] for price, amount in
                    zip(data["sellBook"][0]["prices"].split(','), data["sellBook"][0]["quantities"].split(','))]

        bids = [list(self._connector._format_evmamount_to_amount(trading_pair, Decimal(evm_price), Decimal(evm_amount)))
                for
                evm_price, evm_amount in row_bids]
        asks = [list(self._connector._format_evmamount_to_amount(trading_pair, Decimal(evm_price), Decimal(evm_amount)))
                for
                evm_price, evm_amount in row_asks]

        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": timestamp,
            "bids": bids,
            "asks": asks
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Suppressing call to this function as the orderbook snapshots are handled by
        listen_for_order_book_diffs() for dexalot
        """
        pass

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        stream_name = event_message.get("type")
        if stream_name == "orderBooks":
            channel = self._snapshot_messages_queue_key
        elif stream_name == "lastTrade":
            channel = self._trade_messages_queue_key
        return channel

    def _time(self):
        return time.time()
