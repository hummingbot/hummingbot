import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# XRPL imports
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import BookOffers, Subscribe, SubscribeBook
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

    def __init__(self, trading_pairs: List[str], connector: "XrplExchange", api_factory: WebAssistantsFactory):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._snapshot_messages_queue_key = CONSTANTS.SNAPSHOT_EVENT_TYPE
        self._xrpl_client = self._connector.order_book_data_client
        self._open_client_lock = asyncio.Lock()

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        base_currency, quote_currency = self._connector.get_currencies_from_trading_pair(trading_pair)

        async with self._open_client_lock:
            try:
                if not self._xrpl_client.is_open():
                    await self._xrpl_client.open()

                self._xrpl_client._websocket.max_size = 2**23

                orderbook_asks_task = self.fetch_order_book_side(
                    self._xrpl_client, "current", base_currency, quote_currency, CONSTANTS.ORDER_BOOK_DEPTH
                )
                orderbook_bids_task = self.fetch_order_book_side(
                    self._xrpl_client, "current", quote_currency, base_currency, CONSTANTS.ORDER_BOOK_DEPTH
                )

                orderbook_asks_info, orderbook_bids_info = await safe_gather(orderbook_asks_task, orderbook_bids_task)

                asks = orderbook_asks_info.result.get("offers", None)
                bids = orderbook_bids_info.result.get("offers", None)

                if asks is None or bids is None:
                    raise ValueError(f"Error fetching order book snapshot for {trading_pair}")

                order_book = {
                    "asks": asks,
                    "bids": bids,
                }

                await self._xrpl_client.close()
            except Exception as e:
                raise Exception(f"Error fetching order book snapshot for {trading_pair}: {e}")

        return order_book

    async def fetch_order_book_side(
        self, client: AsyncWebsocketClient, ledger_index, taker_gets, taker_pays, limit, try_count: int = 0
    ):
        try:
            response = await client.request(
                BookOffers(
                    ledger_index=ledger_index,
                    taker_gets=taker_gets,
                    taker_pays=taker_pays,
                    limit=limit,
                )
            )
            if response.status != "success":
                error = response.to_dict().get("error", "")
                error_message = response.to_dict().get("error_message", "")
                exception_msg = f"Error fetching order book snapshot: {error} - {error_message}"
                self.logger().error(exception_msg)
                raise ValueError(exception_msg)
            return response
        except (TimeoutError, asyncio.exceptions.TimeoutError) as e:
            self.logger().debug(
                f"Verify transaction timeout error, Attempt {try_count + 1}/{CONSTANTS.FETCH_ORDER_BOOK_MAX_RETRY}"
            )
            if try_count < CONSTANTS.FETCH_ORDER_BOOK_MAX_RETRY:
                await self._sleep(CONSTANTS.FETCH_ORDER_BOOK_RETRY_INTERVAL)
                return await self.fetch_order_book_side(
                    client, ledger_index, taker_gets, taker_pays, limit, try_count + 1
                )
            else:
                self.logger().error("Max retries reached. Fetching order book failed due to timeout.")
                raise e

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
                await self._sleep(CONSTANTS.REQUEST_ORDERBOOK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public order book snapshots from exchange")
                await self._sleep(CONSTANTS.REQUEST_ORDERBOOK_INTERVAL)

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
            "price": trade["price"],
            "amount": trade["amount"],
            "transact_time": trade["update_id"],
            "trade_id": trade["trade_id"],
            "trade_type": trade["trade_type"],
            "timestamp": trade["timestamp"],
        }

        trade_message = XRPLOrderBook.trade_message_from_exchange(msg)
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    def _get_client(self) -> AsyncWebsocketClient:
        return AsyncWebsocketClient(self._connector.node_url)

    async def _process_websocket_messages_for_pair(self, trading_pair: str):
        base_currency, quote_currency = self._connector.get_currencies_from_trading_pair(trading_pair)
        account = self._connector.auth.get_account()
        subscribe_book_request = SubscribeBook(
            taker_gets=base_currency,
            taker_pays=quote_currency,
            taker=account,
            snapshot=False,
            both=True,
        )

        subscribe = Subscribe(books=[subscribe_book_request])

        async with self._get_client() as client:
            client._websocket.max_size = 2**23
            await client.send(subscribe)

            async for message in client:
                transaction = message.get("transaction")
                meta = message.get("meta")

                if transaction is None or meta is None:
                    self.logger().debug(f"Received message without transaction or meta: {message}")
                    continue

                order_book_changes = get_order_book_changes(meta)
                for account_offer_changes in order_book_changes:
                    for offer_change in account_offer_changes["offer_changes"]:
                        if offer_change["status"] in ["partially-filled", "filled"]:
                            taker_gets = offer_change["taker_gets"]
                            taker_gets_currency = taker_gets["currency"]

                            price = float(offer_change["maker_exchange_rate"])
                            filled_quantity = abs(Decimal(offer_change["taker_gets"]["value"]))
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
                                "price": Decimal(price),
                                "amount": filled_quantity,
                                "timestamp": timestamp,
                            }

                            self._message_queue[CONSTANTS.TRADE_EVENT_TYPE].put_nowait(
                                {"trading_pair": trading_pair, "trade": trade_data}
                            )

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
                        f"The websocket connection to {trading_pair} was closed ({connection_exception})"
                    )
                except TimeoutError:
                    self.logger().warning(
                        "Timeout error occurred while listening to user stream. Retrying after 5 seconds..."
                    )
                except Exception:
                    self.logger().exception(
                        "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    )
                finally:
                    await self._sleep(5.0)

        tasks = [handle_subscription(trading_pair) for trading_pair in self._trading_pairs]
        await safe_gather(*tasks)
