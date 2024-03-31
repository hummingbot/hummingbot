import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

from hummingbot.connector.derivative.bybit_perpetual import (  # bybit_perpetual_web_utils as web_utils,
    bybit_perpetual_constants as CONSTANTS,
    bybit_perpetual_utils as bybit_utils,
)
from hummingbot.connector.derivative.bybit_perpetual.bybit_order_book import BybitOrderBook
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
        self._depth = CONSTANTS.WS_ORDER_BOOK_DEPTH

    async def get_last_traded_prices(self, trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info, tickers = await self._request_complete_funding_info(trading_pair)
        funding_info = funding_info["list"][0]
        tickers = tickers["list"][0]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(tickers["indexPrice"])),
            mark_price=Decimal(str(tickers["markPrice"])),
            next_funding_utc_timestamp=int(pd.Timestamp(int(tickers["nextFundingTime"])).timestamp()),
            rate=Decimal(str(tickers["fundingRate"])),
        )
        return funding_info

    async def listen_for_subscriptions(self):
        """
        Subscribe to all required events and start the listening cycle.
        """
        tasks_future = None
        try:
            linear_trading_pairs, non_linear_trading_pairs = bybit_utils.get_linear_non_linear_split(
                self._trading_pairs
            )

            tasks = []
            if linear_trading_pairs:
                tasks.append(
                    self._listen_for_subscriptions_on_url(
                        url=CONSTANTS.WSS_PUBLIC_URL_LINEAR[self._domain],
                        trading_pairs=linear_trading_pairs
                    )
                )
            if non_linear_trading_pairs:
                tasks.append(
                    self._listen_for_subscriptions_on_url(
                        url=CONSTANTS.WSS_PUBLIC_URL_INVERSE[self._domain],
                        trading_pairs=non_linear_trading_pairs
                    )
                )

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

    def _get_trade_topic_from_symbol(self, symbol: str) -> str:
        return f"publicTrade.{symbol}"

    def _get_ob_topic_from_symbol(self, symbol: str, depth: int) -> str:
        return f"orderbook.{depth}.{symbol}"

    def _get_tickers_topic_from_symbol(self, symbol: str) -> str:
        return f"tickers.{symbol}"

    async def _subscribe_to_channels(self, ws: WSAssistant, trading_pairs: List[str]):
        try:
            symbols = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in trading_pairs
            ]

            payload = {
                "op": "subscribe",
                "args": [self._get_ob_topic_from_symbol(symbol, self._depth) for symbol in symbols],
            }
            subscribe_trade_request = WSJSONRequest(payload=payload)

            payload = {
                "op": "subscribe",
                "args": [self._get_trade_topic_from_symbol(symbol) for symbol in symbols],
            }
            subscribe_orderbook_request = WSJSONRequest(payload=payload)

            payload = {
                "op": "subscribe",
                "args": [self._get_tickers_topic_from_symbol(symbol) for symbol in symbols],
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
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            symbol=raw_message["data"]["s"]
        )
        data = raw_message["data"]
        timestamp = raw_message["ts"]
        # timestamps from ByBit is in ms
        update_id = self._nonce_provider.get_tracking_nonce(timestamp=raw_message["ts"] * 1e-3)
        # update_id = data["u"]
        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": data["b"],
            "asks": data["a"],
        }
        order_book_message: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=order_book_message_content,
            timestamp=timestamp,
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message["data"]
        topic = raw_message["topic"]
        symbol = topic.split('.')[1]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        for trades in data:
            trade_message: OrderBookMessage = BybitOrderBook.trade_message_from_exchange(
                trades,
                {"trading_pair": trading_pair}
            )
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        print("_parse_funding_info_message")
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
        funding_info = await self._get_funding_info(trading_pair)
        tickers = await self._get_tickers(trading_pair)
        return funding_info, tickers

    async def _get_funding_info(self, trading_pair: str):
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)

        params = {
            "category": bybit_utils.get_trading_pair_category(trading_pair),
            "symbol": exchange_symbol,
            "limit": 1  # Get last
        }
        response: Dict[str, Any] = await self._connector._api_get(
            path_url=CONSTANTS.FUNDING_RATE_PATH_URL,
            params=params,
            is_auth_required=False,
            trading_pair=trading_pair,
        )
        result: Dict[str, Any] = response["result"]
        return result

    async def _get_tickers(self, trading_pair: str):
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)

        params = {
            "category": bybit_utils.get_trading_pair_category(trading_pair),
            "symbol": exchange_symbol
        }
        response: Dict[str, Any] = await self._connector._api_get(
            path_url=CONSTANTS.TICKERS_PATH_URL,
            params=params,
            is_auth_required=False,
            trading_pair=trading_pair,
        )
        result: Dict[str, Any] = response["result"]
        return result

    async def _request_trading_history(self, trading_pair: str):
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)

        params = {
            "category": bybit_utils.get_trading_pair_category(trading_pair),
            "symbol": exchange_symbol,
            "limit": 1  # Get last
        }

        response: Dict[str, Any] = await self._connector._api_get(
            path_url=CONSTANTS.RECENT_TRADING_HISTORY_PATH_URL,
            params=params,
            is_auth_required=True,
            trading_pair=trading_pair,
        )
        result: Dict[str, Any] = response["result"]
        return result

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        timestamp = float(snapshot["ts"])
        update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp * 1e-3)

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": snapshot["b"],
            "asks": snapshot["a"],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=order_book_message_content,
            timestamp=timestamp,
        )

        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "category": bybit_utils.get_trading_pair_category(trading_pair),
            "symbol": await self._connector.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair
            ),
            "limit": "1000"
        }
        response = await self._connector._api_request(
            path_url=CONSTANTS.ORDERBOOK_SNAPSHOT_PATH_URL,
            method=RESTMethod.GET,
            params=params
        )
        return response['result']

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass  # unused

    async def _subscribe_channels(self, ws: WSAssistant):
        pass  # unused
