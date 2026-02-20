from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_utils import (
    convert_from_exchange_symbol,
    convert_to_exchange_symbol,
)
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import PerpetualDerivativeInFlightOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class DecibelPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    """
    Order Book Data Source for Decibel Perpetual exchange
    Handles REST API for market data and WebSocket for real-time updates
    """

    def __init__(self, trading_pairs: List[str], connector: PerpetualDerivativePyBase, 
                 auth: Optional[DecibelPerpetualAuth] = None):
        super().__init__(trading_pairs)
        self._connector = connector
        self._auth = auth
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._ws_assistant: Optional[WSAssistant] = None

    async def get_last_traded_price(self, trading_pair: str) -> float:
        """Returns the last traded price for a trading pair"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._connector._web_assistants_factory.get_rest_assistant()
        
        params = {"market": convert_to_exchange_symbol(trading_pair)}
        data = await rest_assistant.get(
            CONSTANTS.REST_URL + CONSTANTS.GET_MARKET_PRICES,
            params=params,
            throttler=self._throttler,
        )
        
        if data and len(data) > 0:
            return float(data[0].get("oracle_price", 0))
        return 0.0

    async def get_order_book(self, trading_pair: str) -> OrderBook:
        """Returns the current order book for a trading pair"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._connector._web_assistants_factory.get_rest_assistant()
        
        params = {"market": convert_to_exchange_symbol(trading_pair)}
        data = await rest_assistant.get(
            CONSTANTS.REST_URL + CONSTANTS.GET_ORDER_BOOK_DEPTH,
            params=params,
            throttler=self._throttler,
        )
        
        order_book = OrderBook()
        bids = [(Decimal(str(bid["price"])), Decimal(str(bid["size"]))) for bid in data.get("bids", [])]
        asks = [(Decimal(str(ask["price"])), Decimal(str(ask["size"]))) for ask in data.get("asks", [])]
        
        order_book.apply_snapshot(bids, asks)
        return order_book

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """Returns funding info for a trading pair"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._connector._web_assistants_factory.get_rest_assistant()
        
        params = {"market": convert_to_exchange_symbol(trading_pair)}
        data = await rest_assistant.get(
            CONSTANTS.REST_URL + CONSTANTS.GET_ASSET_CONTEXTS,
            params=params,
            throttler=self._throttler,
        )
        
        if data:
            market_data = data[0] if isinstance(data, list) else data
            return FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal(str(market_data.get("oracle_price", 0))),
                mark_price=Decimal(str(market_data.get("mark_price", 0))),
                next_funding_time=market_data.get("next_funding_time", 0),
                rate=Decimal(str(market_data.get("funding_rate_bps", 0))) / Decimal("10000"),
            )
        
        raise ValueError(f"Could not fetch funding info for {trading_pair}")

    async def get_trading_pairs(self) -> List[str]:
        """Returns list of available trading pairs"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._connector._web_assistants_factory.get_rest_assistant()
        
        data = await rest_assistant.get(
            CONSTANTS.REST_URL + CONSTANTS.GET_ALL_AVAILABLE_MARKETS,
            throttler=self._throttler,
        )
        
        trading_pairs = []
        for market in data:
            symbol = market.get("symbol", "")
            if symbol:
                trading_pairs.append(convert_from_exchange_symbol(symbol))
        
        return trading_pairs

    async def _connect_websocket(self) -> WSAssistant:
        """Connects to the WebSocket API"""
        ws_url = CONSTANTS.WS_URL
        self._ws_assistant = WSAssistant(ws_url, throttler=self._throttler)
        await self._ws_assistant.connect()
        return self._ws_assistant

    async def _listen_for_subscriptions(self):
        """Listens for WebSocket messages"""
        ws = await self._connect_websocket()
        
        # Subscribe to orderbook and trades for all trading pairs
        for trading_pair in self._trading_pairs:
            exchange_symbol = convert_to_exchange_symbol(trading_pair)
            await ws.send({
                "type": "subscribe",
                "channel": "orderbook",
                "market": exchange_symbol,
            })
            await ws.send({
                "type": "subscribe",
                "channel": "trades",
                "market": exchange_symbol,
            })
        
        async for ws_message in ws.iter_messages():
            data = ws_message.data
            
            if data.get("channel") == "orderbook":
                await self._handle_orderbook_update(data)
            elif data.get("channel") == "trades":
                await self._handle_trade_update(data)

    async def _handle_orderbook_update(self, data: Dict):
        """Handles incoming orderbook updates"""
        trading_pair = convert_from_exchange_symbol(data.get("market", ""))
        bids = [(Decimal(str(b["p"])), Decimal(str(b["s"]))) for b in data.get("bids", [])]
        asks = [(Decimal(str(a["p"])), Decimal(str(a["s"]))) for a in data.get("asks", [])]
        
        order_book_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": trading_pair,
                "bids": bids,
                "asks": asks,
                "update_id": data.get("sequence", 0),
            },
            timestamp=data.get("timestamp", 0) / 1e6,
        )
        self._order_book_messages.put(order_book_message)

    async def _handle_trade_update(self, data: Dict):
        """Handles incoming trade updates"""
        # Implementation for trade updates
        pass

    async def _on_funding_info(self, funding_info: FundingInfo):
        """Handles funding info updates"""
        self._funding_info[funding_info.trading_pair] = funding_info
