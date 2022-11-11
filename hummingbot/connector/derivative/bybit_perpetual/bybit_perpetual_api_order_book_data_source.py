import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from hummingbot.connector.derivative.bybit_perpetual import (
    bybit_perpetual_constants as CONSTANTS,
    bybit_perpetual_utils,
    bybit_perpetual_web_utils as web_utils,
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
    from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import BybitPerpetualDerivative


class BybitPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'BybitPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._nonce_provider = NonceCreator.for_microseconds()

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info_response = await self._request_complete_funding_info(trading_pair)
        general_info = funding_info_response[0]["result"][0]
        predicted_funding = funding_info_response[1]["result"]

        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(general_info["index_price"])),
            mark_price=Decimal(str(general_info["mark_price"])),
            next_funding_utc_timestamp=int(pd.Timestamp(general_info["next_funding_time"]).timestamp()),
            rate=Decimal(str(predicted_funding["predicted_funding_rate"])),
        )
        return funding_info

    async def listen_for_subscriptions(self):
        """
        Subscribe to all required events and start the listening cycle.
        """
        tasks_future = None
        try:
            linear_trading_pairs, non_linear_trading_pairs = bybit_perpetual_utils.get_linear_non_linear_split(
                self._trading_pairs
            )

            tasks = []
            if linear_trading_pairs:
                tasks.append(self._listen_for_subscriptions_on_url(
                    url=web_utils.wss_linear_public_url(self._domain),
                    trading_pairs=linear_trading_pairs))
            if non_linear_trading_pairs:
                tasks.append(self._listen_for_subscriptions_on_url(
                    url=web_utils.wss_non_linear_public_url(self._domain),
                    trading_pairs=non_linear_trading_pairs))

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
                ws = await self._get_connected_websocket_assistant(url)
                await self._subscribe_to_channels(ws, trading_pairs)
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    f"Unexpected error occurred when listening to order book streams {url}. Retrying in 5 seconds..."
                )
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def _get_connected_websocket_assistant(self, ws_url: str) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=ws_url, message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
        )
        return ws

    async def _subscribe_to_channels(self, ws: WSAssistant, trading_pairs: List[str]):
        try:
            symbols = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in trading_pairs
            ]
            symbols_str = "|".join(symbols)

            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_TRADES_TOPIC}.{symbols_str}"],
            }
            subscribe_trade_request = WSJSONRequest(payload=payload)

            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC}.{symbols_str}"],
            }
            subscribe_orderbook_request = WSJSONRequest(payload=payload)

            payload = {
                "op": "subscribe",
                "args": [f"{CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC}.{symbols_str}"],
            }
            subscribe_instruments_request = WSJSONRequest(payload=payload)

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
                await super()._process_websocket_messages(websocket_assistant=websocket_assistant)
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"op": "ping"})
                await websocket_assistant.send(ping_request)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "success" not in event_message:
            event_channel = event_message["topic"]
            event_channel = ".".join(event_channel.split(".")[:-1])
            if event_channel == CONSTANTS.WS_TRADES_TOPIC:
                channel = self._trade_messages_queue_key
            elif event_channel == CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC:
                channel = self._diff_messages_queue_key
            elif event_channel == CONSTANTS.WS_INSTRUMENTS_INFO_TOPIC:
                channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event_type = raw_message["type"]

        if event_type == "delta":
            symbol = raw_message["topic"].split(".")[-1]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            timestamp_us = int(raw_message["timestamp_e6"])
            update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp_us * 1e-6)
            diffs_data = raw_message["data"]
            bids, asks = self._get_bids_and_asks_from_ws_msg_data(diffs_data)
            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            }
            diff_message = OrderBookMessage(
                message_type=OrderBookMessageType.DIFF,
                content=order_book_message_content,
                timestamp=timestamp_us * 1e-6,
            )
            message_queue.put_nowait(diff_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_updates = raw_message["data"]

        for trade_data in trade_updates:
            symbol = trade_data["symbol"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            ts_ms = int(trade_data["trade_time_ms"])
            trade_type = float(TradeType.BUY.value) if trade_data["side"] == "Buy" else float(TradeType.SELL.value)
            message_content = {
                "trade_id": trade_data["trade_id"],
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
        event_type = raw_message["type"]
        if event_type == "delta":
            symbol = raw_message["topic"].split(".")[-1]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            entries = raw_message["data"]["update"]
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
                if "predicted_funding_rate_e6" in entry:
                    info_update.rate = (
                        Decimal(str(entry["predicted_funding_rate_e6"])) * Decimal(1e-6)
                    )
                message_queue.put_nowait(info_update)

    async def _request_complete_funding_info(self, trading_pair: str):
        tasks = []
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint_info = CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT
        url_info = web_utils.get_rest_url_for_endpoint(endpoint=endpoint_info, trading_pair=trading_pair, domain=self._domain)
        limit_id = web_utils.get_rest_api_limit_id_for_endpoint(endpoint_info)
        tasks.append(rest_assistant.execute_request(
            url=url_info,
            throttler_limit_id=limit_id,
            params=params,
            method=RESTMethod.GET,
        ))
        endpoint_predicted = CONSTANTS.GET_PREDICTED_FUNDING_RATE_PATH_URL
        url_predicted = web_utils.get_rest_url_for_endpoint(endpoint=endpoint_predicted, trading_pair=trading_pair, domain=self._domain)
        limit_id_predicted = web_utils.get_rest_api_limit_id_for_endpoint(endpoint_predicted, trading_pair)
        tasks.append(rest_assistant.execute_request(
            url=url_predicted,
            throttler_limit_id=limit_id_predicted,
            params=params,
            method=RESTMethod.GET,
            is_auth_required=True
        ))

        responses = await asyncio.gather(*tasks)
        return responses

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_data = snapshot_response["result"]
        timestamp = float(snapshot_response["time_now"])
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
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint, trading_pair=trading_pair, domain=self._domain)
        limit_id = web_utils.get_rest_api_limit_id_for_endpoint(endpoint)
        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=limit_id,
            params=params,
            method=RESTMethod.GET,
        )

        return data

    @staticmethod
    def _get_bids_and_asks_from_rest_msg_data(
        snapshot: List[Dict[str, Union[str, int, float]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        bisect_idx = 0
        for i, row in enumerate(snapshot):
            if row["side"] == "Sell":
                bisect_idx = i
                break
        bids = [
            (float(row["price"]), float(row["size"]))
            for row in snapshot[:bisect_idx]
        ]
        asks = [
            (float(row["price"]), float(row["size"]))
            for row in snapshot[bisect_idx:]
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
        pass  # unused

    async def _subscribe_channels(self, ws: WSAssistant):
        pass  # unused
