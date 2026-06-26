import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.backpack_perpetual import (
    backpack_perpetual_constants as CONSTANTS,
    backpack_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_order_book import BackpackPerpetualOrderBook
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
        BackpackPerpetualDerivative,
    )


class BackpackPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'BackpackPerpetualDerivative',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._funding_info_messages_queue_key = CONSTANTS.FUNDING_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        ex_trading_pair = self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"symbol": ex_trading_pair}
        data = await self._connector._api_get(
            path_url=CONSTANTS.MARK_PRICE_PATH_URL,
            params=params,
            throttler_limit_id=CONSTANTS.MARK_PRICE_PATH_URL)
        return FundingInfo(trading_pair=trading_pair,
                           index_price=Decimal(data[0]["indexPrice"]),
                           mark_price=Decimal(data[0]["markPrice"]),
                           next_funding_utc_timestamp=data[0]["nextFundingTimestamp"] * 1e-3,
                           rate=Decimal(data[0]["fundingRate"]))

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "symbol": self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "limit": "1000"
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )
        return data

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL.format(self._domain),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                trading_pair = self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                await self.subscribe_to_trading_pair(trading_pair)
                await self.subscribe_funding_info(trading_pair)
            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected"
            )
            return False

        trade_params = [f"trade.{trading_pair}"]
        payload = {
            "method": "SUBSCRIBE",
            "params": trade_params,
        }
        subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

        depth_params = [f"depth.{trading_pair}"]
        payload = {
            "method": "SUBSCRIBE",
            "params": depth_params,
        }
        subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

        try:
            await self._ws_assistant.send(subscribe_trade_request)
            await self._ws_assistant.send(subscribe_orderbook_request)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error subscribing to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected"
            )
            return False

        trade_params = [f"trade.{trading_pair}"]
        payload = {
            "method": "UNSUBSCRIBE",
            "params": trade_params,
        }
        unsubscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

        depth_params = [f"depth.{trading_pair}"]
        payload = {
            "method": "UNSUBSCRIBE",
            "params": depth_params,
        }
        unsubscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

        try:
            await self._ws_assistant.send(unsubscribe_trade_request)
            await self._ws_assistant.send(unsubscribe_orderbook_request)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Unexpected error occurred unsubscribing from {trading_pair}...",
                exc_info=True
            )
            return False

    async def subscribe_funding_info(self, trading_pair: str) -> None:
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected"
            )
            return

        funding_info_params = [f"markPrice.{trading_pair}"]
        payload = {
            "method": "SUBSCRIBE",
            "params": funding_info_params,
        }
        subscribe_funding_info_request: WSJSONRequest = WSJSONRequest(payload=payload)

        try:
            await self._ws_assistant.send(subscribe_funding_info_request)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Unexpected error occurred subscribing to funding info for {trading_pair}...")

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        stream = event_message.get("stream", "")
        if CONSTANTS.DIFF_EVENT_TYPE in stream:
            channel = self._diff_messages_queue_key
        elif CONSTANTS.TRADE_EVENT_TYPE in stream:
            channel = self._trade_messages_queue_key
        elif CONSTANTS.FUNDING_EVENT_TYPE in stream:
            channel = self._funding_info_messages_queue_key
        return channel

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BackpackPerpetualOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "data" in raw_message and CONSTANTS.DIFF_EVENT_TYPE in raw_message.get("stream"):
            trading_pair = self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["data"]["s"])
            order_book_message: OrderBookMessage = BackpackPerpetualOrderBook.diff_message_from_exchange(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "data" in raw_message and CONSTANTS.TRADE_EVENT_TYPE in raw_message.get("stream"):
            trading_pair = self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["data"]["s"])
            trade_message = BackpackPerpetualOrderBook.trade_message_from_exchange(
                raw_message, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue) -> None:
        data: Dict[str, Any] = raw_message["data"]
        trading_pair: str = self._connector.trading_pair_associated_to_exchange_symbol(data["s"])
        funding_update = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(data["i"]),
            mark_price=Decimal(data["p"]),
            next_funding_utc_timestamp=int(int(data["n"]) * 1e-3),
            rate=Decimal(data["f"])
        )
        message_queue.put_nowait(funding_update)
