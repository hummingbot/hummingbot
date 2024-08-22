import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

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
        params = {
            "category": "linear" if web_utils.is_linear_perpetual(trading_pair) else "inverse",
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint_info = CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT
        url_info = web_utils.get_rest_url_for_endpoint(endpoint=endpoint_info, trading_pair=trading_pair,
                                                       domain=self._domain)
        limit_id = web_utils.get_rest_api_limit_id_for_endpoint(endpoint_info)
        funding_info_response = await rest_assistant.execute_request(
            url=url_info,
            throttler_limit_id=limit_id,
            params=params,
            method=RESTMethod.GET,
        )
        if not funding_info_response["result"]:
            self._connector.logger().warning(f"Failed to get funding info for {trading_pair}")
            raise ValueError(f"Failed to get funding info for {trading_pair}")
        general_info = funding_info_response["result"]["list"][0]

        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(general_info["indexPrice"])),
            mark_price=Decimal(str(general_info["markPrice"])),
            next_funding_utc_timestamp=int(general_info["nextFundingTime"]) // 1000,
            rate=Decimal(str(general_info["fundingRate"])),
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
            timestamp_seconds = int(raw_message["ts"]) / 1e3
            update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp_seconds)
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
                timestamp=timestamp_seconds,
            )
            message_queue.put_nowait(diff_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_updates = raw_message["data"]

        for trade_data in trade_updates:
            symbol = trade_data["s"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            ts_ms = int(trade_data["T"])
            trade_type = float(TradeType.BUY.value) if trade_data["S"] == "Buy" else float(TradeType.SELL.value)
            message_content = {
                "trade_id": trade_data["i"],
                "trading_pair": trading_pair,
                "trade_type": trade_type,
                "amount": trade_data["v"],
                "price": trade_data["p"],
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
            entry = raw_message["data"]
            info_update = FundingInfoUpdate(trading_pair)
            if "indexPrice" in entry:
                info_update.index_price = Decimal(entry["indexPrice"])
            if "markPrice" in entry:
                info_update.mark_price = Decimal(entry["markPrice"])
            if "nextFundingTime" in entry:
                info_update.next_funding_utc_timestamp = int(entry["nextFundingTime"]) // 1e3
            if "fundingRate" in entry:
                info_update.rate = Decimal(str(entry["fundingRate"]))
            message_queue.put_nowait(info_update)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_data = snapshot_response["result"]
        timestamp = float(snapshot_data["ts"])
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
            "category": "linear" if web_utils.is_linear_perpetual(trading_pair) else "inverse",
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
        bids = [
            (float(row[0]), float(row[1]))
            for row in snapshot["b"]
        ]
        asks = [
            (float(row[0]), float(row[1]))
            for row in snapshot["a"]
        ]
        return bids, asks

    @staticmethod
    def _get_bids_and_asks_from_ws_msg_data(
            snapshot: Dict[str, Union[List[List[str]], str, int]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        This method processes snapshot data from the websocket message and returns
        the bids and asks as lists of tuples (price, size).

        :param snapshot: Websocket message snapshot data
        :return: Tuple containing bids and asks as lists of (price, size) tuples
        """
        bids = []
        asks = []

        bids_list = snapshot.get("b", [])
        asks_list = snapshot.get("a", [])

        for bid in bids_list:
            bid_price = float(bid[0])
            bid_size = float(bid[1])
            if bid_size == 0:
                # Size of 0 means delete the entry
                continue
            bids.append((bid_price, bid_size))

        # Process asks
        for ask in asks_list:
            ask_price = float(ask[0])
            ask_size = float(ask[1])
            if ask_size == 0:
                # Size of 0 means delete the entry
                continue
            asks.append((ask_price, ask_size))

        return bids, asks

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass  # unused

    async def _subscribe_channels(self, ws: WSAssistant):
        pass  # unused
