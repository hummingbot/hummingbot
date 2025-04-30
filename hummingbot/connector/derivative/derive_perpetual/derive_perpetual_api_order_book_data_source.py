import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

# from bidict import bidict
from hummingbot.connector.derivative.derive_perpetual import (
    derive_perpetual_constants as CONSTANTS,
    derive_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative import DerivePerpetualDerivative


class DerivePerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'DerivePerpetualDerivative',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory
        self._snapshot_messages = {}
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._snapshot_messages_queue_key = "order_book_snapshot"
        self._instrument_ticker = []

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        general_info = await self._request_complete_funding_info(trading_pair)
        data = general_info["result"]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(data["index_price"])),
            mark_price=Decimal(str(data["mark_price"])),
            next_funding_utc_timestamp=self._next_funding_time(),
            rate=Decimal(str(data["perp_details"]["funding_rate"])),
        )
        return funding_info

    async def listen_for_funding_info(self, output: asyncio.Queue):
        """
        Reads the funding info events queue and updates the local funding info information.
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    funding_info = await self.get_funding_info(trading_pair)
                    funding_info_update = FundingInfoUpdate(
                        trading_pair=trading_pair,
                        index_price=funding_info.index_price,
                        mark_price=funding_info.mark_price,
                        next_funding_utc_timestamp=funding_info.next_funding_utc_timestamp,
                        rate=funding_info.rate,
                    )
                    output.put_nowait(funding_info_update)
                await self._sleep(CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public funding info updates from exchange")
                await self._sleep(CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        pass

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            params = []

            for trading_pair in self._trading_pairs:
                # NB: DONT want exchange_symbol_associated_with_trading_pair, to avoid too much request
                symbol = trading_pair.replace("USDC", "PERP")
                params.append(f"trades.{symbol.upper()}")
                params.append(f"orderbook.{symbol.upper()}.1.100")

            trades_payload = {
                "method": "subscribe",
                "params": {
                    "channels": params
                }
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)
            await ws.send(subscribe_trade_request)

            self.logger().info("Subscribed to public order book, trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_timestamp: float = self._time()
        if trading_pair in self._snapshot_messages:
            snapshot_msg = self._snapshot_messages[trading_pair]
            return snapshot_msg
        # If we don't have a snapshot message, create one
        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": snapshot_timestamp,
            "bids": [],
            "asks": [],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp)
        return snapshot_msg

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["params"]["data"]["instrument_name"])
        data = raw_message["params"]["data"]
        timestamp: float = raw_message["params"]["data"]["timestamp"] * 1e-3
        trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": int(data['publish_id']),
            "bids": [[i[0], i[1]] for i in data.get('bids', [])],
            "asks": [[i[0], i[1]] for i in data.get('asks', [])],
        }, timestamp=timestamp)
        self._snapshot_messages[trading_pair] = trade_message
        message_queue.put_nowait(trade_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message["params"]["data"]
        for trade_data in data:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                trade_data["instrument_name"])
            trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade_data["direction"] == "sell" else float(
                    TradeType.BUY.value),
                "trade_id": trade_data["trade_id"],
                "price": float(trade_data["trade_price"]),
                "amount": float(trade_data["trade_amount"])
            }, timestamp=trade_data["timestamp"] * 1e-3)
            message_queue.put_nowait(trade_message)

    async def listen_for_order_book_diffs(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "error" not in event_message:
            if "params" in event_message:
                stream_name = event_message["params"]["channel"]
                if "orderbook" in stream_name:
                    channel = self._snapshot_messages_queue_key
                elif "trades" in stream_name:
                    channel = self._trade_messages_queue_key
            return channel

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    async def _request_complete_funding_info(self, trading_pair: str):
        # NB: DONT want exchange_symbol_associated_with_trading_pair, to avoid too much request
        pair = trading_pair.replace("USDC", "PERP")
        payload = {
            "instrument_name": pair,
        }
        exchange_info = await self._connector._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
                                                        data=payload)
        if "error" in exchange_info:
            self.logger().warning(f"Error: {exchange_info['error']['message']}")
        return exchange_info

    def _next_funding_time(self) -> int:
        return int(((time.time() // 3600) + 1) * 3600)
