import asyncio
import json
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

from hummingbot.connector.derivative.gate_io_perpetual import (
    gate_io_perpetual_constants as CONSTANTS,
    gate_io_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book import OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_derivative import GateIoPerpetualDerivative


class GateIoPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'GateIoPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info_response = await self._request_complete_funding_info(trading_pair)
        symbol_info: Dict[str, Any] = funding_info_response
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(symbol_info["index_price"])),
            mark_price=Decimal(str(symbol_info["mark_price"])),
            next_funding_utc_timestamp=int(symbol_info["funding_next_apply"]),
            rate=Decimal(str(symbol_info["funding_rate_indicative"])),
        )
        return funding_info

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = self._time()
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": snapshot_response["id"],
                "bids": [[i['p'], self._connector._format_size_to_amount(trading_pair, Decimal(str(i['s'])))] for i in
                         snapshot_response["bids"]],
                "asks": [[i['p'], self._connector._format_size_to_amount(trading_pair, Decimal(str(i['s'])))] for i in
                         snapshot_response["asks"]],
            },
            timestamp=snapshot_timestamp)
        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "contract": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "with_id": json.dumps(True)
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url=web_utils.public_rest_url(endpoint=CONSTANTS.ORDER_BOOK_PATH_URL),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
        )

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        for trade_data in raw_message["result"]:
            trade_timestamp: int = trade_data["create_time"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=trade_data["contract"])
            message_content = {
                "trading_pair": trading_pair,
                "trade_type": (float(TradeType.SELL.value)
                               if trade_data["size"] < 0
                               else float(TradeType.BUY.value)),
                "trade_id": trade_data["id"],
                "update_id": trade_timestamp,
                "price": trade_data["price"],
                "amount": abs(self._connector._format_size_to_amount(trading_pair, (Decimal(str(trade_data["size"])))))
            }
            trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=trade_timestamp)

            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        diff_data: [str, Any] = raw_message["result"]
        timestamp: float = (diff_data["t"]) * 1e-3
        update_id: int = diff_data["u"]

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=diff_data["s"])

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "first_update_id": diff_data["U"],
            "bids": [[i['p'], self._connector._format_size_to_amount(trading_pair, Decimal(str(i['s'])))] for i in
                     diff_data["b"]],
            "asks": [[i['p'], self._connector._format_size_to_amount(trading_pair, Decimal(str(i['s'])))] for i in
                     diff_data["a"]],
        }
        diff_message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.DIFF,
            order_book_message_content,
            timestamp)

        message_queue.put_nowait(diff_message)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                trades_payload = {
                    "time": int(self._time()),
                    "channel": CONSTANTS.TRADES_ENDPOINT_NAME,
                    "event": "subscribe",
                    "payload": [symbol]
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

                order_book_payload = {
                    "time": int(self._time()),
                    "channel": CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME,
                    "event": "subscribe",
                    "payload": [symbol, "100ms"]
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
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", event_message.get("error"))
            raise IOError(f"Error event received from the server ({err_msg})")
        elif event_message.get("event") == "update":
            if event_message.get("channel") == CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME:
                channel = self._diff_messages_queue_key
            elif event_message.get("channel") == CONSTANTS.TRADES_ENDPOINT_NAME:
                channel = self._trade_messages_queue_key

        return channel

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_URL, ping_timeout=CONSTANTS.PING_TIMEOUT)
        return ws

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event_type = raw_message["event"]
        if event_type == "update":
            symbol = raw_message['result'][0]["contract"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            entries = raw_message['result']
            for entry in entries:
                info_update = FundingInfoUpdate(trading_pair)
                if "index_price" in entry:
                    info_update.index_price = Decimal(str(entry["index_price"]))
                if "mark_price" in entry:
                    info_update.mark_price = Decimal(str(entry["mark_price"]))
                if "next_funding_time" in entry:
                    info_update.next_funding_utc_timestamp = int(
                        pd.Timestamp(str(entry["next_funding_time"]), tz="UTC").timestamp()
                    )
                if "funding_rate_indicative" in entry:
                    info_update.rate = (
                        Decimal(str(entry["funding_rate_indicative"]))
                    )
                message_queue.put_nowait(info_update)

    async def _request_complete_funding_info(self, trading_pair: str):
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(endpoint=CONSTANTS.MARK_PRICE_URL.format(id=ex_trading_pair)),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.MARK_PRICE_URL,
        )
        return data
