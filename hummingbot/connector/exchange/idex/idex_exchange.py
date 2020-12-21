import time
import asyncio

import pandas as pd

from dataclasses import asdict
from decimal import Decimal
from typing import Optional, List, Dict, Any, AsyncIterable

from async_timeout import timeout

from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import OrderType, TradeType, TradeFee, MarketEvent, BuyOrderCreatedEvent, \
    SellOrderCreatedEvent, MarketOrderFailureEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import estimate_fee

from .client.asyncio import AsyncIdexClient
from .idex_auth import IdexAuth
from .idex_in_flight_order import IdexInFlightOrder
from .idex_order_book_tracker import IdexOrderBookTracker
from .idex_user_stream_tracker import IdexUserStreamTracker
from .types.rest.request import RestRequestCancelOrder, RestRequestOrder, OrderSide, OrderStatus
from .types.websocket.response import WebSocketResponseTradeShort, WebSocketResponseBalanceShort, \
    WebSocketResponseL1OrderBookShort, WebSocketResponseL2OrderBookShort
from .utils import to_idex_pair, to_idex_order_type, create_id, EXCHANGE_NAME


class IdexExchange(ExchangeBase):

    name: str = EXCHANGE_NAME

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(self,
                 idex_api_key: str,
                 idex_api_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        """
        :param idex_com_api_key: The API key to connect to private idex.io APIs.
        :param idex_com_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._idex_auth: IdexAuth = IdexAuth(idex_api_key, idex_api_secret_key)
        self._client: AsyncIdexClient = AsyncIdexClient(auth=self._idex_auth)
        self._order_book_tracker = IdexOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = IdexUserStreamTracker(self._idex_auth, trading_pairs)
        self._user_stream_tracker_task = None
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, idexComInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._account_balances = {}  # Dict[asset_name:str, Decimal]
        self._account_available_balances = {}  # Dict[asset_name:str, Decimal]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        :return active in-flight orders in json format, is used to save in sqlite db.
        """
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
            if not value.is_done
        }

    def supported_order_types(self) -> List[OrderType]:
        # TODO: Validate against
        """
        0	Market
        1	Limit
        2	Limit maker
        3	Stop loss
        4	Stop loss limit
        5	Take profit
        6	Take profit limit
        :return:
        """
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def limit_orders(self) -> List[LimitOrder]:
        """
        TODO: Validate
        """
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        :return: data frame with trading_pair as index, and at least the following columns --
                 ["baseAsset", "quoteAsset", "volume", "USDVolume"]
        TODO: Validate that this method actually needed
        TODO: How to get USDVolume
        """
        pass

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_NaN):
        return await self._create_order(
            "buy",
            order_id,
            trading_pair,
            amount,
            order_type,
            price
        )

    async def execute_sell(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_NaN):
        return await self._create_order(
            "sell",
            order_id,
            trading_pair,
            amount,
            order_type,
            price
        )

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN,
            **kwargs):
        order_id = create_id()
        safe_ensure_future(self._create_order(
            "buy",
            order_id,
            trading_pair,
            amount,
            order_type,
            price
        ))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN,
             **kwargs):
        order_id = create_id()
        safe_ensure_future(self._create_order(
            "sell",
            order_id,
            trading_pair,
            amount,
            order_type,
            price
        ))
        return order_id

    async def _create_order(self,
                            side: OrderSide,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type=OrderType.MARKET,
                            price: Decimal = s_decimal_NaN):
        market = await to_idex_pair(trading_pair)
        try:
            result = await self._client.trade.create_order(
                parameters=RestRequestOrder(
                    wallet=self._idex_auth.get_wallet().address,
                    clientOrderId=order_id,
                    market=market,
                    quantity=str(amount),
                    type=to_idex_order_type(order_type),
                    price=str(price),
                    side=side
                )
            )
            print(f"CREATE ORDER: {result}")
            if result.status == "active":
                event_tag = MarketEvent.BuyOrderCreated if side == "buy" else MarketEvent.SellOrderCreated
                event_class = BuyOrderCreatedEvent if side == "buy" else SellOrderCreatedEvent
                self.trigger_event(
                    event_tag,
                    event_class(
                        self.current_timestamp,
                        order_type,
                        trading_pair,
                        amount,
                        price,
                        order_id
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {side} {order_type.name} order to Idex for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(
                MarketEvent.OrderFailure,
                MarketOrderFailureEvent(
                    self.current_timestamp, order_id, order_type
                )
            )

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal(0.00000001)

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal(0.00000001)

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = IdexInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def cancel(self, trading_pair: str, client_order_id: str):
        safe_ensure_future(self._cancel_order(trading_pair, client_order_id))

    async def _cancel_order(self, trading_pair: str, client_order_id: str):
        market = await to_idex_pair(trading_pair)
        await self._client.trade.cancel_order(parameters=RestRequestCancelOrder(
            wallet="None",  # TODO: Get wallet
            orderId=client_order_id,
            market=market
        ))

    async def get_order(self, client_order_id: str) -> Dict[str, Any]:
        order = self._in_flight_orders.get(client_order_id)
        exchange_order_id = await order.get_exchange_order_id()
        orders = await self._client.trade.get_order(orderId=exchange_order_id)
        return [asdict(order) for order in orders] if isinstance(orders, list) else asdict(orders)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    async def check_network(self) -> NetworkStatus:
        try:
            result = await self._client.public.get_ping()
            assert result == {}
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def start_network(self):
        await self.stop_network()
        self._order_book_tracker.start()
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        self._order_book_tracker.stop()

        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        # TODO: Implement
        # if self._trading_rules_polling_task is not None:
        #     self._trading_rules_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = self._user_stream_event_listener_task = None

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances("_status_polling_loop"),
                    # self._update_order_fills_from_trades(), # TODO: TBI
                    # self._update_order_status(),  # TODO: TBI
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"EXC: {e}")
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Idex. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        return estimate_fee(EXCHANGE_NAME, order_type == TradeType.BUY)

    @property
    def status_dict(self) -> Dict[str, bool]:
        result = {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            # "trading_rule_initialized": len(self._trading_rules) > 0, # TODO: Implement _trading_rules_polling_task
            "user_stream_initialized": self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
        }
        return result

    async def server_time(self) -> int:
        return (await self._client.public.get_time()).serverTime

    @property
    def ready(self) -> bool:
        print(f"READY: {self.status_dict} {self._account_balances}")
        return all(self.status_dict.values())

    @property
    def in_flight_orders(self)  -> Dict[str, InFlightOrderBase]:
        return self._in_flight_orders

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self._execute_cancel(o.trading_pair, o.client_order_id, True) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []
        try:
            async with timeout(timeout_seconds):
                results = await safe_gather(*tasks, return_exceptions=True)
                for result in results:
                    if result is not None and not isinstance(result, Exception):
                        order_id_set.remove(result)
                        successful_cancellations.append(CancellationResult(result, True))
        except Exception as e:
            print(f"EXC: {e}")
            self.logger().error("Cancel all failed.", exc_info=True)
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order on Crypto.com. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = self._last_timestamp / poll_interval
        current_tick = timestamp / poll_interval
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def stop_tracking_order(self, order_id: str):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    _account_available_balances = None
    _account_balances = None

    async def _update_balances(self, sender=None):
        self._account_available_balances = self._account_available_balances or {}
        self._account_balances = self._account_balances or {}
        balances_available = {}
        balances = {}
        wallets = await self._client.user.wallets()
        for wallet in wallets:
            accounts = await self._client.user.balances(wallet=wallet.address)
            for account in accounts:
                # Set available balance
                balances_available.setdefault(wallet.address, {})
                balances_available[wallet.address][account.asset] = Decimal(account.availableForTrade)
                # Set balance
                balances.setdefault(wallet.address, {})
                balances[wallet.address][account.asset] = Decimal(account.quantity)

        self._account_available_balances = balances_available
        self._account_balances = balances

        print(f"BAL: {self._account_balances}")

    def get_balance(self, currency: str) -> Decimal:
        """
        :param currency: The currency (token) name
        :return: A balance for the given currency (token)
        """
        wallet = self._idex_auth.get_wallet()
        return self._account_balances[wallet.address].get(currency, Decimal(0))

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"EXC: {e}")
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Idex. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        TODO: implement trade absorb
        TODO: implement order absorb

        :return:
        """
        async for event in self._iter_user_event_queue():
            if not isinstance(event, (
                    WebSocketResponseTradeShort,
                    WebSocketResponseBalanceShort,
                    WebSocketResponseL1OrderBookShort,
                    WebSocketResponseL2OrderBookShort)):
                continue

            print(f"USEL: {event}")

            if isinstance(event, WebSocketResponseBalanceShort):
                self._account_balances[event.w][event.a] = Decimal(str(event.q))
                self._account_available_balances[event.w][event.a] = Decimal(str(event.f))

            # try:
            #     if "result" not in event_message or "channel" not in event_message["result"]:
            #         continue
            #     channel = event_message["result"]["channel"]
            #     if "user.trade" in channel:
            #         for trade_msg in event_message["result"]["data"]:
            #             await self._process_trade_message(trade_msg)
            #     elif "user.order" in channel:
            #         for order_msg in event_message["result"]["data"]:
            #             self._process_order_message(order_msg)
            # except asyncio.CancelledError:
            #     raise
            # except Exception:
            #     self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
            #     await asyncio.sleep(5.0)
