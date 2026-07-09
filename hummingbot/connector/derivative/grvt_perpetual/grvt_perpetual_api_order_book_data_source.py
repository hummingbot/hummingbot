import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_order_book import GrvtPerpetualOrderBook
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GrvtPerpetualDerivative


class GrvtPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "GrvtPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_request_id = 0

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        response = await self._connector._api_post(
            path_url=CONSTANTS.TICKER_PATH_URL,
            data={"instrument": exchange_symbol},
        )
        result = response["result"]
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(result["index_price"])),
            mark_price=Decimal(str(result["mark_price"])),
            next_funding_utc_timestamp=self._next_funding_time(result),
            rate=Decimal(str(result["funding_rate_8h_curr"])),
        )

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        response = await self._connector._api_post(
            path_url=CONSTANTS.ORDER_BOOK_PATH_URL,
            data={"instrument": exchange_symbol, "depth": 50, "aggregate": 1},
        )
        return response["result"]

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        return GrvtPerpetualOrderBook.snapshot_message_from_exchange(
            snapshot,
            int(snapshot["event_time"]) * 1e-9,
            metadata={"trading_pair": trading_pair},
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.public_wss_url(domain=self._domain),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                await self.subscribe_to_trading_pair(trading_pair)
                exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                await ws.send(self._subscription_request(stream=CONSTANTS.PUBLIC_WS_CHANNEL_TICKER, selector=f"{exchange_symbol}@1000"))
            self.logger().info("Subscribed to GRVT public order book, trades, and ticker channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to GRVT order book streams.", exc_info=True)
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        stream = event_message.get("stream", "")
        if stream == CONSTANTS.PUBLIC_WS_CHANNEL_BOOK_DIFF:
            return self._diff_messages_queue_key
        if stream == CONSTANTS.PUBLIC_WS_CHANNEL_TRADE:
            return self._trade_messages_queue_key
        if stream == CONSTANTS.PUBLIC_WS_CHANNEL_TICKER:
            return self._funding_info_messages_queue_key
        return ""

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        feed = raw_message["feed"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(feed["instrument"])
        message_queue.put_nowait(
            GrvtPerpetualOrderBook.diff_message_from_exchange(raw_message, metadata={"trading_pair": trading_pair})
        )

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        feed = raw_message["feed"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(feed["instrument"])
        message_queue.put_nowait(
            GrvtPerpetualOrderBook.snapshot_message_from_ws(raw_message, metadata={"trading_pair": trading_pair})
        )

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        feed = raw_message["feed"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(feed["instrument"])
        message_queue.put_nowait(
            GrvtPerpetualOrderBook.trade_message_from_exchange(raw_message, metadata={"trading_pair": trading_pair})
        )

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        feed = raw_message["feed"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(feed["instrument"])
        message_queue.put_nowait(
            FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(str(feed["index_price"])),
                mark_price=Decimal(str(feed["mark_price"])),
                next_funding_utc_timestamp=self._next_funding_time(feed),
                rate=Decimal(str(feed["funding_rate_8h_curr"])),
            )
        )

    def _subscription_request(self, stream: str, selector: str) -> WSJSONRequest:
        self._ws_request_id += 1
        return WSJSONRequest(
            payload={
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": {
                    "stream": stream,
                    "selectors": [selector],
                },
                "id": self._ws_request_id,
            }
        )

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        await self._ws_assistant.send(
            self._subscription_request(stream=CONSTANTS.PUBLIC_WS_CHANNEL_BOOK_DIFF, selector=f"{exchange_symbol}@100")
        )
        await self._ws_assistant.send(
            self._subscription_request(stream=CONSTANTS.PUBLIC_WS_CHANNEL_TRADE, selector=f"{exchange_symbol}@50")
        )
        self.add_trading_pair(trading_pair)
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        for stream, selector in [
            (CONSTANTS.PUBLIC_WS_CHANNEL_BOOK_DIFF, f"{exchange_symbol}@100"),
            (CONSTANTS.PUBLIC_WS_CHANNEL_TRADE, f"{exchange_symbol}@50"),
        ]:
            self._ws_request_id += 1
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "jsonrpc": "2.0",
                        "method": "unsubscribe",
                        "params": {"stream": stream, "selectors": [selector]},
                        "id": self._ws_request_id,
                    }
                )
            )
        self.remove_trading_pair(trading_pair)
        return True

    @staticmethod
    def _next_funding_time(feed: Dict[str, Any]) -> int:
        return int(int(feed["next_funding_time"]) * 1e-9)
