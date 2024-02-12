import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from hummingbot.connector.derivative.okx_perpetual import (
    okx_perpetual_constants as CONSTANTS,
    okx_perpetual_web_utils as web_utils,
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
    from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_derivative import OkxPerpetualDerivative


class OkxPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'OkxPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__(trading_pairs)
        self._mark_price_queue_key = "mark_price"
        self._index_price_queue_key = "index_price"
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._nonce_provider = NonceCreator.for_microseconds()
        self._last_index_price = None
        self._last_mark_price = None
        self._last_next_funding_utc_timestamp = None
        self._last_rate = None

    # 1 - Order Book Snapshot REST
    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_data = snapshot_response["data"][0]
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
            "instId": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "sz": "300"
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint = CONSTANTS.REST_ORDER_BOOK[CONSTANTS.ENDPOINT]
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint, domain=self._domain)
        limit_id = web_utils.get_rest_api_limit_id_for_endpoint(
            method=CONSTANTS.REST_ORDER_BOOK[CONSTANTS.METHOD],
            endpoint=endpoint)
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
        # asks: ascending, bids: descending
        bids = [tuple(map(float, row[:2])) for row in snapshot['bids']]
        asks = [tuple(map(float, row[:2])) for row in snapshot['asks']]
        return bids, asks

    @staticmethod
    def _get_bids_and_asks_from_ws_msg_data(
        snapshot: Dict[str, List[Dict[str, Union[str, int, float]]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        bids = [tuple(map(float, row[:2])) for row in snapshot['bids']]
        asks = [tuple(map(float, row[:2])) for row in snapshot['asks']]
        return bids, asks

    # 2 - Get Last Traded Prices REST
    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices()

    # 3 - Get Funding Info REST
    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info_response = await self._request_complete_funding_info(trading_pair)
        index_price = funding_info_response[0]["data"][0]
        mark_price = funding_info_response[1]["data"][0]
        funding_data = funding_info_response[2]["data"][0]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(index_price["idxPx"])),
            mark_price=Decimal(str(mark_price["markPx"])),
            next_funding_utc_timestamp=int(funding_data["nextFundingTime"]),
            rate=Decimal(str(funding_data["fundingRate"])),
        )
        return funding_info

    async def _request_complete_funding_info(self, trading_pair: str):
        tasks = []
        rest_assistant = await self._api_factory.get_rest_assistant()
        inst_id = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        # TODO: Check what happens with index price in OKX API, only available for spot?
        params_index_price = {
            "instId": trading_pair
        }
        endpoint_index_price = CONSTANTS.REST_INDEX_TICKERS[CONSTANTS.ENDPOINT]
        url_index_price = web_utils.get_rest_url_for_endpoint(endpoint=endpoint_index_price, domain=self._domain)
        limit_id_index_price = web_utils.get_pair_specific_limit_id(
            method=CONSTANTS.REST_INDEX_TICKERS[CONSTANTS.METHOD],
            endpoint=endpoint_index_price,
            trading_pair=trading_pair)
        tasks.append(rest_assistant.execute_request(
            url=url_index_price,
            throttler_limit_id=limit_id_index_price,
            params=params_index_price,
            method=RESTMethod.GET,
        ))

        params_mark_price = {
            "instId": inst_id,
            "instType": "SWAP",
        }
        endpoint_mark_price = CONSTANTS.REST_MARK_PRICE[CONSTANTS.ENDPOINT]
        url_mark_price = web_utils.get_rest_url_for_endpoint(endpoint=endpoint_mark_price, domain=self._domain)
        limit_id_mark_price = web_utils.get_pair_specific_limit_id(
            method=CONSTANTS.REST_MARK_PRICE[CONSTANTS.METHOD],
            endpoint=endpoint_mark_price,
            trading_pair=trading_pair
        )
        tasks.append(rest_assistant.execute_request(
            url=url_mark_price,
            throttler_limit_id=limit_id_mark_price,
            params=params_mark_price,
            method=RESTMethod.GET,
            is_auth_required=True
        ))

        params_funding_data = {
            "instId": inst_id
        }
        endpoint_funding_data = CONSTANTS.REST_FUNDING_RATE_INFO[CONSTANTS.ENDPOINT]
        url_funding_data = web_utils.get_rest_url_for_endpoint(endpoint=endpoint_funding_data, domain=self._domain)
        limit_id_funding_data = web_utils.get_pair_specific_limit_id(
            method=CONSTANTS.REST_FUNDING_RATE_INFO[CONSTANTS.METHOD],
            endpoint=endpoint_funding_data,
            trading_pair=trading_pair
        )
        tasks.append(rest_assistant.execute_request(
            url=url_funding_data,
            throttler_limit_id=limit_id_funding_data,
            params=params_funding_data,
            method=RESTMethod.GET,
        ))

        responses = await asyncio.gather(*tasks)
        return responses

    # 4 - Websocket Connection
    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_PUBLIC_URLS[CONSTANTS.DEFAULT_DOMAIN],
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            ex_trading_pairs = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in self._trading_pairs
            ]

            trades_args = [
                {
                    "channel": CONSTANTS.WS_TRADES_CHANNEL,
                    "instId": ex_trading_pair
                } for ex_trading_pair in ex_trading_pairs
            ]
            trades_payload = {
                "op": "subscribe",
                "args": trades_args,
            }
            subscribe_trades_request = WSJSONRequest(payload=trades_payload)

            order_book_args = [
                {
                    "channel": CONSTANTS.WS_ORDER_BOOK_400_DEPTH_100_MS_EVENTS_CHANNEL,
                    "instId": ex_trading_pair
                } for ex_trading_pair in ex_trading_pairs
            ]
            order_book_payload = {
                "op": "subscribe",
                "args": order_book_args,
            }
            subscribe_orderbook_request = WSJSONRequest(payload=order_book_payload)

            funding_info_args = [
                {
                    "channel": CONSTANTS.WS_FUNDING_INFO_CHANNEL,
                    "instId": ex_trading_pair
                } for ex_trading_pair in ex_trading_pairs
            ]
            instruments_payload = {
                "op": "subscribe",
                "args": funding_info_args,
            }
            subscribe_instruments_request = WSJSONRequest(payload=instruments_payload)

            mark_price_args = [
                {
                    "channel": CONSTANTS.WS_MARK_PRICE_CHANNEL,
                    "instId": ex_trading_pair
                } for ex_trading_pair in ex_trading_pairs
            ]
            mark_price_payload = {
                "op": "subscribe",
                "args": mark_price_args,
            }
            subscribe_mark_price_request = WSJSONRequest(payload=mark_price_payload)

            index_price_args = [
                {
                    "channel": CONSTANTS.WS_INDEX_TICKERS_CHANNEL,
                    "instId": ex_trading_pair
                } for ex_trading_pair in ex_trading_pairs
            ]
            index_price_payload = {
                "op": "subscribe",
                "args": index_price_args,
            }
            subscribe_index_price_request = WSJSONRequest(payload=index_price_payload)

            # TODO: Add 3 rps Rate Limit / 480 prh Rate Limit?
            await ws.send(subscribe_trades_request)
            await ws.send(subscribe_orderbook_request)
            await ws.send(subscribe_instruments_request)
            await ws.send(subscribe_mark_price_request)
            await ws.send(subscribe_index_price_request)
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
                ping_request = WSJSONRequest(payload="ping")
                await websocket_assistant.send(ping_request)

    # 5 - Listen for Specific Channels
    async def listen_for_mark_price_info(self, output: asyncio.Queue):
        """
        Reads the funding info events queue and updates the local funding info information.
        """
        message_queue = self._message_queue[self._mark_price_queue_key]
        while True:
            try:
                funding_info_event = await message_queue.get()
                await self._parse_mark_price_message(raw_message=funding_info_event, message_queue=output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public mark price updates from exchange")

    async def listen_for_index_price_info(self, output: asyncio.Queue):
        """
        Reads the funding info events queue and updates the local funding info information.
        """
        message_queue = self._message_queue[self._index_price_queue_key]
        while True:
            try:
                funding_info_event = await message_queue.get()
                await self._parse_index_price_message(raw_message=funding_info_event, message_queue=output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public index price updates from exchange")

    # 6 - Parsers
    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event_type = raw_message["action"]
        if event_type == "update":
            symbol = raw_message["arg"]["instId"]
            trading_pair = self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            timestamp_ms = int(raw_message["data"][0]["ts"])
            update_id = int(raw_message["data"][0]["seqId"])
            diffs_data = raw_message["data"][0]
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
                timestamp=timestamp_ms,
            )
            message_queue.put_nowait(diff_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event_type = raw_message.get("action", None)
        if event_type == "snapshot":
            symbol = raw_message["arg"]["instId"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            timestamp_ms = int(raw_message["data"][0]["ts"])
            update_id = int(raw_message["data"][0]["seqId"])
            diffs_data = raw_message["data"][0]
            bids, asks = self._get_bids_and_asks_from_ws_msg_data(diffs_data)
            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            }
            snapshot_message = OrderBookMessage(
                message_type=OrderBookMessageType.SNAPSHOT,
                content=order_book_message_content,
                timestamp=timestamp_ms,
            )
            message_queue.put_nowait(snapshot_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # TODO: Check with dman if this handling is ok
        subscription_event = raw_message.get("event")
        if subscription_event == "subscribe":
            pass
        elif subscription_event == "error":
            self.logger().error(f"Error in trades subscription: {raw_message}")
            pass
        trade_updates = raw_message.get("data")
        if trade_updates is not None:
            for trade_data in trade_updates:
                symbol = trade_data["instId"]
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
                ts_ms = int(trade_data["ts"])
                trade_type = float(TradeType.BUY.value) if trade_data["side"] == "buy" else float(TradeType.SELL.value)
                message_content = {
                    "trade_id": trade_data["tradeId"],
                    "trading_pair": trading_pair,
                    "trade_type": trade_type,
                    "amount": trade_data["sz"],
                    "price": trade_data["px"],
                }
                trade_message = OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content=message_content,
                    timestamp=ts_ms * 1e-3,
                )
                message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol = raw_message["arg"]["instId"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        funding_data = raw_message["data"][0]
        self._last_next_funding_utc_timestamp = int(funding_data["nextFundingTime"])
        self._last_rate = (Decimal(str(funding_data["fundingRate"])))
        info_update = FundingInfoUpdate(trading_pair=trading_pair,
                                        index_price=self._last_index_price,
                                        mark_price=self._last_mark_price,
                                        next_funding_utc_timestamp=self._last_next_funding_utc_timestamp,
                                        rate=self._last_rate)
        message_queue.put_nowait(info_update)

    async def _parse_index_price_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol = raw_message["arg"]["instId"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        index_price_data = raw_message["data"][0]
        self._last_index_price = Decimal(str(index_price_data["idxPx"]))
        info_update = FundingInfoUpdate(trading_pair=trading_pair,
                                        index_price=self._last_index_price,
                                        mark_price=self._last_mark_price,
                                        next_funding_utc_timestamp=self._last_next_funding_utc_timestamp,
                                        rate=self._last_rate)
        message_queue.put_nowait(info_update)

    async def _parse_mark_price_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol = raw_message["arg"]["instId"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        mark_price_data = raw_message["data"][0]
        self._last_mark_price = Decimal(str(mark_price_data["markPx"]))
        info_update = FundingInfoUpdate(trading_pair=trading_pair,
                                        index_price=self._last_index_price,
                                        mark_price=self._last_mark_price,
                                        next_funding_utc_timestamp=self._last_next_funding_utc_timestamp,
                                        rate=self._last_rate)
        message_queue.put_nowait(info_update)

    def _get_messages_queue_keys(self) -> List[str]:
        return [
            self._snapshot_messages_queue_key,
            self._diff_messages_queue_key,
            self._trade_messages_queue_key,
            self._funding_info_messages_queue_key,
            self._mark_price_queue_key,
            self._index_price_queue_key,
        ]

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        arg_dict = event_message.get("arg", {})
        channel_value = arg_dict.get("channel")

        if channel_value is not None:
            event_channel = event_message["arg"]["channel"]
            if event_channel == CONSTANTS.WS_TRADES_CHANNEL:
                channel = self._trade_messages_queue_key
            elif event_channel == CONSTANTS.WS_ORDER_BOOK_400_DEPTH_100_MS_EVENTS_CHANNEL:
                channel = self._diff_messages_queue_key
            elif event_channel == CONSTANTS.WS_INSTRUMENTS_INFO_CHANNEL:
                channel = self._funding_info_messages_queue_key
            elif event_channel == CONSTANTS.WS_MARK_PRICE_CHANNEL:
                channel = self._mark_price_queue_key
            elif event_channel == CONSTANTS.WS_INDEX_TICKERS_CHANNEL:
                channel = self._index_price_queue_key
        return channel
