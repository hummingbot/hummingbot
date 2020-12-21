import time
import asyncio

import pandas as pd

from dataclasses import asdict
from decimal import Decimal
from typing import Optional, List, Dict, Any, AsyncIterable

# from async_timeout import timeout

from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
# from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import OrderType, OrderCancelledEvent, TradeType, TradeFee, MarketEvent, BuyOrderCreatedEvent, \
    SellOrderCreatedEvent, MarketOrderFailureEvent, BuyOrderCompletedEvent, SellOrderCompletedEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import estimate_fee

from .types.enums import OrderStatus

from .client.exceptions import ResourceNotFoundError

from .client.asyncio import AsyncIdexClient
from .idex_auth import IdexAuth
from .idex_in_flight_order import IdexInFlightOrder
from .idex_order_book_tracker import IdexOrderBookTracker
from .idex_user_stream_tracker import IdexUserStreamTracker
from .types.rest.request import RestRequestCancelOrder, RestRequestCancelAllOrders, RestRequestOrder, OrderSide
from .types.websocket.response import WebSocketResponseTradeShort, \
    WebSocketResponseOrderShort
from .utils import to_idex_pair, to_idex_order_type, create_id, create_nonce, EXCHANGE_NAME, round_to_8_decimals


class IdexExchange(ExchangeBase):

    name: str = EXCHANGE_NAME

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    def __init__(self,
                 idex_api_key: str,
                 idex_api_secret_key: str,
                 idex_wallet_private_key: str,
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
        self._idex_auth: IdexAuth = IdexAuth(idex_api_key, idex_api_secret_key, idex_wallet_private_key)
        self._account_available_balances = {}  # Dict[asset_name:str, Decimal]
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

    # def amount_to_precision(self, symbol, amount):
        # return self.decimal_to_precision(amount, TRUNCATE, self.markets[symbol]['precision']['amount'], self.precisionMode, self.paddingMode)

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

    async def _fetch_order(self, order_id: str):
        nonce = create_nonce()
        order = await self._client.trade.get_orders(
            wallet=self._idex_auth.get_wallet().address,
            nonce=str(nonce),
            orderId=order_id,
        )
        return order

    async def _create_order(self,
                            side: OrderSide,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type=OrderType.MARKET,
                            price: Decimal = s_decimal_NaN):

        try:
            orderVersion = 1
            market = await to_idex_pair(trading_pair)
            if order_type == OrderType.MARKET:
                typeEnum = 0
            elif order_type == OrderType.LIMIT:
                typeEnum = 1
            elif order_type == OrderType.LIMIT_MAKER:
                typeEnum = 2
            else:
                raise Exception(order_type + " is not a valid order type")

            nonce = create_nonce()
            walletBytes = self._idex_auth.get_wallet_bytes()
            price = round_to_8_decimals(price)  # TODO precision
            sideEnum = 0 if (side == 'buy') else 1
            amountEnum = 0  # base quantity
            amountString = round_to_8_decimals(amount)  # TODO self.amount_to_precision(symbol, amount)
            timeInForceEnum = 0
            selfTradePreventionEnum = 0

            byteArray = [
                IdexAuth.number_to_be(orderVersion, 1),
                nonce.bytes,
                IdexAuth.base16_to_binary(walletBytes),
                IdexAuth.encode(market),
                IdexAuth.number_to_be(typeEnum, 1),
                IdexAuth.number_to_be(sideEnum, 1),
                IdexAuth.encode(amountString),
                IdexAuth.number_to_be(amountEnum, 1),
                IdexAuth.encode(price),
                IdexAuth.encode(''),  # stopPrice
                IdexAuth.encode(order_id),  # clientOrderId
                IdexAuth.number_to_be(timeInForceEnum, 1),
                IdexAuth.number_to_be(selfTradePreventionEnum, 1),
                IdexAuth.number_to_be(0, 8),  # unused
            ]

            binary = IdexAuth.binary_concat_array(byteArray)
            hash = IdexAuth.hash(binary, 'keccak', 'hex')
            signature = self._idex_auth.sign_message_string(hash, IdexAuth.binary_to_base16(self._idex_auth.get_wallet().key))

            result = await self._client.trade.create_order(
                parameters=RestRequestOrder(
                    wallet=self._idex_auth.get_wallet().address,
                    clientOrderId=order_id,
                    market=market,
                    nonce=str(nonce),
                    quantity=round_to_8_decimals(amount),
                    type=to_idex_order_type(order_type),
                    timeInForce='gtc',
                    price=price,
                    side=side,
                    selfTradePrevention='dc'
                ),
                signature=signature
            )

            self.start_tracking_order(
                order_id,  # client_order_id
                result.orderId,  # exchange_order_id
                market,
                TradeType.BUY if (side == 'buy') else TradeType.SELL,
                price,
                amount,
                order_type
            )

            print(f"....................CREATED ORDER.......: {result}")
            if result.status != "rejected" and result.status != "cancelled":
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
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def cancel(self, trading_pair: str, order_id: str):
        safe_ensure_future(self._cancel_order(trading_pair, order_id))

    async def _cancel_order(self, trading_pair: str, client_order_id: str):
        # market = await to_idex_pair(trading_pair)
        nonce = create_nonce()
        walletBytes = self._idex_auth.get_wallet_bytes()
        byteArray = [
            nonce.bytes,
            IdexAuth.base16_to_binary(walletBytes),
            IdexAuth.encode("client:" + client_order_id),
        ]
        binary = IdexAuth.binary_concat_array(byteArray)
        hash = IdexAuth.hash(binary, 'keccak', 'hex')
        self.logger().info(f"Cancel order id: {client_order_id}")
        signature = self._idex_auth.sign_message_string(hash, IdexAuth.binary_to_base16(self._idex_auth.get_wallet().key))
        await self._client.trade.cancel_order(
            parameters=RestRequestCancelOrder(
                wallet=self._idex_auth.get_wallet().address,
                orderId="client:" + client_order_id,
                nonce=str(nonce),
            ),
            signature=signature
        )
        # TODO confirm order was cancelled
        tracked_order = self._in_flight_orders.get(client_order_id)
        self.trigger_event(
            MarketEvent.OrderCancelled,
            OrderCancelledEvent(
                self.current_timestamp,
                client_order_id
            )
        )
        tracked_order.cancelled_event.set()
        self.stop_tracking_order(client_order_id)
        return client_order_id

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
            # await result.text()
            assert result == {}
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().info(f"Failed network status check.... {e}")
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
                    self._update_order_status(),
                    asyncio.sleep(1),
                    # self._update_order_fills_from_trades(), # TODO: TBI
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Status Polling Loop Error: {e}")
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
        account_balance_status = False
        if (self._account_balances is not None):
            account_balance_status = len(self._account_balances) > 0 if self._trading_required else True
        result = {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": account_balance_status,
            # "trading_rule_initialized": len(self._trading_rules) > 0, # TODO: Implement _trading_rules_polling_task
            "user_stream_initialized": self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
        }
        return result

    async def server_time(self) -> int:
        return (await self._client.public.get_time()).serverTime

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrderBase]:
        return self._in_flight_orders

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = []
            for tracked_order in tracked_orders:
                tasks.append(self._fetch_order(order_id=tracked_order.exchange_order_id))
            orders = await safe_gather(*tasks, return_exceptions=True)

            for index, order in enumerate(orders):
                if isinstance(order, ResourceNotFoundError):
                    tracked_order = tracked_orders[index]
                    client_order_id = tracked_order.client_order_id
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(
                                           self.current_timestamp,
                                           tracked_order.client_order_id))
                    tracked_order.cancelled_event.set()
                    self.stop_tracking_order(client_order_id)
                    continue
                self._process_order_message(client_order_id=order.clientOrderId, status=order.status)

    # async def _process_trade_message(self, trade_msg: Dict[str, Any]):
    #     """
    #     Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
    #     event if the total executed amount equals to the specified order amount.
    #     """
    #     for order in self._in_flight_orders.values():
    #         await order.get_exchange_order_id()
    #     track_order = [o for o in self._in_flight_orders.values() if trade_msg["order_id"] == o.exchange_order_id]
    #     if not track_order:
    #         return
    #     tracked_order = track_order[0]
    #     updated = tracked_order.update_with_trade_update(trade_msg)
    #     if not updated:
    #         return
    #     self.trigger_event(
    #         MarketEvent.OrderFilled,
    #         OrderFilledEvent(
    #             self.current_timestamp,
    #             tracked_order.client_order_id,
    #             tracked_order.trading_pair,
    #             tracked_order.trade_type,
    #             tracked_order.order_type,
    #             Decimal(str(trade_msg["traded_price"])),
    #             Decimal(str(trade_msg["traded_quantity"])),
    #             TradeFee(0.0, [(trade_msg["fee_currency"], Decimal(str(trade_msg["fee"])))]),
    #             exchange_trade_id=trade_msg["order_id"]
    #         )
    #     )
    #     if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
    #             tracked_order.executed_amount_base >= tracked_order.amount:
    #         tracked_order.last_state = "FILLED"
    #         self.logger().info(f"The {tracked_order.trade_type.name} order "
    #                            f"{tracked_order.client_order_id} has completed "
    #                            f"according to order status API.")
    #         event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
    #             else MarketEvent.SellOrderCompleted
    #         event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
    #             else SellOrderCompletedEvent
    #         self.trigger_event(event_tag,
    #                            event_class(self.current_timestamp,
    #                                        tracked_order.client_order_id,
    #                                        tracked_order.base_asset,
    #                                        tracked_order.quote_asset,
    #                                        tracked_order.fee_asset,
    #                                        tracked_order.executed_amount_base,
    #                                        tracked_order.executed_amount_quote,
    #                                        tracked_order.fee_paid,
    #                                        tracked_order.order_type))
    #         self.stop_tracking_order(tracked_order.client_order_id)

    def _process_order_message(self, client_order_id: str, status: OrderStatus):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        if client_order_id not in self._in_flight_orders:
            return
        tracked_order = self._in_flight_orders[client_order_id]
        print(f"_process_order_message tracked_order: {tracked_order}")
        if status == "canceled":
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(
                                   self.current_timestamp,
                                   tracked_order.client_order_id))
            tracked_order.cancelled_event.set()
            self.stop_tracking_order(client_order_id)
        elif status == "rejected":
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp,
                                   tracked_order.client_order_id,
                                   tracked_order.order_type
                               ))
            self.stop_tracking_order(client_order_id)
        elif status == "filled":
            event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                else MarketEvent.SellOrderCompleted
            event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                else SellOrderCompletedEvent
            self.trigger_event(event_tag,
                               event_class(self.current_timestamp,
                                           tracked_order.client_order_id,
                                           tracked_order.base_asset,
                                           tracked_order.quote_asset,
                                           tracked_order.fee_asset,
                                           tracked_order.executed_amount_base,
                                           tracked_order.executed_amount_quote,
                                           tracked_order.fee_paid,
                                           tracked_order.order_type))
        elif status == "active" or status == "open" or status == "partiallyFilled":
            print("active or partiallyFilled")

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """

        self.logger().info("CANCEL ALL")
        nonce = create_nonce()
        walletBytes = self._idex_auth.get_wallet_bytes()
        byteArray = [
            nonce.bytes,
            IdexAuth.base16_to_binary(walletBytes),
        ]
        binary = IdexAuth.binary_concat_array(byteArray)
        hash = IdexAuth.hash(binary, 'keccak', 'hex')
        signature = self._idex_auth.sign_message_string(hash, IdexAuth.binary_to_base16(self._idex_auth.get_wallet().key))
        await self._client.trade.cancel_order(
            parameters=RestRequestCancelAllOrders(
                wallet=self._idex_auth.get_wallet().address,
                nonce=str(nonce),
            ),
            signature=signature
        )

        return []

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

    async def _update_balances(self, sender=None):
        balances_available = {}
        balances = {}

        wallets = await self._client.user.wallets()

        wallet_address = self._idex_auth.get_wallet().address
        is_wallet_associated = False
        for wallet in wallets:
            if wallet.address == wallet_address:
                is_wallet_associated = True

        if is_wallet_associated is False:
            nonce = create_nonce()
            byteArray = [
                nonce.bytes,
                IdexAuth.base16_to_binary(self._idex_auth.get_wallet_bytes()),
            ]
            binary = IdexAuth.binary_concat_array(byteArray)
            hash = IdexAuth.hash(binary, 'keccak', 'hex')
            signature = self._idex_auth.sign_message_string(hash, IdexAuth.binary_to_base16(self._idex_auth.get_wallet().key))
            await self._client.user.associate_wallet(str(nonce), wallet_address=wallet_address, wallet_signature=signature)

        # for wallet in wallets:
        accounts = await self._client.user.balances(wallet=wallet_address)
        print(f"balances... {accounts}")
        if len(accounts) == 0:
            raise Exception("Wallet does not have any token balances. Please deposit some tokens.")
        for account in accounts:
            # Set available balance
            balances_available.setdefault(wallet_address, {})
            balances_available[wallet_address][account.asset] = Decimal(account.availableForTrade)
            self._account_available_balances[account.asset] = Decimal(account.availableForTrade)

            # Set balance
            balances.setdefault(wallet_address, {})
            balances[wallet_address][account.asset] = Decimal(account.quantity)
            self._account_balances[account.asset] = Decimal(account.quantity)

    def get_balance(self, currency: str) -> Decimal:
        """
        :param currency: The currency (token) name
        :return: A balance for the given currency (token)
        """
        wallet = self._idex_auth.get_wallet()
        # print(f"get_balance: walletAddress: {wallet.address} currency: {currency}")
        return self._account_balances[wallet.address].get(currency, Decimal(0))

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"_iter_user_event_queue Error: {e}")
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Idex. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        TODO: implement trade absorb
        """
        async for event in self._iter_user_event_queue():
            if not isinstance(event, (
                    # WebSocketResponseL2OrderBookShort,
                    WebSocketResponseTradeShort,
                    # WebSocketResponseBalanceShort,
                    # WebSocketResponseL1OrderBookShort,
                    WebSocketResponseOrderShort)):
                continue

            print(f"USER WS EVENT: {event}")

            # TODO
            """
            if isinstance(event, WebSocketResponseBalanceShort):
                self._account_balances[event.w][event.a] = Decimal(str(event.q))
                self._account_available_balances[event.w][event.a] = Decimal(str(event.f))
            """
            if isinstance(event, WebSocketResponseOrderShort):
                self._process_order_message(event.c, event.X)

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
