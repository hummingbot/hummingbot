import asyncio
import sys
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import dateutil.parser as dp

from hummingbot.connector.derivative.dydx_v4_perpetual import (
    dydx_v4_perpetual_constants as CONSTANTS,
    dydx_v4_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book import OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_derivative import DydxV4PerpetualDerivative


class DydxV4PerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    FULL_ORDER_BOOK_RESET_DELTA_SECONDS = sys.maxsize

    def __init__(
            self,
            trading_pairs: List[str],
            connector: "DydxV4PerpetualDerivative",
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._nonce_provider = NonceCreator.for_microseconds()

    def _time(self):
        return time.time()

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info_response = await self._request_complete_funding_info(trading_pair)
        market_info: Dict[str, Any] = funding_info_response["markets"][trading_pair]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(market_info["oraclePrice"])),
            mark_price=Decimal(str(market_info["oraclePrice"])),
            next_funding_utc_timestamp=self._next_funding_time(),
            rate=Decimal(str(market_info["nextFundingRate"])),
        )
        return funding_info

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(
                    payload={
                        "type": CONSTANTS.WS_TYPE_SUBSCRIBE,
                        "channel": CONSTANTS.WS_CHANNEL_ORDERBOOK,
                        "id": trading_pair,
                    },
                    is_auth_required=False,
                )
                subscribe_trades_request: WSJSONRequest = WSJSONRequest(
                    payload={
                        "type": CONSTANTS.WS_TYPE_SUBSCRIBE,
                        "channel": CONSTANTS.WS_CHANNEL_TRADES,
                        "id": trading_pair,
                    },
                    is_auth_required=False,
                )
                subscribe_markets_request: WSJSONRequest = WSJSONRequest(
                    payload={
                        "type": CONSTANTS.WS_TYPE_SUBSCRIBE,
                        "channel": CONSTANTS.WS_CHANNEL_MARKETS,
                        "id": trading_pair,
                    },
                    is_auth_required=False,
                )
                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_trades_request)
                await ws.send(subscribe_markets_request)
            self.logger().info("Subscribed to public orderbook and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "channel" in event_message:
            event_channel = event_message["channel"]
            event_type = event_message["type"]
            if event_channel == CONSTANTS.WS_CHANNEL_TRADES:
                channel = self._trade_messages_queue_key
            elif event_channel == CONSTANTS.WS_CHANNEL_ORDERBOOK:
                if event_type == CONSTANTS.WS_TYPE_SUBSCRIBED:
                    channel = self._snapshot_messages_queue_key
                if event_type == CONSTANTS.WS_TYPE_CHANNEL_DATA:
                    channel = self._diff_messages_queue_key
            elif event_channel == CONSTANTS.WS_CHANNEL_MARKETS:
                channel = self._funding_info_messages_queue_key
        return channel

    async def _make_order_book_message(
            self,
            raw_message: Dict[str, Any],
            message_queue: asyncio.Queue,
            bids: List[Tuple[float, float]],
            asks: List[Tuple[float, float]],
            message_type: OrderBookMessageType,
    ):
        symbol = raw_message["id"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        timestamp_s = self._time()
        update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp_s)

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        message = OrderBookMessage(
            message_type=message_type,
            content=order_book_message_content,
            timestamp=timestamp_s,
        )
        message_queue.put_nowait(message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if raw_message["type"] in ["subscribed", "channel_data"]:
            bids, asks = self._get_bids_and_asks_from_snapshot(raw_message["contents"])
            await self._make_order_book_message(
                raw_message=raw_message,
                message_queue=message_queue,
                bids=bids,
                asks=asks,
                message_type=OrderBookMessageType.SNAPSHOT,
            )

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if raw_message["type"] in ["subscribed", "channel_data"]:
            bids, asks = self._get_bids_and_asks_from_diff(raw_message["contents"])
            await self._make_order_book_message(
                raw_message=raw_message,
                message_queue=message_queue,
                bids=bids,
                asks=asks,
                message_type=OrderBookMessageType.DIFF,
            )

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if raw_message["type"] == "channel_data":
            symbol = raw_message["id"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

            trade_updates = raw_message["contents"]["trades"]

            for trade_data in trade_updates:
                ts_ms = dp.parse(trade_data["createdAt"]).timestamp() * 1e3
                trade_type = float(TradeType.BUY.value) if trade_data["side"] == "BUY" else float(TradeType.SELL.value)
                message_content = {
                    "trade_id": ts_ms,
                    "trading_pair": trading_pair,
                    "trade_type": trade_type,
                    "amount": trade_data["size"],
                    "price": trade_data["price"],
                }
                trade_message = OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content=message_content,
                    timestamp=ts_ms * 1e-3,
                )
                message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if raw_message["type"] == "channel_data":
            print(raw_message)
            for trading_pair in raw_message["contents"]["markets"].keys():
                if trading_pair in self._trading_pairs:
                    market_info = raw_message["contents"]["markets"][trading_pair]

                    if any(
                            info in ["oraclePrice", "nextFundingRate", "nextFundingAt"]
                            for info in market_info.keys()
                    ):

                        info_update = FundingInfoUpdate(trading_pair)
                        if "oraclePrice" in market_info.keys():
                            info_update.index_price = Decimal(market_info["oraclePrice"])
                            info_update.mark_price = Decimal(market_info["oraclePrice"])
                        if "nextFundingRate" in market_info.keys():
                            info_update.rate = Decimal(market_info["nextFundingRate"])
                            info_update.next_funding_utc_timestamp = self._next_funding_time(),

                        message_queue.put_nowait(info_update)

    async def _request_complete_funding_info(self, trading_pair: str) -> Dict[str, Any]:
        ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        params = {
            "limit": 1,
            "ticker": ex_symbol
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint = CONSTANTS.PATH_MARKETS
        url = web_utils.public_rest_url(path_url=endpoint)
        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=endpoint,
            params=params,
            method=RESTMethod.GET,
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)

        timestamp = self._time()
        update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp)

        bids, asks = self._get_bids_and_asks_from_snapshot(snapshot_response)
        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=order_book_message_content,
            timestamp=timestamp,
        )

        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint = CONSTANTS.PATH_SNAPSHOT
        ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        url = web_utils.public_rest_url(path_url=endpoint + "/" + ex_symbol)
        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=endpoint,
            method=RESTMethod.GET,
        )

        return data

    @staticmethod
    def _get_bids_and_asks_from_snapshot(
            snapshot: Dict[str, List[Dict[str, Union[str, int, float]]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:

        bids = [(Decimal(bid["price"]), Decimal(bid["size"])) for bid in snapshot["bids"]]
        asks = [(Decimal(ask["price"]), Decimal(ask["size"])) for ask in snapshot["asks"]]

        return bids, asks

    @staticmethod
    def _get_bids_and_asks_from_diff(
            diff: Dict[str, List[Dict[str, Union[str, int, float]]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:

        bids = [(Decimal(bid[0]), Decimal(bid[1])) for bid in diff.get("bids", [])]
        asks = [(Decimal(ask[0]), Decimal(ask[1])) for ask in diff.get("asks", [])]

        return bids, asks

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.DYDX_V4_WS_URL, ping_timeout=CONSTANTS.HEARTBEAT_INTERVAL)
        return ws

    async def _request_order_book_snapshots(self, output: asyncio.Queue):
        pass  # unused

    def _next_funding_time(self) -> int:
        """
        Funding settlement occurs every 1 hours as mentioned in https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
        """
        return ((time.time() // 3600) + 1) * 3600
