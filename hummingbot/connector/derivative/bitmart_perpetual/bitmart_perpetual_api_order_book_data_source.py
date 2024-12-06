import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import pandas as pd

import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative import (
        BitmartPerpetualDerivative,
    )


class BitmartPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'BitmartPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._trade_messages_queue_key = CONSTANTS.TRADE_STREAM_CHANNEL
        self._diff_messages_queue_key = CONSTANTS.DIFF_STREAM_CHANNEL
        self._funding_info_messages_queue_key = CONSTANTS.FUNDING_INFO_CHANNEL
        self._tickers_messages_queue_key = CONSTANTS.TICKERS_CHANNEL
        self._snapshot_messages_queue_key = CONSTANTS.SNAPSHOT_CHANNEL
        self._last_index_price = None
        self._last_mark_price = None
        self._last_next_funding_utc_timestamp = None
        self._last_rate = None

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol_response, funding_response = await asyncio.gather(
            self._request_complete_contract_details(trading_pair),
            self._request_complete_funding_info(trading_pair)
        )

        symbol_data = symbol_response["data"].get("symbols")
        funding_data = funding_response.get("data")

        if symbol_data is not None and funding_data is not None:
            # TODO: Check if last_price replaces mark_price
            funding_info = FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal(symbol_data[0].get("index_price")),
                mark_price=Decimal(symbol_data[0].get("last_price")),
                next_funding_utc_timestamp=int(float(funding_data.get("funding_time")) * 1e-3),
                rate=Decimal(funding_data.get("expected_rate"))
            )
            return funding_info

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        params = {
            "symbol": ex_trading_pair,
            "limit": "1000"
        }

        data = await self._connector._api_get(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            params=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_data: Dict[str, Any] = snapshot_response.get("data")
        snapshot_timestamp: float = snapshot_data["timestamp"] / 1e3
        snapshot_data.update({"trading_pair": trading_pair})
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": snapshot_data["trading_pair"],
            "update_id": int(time.time()),  # TODO: check for what is this
            "bids": snapshot_data["bids"],
            "asks": snapshot_data["asks"]
        }, timestamp=snapshot_timestamp)
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, domain=self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            stream_id_channel_pairs = [
                CONSTANTS.DIFF_STREAM_CHANNEL,
                CONSTANTS.TRADE_STREAM_CHANNEL,
                CONSTANTS.FUNDING_INFO_CHANNEL,
                CONSTANTS.TICKERS_CHANNEL,
            ]
            for channel in stream_id_channel_pairs:
                params = []
                for trading_pair in self._trading_pairs:
                    symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                    params.append(f"{channel}{f':{symbol.upper()}' if channel != 'futures/ticker' else ''}")
                    payload = {
                        "action": "subscribe",
                        "args": params,
                    }
                    subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                    await ws.send(subscribe_request)
            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message and event_message.get("data") is not None:
            stream_name = event_message.get("group")
            if CONSTANTS.DIFF_STREAM_CHANNEL in stream_name:
                channel = self._diff_messages_queue_key
            elif CONSTANTS.TRADE_STREAM_CHANNEL in stream_name:
                channel = self._trade_messages_queue_key
            elif CONSTANTS.FUNDING_INFO_CHANNEL in stream_name:
                channel = self._funding_info_messages_queue_key
            elif CONSTANTS.TICKERS_CHANNEL in stream_name:
                channel = self._tickers_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raw_message["data"]["symbol"] = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["data"]["symbol"])
        data = raw_message["data"]
        # TODO: Check what's going on with order book differences
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": data["symbol"],
            "update_id": int(data["ms_t"]),
            "bids": [(depth["price"], depth["vol"]) for depth in data["depths"] if data["way"] == 1],
            "asks": [(depth["price"], depth["vol"]) for depth in data["depths"] if data["way"] == 2]
        }, timestamp=data["ms_t"] / 1e3)
        message_queue.put_nowait(order_book_message)

    @staticmethod
    def _parse_trade_way(way: int) -> str:
        """
        Parse the trade 'way' to determine if it's a buy or sell action.

        Args:
            way (int): The integer value representing the trade way.

        Returns:
            str: "buy" or "sell" based on the way value.
        """
        way_to_trade_type = {
            1: TradeType.BUY,  # buy_open_long or sell_open_short (treated as buy)
            2: TradeType.BUY,  # buy_open_long or sell_close_long (treated as buy)
            3: TradeType.SELL,  # buy_close_short or sell_open_short (treated as sell)
            4: TradeType.SELL,  # buy_close_short or sell_close_long (treated as sell)
            5: TradeType.BUY,  # sell_open_short or buy_open_long (treated as buy)
            6: TradeType.SELL,  # sell_open_short or buy_close_short (treated as sell)
            7: TradeType.SELL,  # sell_close_long or buy_open_long (treated as sell)
            8: TradeType.BUY,  # sell_close_long or buy_close_short (treated as buy)
        }

        return way_to_trade_type.get(way)  # Default to "unknown" if way is invalid

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if len(raw_message["data"]) > 0:
            trade_data = raw_message["data"][0]
            trade_data["symbol"] = await self._connector.trading_pair_associated_to_exchange_symbol(trade_data["symbol"])
            trade_data["created_at"] = pd.to_datetime(trade_data["created_at"]).timestamp()
            trade_message: OrderBookMessage = OrderBookMessage(
                OrderBookMessageType.TRADE,
                {
                    "trading_pair": trade_data["symbol"],
                    "trade_type": self._parse_trade_way(trade_data["way"]),
                    "trade_id": trade_data["trade_id"],
                    "price": trade_data["deal_price"],
                    "amount": trade_data["deal_vol"]
                },
                timestamp=trade_data["created_at"])
            message_queue.put_nowait(trade_message)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot_msg: OrderBookMessage = await self._order_book_snapshot(trading_pair)
                    output.put_nowait(snapshot_msg)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                delta = CONSTANTS.ONE_HOUR - time.time() % CONSTANTS.ONE_HOUR
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds...", exc_info=True
                )
                await self._sleep(5.0)

    def _get_messages_queue_keys(self) -> List[str]:
        return [
            self._snapshot_messages_queue_key,
            self._diff_messages_queue_key,
            self._trade_messages_queue_key,
            self._funding_info_messages_queue_key,
            self._tickers_messages_queue_key
        ]

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data: Dict[str, Any] = raw_message["data"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(data["symbol"])

        if trading_pair not in self._trading_pairs:
            return
        self._last_next_funding_utc_timestamp = int(float(data["nextFundingTime"]) * 1e-3)
        self._next_funding_rate = Decimal(data["fundingRate"])
        # TODO: Check if fair and last price replaces index and mark prices
        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=self._last_index_price,
            mark_price=self._last_mark_price,
            next_funding_utc_timestamp=self._last_next_funding_utc_timestamp,
            rate=self._last_rate,
        )
        message_queue.put_nowait(funding_info)

    async def _parse_tickers_message(self, raw_message: Dict[str, Any]):
        data: Dict[str, Any] = raw_message["data"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(data["symbol"])

        if trading_pair not in self._trading_pairs:
            return

        self._last_mark_price = data["last_price"]
        self._last_index_price = data["fair_price"]

    async def _request_complete_funding_info(self, trading_pair: str):
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=CONSTANTS.FUNDING_INFO_URL,
            params={"symbol": ex_trading_pair})
        return data

    async def _request_complete_contract_details(self, trading_pair: str):
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=CONSTANTS.EXCHANGE_INFO_URL,
            params={"symbol": ex_trading_pair})
        return data
