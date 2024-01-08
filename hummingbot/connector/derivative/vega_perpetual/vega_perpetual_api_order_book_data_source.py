import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_data import Market
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_derivative import VegaPerpetualDerivative


class VegaPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'VegaPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_assistants: List[WSAssistant] = []
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._ws_total_count = 0
        self._ws_total_closed_count = 0
        self._ws_connected = True

    async def listen_for_subscriptions(self):
        """
        Called from the HB core.  This is where we start the websocket connections
        """
        tasks_future = None
        try:
            channels = [
                CONSTANTS.DIFF_STREAM_URL,
                CONSTANTS.TRADE_STREAM_URL,
                CONSTANTS.SNAPSHOT_STREAM_URL,
                CONSTANTS.MARKET_DATA_STREAM_URL
            ]
            tasks = []

            # build our combined market id's into a query param
            market_id_param = ""
            for trading_pair in self._trading_pairs:
                market_id = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                if market_id_param:
                    market_id_param += "&"
                market_id_param += f"marketIds={market_id}"

            for channel in channels:
                if self._connector._best_connection_endpoint == "":
                    await self._connector.connection_base()
                _url = f"{web_utils._wss_url(channel, self._connector._best_connection_endpoint)}?{market_id_param}"
                tasks.append(self._start_websocket(url=_url))

            tasks_future = asyncio.gather(*tasks)
            await tasks_future

        except asyncio.CancelledError:
            tasks_future and tasks_future.cancel()
            raise

    async def _start_websocket(self, url: str):
        """
        Starts a websocket connection to the provided url and listens to the events coming from it.
        Events are passed back to the super class which then puts calls _channel_originating_message
        to get the correct channel to put the message on.
        """
        ws: Optional[WSAssistant] = None
        self._ws_total_count += 1
        _sleep_count = 0
        while True:
            try:
                ws = await self._create_websocket(url)
                self._ws_assistants.append(ws)
                await ws.ping()
                _sleep_count = 0  # success, reset sleep count
                self._ws_connected = True
                await self._process_websocket_messages(websocket_assistant=ws)

            except ConnectionError as connection_exception:
                self._ws_total_closed_count += 1
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception as e:
                self._ws_total_closed_count += 1
                self.logger().exception(
                    f"Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...  WSTOTAL {self._ws_total_count} closed - {self._ws_total_closed_count} {e}",
                )
                _sleep_count += 1
                _sleep_duration = 5.0
                if _sleep_count > 10:
                    # sleep for longer as we keep failing
                    self._ws_connected = False
                    _sleep_duration = 30.0
                await self._sleep(_sleep_duration)
            finally:
                await self._on_order_stream_interruption(websocket_assistant=ws)
                if ws in self._ws_assistants:
                    ws and self._ws_assistants.remove(ws)

    async def _create_websocket(self, ws_url: str) -> WSAssistant:
        """
        Creates a wsassistant and connects to the url
        :return: the wsassistant
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        This is what messages come to after ws
        """
        channel = ""
        if "result" in event_message:
            if "marketDepth" in event_message["result"]:
                # NOTE: This is a list
                channel = self._snapshot_messages_queue_key
                # NOTE: This is processed in _parse_order_book_snapshot_message
            if "update" in event_message["result"]:
                # NOTE: This is a list
                channel = self._diff_messages_queue_key
                # NOTE: This is processed in _parse_order_book_diff_message
            if "trades" in event_message["result"]:
                # NOTE: This is a list
                channel = self._trade_messages_queue_key
                # NOTE: This is processed in _parse_trade_message
            if "marketData" in event_message["result"]:
                # NOTE: This is a list
                channel = self._funding_info_messages_queue_key
                # NOTE: This is processed in _parse_funding_info_message

        # NOTE: if channel is empty, it is processed in _process_message_for_unknown_channel
        return channel

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        """
        Processes a message coming from a not identified channel.
        Does nothing by default but allows subclasses to reimplement

        :param event_message: the event received through the websocket connection
        :param websocket_assistant: the websocket connection to use to interact with the exchange
        """
        pass

    async def get_last_traded_prices(self, trading_pairs: List[str]):
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Requests an order book snapshot from the exchange
        NOTE: Rest call
        """
        market_id = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=f"{CONSTANTS.SNAPSHOT_REST_URL}/{market_id}/{CONSTANTS.RECENT_SUFFIX}")
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()

        m: Market = self._connector._exchange_info.get(snapshot_response["marketId"])

        snapshot_response.update({"trading_pair": m.hb_trading_pair})
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": snapshot_response["trading_pair"],
            "update_id": int(snapshot_response["sequenceNumber"]),
            "bids": [[Decimal(d['price']) / m.price_quantum, Decimal(d['volume']) / m.quantity_quantum] for d in snapshot_response["buy"]],
            "asks": [[Decimal(d['price']) / m.price_quantum, Decimal(d['volume']) / m.quantity_quantum] for d in snapshot_response["sell"]],
        }, timestamp=snapshot_timestamp)
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass

    async def _subscribe_channels(self, ws: WSAssistant):
        pass

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        for diff in raw_message["result"]["update"]:
            timestamp: float = time.time()

            m: Market = self._connector._exchange_info.get(diff['marketId'])

            bids = [[Decimal(d['price']) / m.price_quantum, Decimal(d.get('volume', "0.0")) / m.quantity_quantum] for d in diff["buy"]] if "buy" in diff else []
            asks = [[Decimal(d['price']) / m.price_quantum, Decimal(d.get('volume', "0.0")) / m.quantity_quantum] for d in diff["sell"]] if "sell" in diff else []
            order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
                "trading_pair": m.hb_trading_pair,
                "update_id": int(diff["sequenceNumber"]),
                "bids": bids,
                "asks": asks,
            }, timestamp=timestamp)
            message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        for snapshot in raw_message["result"]["marketDepth"]:
            timestamp: float = time.time()

            m: Market = self._connector._exchange_info.get(snapshot['marketId'])

            bids = [[Decimal(d['price']) / m.price_quantum, Decimal(d.get('volume', "0.0")) / m.quantity_quantum] for d in snapshot["buy"]] if "buy" in snapshot else []
            asks = [[Decimal(d['price']) / m.price_quantum, Decimal(d.get('volume', "0.0")) / m.quantity_quantum] for d in snapshot["sell"]] if "sell" in snapshot else []
            snapshot_order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
                "trading_pair": m.hb_trading_pair,
                "update_id": int(snapshot["sequenceNumber"]),
                "bids": bids,
                "asks": asks,
            }, timestamp=timestamp)
            message_queue.put_nowait(snapshot_order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        for trade in raw_message["result"]["trades"]:
            timestamp = web_utils.hb_time_from_vega(trade.get("timestamp"))
            market_id = trade.get("marketId")

            m: Market = self._connector._exchange_info.get(market_id)

            trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": m.hb_trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade["aggressor"] == 2 else float(TradeType.BUY.value),
                "trade_id": trade["id"],
                "update_id": time.time(),
                "price": str(Decimal(trade["price"]) / m.price_quantum),
                "amount": str(Decimal(trade["size"]) / m.quantity_quantum)
            }, timestamp=timestamp)
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        for data in raw_message["result"]["marketData"]:
            m: Market = self._connector._exchange_info.get(data["market"])
            trading_pair = m.hb_trading_pair
            if trading_pair not in self._trading_pairs:
                continue
            if "productData" not in data:
                # NOTE: Not a known product
                continue
            if "perpetualData" not in data["productData"]:
                # NOTE: Not a perp product
                continue
            perp_data = data["productData"]["perpetualData"]
            index_price = perp_data.get("externalTwap")
            funding_rate = perp_data.get("fundingRate")
            mark_price = data.get("markPrice")

            funding_info = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(index_price) / m.price_quantum,
                mark_price=Decimal(mark_price) / m.price_quantum,
                # NOTE: This updates constantly
                next_funding_utc_timestamp=time.time() + 1,
                rate=Decimal(funding_rate),
            )

            message_queue.put_nowait(funding_info)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_info: Dict[str, Any] = await self._request_complete_funding_info(trading_pair)
        m: Market = self._connector._exchange_info.get(funding_info["market"])
        funding_rate = funding_info["fundingRate"]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=(Decimal(funding_info.get("indexPrice", 0.0)) / m.price_quantum),
            mark_price=(Decimal(funding_info.get("markPrice", 0.0)) / m.price_quantum),
            next_funding_utc_timestamp=float(time.time() + 1),
            rate=funding_rate,
        )
        return funding_info

    async def _request_complete_funding_info(self, trading_pair: str):
        market_id = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        current_market_data = await self._connector._api_get(
            path_url=f"{CONSTANTS.MARK_PRICE_URL}/{market_id}/{CONSTANTS.RECENT_SUFFIX}"
        )
        _funding_details = {}
        if "marketData" in current_market_data:
            funding_details = current_market_data["marketData"]
            _funding_details = {
                "market": funding_details["market"],
                "markPrice": funding_details["markPrice"],
                "trading_pair": trading_pair,
                # NOTE: We don't have an index price to reference yet
                "indexPrice": "0",
                "fundingRate": "0",
            }
            if "productData" in funding_details:
                perp_data = funding_details["productData"]["perpetualData"]
                index_price = perp_data.get("externalTwap")
                funding_rate = perp_data.get("fundingRate")
                _funding_details["indexPrice"] = index_price
                _funding_details["fundingRate"] = funding_rate

        return _funding_details
