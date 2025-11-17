import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

import hummingbot.connector.derivative.vest_perpetual.vest_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.vest_perpetual.vest_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_utils import (
    convert_from_exchange_trading_pair,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_derivative import (
        VestPerpetualDerivative,
    )


class VestPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'VestPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        use_testnet: bool = False,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._use_testnet = use_testnet
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """Get funding info for a trading pair."""
        rest_assistant = await self._api_factory.get_rest_assistant()
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)

        url = web_utils.rest_url(CONSTANTS.TICKER_LATEST_PATH_URL, self._use_testnet)
        params = {"symbols": symbol}

        response = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=CONSTANTS.TICKER_LATEST_PATH_URL,
            method=RESTMethod.GET,
            params=params,
        )

        tickers = response.get("tickers", [])
        if not tickers:
            raise ValueError(f"No ticker data for {trading_pair}")

        ticker = tickers[0]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(ticker["indexPrice"]),
            mark_price=Decimal(ticker["markPrice"]),
            next_funding_utc_timestamp=int(pd.Timestamp.now().timestamp() + 3600),  # 1 hour from now
            rate=Decimal(ticker.get("oneHrFundingRate", "0")),
        )
        return funding_info

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """Create and connect a WebSocket assistant."""
        account_group = self._connector._account_group
        ws_url = f"{web_utils.wss_url(self._use_testnet)}?version=1.0&xwebsocketserver=restserver{account_group}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=30)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """Subscribe to order book and trade channels."""
        try:
            subscription_id = 1
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)

                # Subscribe to depth
                depth_channel = CONSTANTS.WS_DEPTH_CHANNEL.format(symbol=symbol)
                trades_channel = CONSTANTS.WS_TRADES_CHANNEL.format(symbol=symbol)

                subscribe_request = WSJSONRequest(
                    payload={
                        "method": "SUBSCRIBE",
                        "params": [depth_channel, trades_channel],
                        "id": subscription_id,
                    }
                )
                await ws.send(subscribe_request)
                subscription_id += 1

            # Also subscribe to tickers for funding info
            subscribe_tickers = WSJSONRequest(
                payload={
                    "method": "SUBSCRIBE",
                    "params": [CONSTANTS.WS_TICKERS_CHANNEL],
                    "id": subscription_id,
                }
            )
            await ws.send(subscribe_tickers)

            self.logger().info("Subscribed to Vest public channels")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error subscribing to channels")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        """Process incoming WebSocket messages."""
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            channel = data.get("channel", "")

            if "depth" in channel:
                order_book_message = self._parse_order_book_snapshot(data)
                self._message_queue[self._snapshot_messages_queue_key].put_nowait(order_book_message)
            elif "trades" in channel:
                trade_message = self._parse_trade_message(data)
                self._message_queue[self._trade_messages_queue_key].put_nowait(trade_message)
            elif channel == CONSTANTS.WS_TICKERS_CHANNEL:
                funding_info_updates = self._parse_funding_info_message(data)
                for funding_update in funding_info_updates:
                    self._message_queue[self._funding_info_messages_queue_key].put_nowait(funding_update)

    def _parse_order_book_snapshot(self, raw_message: Dict[str, Any]) -> OrderBookMessage:
        """Parse order book snapshot from WebSocket."""
        data = raw_message["data"]
        channel = raw_message["channel"]
        symbol = channel.split("@")[0]
        trading_pair = convert_from_exchange_trading_pair(symbol)

        timestamp = pd.Timestamp.now().timestamp()

        order_book_message = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": int(timestamp * 1000),
                "bids": [[Decimal(price), Decimal(qty)] for price, qty in data.get("bids", [])],
                "asks": [[Decimal(price), Decimal(qty)] for price, qty in data.get("asks", [])],
            },
            timestamp=timestamp,
        )
        return order_book_message

    def _parse_trade_message(self, raw_message: Dict[str, Any]) -> OrderBookMessage:
        """Parse trade message from WebSocket."""
        data = raw_message["data"]
        channel = raw_message["channel"]
        symbol = channel.split("@")[0]
        trading_pair = convert_from_exchange_trading_pair(symbol)

        timestamp = float(data["time"]) / 1000

        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": trading_pair,
                "trade_type": float(data["qty"]),
                "trade_id": data["id"],
                "update_id": int(data["time"]),
                "price": Decimal(data["price"]),
                "amount": Decimal(data["qty"]),
            },
            timestamp=timestamp,
        )
        return trade_message

    def _parse_funding_info_message(self, raw_message: Dict[str, Any]) -> List[FundingInfoUpdate]:
        """Parse funding info from tickers WebSocket message."""
        tickers = raw_message.get("data", [])
        funding_updates = []

        for ticker in tickers:
            try:
                symbol = ticker["symbol"]
                trading_pair = convert_from_exchange_trading_pair(symbol)

                funding_update = FundingInfoUpdate(
                    trading_pair=trading_pair,
                    index_price=Decimal(ticker["indexPrice"]),
                    mark_price=Decimal(ticker["markPrice"]),
                    next_funding_utc_timestamp=int(pd.Timestamp.now().timestamp() + 3600),
                    rate=Decimal(ticker.get("oneHrFundingRate", "0")),
                )
                funding_updates.append(funding_update)
            except (KeyError, ValueError) as e:
                self.logger().debug(f"Error parsing funding info: {e}")
                continue

        return funding_updates
