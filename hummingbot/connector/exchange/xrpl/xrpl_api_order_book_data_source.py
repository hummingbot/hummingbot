import asyncio
import time
from decimal import Decimal

# import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# XRPL imports
from xrpl.clients import WebsocketClient
from xrpl.models.requests import BookOffers, Subscribe, SubscribeBook
from xrpl.models.transactions.metadata import TransactionMetadata
from xrpl.utils import get_order_book_changes, ripple_time_to_posix

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_order_book import XRPLOrderBook
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange


class XRPLAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'XrplExchange',
                 api_factory: WebAssistantsFactory):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._snapshot_messages_queue_key = CONSTANTS.SNAPSHOT_EVENT_TYPE
        self._client = WebsocketClient(self._connector.node_url)

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        # Create a client to connect to the test network
        # client = self._client
        base_currency, quote_currency = self._connector.get_currencies_from_trading_pair(trading_pair)

        try:
            with self._client:
                orderbook_asks_info = self._client.request(
                    BookOffers(
                        ledger_index="current",
                        taker_gets=base_currency,
                        taker_pays=quote_currency,
                        limit=CONSTANTS.ORDER_BOOK_DEPTH,
                    )
                )

                orderbook_bids_info = self._client.request(
                    BookOffers(
                        ledger_index="current",
                        taker_gets=quote_currency,
                        taker_pays=base_currency,
                        limit=CONSTANTS.ORDER_BOOK_DEPTH,
                    )
                )

                asks = orderbook_asks_info.result.get("offers", [])
                bids = orderbook_bids_info.result.get("offers", [])

                order_book = {
                    "asks": asks,
                    "bids": bids,
                }
        except Exception as e:
            self.logger().error(f"Error fetching order book snapshot for {trading_pair}: {e}")
            return {}

        return order_book

    # async def _subscribe_channels(self, ws: WSAssistant):
    #     pass
    #
    # async def _connected_websocket_assistant(self) -> WSAssistant:
    #     pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Reads the order snapshot events queue. For each event it creates a snapshot message instance and adds it to the
        output queue.
        This method also request the full order book content from the exchange using HTTP requests if it does not
        receive events during one hour.

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created snapshot messages
        """
        while True:
            try:
                await self._request_order_book_snapshots(output=output)
                await self._sleep(2.0)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public order book snapshots from exchange")
                await self._sleep(2.0)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()

        snapshot_msg: OrderBookMessage = XRPLOrderBook.snapshot_message_from_exchange(
            msg=snapshot,
            timestamp=snapshot_timestamp,
            metadata={"trading_pair": trading_pair},
        )

        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = raw_message["trading_pair"]
        trade = raw_message["trade"]

        msg = {
            "trading_pair": trading_pair,
            "price": trade.price,
            "fill_quantity": trade.fill_quantity,
            "transact_time": trade.transact_time,
            "trade_id": trade.trade_id,
            "trade_type": trade.trade_type,
            "timestamp": trade.timestamp,
        }

        trade_message = XRPLOrderBook.trade_message_from_exchange(msg)
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    async def _process_websocket_messages_for_pair(self, trading_pair: str):
        base_currency, quote_currency = self._connector.get_currencies_from_trading_pair(trading_pair)
        account = self._connector.get_account()
        book_ask = SubscribeBook(
            taker_gets=base_currency,
            taker_pays=quote_currency,
            taker=account,
            snapshot=False,
        )
        book_bid = SubscribeBook(
            taker_gets=quote_currency,
            taker_pays=base_currency,
            taker=account,
            snapshot=False,
        )

        subscribe = Subscribe(books=[book_ask, book_bid])

        with WebsocketClient(self._connector.node_url) as client:
            client.send(subscribe)

            for message in client:
                meta = message.get("meta", None)
                transaction = message.get("transaction", {})
                if isinstance(meta, TransactionMetadata):
                    order_book_changes = get_order_book_changes(meta)
                    for account_offer_changes in order_book_changes:
                        for offer_change in account_offer_changes["offer_changes"]:
                            if offer_change["status"] in ["partially_filled", "filled"]:
                                taker_gets = offer_change["taker_gets"]
                                taker_gets_currency = taker_gets["currency"]

                                price = float(offer_change["maker_exchange_rate"])
                                filled_quantity = Decimal(offer_change["taker_gets"]["value"])
                                transact_time = ripple_time_to_posix(transaction["date"])
                                trade_id = transaction["date"] + transaction["Sequence"]
                                timestamp = time.time()

                                if taker_gets_currency == base_currency.currency:
                                    # This is BUY trade (consume ASK)
                                    trade_type = float(TradeType.BUY.value)
                                else:
                                    # This is SELL trade (consume BID)
                                    price = 1 / price
                                    trade_type = float(TradeType.SELL.value)

                                trade_data = {
                                    "trade_type": trade_type,
                                    "trade_id": trade_id,
                                    "update_id": transact_time,
                                    "price": price,
                                    "amount": filled_quantity,
                                    "timestamp": timestamp,
                                }
                                self._message_queue[CONSTANTS.TRADE_EVENT_TYPE].put_nowait(
                                    {"trading_pair": trading_pair, "trade": trade_data})

    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """

        async def handle_subscription(trading_pair):
            while True:
                try:
                    await self._process_websocket_messages_for_pair(trading_pair=trading_pair)
                except asyncio.CancelledError:
                    raise
                except ConnectionError as connection_exception:
                    self.logger().warning(
                        f"The websocket connection to {trading_pair} was closed ({connection_exception})")
                except TimeoutError:
                    self.logger().warning(
                        "Timeout error occurred while listening to user stream. Retrying after 5 seconds...")
                except Exception:
                    self.logger().exception(
                        "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    )
                finally:
                    await self._sleep(5.0)

        tasks = [handle_subscription(trading_pair) for trading_pair in self._trading_pairs]
        await safe_gather(*tasks)
