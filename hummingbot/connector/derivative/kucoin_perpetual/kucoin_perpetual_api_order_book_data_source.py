import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from hummingbot.connector.derivative.kucoin_perpetual import (
    kucoin_perpetual_constants as CONSTANTS,
    kucoin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_derivative import KucoinPerpetualDerivative


class KucoinPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'KucoinPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        time_provider: TimeSynchronizer,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._nonce_provider = NonceCreator.for_microseconds()
        self._time_provider = time_provider

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info_response = await self._request_complete_funding_info(trading_pair)
        if "symbol" in funding_info_response["data"]:
            symbol_info = funding_info_response["data"]
        else:
            symbol_info = funding_info_response["data"][0]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(symbol_info["indexPrice"])),
            mark_price=Decimal(str(symbol_info["markPrice"])),
            next_funding_utc_timestamp=int(pd.Timestamp(symbol_info["nextFundingRateTime"]).timestamp()),
            rate=Decimal(str(symbol_info["predictedFundingFeeRate"])),
        )
        return funding_info

    async def listen_for_subscriptions(self):
        """
        Subscribe to all required events and start the listening cycle.
        """
        tasks_future = None
        try:
            tasks = []
            tasks.append(self._listen_for_subscriptions_on_url(
                url=web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.PUBLIC_WS_DATA_PATH_URL, domain=self._domain),
                trading_pairs=self._trading_pairs))

            if tasks:
                tasks_future = asyncio.gather(*tasks)
                await tasks_future

        except asyncio.CancelledError:
            tasks_future and tasks_future.cancel()
            raise

    async def _listen_for_subscriptions_on_url(self, url: str, trading_pairs: List[str]):
        """
        Subscribe to all required events and start the listening cycle.
        :param url: the wss url to connect to
        :param trading_pairs: the trading pairs for which the function should listen events
        """

        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_to_channels(ws, trading_pairs)
                await ws.ping()  # to update last_recv_timestamp
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception('ExceptionThrown', exc_info=True)
                self.logger().exception(
                    f"Unexpected error occurred when listening to order book streams {url}. Retrying in 5 seconds..."
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def _subscribe_to_channels(self, ws: WSAssistant, trading_pairs: List[str]):
        try:
            symbols = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in trading_pairs
            ]
            symbols_str = ",".join(symbols)

            trades_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": f"/contractMarket/ticker:{symbols_str}",
                "privateChannel": False,
                "response": False,
            }
            subscribe_trade_request = WSJSONRequest(payload=trades_payload)

            order_book_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": f"/contractMarket/level2:{symbols_str}",
                "privateChannel": False,
                "response": False,
            }
            subscribe_orderbook_request = WSJSONRequest(payload=order_book_payload)

            instrument_payload = {
                "id": web_utils.next_message_id(),
                "type": "subscribe",
                "topic": f"/contract/instrument:{symbols_str}",
                "privateChannel": False,
                "response": False,
            }
            subscribe_instruments_request = WSJSONRequest(payload=instrument_payload)
            await ws.send(subscribe_trade_request)  # not rate-limited
            await ws.send(subscribe_orderbook_request)  # not rate-limited
            await ws.send(subscribe_instruments_request)  # not rate-limited
            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        while True:
            try:
                await asyncio.wait_for(super()._process_websocket_messages(websocket_assistant=websocket_assistant),
                                       timeout=CONSTANTS.WS_CONNECTION_TIME_INTERVAL)
            except asyncio.TimeoutError:
                payload = {
                    "id": web_utils.next_message_id(),
                    "type": "ping",
                }
                ping_request = WSJSONRequest(payload=payload)
                self._last_ws_message_sent_timestamp = self._time()
                await websocket_assistant.send(request=ping_request)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "data" in event_message and event_message.get("type") == "message":
            event_channel = event_message.get("topic")
            if CONSTANTS.WS_TRADES_TOPIC in event_channel:
                channel = self._trade_messages_queue_key
            elif CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC in event_channel:
                channel = self._diff_messages_queue_key
            elif CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC in event_channel:
                channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):

        event_type = raw_message["type"]

        if event_type == "message":
            symbol = raw_message["topic"].split(":")[-1]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            diffs_data = raw_message["data"]
            timestamp: float = float(diffs_data["timestamp"]) * 1e-3
            bids = []
            asks = []
            price = diffs_data["change"].split(",")[0]
            side = diffs_data["change"].split(",")[1]
            quantity = diffs_data["change"].split(",")[2]
            row_tuple = (price, quantity)
            if side == "buy":
                bids.append(row_tuple)
            else:
                asks.append(row_tuple)
            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": diffs_data["sequence"],
                "bids": bids,
                "asks": asks,
            }
            diff_message = OrderBookMessage(
                message_type=OrderBookMessageType.DIFF,
                content=order_book_message_content,
                timestamp=timestamp,
            )
            message_queue.put_nowait(diff_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_data: Dict[str, Any] = raw_message["data"]
        timestamp: float = int(trade_data["time"]) * 1e-9
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=trade_data["symbol"])
        message_content = {
            "trade_id": str(trade_data["tradeId"]),
            "update_id": int(trade_data["sequence"]),
            "trading_pair": trading_pair,
            "trade_type": float(TradeType.BUY.value) if trade_data["side"] == "buy" else float(
                TradeType.SELL.value),
            "amount": Decimal(trade_data["size"]),
            "price": Decimal(trade_data["price"])
        }
        trade_message: Optional[OrderBookMessage] = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=message_content,
            timestamp=timestamp)

        message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event_type = raw_message["subject"]
        if event_type == "funding.rate" or event_type == "mark.index.price" or event_type == "position.settlement":
            symbol = raw_message["topic"].split(":")[-1]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            entries = raw_message["data"]
            info_update = FundingInfoUpdate(trading_pair)
            if "indexPrice" in entries:
                info_update.index_price = Decimal(str(entries["indexPrice"]))
            if "markPrice" in entries:
                info_update.mark_price = Decimal(str(entries["markPrice"]))
            if "fundingRate" in entries:
                info_update.rate = Decimal(str(entries["fundingRate"]))
                message_queue.put_nowait(info_update)

    async def _request_complete_funding_info(self, trading_pair: str) -> Dict[str, Any]:
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint = CONSTANTS.GET_CONTRACT_INFO_PATH_URL.format(symbol=exchange_symbol[0])
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint, domain=self._domain)
        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=CONSTANTS.GET_CONTRACT_INFO_PATH_URL,
            method=RESTMethod.GET,
            is_auth_required=True,
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        if len(exchange_symbol) > 0:
            exchange_symbol = exchange_symbol[0]
        snapshot_response = await self._request_order_book_snapshot(exchange_symbol)
        snapshot_data = snapshot_response["data"]
        if "time" in snapshot_data:
            timestamp = float(snapshot_data["time"]) * 1e-3
        elif "ts" in snapshot_data:
            timestamp = float(snapshot_data["ts"]) * 1e-9
        else:
            timestamp = time.time()
        if "sequence" in snapshot_data:
            update_id = int(snapshot_data["sequence"])
        else:
            update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp)
        bids, asks = self._get_bids_and_asks_from_rest_msg_data(snapshot_data)
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
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint.format(symbol=trading_pair))
        limit_id = web_utils.get_rest_api_limit_id_for_endpoint(endpoint)
        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=limit_id,
            method=RESTMethod.GET,
        )

        return data

    @staticmethod
    def _get_bids_and_asks_from_rest_msg_data(
        snapshot: List[Dict[str, Union[str, int, float]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        bids = [
            (float(row[0]), float(row[1]))
            for row in snapshot['bids']
        ]
        asks = [
            (float(row[0]), float(row[1]))
            for row in snapshot['asks']
        ]
        return bids, asks

    @staticmethod
    def _get_bids_and_asks_from_ws_msg_data(
        snapshot: Dict[str, List[Dict[str, Union[str, int, float]]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        bids = []
        asks = []
        for action, rows_list in snapshot.items():
            if action not in ["delete", "update", "insert"]:
                continue
            is_delete = action == "delete"
            for row_dict in rows_list:
                row_price = row_dict["price"]
                row_size = 0.0 if is_delete else row_dict["size"]
                row_tuple = (row_price, row_size)
                if row_dict["side"] == "Buy":
                    bids.append(row_tuple)
                else:
                    asks.append(row_tuple)
        return bids, asks

    async def _connected_websocket_assistant(self) -> WSAssistant:
        rest_assistant = await self._api_factory.get_rest_assistant()
        connection_info = await rest_assistant.execute_request(
            url=web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.PUBLIC_WS_DATA_PATH_URL, domain=self._domain),
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.PUBLIC_WS_DATA_PATH_URL,
        )

        ws_url = connection_info["data"]["instanceServers"][0]["endpoint"]
        self._ping_interval = int(connection_info["data"]["instanceServers"][0]["pingInterval"]) * 0.8 * 1e-3
        message_timeout = int(connection_info["data"]["instanceServers"][0]["pingTimeout"]) * 0.8 * 1e-3
        token = connection_info["data"]["token"]

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=f"{ws_url}?token={token}", ping_timeout=self._ping_interval, message_timeout=message_timeout)
        return ws
