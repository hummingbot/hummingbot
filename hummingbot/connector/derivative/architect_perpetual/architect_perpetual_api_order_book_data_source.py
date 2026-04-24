import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_constants import WSMessageTypes
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
        ArchitectPerpetualDerivative,
    )


class ArchitectPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _next_request_id = 0

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'ArchitectPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ) -> None:
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def listen_for_funding_info(self, output: asyncio.Queue):
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

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        funding_rates = await self._connector._fetch_last_funding_info(trading_pair=trading_pair)
        if len(funding_rates) == 0:
            raise RuntimeError(f"No funding rates available for {trading_pair}.")
        funding_data = funding_rates[0]
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(funding_data["benchmark_price"]),
            mark_price=Decimal(funding_data["settlement_price"]),
            next_funding_utc_timestamp=int(int(funding_data["timestamp_ns"]) * 1e-9),
            rate=Decimal(funding_data["funding_rate"]),
        )
        return funding_info

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        success = True

        if self._ws_assistant is None:
            self.logger().warning(f"Cannot subscribe to {trading_pair}: WebSocket not connected")
            success = False
        elif trading_pair in self._trading_pairs:
            self.logger().warning(f"{trading_pair} already subscribed. Ignoring request.")
        else:
            try:
                await self._subscribe_to_trading_pairs(ws=self._ws_assistant, trading_pairs=[trading_pair])
                self.add_trading_pair(trading_pair)
            except asyncio.CancelledError:
                raise
            except Exception:
                success = False

        return success

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        success = True

        if self._ws_assistant is None:
            self.logger().warning(f"Cannot unsubscribe from {trading_pair}: WebSocket not connected")
            success = False
        elif trading_pair not in self._trading_pairs:
            self.logger().warning(f"{trading_pair} not subscribed. Ignoring request.")
        else:
            try:
                await self._unsubscribe_from_trading_pairs(ws=self._ws_assistant, trading_pairs=[trading_pair])
                self.remove_trading_pair(trading_pair)
            except asyncio.CancelledError:
                raise
            except Exception:
                success = False

        return success

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError  # no stream offered

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["s"])
        trade_message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if raw_message["d"] == "S" else float(TradeType.BUY.value),
                "trade_id": int(f"{raw_message['ts']}{raw_message['tn']}"),
                "price": float(raw_message["p"]),
                "amount": float(raw_message["q"])
            },
            timestamp=raw_message["ts"],
        )

        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError  # only snapshot events provided

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            symbol=raw_message["s"]
        )
        update_id = int(f"{raw_message['ts']}{raw_message['tn']}")
        snapshot_message = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": [
                    (float(row["p"]), float(row["q"]))
                    for row in raw_message["b"]
                ],
                "asks": [
                    (float(row["p"]), float(row["q"]))
                    for row in raw_message["a"]
                ],
            },
            timestamp=raw_message["ts"],
        )

        message_queue.put_nowait(snapshot_message)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT, domain=self._domain),
            throttler_limit_id=CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT,
            params={"symbol": ex_trading_pair, "level": 2},
            method=RESTMethod.GET,
            is_auth_required=True,
        )
        snapshot_response = response["book"]
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "bids": [[float(i['p']), float(i['q'])] for i in snapshot_response['b']],
                "asks": [[float(i['p']), float(i['q'])] for i in snapshot_response['a']],
                "update_id": int(f"{snapshot_response['ts']}{snapshot_response['tn']}")
            },
            timestamp=int(snapshot_response["ts"]),
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        websocket_assistant: WSAssistant = await self._api_factory.get_ws_assistant()
        await websocket_assistant.connect(
            ws_url=web_utils.public_ws_url(domain=self._domain),
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE,
            ws_headers={"Authorization": f"Bearer {await self._api_factory.auth.get_token_for_ws_stream()}"}
        )
        return websocket_assistant

    async def _subscribe_channels(self, ws: WSAssistant):
        await self._subscribe_to_trading_pairs(ws=ws, trading_pairs=self._trading_pairs)

    async def _subscribe_to_trading_pairs(self, ws: WSAssistant, trading_pairs: list[str]):
        try:
            exchange_pairs = await safe_gather(
                *[
                    self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                    for trading_pair in trading_pairs
                ]
            )
            sub_operations = [
                ws.send(
                    WSJSONRequest(
                        {
                            "request_id": self._get_next_request_id(),
                            "type": "subscribe",
                            "symbol": exchange_trading_pair,
                            "level": "LEVEL_2",
                        },
                    ),
                ) for exchange_trading_pair in exchange_pairs
            ]
            await safe_gather(*sub_operations)
            self.logger().info(f"Subscribed to public channels for {', '.join(trading_pairs)}...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                f"Unexpected error occurred subscribing to order book data streams for {', '.join(trading_pairs)}.")
            raise

    async def _unsubscribe_from_trading_pairs(self, ws: WSAssistant, trading_pairs: list[str]):
        try:
            exchange_pairs = await safe_gather(
                *[
                    self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                    for trading_pair in trading_pairs
                ]
            )
            sub_operations = [
                ws.send(
                    WSJSONRequest(
                        {
                            "request_id": self._get_next_request_id(),
                            "type": "unsubscribe",
                            "symbol": exchange_trading_pair,
                        },
                    ),
                ) for exchange_trading_pair in exchange_pairs
            ]
            await safe_gather(*sub_operations)
            self.logger().info(f"Unsubscribed from public channels for {', '.join(trading_pairs)}.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                f"Unexpected error occurred unsubscribing from order book data streams for {', '.join(trading_pairs)}.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        message_type = event_message.get("t", None)
        channel = ""
        if message_type == WSMessageTypes.ORDER_BOOK_SNAPSHOT:
            channel = self._snapshot_messages_queue_key
        elif message_type == WSMessageTypes.TRADE:
            channel = self._trade_messages_queue_key
        return channel

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        pass

    def _get_next_request_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    def _time(self) -> float:
        return time.time()
