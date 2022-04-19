import asyncio
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.okex import constants as CONSTANTS, okex_utils, okex_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest, WSPlainTextRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class OkexAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__(trading_pairs)
        self._time_synchronizer = time_synchronizer
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
        )

    @classmethod
    def _default_domain(cls):
        return ""

    @classmethod
    async def _get_last_traded_price(cls,
                                     trading_pair: str,
                                     api_factory: Optional[WebAssistantsFactory] = None,
                                     throttler: Optional[AsyncThrottler] = None,
                                     domain: Optional[str] = None,
                                     time_synchronizer: Optional[TimeSynchronizer] = None) -> float:
        throttler = throttler or web_utils.create_throttler()
        api_factory = api_factory or web_utils.build_api_factory(
            throttler=throttler,
            time_synchronizer=time_synchronizer,
        )
        rest_assistant = await api_factory.get_rest_assistant()
        params = {
            "instId": await cls.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair,
                domain=domain,
                api_factory=api_factory,
                throttler=throttler,
                time_synchronizer=time_synchronizer)
        }

        resp_json = await rest_assistant.execute_request(
            url=web_utils.rest_url(path_url=CONSTANTS.OKEX_TICKER_PATH),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.OKEX_TICKER_PATH,
        )

        ticker_data, *_ = resp_json["data"]
        return float(ticker_data["last"])

    @classmethod
    async def _exchange_symbols_and_trading_pairs(
            cls,
            domain: Optional[str] = None,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            time_synchronizer: Optional[TimeSynchronizer] = None) -> Dict[str, str]:
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation
        """
        api_factory = api_factory or web_utils.build_api_factory(
            throttler=throttler,
            time_synchronizer=time_synchronizer,
        )
        mapping = {}
        rest_assistant = await api_factory.get_rest_assistant()

        try:
            data = await rest_assistant.execute_request(
                url=web_utils.rest_url(path_url=CONSTANTS.OKEX_INSTRUMENTS_PATH),
                params={"instType": "SPOT"},
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.OKEX_INSTRUMENTS_PATH,
            )

            for symbol_data in filter(okex_utils.is_exchange_information_valid, data["data"]):
                mapping[symbol_data["instId"]] = combine_to_hb_trading_pair(base=symbol_data["baseCcy"],
                                                                            quote=symbol_data["quoteCcy"])

        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")

        return mapping

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_data: Dict[str, Any] = snapshot_response['data'][0]
        snapshot_timestamp: float = int(snapshot_data["ts"]) * 1e-3
        update_id: int = int(snapshot_timestamp)

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid[0], bid[3]) for bid in snapshot_data["bids"]],
            "asks": [(ask[0], ask[3]) for ask in snapshot_data["asks"]],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp)

        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "instId": await self.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair,
                domain=self._default_domain(),
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer),
            "sz": "400"
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.rest_url(path_url=CONSTANTS.OKEX_ORDER_BOOK_PATH),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.OKEX_ORDER_BOOK_PATH,
        )

        return data

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_updates = raw_message["data"]

        for trade_data in trade_updates:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                symbol=trade_data["instId"],
                domain=self._default_domain(),
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer)
            message_content = {
                "trade_id": trade_data["tradeId"],
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value) if trade_data["side"] == "buy" else float(
                    TradeType.SELL.value),
                "amount": trade_data["sz"],
                "price": trade_data["px"]
            }
            trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=(int(trade_data["ts"]) * 1e-3))

            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        diff_updates: Dict[str, Any] = raw_message["data"]

        for diff_data in diff_updates:
            timestamp: float = int(diff_data["ts"]) * 1e-3
            update_id: int = int(timestamp)
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                symbol=raw_message["arg"]["instId"],
                domain=self._default_domain(),
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer)

            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": [(bid[0], bid[3]) for bid in diff_data["bids"]],
                "asks": [(ask[0], ask[3]) for ask in diff_data["asks"]],
            }
            diff_message: OrderBookMessage = OrderBookMessage(
                OrderBookMessageType.DIFF,
                order_book_message_content,
                timestamp)

            message_queue.put_nowait(diff_message)

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair,
                    domain=self._default_domain(),
                    api_factory=self._api_factory,
                    throttler=self._throttler,
                    time_synchronizer=self._time_synchronizer)

                payload = {
                    "op": "subscribe",
                    "args": [
                        {
                            "channel": "trades",
                            "instId": symbol,
                        }
                    ]
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

                payload = {
                    "op": "subscribe",
                    "args": [
                        {
                            "channel": "books",
                            "instId": symbol,
                        }]
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

                async with self._throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIPTION_LIMIT_ID):
                    await ws.send(subscribe_trade_request)
                async with self._throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIPTION_LIMIT_ID):
                    await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "data" in event_message:
            event_channel = event_message["arg"]["channel"]
            if event_channel == CONSTANTS.OKEX_WS_PUBLIC_TRADES_CHANNEL:
                channel = self._trade_messages_queue_key
            if event_channel == CONSTANTS.OKEX_WS_PUBLIC_BOOKS_CHANNEL and event_message["action"] == "update":
                channel = self._diff_messages_queue_key

        return channel

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        while True:
            try:
                await super()._process_websocket_messages(websocket_assistant=websocket_assistant)
            except asyncio.TimeoutError:
                ping_request = WSPlainTextRequest(payload="ping")
                await websocket_assistant.send(request=ping_request)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        async with self._throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTION_LIMIT_ID):
            await ws.connect(
                ws_url=CONSTANTS.OKEX_WS_URI_PUBLIC,
                message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE)
        return ws
