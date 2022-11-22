import asyncio
import sys
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.bitget_perpetual import (
    bitget_perpetual_constants as CONSTANTS,
    bitget_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest, WSPlainTextRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative


class BitgetPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):

    FULL_ORDER_BOOK_RESET_DELTA_SECONDS = sys.maxsize

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'BitgetPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = ""
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._diff_messages_queue_key = "books"
        self._trade_messages_queue_key = "trade"
        self._funding_info_messages_queue_key = "ticker"
        self._pong_response_event = None

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info_response = await self._request_complete_funding_info(trading_pair)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(funding_info_response["amount"]),
            mark_price=Decimal(funding_info_response["markPrice"]),
            next_funding_utc_timestamp=int(int(funding_info_response["fundingTime"]) * 1e-3),
            rate=Decimal(funding_info_response["fundingRate"]),
        )
        return funding_info

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        while True:
            try:
                await asyncio.wait_for(
                    super()._process_websocket_messages(websocket_assistant=websocket_assistant),
                    timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE)
            except asyncio.TimeoutError:
                if self._pong_response_event and not self._pong_response_event.is_set():
                    # The PONG response for the previous PING request was never received
                    raise IOError("The user stream channel is unresponsive (pong response not received)")
                self._pong_response_event = asyncio.Event()
                await self._send_ping(websocket_assistant=websocket_assistant)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if event_message == CONSTANTS.WS_PONG_RESPONSE and self._pong_response_event:
            self._pong_response_event.set()
        elif "event" in event_message:
            if event_message["event"] == "error":
                raise IOError(f"Public channel subscription failed ({event_message})")
        elif "arg" in event_message:
            channel = event_message["arg"].get("channel")
            if channel == CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC and event_message.get("action") == "snapshot":
                channel = self._snapshot_messages_queue_key

        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        inst_id = raw_message["arg"]["instId"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_instrument_id(instrument_id=inst_id)

        for book in data:
            update_id = int(book["ts"])
            timestamp = update_id * 1e-3

            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": book["bids"],
                "asks": book["asks"],
            }
            diff_message = OrderBookMessage(
                message_type=OrderBookMessageType.DIFF,
                content=order_book_message_content,
                timestamp=timestamp
            )

            message_queue.put_nowait(diff_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        inst_id = raw_message["arg"]["instId"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_instrument_id(instrument_id=inst_id)

        for book in data:
            update_id = int(book["ts"])
            timestamp = update_id * 1e-3

            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": book["bids"],
                "asks": book["asks"],
            }
            snapshot_msg: OrderBookMessage = OrderBookMessage(
                message_type=OrderBookMessageType.SNAPSHOT,
                content=order_book_message_content,
                timestamp=timestamp
            )
            message_queue.put_nowait(snapshot_msg)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", [])
        inst_id = raw_message["arg"]["instId"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_instrument_id(instrument_id=inst_id)

        for trade_data in data:
            ts_ms = int(trade_data[0])
            trade_type = float(TradeType.BUY.value) if trade_data[3] == "buy" else float(TradeType.SELL.value)
            message_content = {
                "trade_id": ts_ms,
                "trading_pair": trading_pair,
                "trade_type": trade_type,
                "amount": trade_data[2],
                "price": trade_data[1],
            }
            trade_message = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=ts_ms * 1e-3,
            )
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        entries = raw_message.get("data", [])
        inst_id = raw_message["arg"]["instId"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_instrument_id(instrument_id=inst_id)

        for entry in entries:
            info_update = FundingInfoUpdate(trading_pair)
            info_update.index_price = Decimal(entry["indexPrice"])
            info_update.mark_price = Decimal(entry["markPrice"])
            info_update.next_funding_utc_timestamp = int(entry["nextSettleTime"]) * 1e-3
            info_update.rate = Decimal(entry["capitalRate"])
            message_queue.put_nowait(info_update)

    async def _request_complete_funding_info(self, trading_pair: str) -> Dict[str, Any]:
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair),
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoints = [
            CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL,
            CONSTANTS.OPEN_INTEREST_PATH_URL,
            CONSTANTS.MARK_PRICE_PATH_URL,
            CONSTANTS.FUNDING_SETTLEMENT_TIME_PATH_URL
        ]
        tasks = []
        for endpoint in endpoints:
            tasks.append(rest_assistant.execute_request(
                url=web_utils.get_rest_url_for_endpoint(endpoint=endpoint),
                throttler_limit_id=endpoint,
                params=params,
                method=RESTMethod.GET,
            ))
        results = await safe_gather(*tasks)
        funding_info = {}
        for result in results:
            funding_info.update(result["data"])
        return funding_info

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_URL, message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            payloads = []

            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair_without_product_type(
                    trading_pair=trading_pair
                )

                for channel in [
                    self._diff_messages_queue_key,
                    self._trade_messages_queue_key,
                    self._funding_info_messages_queue_key,
                ]:
                    payloads.append({
                        "instType": "mc",
                        "channel": channel,
                        "instId": symbol
                    })
            final_payload = {
                "op": "subscribe",
                "args": payloads,
            }
            subscribe_request = WSJSONRequest(payload=final_payload)
            await ws.send(subscribe_request)
            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "symbol": symbol,
            "limit": "100",
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_ENDPOINT),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_ENDPOINT,
        )

        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_data: Dict[str, Any] = snapshot_response["data"]
        update_id: int = int(snapshot_data["timestamp"])
        snapshot_timestamp: float = update_id * 1e-3

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(price, amount) for price, amount in snapshot_data.get("bids", [])],
            "asks": [(price, amount) for price, amount in snapshot_data.get("asks", [])],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp)

        return snapshot_msg

    async def _send_ping(self, websocket_assistant: WSAssistant):
        ping_request = WSPlainTextRequest(payload=CONSTANTS.WS_PING_REQUEST)
        await websocket_assistant.send(ping_request)
