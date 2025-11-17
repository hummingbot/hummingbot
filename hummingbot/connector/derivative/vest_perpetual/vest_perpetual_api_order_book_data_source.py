"""Order book and funding data source for Vest Perpetual."""
import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.vest_perpetual.vest_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.vest_perpetual.vest_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_utils import convert_from_exchange_trading_pair
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_derivative import VestPerpetualDerivative


class VestPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "VestPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        use_testnet: bool = False,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._use_testnet = use_testnet
        self._trading_pairs: List[str] = trading_pairs

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        rest_assistant = await self._api_factory.get_rest_assistant()
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        params = {"symbols": symbol}

        response = await rest_assistant.execute_request(
            url=web_utils.rest_url(CONSTANTS.TICKER_LATEST_PATH_URL, use_testnet=self._use_testnet),
            throttler_limit_id=CONSTANTS.TICKER_LATEST_PATH_URL,
            method=RESTMethod.GET,
            params=params,
        )

        tickers = response.get("tickers", [])
        if not tickers:
            raise ValueError(f"No ticker data for {trading_pair}")

        ticker = tickers[0]
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(ticker["indexPrice"]),
            mark_price=Decimal(ticker["markPrice"]),
            next_funding_utc_timestamp=int(self._time()) + 3600,
            rate=Decimal(ticker.get("oneHrFundingRate", "0")),
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        account_group = getattr(self._connector, "_account_group", 0)
        domain = getattr(self._connector, "domain", CONSTANTS.DEFAULT_DOMAIN)
        ws_url = web_utils.public_ws_url(domain=domain, account_group=account_group)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            subscription_id = 1
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                channels = [
                    CONSTANTS.WS_DEPTH_CHANNEL.format(symbol=symbol),
                    CONSTANTS.WS_TRADES_CHANNEL.format(symbol=symbol),
                ]
                request = WSJSONRequest(
                    payload={
                        "method": "SUBSCRIBE",
                        "params": channels,
                        "id": subscription_id,
                    }
                )
                await ws.send(request)
                subscription_id += 1

            tickers_request = WSJSONRequest(
                payload={
                    "method": "SUBSCRIBE",
                    "params": [CONSTANTS.WS_TICKERS_CHANNEL],
                    "id": subscription_id,
                }
            )
            await ws.send(tickers_request)
            self.logger().info("Subscribed to Vest public channels")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error subscribing to channels")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = event_message.get("channel", "")
        if channel.endswith("@depth"):
            return self._diff_messages_queue_key
        if channel.endswith("@trades"):
            return self._trade_messages_queue_key
        if channel == CONSTANTS.WS_TICKERS_CHANNEL:
            return self._funding_info_messages_queue_key
        return ""

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        rest_assistant = await self._api_factory.get_rest_assistant()
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        params = {"symbol": symbol, "limit": 100}

        response = await rest_assistant.execute_request(
            url=web_utils.rest_url(CONSTANTS.DEPTH_PATH_URL, use_testnet=self._use_testnet),
            throttler_limit_id=CONSTANTS.DEPTH_PATH_URL,
            method=RESTMethod.GET,
            params=params,
        )

        return self._order_book_message_from_depth(
            trading_pair=trading_pair,
            depth_data=response,
            message_type=OrderBookMessageType.SNAPSHOT,
        )

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        message = self._order_book_message_from_ws_depth(
            raw_message=raw_message,
            message_type=OrderBookMessageType.SNAPSHOT,
        )
        message_queue.put_nowait(message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        message = self._order_book_message_from_ws_depth(
            raw_message=raw_message,
            message_type=OrderBookMessageType.DIFF,
        )
        message_queue.put_nowait(message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        channel = raw_message.get("channel", "")
        symbol = channel.split("@")[0]
        trading_pair = convert_from_exchange_trading_pair(symbol)
        timestamp = float(data.get("time", 0)) / 1000 if data.get("time") is not None else self._time()

        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value),
                "trade_id": data.get("id"),
                "price": float(data.get("price", "0")),
                "amount": float(data.get("qty", "0")),
            },
            timestamp=timestamp,
        )
        message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        tickers = raw_message.get("data", [])
        for ticker in tickers:
            try:
                symbol = ticker["symbol"]
                trading_pair = convert_from_exchange_trading_pair(symbol)
                funding_update = FundingInfoUpdate(
                    trading_pair=trading_pair,
                    index_price=Decimal(ticker["indexPrice"]),
                    mark_price=Decimal(ticker["markPrice"]),
                    next_funding_utc_timestamp=int(self._time()) + 3600,
                    rate=Decimal(ticker.get("oneHrFundingRate", "0")),
                )
                message_queue.put_nowait(funding_update)
            except (KeyError, ValueError) as exc:
                self.logger().debug(f"Error parsing funding info: {exc}")

    def _order_book_message_from_depth(
        self,
        trading_pair: str,
        depth_data: Dict[str, Any],
        message_type: OrderBookMessageType,
    ) -> OrderBookMessage:
        timestamp = self._time()
        bids = [[Decimal(price), Decimal(size)] for price, size in depth_data.get("bids", [])]
        asks = [[Decimal(price), Decimal(size)] for price, size in depth_data.get("asks", [])]
        return OrderBookMessage(
            message_type=message_type,
            content={
                "trading_pair": trading_pair,
                "update_id": int(timestamp * 1e3),
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp,
        )

    def _order_book_message_from_ws_depth(
        self,
        raw_message: Dict[str, Any],
        message_type: OrderBookMessageType,
    ) -> OrderBookMessage:
        data = raw_message.get("data", {})
        channel = raw_message.get("channel", "")
        symbol = channel.split("@")[0]
        trading_pair = convert_from_exchange_trading_pair(symbol)
        event_time = data.get("time")
        timestamp = float(event_time) / 1000 if event_time is not None else self._time()
        update_id = int(event_time) if event_time is not None else int(timestamp * 1e3)
        bids = [[Decimal(price), Decimal(size)] for price, size in data.get("bids", [])]
        asks = [[Decimal(price), Decimal(size)] for price, size in data.get("asks", [])]
        return OrderBookMessage(
            message_type=message_type,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp,
        )
