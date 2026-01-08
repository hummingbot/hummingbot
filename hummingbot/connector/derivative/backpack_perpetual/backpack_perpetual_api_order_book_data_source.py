import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BackpackPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "BackpackPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = {}

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        result = {}
        domain = domain or self._domain

        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.public_rest_url(CONSTANTS.TICKERS_URL, domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TICKERS_URL,
        )

        for ticker in response:
            trading_pair = self._connector.exchange_symbol_to_trading_pair(ticker.get("symbol", ""))
            if trading_pair in trading_pairs:
                result[trading_pair] = float(ticker.get("lastPrice", 0))

        return result

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.public_rest_url(CONSTANTS.FUNDING_RATES_URL, self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.FUNDING_RATES_URL,
        )

        symbol = self._connector.trading_pair_to_exchange_symbol(trading_pair)

        for rate_info in response:
            if rate_info.get("symbol") == symbol:
                return FundingInfo(
                    trading_pair=trading_pair,
                    index_price=Decimal(str(rate_info.get("indexPrice", 0))),
                    mark_price=Decimal(str(rate_info.get("markPrice", 0))),
                    next_funding_utc_timestamp=int(rate_info.get("nextFundingTime", 0)),
                    rate=Decimal(str(rate_info.get("fundingRate", 0))),
                )

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal("0"),
            mark_price=Decimal("0"),
            next_funding_utc_timestamp=0,
            rate=Decimal("0"),
        )

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        symbol = self._connector.trading_pair_to_exchange_symbol(trading_pair)
        url = web_utils.public_rest_url(CONSTANTS.DEPTH_URL, self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params={"symbol": symbol},
            throttler_limit_id=CONSTANTS.DEPTH_URL,
        )

        return response

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        timestamp = time.time()

        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": int(timestamp * 1000),
                "bids": snapshot.get("bids", []),
                "asks": snapshot.get("asks", []),
            },
            timestamp=timestamp,
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain))
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        for trading_pair in self._trading_pairs:
            symbol = self._connector.trading_pair_to_exchange_symbol(trading_pair)

            subscribe_orderbook = WSJSONRequest(
                payload={
                    "method": "SUBSCRIBE",
                    "params": [f"depth.{symbol}"],
                }
            )
            await ws.send(subscribe_orderbook)

            subscribe_trades = WSJSONRequest(
                payload={
                    "method": "SUBSCRIBE",
                    "params": [f"trades.{symbol}"],
                }
            )
            await ws.send(subscribe_trades)

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            stream = data.get("stream", "")
            if "depth" in stream:
                await self._process_order_book_message(data)
            elif "trades" in stream:
                await self._process_trade_message(data)

    async def _process_order_book_message(self, data: Dict[str, Any]):
        stream = data.get("stream", "")
        symbol = stream.replace("depth.", "")
        trading_pair = self._connector.exchange_symbol_to_trading_pair(symbol)
        timestamp = time.time()

        order_data = data.get("data", {})

        message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": trading_pair,
                "update_id": order_data.get("lastUpdateId", int(timestamp * 1000)),
                "bids": order_data.get("bids", []),
                "asks": order_data.get("asks", []),
            },
            timestamp=timestamp,
        )

        if trading_pair in self._message_queue:
            self._message_queue[trading_pair].put_nowait(message)

    async def _process_trade_message(self, data: Dict[str, Any]):
        stream = data.get("stream", "")
        symbol = stream.replace("trades.", "")
        trading_pair = self._connector.exchange_symbol_to_trading_pair(symbol)
        timestamp = time.time()

        trade_data = data.get("data", {})

        message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value) if trade_data.get("isBuyerMaker") else float(TradeType.SELL.value),
                "trade_id": trade_data.get("tradeId", ""),
                "update_id": int(timestamp * 1000),
                "price": trade_data.get("price", 0),
                "amount": trade_data.get("quantity", 0),
            },
            timestamp=timestamp,
        )

        if trading_pair in self._message_queue:
            self._message_queue[trading_pair].put_nowait(message)

    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"WebSocket error: {e}")
                await asyncio.sleep(5.0)
            finally:
                if ws:
                    await ws.disconnect()
