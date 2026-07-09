import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.pacifica_perpetual import (
    pacifica_perpetual_constants as CONSTANTS,
    pacifica_perpetual_web_utils as web_utils,
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
    from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_derivative import (
        PacificaPerpetualDerivative,
    )


class PacificaPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "PacificaPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ping_task: Optional[asyncio.Task] = None

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    def _get_headers(self) -> Dict[str, str]:
        headers = {}
        if self._connector.api_config_key:
            headers["PF-API-KEY"] = self._connector.api_config_key
        return headers

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/markets/get-orderbook

        {
            "success": true,
            "data": {
                "s": "BTC",
                "l": [
                [
                    {
                    "p": "106504",
                    "a": "0.26203",
                    "n": 1
                    },
                    {
                    "p": "106498",
                    "a": "0.29281",
                    "n": 1
                    }
                ],
                [
                    {
                    "p": "106559",
                    "a": "0.26802",
                    "n": 1
                    },
                    {
                    "p": "106564",
                    "a": "0.3002",
                    "n": 1
                    },
                ]
                ],
                "t": 1751370536325
            },
            "error": null,
            "code": null
        }
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)}

        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL,
            headers=self._get_headers()
        )

        if not response.get("success") is True:
            raise ValueError(f"[get_order_book_snapshot] Failed to get order book snapshot for {trading_pair}: {response}")

        if not response.get("data", []):
            raise ValueError(f"[get_order_book_snapshot] No data when requesting order book snapshot for {trading_pair}: {response}")

        return response["data"]

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        order_book_snapshot_data = await self._request_order_book_snapshot(trading_pair)
        order_book_snapshot_timestamp = order_book_snapshot_data["t"] / 1000

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": order_book_snapshot_timestamp,
            "bids": [(bids["p"], bids["a"]) for bids in order_book_snapshot_data["l"][0]],
            "asks": [(asks["p"], asks["a"]) for asks in order_book_snapshot_data["l"][1]]
        }, timestamp=order_book_snapshot_timestamp)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/markets/get-prices

        {
            "success": true,
            "data": [
                {
                "funding": "0.00010529",
                "mark": "1.084819",
                "mid": "1.08615",
                "next_funding": "0.00011096",
                "open_interest": "3634796",
                "oracle": "1.084524",
                "symbol": "XPL",
                "timestamp": 1759222967974,
                "volume_24h": "20896698.0672",
                "yesterday_price": "1.3412"
                }
            ],
            "error": null,
            "code": null
        }

        Index price = Oracle price
        Next funding timestamp = :00 of next hour
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.GET_PRICES_PATH_URL, domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.GET_PRICES_PATH_URL,
            headers=self._get_headers()
        )

        if not response.get("success") is True:
            raise ValueError(f"[get_funding_info] Failed to get price info for {trading_pair}: {response}")

        if not response.get("data", []):
            raise ValueError(f"[get_funding_info] No data when requesting price info for {trading_pair}: {response}")

        for price_info in response["data"]:
            if price_info["symbol"] == symbol:
                break
        else:
            raise ValueError(f"[get_funding_info] Failed to get price info for {trading_pair}: {response}")

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(price_info["oracle"]),
            mark_price=Decimal(price_info["mark"]),
            next_funding_utc_timestamp=int((time.time() // 3600 + 1) * 3600),
            rate=Decimal(price_info["funding"]),
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()

        await ws.connect(ws_url=web_utils.wss_url(self._domain), ws_headers=self._get_headers())
        self._ping_task = safe_ensure_future(self._ping_loop(ws))
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            # OB snapshots
            for trading_pair in self._trading_pairs:
                payload = {
                    "method": "subscribe",
                    "params": {
                        "source": "book",
                        "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair),
                        "agg_level": 1,
                    },
                }
                subscribe_request = WSJSONRequest(payload=payload)
                await ws.send(subscribe_request)

            # no OB diffs

            # trades
            for trading_pair in self._trading_pairs:
                payload = {
                    "method": "subscribe",
                    "params": {
                        "source": "trades",
                        "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair),
                    },
                }
                subscribe_request = WSJSONRequest(payload=payload)
                await ws.send(subscribe_request)

            # funding info

            payload = {
                "method": "subscribe",
                "params": {
                    "source": "prices",
                },
            }
            subscribe_request = WSJSONRequest(payload=payload)
            await ws.send(subscribe_request)

            self.logger().info("Subscribed to public order book and trade channels...")

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading pairs.")
            raise

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        await super()._on_order_stream_interruption(websocket_assistant)
        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None

    async def _ping_loop(self, ws: WSAssistant):
        while True:
            try:
                await asyncio.sleep(CONSTANTS.WS_PING_INTERVAL)
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await ws.send(ping_request)
            except asyncio.CancelledError:
                raise
            except RuntimeError as e:
                if "WS is not connected" in str(e):
                    return
                raise
            except Exception:
                self.logger().warning("Error sending ping to Pacifica WebSocket", exc_info=True)
                await asyncio.sleep(5.0)  # Wait before retrying

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/orderbook

        {
            "channel": "book",
            "data": {
                "l": [
                [
                    {
                    "a": "37.86",
                    "n": 4,
                    "p": "157.47"
                    },
                    // ... other aggegated bid levels
                ],
                [
                    {
                    "a": "12.7",
                    "n": 2,
                    "p": "157.49"
                    },
                    {
                    "a": "44.45",
                    "n": 3,
                    "p": "157.5"
                    },
                    // ... other aggregated ask levels
                ]
                ],
                "s": "SOL",
                "t": 1749051881187,
                "li": 1559885104
            }
        }
        """
        snapshot_data = raw_message["data"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=snapshot_data["s"])
        snapshot_timestamp = snapshot_data["t"] / 1000  # exchange provides time in ms
        update_id = snapshot_data["li"]

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid["p"], bid["a"]) for bid in snapshot_data["l"][0]],
            "asks": [(ask["p"], ask["a"]) for ask in snapshot_data["l"][1]],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp)

        message_queue.put_nowait(snapshot_msg)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/trades

        {
            "channel": "trades",
            "data": [
                {
                "u": "42trU9A5...",
                "h": 80062522,
                "s": "BTC",
                "a": "0.00001",
                "p": "89471",
                "d": "close_short",
                "tc": "normal",
                "t": 1765018379085,
                "li": 1559885104
                }
            ]
        }

        Trade side:
        (*) open_long
        (*) open_short
        (*) close_long
        (*) close_short
        """
        trade_updates = raw_message["data"]

        for trade_data in trade_updates:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=trade_data["s"])
            message_content = {
                "trade_id": trade_data["h"],  # we use history id as trade id
                "update_id": trade_data["li"],
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value) if trade_data["d"] in ("open_long", "close_short") else float(TradeType.SELL.value),
                "amount": trade_data["a"],
                "price": trade_data["p"]
            }
            trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=trade_data["t"] / 1000  # originally it's time in ms
            )

            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/prices

        {
            "channel": "prices",
            "data": [
                {
                    "funding": "0.0000125",
                    "mark": "105473",
                    "mid": "105476",
                    "next_funding": "0.0000125",
                    "open_interest": "0.00524",
                    "oracle": "105473",
                    "symbol": "BTC",
                    "timestamp": 1749051612681,
                    "volume_24h": "63265.87522",
                    "yesterday_price": "955476"
                }
                // ... other symbol prices
            ],
        }

        Index price = Oracle price
        Next funding timestamp = :00 of next hour
        """
        for price_entry in raw_message["data"]:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(price_entry["symbol"])
            if trading_pair not in self._trading_pairs:
                continue

            info_update = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(price_entry["oracle"]),
                mark_price=Decimal(price_entry["mark"]),
                next_funding_utc_timestamp=int((time.time() // 3600 + 1) * 3600),
                rate=Decimal(price_entry["funding"])
            )

            message_queue.put_nowait(info_update)

            self._connector.set_pacifica_price(
                trading_pair,
                timestamp=price_entry["timestamp"] / 1000,
                index_price=Decimal(price_entry["oracle"]),
                mark_price=Decimal(price_entry["mark"]),
            )

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "data" in event_message:
            event_channel = event_message["channel"]
            if event_channel == CONSTANTS.WS_ORDER_BOOK_SNAPSHOT_CHANNEL:
                channel = self._snapshot_messages_queue_key
            elif event_channel == CONSTANTS.WS_TRADES_CHANNEL:
                channel = self._trade_messages_queue_key
            elif event_channel == CONSTANTS.WS_PRICES_CHANNEL:
                channel = self._funding_info_messages_queue_key
        return channel

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """
        Subscribes to order book and trade channels for a single trading pair
        on the existing WebSocket connection.

        :param trading_pair: the trading pair to subscribe to
        :return: True if subscription was successful, False otherwise
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot subscribe to {trading_pair}: WebSocket not connected"
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            # Subscribe to order book snapshots
            book_payload = {
                "method": "subscribe",
                "params": {
                    "source": "book",
                    "symbol": symbol,
                    "agg_level": 1,
                },
            }
            subscribe_book_request = WSJSONRequest(payload=book_payload)

            # Subscribe to trades
            trades_payload = {
                "method": "subscribe",
                "params": {
                    "source": "trades",
                    "symbol": symbol,
                },
            }
            subscribe_trades_request = WSJSONRequest(payload=trades_payload)

            await self._ws_assistant.send(subscribe_book_request)
            await self._ws_assistant.send(subscribe_trades_request)

            self.add_trading_pair(trading_pair)
            self.logger().info(f"Subscribed to {trading_pair} order book and trade channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error subscribing to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """
        Unsubscribes from order book and trade channels for a single trading pair
        on the existing WebSocket connection.

        :param trading_pair: the trading pair to unsubscribe from
        :return: True if unsubscription was successful, False otherwise
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected"
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            # Unsubscribe from order book snapshots
            book_payload = {
                "method": "unsubscribe",
                "params": {
                    "source": "book",
                    "symbol": symbol,
                    "agg_level": 1,
                },
            }
            unsubscribe_book_request = WSJSONRequest(payload=book_payload)

            # Unsubscribe from trades
            trades_payload = {
                "method": "unsubscribe",
                "params": {
                    "source": "trades",
                    "symbol": symbol,
                },
            }
            unsubscribe_trades_request = WSJSONRequest(payload=trades_payload)

            await self._ws_assistant.send(unsubscribe_book_request)
            await self._ws_assistant.send(unsubscribe_trades_request)

            self.remove_trading_pair(trading_pair)
            self.logger().info(f"Unsubscribed from {trading_pair} order book and trade channels")

            # TODO (dizpers): to be 100% sure we should actually wait until the copy of unsub message is received

            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error unsubscribing from {trading_pair}")
            return False
