import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from hummingbot.connector.derivative.deepcoin_perpetual import (
    deepcoin_perpetual_constants as CONSTANTS,
    deepcoin_perpetual_utils as dp_utils,
    deepcoin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_auth import DeepcoinPerpetualAuth
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest, WSPlainTextRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_derivative import (
        DeepcoinPerpetualDerivative,
    )


# if TYPE_CHECKING:
#     from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import (
#         BybitPerpetualDerivative,
#     )


class DeepcoinPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    def __init__(
            self,
            auth: DeepcoinPerpetualAuth,
            trading_pairs: List[str],
            connector: 'DeepcoinPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._nonce_provider = NonceCreator.for_microseconds()
        self._trading_rules = {}
        self._auth = auth

    async def _set_trading_rules(self) -> Dict[str, Any]:
        if not bool(self._trading_rules):
            resp = await self._request_trading_rules_info()
            for rule in resp["data"]:
                trading_pair = dp_utils.convert_from_exchange_trading_pair(rule["instId"])
                self._trading_rules[trading_pair] = float(rule["ctVal"])
        return self._trading_rules

    async def _request_trading_rules_info(self) -> Dict[str, Any]:
        params = {
            "instType": "SWAP"
        }
        rest_assistant = await self._api_factory.get_rest_assistant()
        endpoint = CONSTANTS.INSTRUMENTID_INFO_URL
        url = web_utils.public_rest_url(endpoint=endpoint, domain=self._domain)

        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=endpoint,
            method=RESTMethod.GET,
            params=params,
        )
        return data

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        instType = "SwapU"
        if dp_utils.is_exchange_inverse(trading_pair):
            instType = "Swap"
        params = {
            "instId": dp_utils.convert_to_exchange_trading_pair(trading_pair),
            "instType": instType
        }
        rest_assistant = await self._api_factory.get_rest_assistant()
        url_info = web_utils.public_rest_url(endpoint=CONSTANTS.FUNDING_INFO_URL,
                                             domain=self._domain)
        # request = RESTRequest(
        #     method=RESTMethod.GET,
        #     url=url_info,
        #     is_auth_required=True,
        #     params=params,
        #     throttler_limit_id=CONSTANTS.FUNDING_INFO_URL
        # )
        # header = self._auth.authentication_headers(request)
        # print("2header:",header)
        funding_info_response = await rest_assistant.execute_request(
            url=url_info,
            throttler_limit_id=CONSTANTS.FUNDING_INFO_URL,
            params=params,
            method=RESTMethod.GET,
            is_auth_required=True,
            # headers=header,
            timeout=5,
        )
        if funding_info_response.get("code") != "0":
            raise ValueError(f"Failed to get funding info for {trading_pair}")

        general_info = funding_info_response["data"]["current_fund_rates"][0]

        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(general_info.get("indexPrice", 0))),
            mark_price=Decimal(str(general_info.get("markPrice", 0))),
            next_funding_utc_timestamp=int(general_info.get("nextFundingTime", 0)) // 1000,
            rate=Decimal(str(general_info.get("fundingRate", 0))),
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
                url=web_utils.public_wss_url(self._domain),
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
            ws_url=ws_url, message_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )
        return ws

    async def _subscribe_to_channels(self, ws: WSAssistant, trading_pairs: List[str]):
        try:
            ex_trading_pairs = [
                dp_utils.convert_to_exchange_trading_pair(trading_pair)
                for trading_pair in self._trading_pairs
            ]

            trades_payload = [
                {
                    "SendTopicAction": {
                        "Action": "1",
                        "FilterValue": "DeepCoin_" + ex_trading_pair.replace("-SWAP", "").replace("-", ""),
                        "LocalNo": 9,
                        "ResumeNo": 0,
                        "TopicID": "2",
                    }
                } for ex_trading_pair in ex_trading_pairs
            ]

            subscribe_trades_request = WSJSONRequest(trades_payload)

            order_book_payload = [
                {
                    "SendTopicAction": {
                        "Action": "1",
                        "FilterValue": "DeepCoin_" + ex_trading_pair.replace("-SWAP", "").replace("-", "") + "_0.1",
                        "LocalNo": 6,
                        "ResumeNo": 0,
                        "TopicID": "25",
                    }
                } for ex_trading_pair in ex_trading_pairs
            ]

            subscribe_orderbook_request = WSJSONRequest(payload=order_book_payload)

            await ws.send(subscribe_orderbook_request)
            await ws.send(subscribe_trades_request)
            self.logger().info("Subscribed to public order book and trade channels...")
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
                ping_request = WSPlainTextRequest(payload="ping")
                await websocket_assistant.send(ping_request)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "a" in event_message:
            event_channel = event_message.get("a", "")
            if CONSTANTS.DIFF_EVENT_TYPE in event_channel:
                channel = self._diff_messages_queue_key
            elif CONSTANTS.TRADE_EVENT_TYPE in event_channel:
                channel = self._trade_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event_type = raw_message.get("a", "")
        await self._set_trading_rules()
        if event_type == CONSTANTS.DIFF_EVENT_TYPE:
            r = raw_message["r"]
            detail = (r[0] or {}).get("d") if r else None
            if detail is None:
                return
            trading_pair = str(detail["I"])
            if trading_pair.endswith("USDT"):
                trading_pair = trading_pair.replace("USDT", "-USDT")
            elif trading_pair.endswith("USD"):
                trading_pair = trading_pair.replace("USD", "-USD")
            ct_val = self._trading_rules[trading_pair]
            timestamp_seconds = int(raw_message.get("mt", 0)) / 1e3
            update_id = int(raw_message.get("tt", 0)) / 1e3
            bids, asks = self._get_bids_and_asks_from_ws_msg_data(r)
            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": [(bid[0], str(float(bid[1]) * ct_val)) for bid in bids],
                "asks": [(ask[0], str(float(ask[1]) * ct_val)) for ask in asks],
            }
            diff_message = OrderBookMessage(
                message_type=OrderBookMessageType.DIFF,
                content=order_book_message_content,
                timestamp=timestamp_seconds,
            )
            message_queue.put_nowait(diff_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event_type = raw_message.get("a", "")
        await self._set_trading_rules()
        if event_type == CONSTANTS.TRADE_EVENT_TYPE:
            for trade_data in raw_message.get("r", []):
                data = trade_data.get("d")
                if data is not None:
                    trading_pair = str(data.get("I"))
                    if trading_pair.endswith("USDT"):
                        trading_pair = trading_pair.replace("USDT", "-USDT")
                    elif trading_pair.endswith("USD"):
                        trading_pair = trading_pair.replace("USD", "-USD")
                    ct_val = self._trading_rules[trading_pair]
                    ts_ms = int(data.get("T", 0))
                    trade_type = float(TradeType.BUY.value) if data.get("D") == "0" else float(TradeType.SELL.value)
                    message_content = {
                        "trade_id": trade_data.get("i", ""),
                        "trading_pair": trading_pair,
                        "trade_type": trade_type,
                        "amount": str(float(data.get("V", 0)) * ct_val),
                        "price": data.get("P", 0),
                    }
                    trade_message = OrderBookMessage(
                        message_type=OrderBookMessageType.TRADE,
                        content=message_content,
                        timestamp=ts_ms,
                    )
                    message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Deepcoin may not have real-time funding info updates via WebSocket
        # This would be implemented if the exchange provides such updates
        pass

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        await self._set_trading_rules()
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        if snapshot_response.get("code") == "0":
            bids = snapshot_response.get("data").get("bids")
            asks = snapshot_response.get("data").get("asks")
            ct_val = self._trading_rules[trading_pair]
            timestamp = float(time.time())
            update_id = self._nonce_provider.get_tracking_nonce(timestamp=timestamp)
            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": [(bid[0], str(float(bid[1]) * ct_val)) for bid in bids],
                "asks": [(ask[0], str(float(ask[1]) * ct_val)) for ask in asks],
            }
            snapshot_msg: OrderBookMessage = OrderBookMessage(
                message_type=OrderBookMessageType.SNAPSHOT,
                content=order_book_message_content,
                timestamp=update_id,
            )

            return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        params = {
            "instId": dp_utils.convert_to_exchange_trading_pair(trading_pair),
            "sz": 400
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.public_rest_url(endpoint=CONSTANTS.SNAPSHOT_REST_URL,
                                        domain=self._domain)
        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=CONSTANTS.SNAPSHOT_REST_URL,
            params=params,
            method=RESTMethod.GET,
        )

        return data

    @staticmethod
    def _get_bids_and_asks_from_rest_msg_data(
            snapshot: Dict[str, Union[str, int, float, List]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        bids = [
            (float(row[0]), float(row[1]))
            for row in snapshot.get("b", [])
        ]
        asks = [
            (float(row[0]), float(row[1]))
            for row in snapshot.get("a", [])
        ]
        return bids, asks

    @staticmethod
    def _get_bids_and_asks_from_ws_msg_data(
            snapshot: List[Dict[str, Dict[str, str]]]
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        This method processes snapshot data from the websocket message and returns
        the bids and asks as lists of tuples (price, size).

        :param snapshot: Websocket message snapshot data
        :return: Tuple containing bids and asks as lists of (price, size) tuples
        """
        bids = []
        asks = []

        for dd in snapshot:
            value = dd.get("d")
            if value is not None:
                price = float(value.get("P"))
                size = float(value.get("V"))
                if value.get("D") == "0":
                    bids.append((price, size))
                else:
                    asks.append((price, size))

        return bids, asks

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass  # unused

    async def _subscribe_channels(self, ws: WSAssistant):
        pass  # unused
