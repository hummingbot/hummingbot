import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ultrade import Client as UltradeClient, socket_options

from hummingbot.connector.exchange.ultrade import ultrade_constants as CONSTANTS
from hummingbot.connector.exchange.ultrade.ultrade_order_book import UltradeOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ultrade.ultrade_exchange import UltradeExchange


class UltradeAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'UltradeExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory
        self.ultrade_client = self.create_ultrade_client()

    def create_ultrade_client(self) -> UltradeClient:
        client = UltradeClient(network=self._domain)
        client.set_trading_key(
            trading_key=self._connector.ultrade_trading_key,
            address=self._connector.ultrade_wallet_address,
            trading_key_mnemonic=self._connector.ultrade_mnemonic_key
        )
        return client

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(websocket_assistant=ws)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                )
                await self._sleep(1.0)
            finally:
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector.ultrade_client.get_depth(symbol)
        order_book = self._connector.process_ultrade_order_book(data)

        return order_book

    def ultrade_market_streams_event_handler(self, event_name, event_data):
        if event_name is not None and event_data is not None:
            event = {
                "event": event_name,
            }
            data = {
                "data": event_data
            }
            channel: str = self._channel_originating_message(event_message=event)
            valid_channels = self._get_messages_queue_keys()
            if channel in valid_channels:
                self._message_queue[channel].put_nowait(data)
            else:
                pass    # Ignore all other channels

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                request = {
                    'symbol': symbol,
                    'streams': [socket_options.DEPTH, socket_options.TRADES],
                    'options': {}
                }

                await self._connector.ultrade_client.subscribe(request, self.ultrade_market_streams_event_handler)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = UltradeOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["data"][1])
        trade = self._process_ultrade_trade_message(raw_message["data"], trading_pair)
        trade_message = UltradeOrderBook.trade_message_from_exchange(
            trade, {"trading_pair": trading_pair})
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["data"].get("pair"))
        order_book = self._connector.process_ultrade_order_book(raw_message["data"])
        order_book_message: OrderBookMessage = UltradeOrderBook.snapshot_message_from_exchange(
            order_book, time.time(), {"trading_pair": trading_pair})
        message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        event_type = event_message.get("event")
        if event_type == CONSTANTS.ORDERBOOK_SNAPSHOT_EVENT_TYPE:
            channel = self._snapshot_messages_queue_key
        elif event_type == CONSTANTS.TRADE_EVENT_TYPE:
            channel = self._trade_messages_queue_key
        else:
            channel = "unknown"

        return channel

    def _process_ultrade_trade_message(self, trade_data: Dict[str, Any], trading_pair: str) -> Dict[str, Any]:
        base, quote = trading_pair.split("-")
        trade = {
            "trade_id": str(trade_data[2]),
            "price": float(self._connector.from_fixed_point(quote, trade_data[3])),
            "amount": float(self._connector.from_fixed_point(base, trade_data[4])),
            "trade_type": "SELL" if trade_data[7] else "BUY",
            "timestamp": int(trade_data[6]),
        }

        return trade
