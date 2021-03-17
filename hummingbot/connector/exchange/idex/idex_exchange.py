import json
import math
import time
import asyncio
import aiohttp

import pandas as pd

from dataclasses import asdict
from decimal import Decimal
from typing import Optional, List, Dict, Any, AsyncIterable

# from async_timeout import timeout
import ujson
from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
# from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import OrderType, OrderCancelledEvent, TradeType, TradeFee, MarketEvent, \
    BuyOrderCreatedEvent, \
    SellOrderCreatedEvent, MarketOrderFailureEvent, BuyOrderCompletedEvent, SellOrderCompletedEvent, OrderFilledEvent
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
from .idex_utils import get_idex_rest_url, get_idex_ws_feed
from .types.rest.request import RestRequestCancelOrder, RestRequestCancelAllOrders, RestRequestOrder, OrderSide
from .types.websocket.response import WebSocketResponseTradeShort, \
    WebSocketResponseOrderShort
from .utils import to_idex_pair, to_idex_order_type, create_id, create_nonce, EXCHANGE_NAME, round_to_8_decimals

s_decimal_0 = Decimal("0.0")


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
        self._trading_pairs = trading_pairs
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
        # return self.decimal_to_precision(amount, TRUNCATE, self.markets[symbol]['precision']['amount'],
    # self.precisionMode, self.paddingMode)

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

    async def _api_request(self,
                           http_method: str,
                           path_url: str = "",
                           data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        """ A wrapper for submitting API requests to Idex. Returns json data from the endpoints """
        """
        rest_url = get_idex_rest_url()
        url = f"{rest_url}{path_url}"
        data_str = "" if data is None else json.dumps(data)
        async with aiohttp.ClientSession() as session:
            if http_method == "GET":
                auth_dict = self._idex_auth.generate_auth_dict_for_get(url)
                async with session.get(auth_dict["url"], headers=auth_dict["headers"]) as response:
                    if response.status != 200:
                        raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {data}")
                    data = await response.json()
                    return data
            elif http_method == "POST" or "DELETE":
                auth_dict = self._idex_auth.generate_auth_dict_for_post(
                    url=url, body=data_str, wallet_signature=self._idex_auth.get_wallet_address())
                # TODO Brian: adjust to wallet signature
                async with session.get(auth_dict["url"], headers=auth_dict["headers"]) as response:
                    data = await response.json()
                    return data
        """

# API Calls

    async def get_orders(self) -> List[Dict[str, Any]]:
        """ Requests status of all active orders. Returns json data of all orders associated with wallet address """

        rest_url = get_idex_rest_url()
        url = f"{rest_url}/v1/orders/"
        params = {
            "nonce": self._idex_auth.get_nonce_str(),
            "wallet": self._idex_auth.get_wallet_address()
        }
        auth_dict = self._idex_auth.generate_auth_dict(http_method="GET", url=url, params=params)
        async with aiohttp.ClientSession() as session:
            async with session.get(auth_dict["url"], headers=auth_dict["headers"]) as response:
                if response.status != 200:
                    raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {response}")
                data = await response.json()
                return data

    async def get_order(self, exchange_order_id: str) -> Dict[str, Any]:
        """ Requests order information through API with exchange orderId. Returns json data with order details """

        rest_url = get_idex_rest_url()
        url = f"{rest_url}/v1/orders/?orderId={exchange_order_id}"
        params = {
            "nonce": self._idex_auth.get_nonce_str(),
            "wallet": self._idex_auth.get_wallet_address()
        }
        auth_dict = self._idex_auth.generate_auth_dict(http_method="GET", url=url, params=params)
        async with aiohttp.ClientSession() as session:
            async with session.get(auth_dict["url"], headers=auth_dict["headers"]) as response:
                if response.status != 200:
                    raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {response}")
                data = await response.json()
                return data

    async def post_order(self, params) -> Dict[str, Any]:
        pass # TODO Brian: Implement

    async def get_balance(self) -> Dict[Dict[str, Any]]:
        """ Requests current balances of all assets through API. Returns json data with balance details """

        rest_url = get_idex_rest_url()
        url = f"{rest_url}/v1/balances/"
        params = {
            "nonce": self._idex_auth.get_nonce_str(),
            "wallet": self._idex_auth.get_wallet_address(),
            "asset": self._trading_pairs
        }
        auth_dict = self._idex_auth.generate_auth_dict(http_method="GET", url=url, params=params)
        async with aiohttp.ClientSession() as session:
            async with session.get(auth_dict["url"], headers=auth_dict["headers"]) as response:
                if response.status != 200:
                    raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {response}")
                data = await response.json()
                return data

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Decimal):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param order_type: The order type (MARKET, LIMIT, etc..)
        :param price: The order price
        """

        if not order_type.is_limit_type():
            raise Exception(f"Unsupported order type: {order_type}")
        trading_rule = self._trading_rules[trading_pair]  # TODO: Implement _trading_rules_polling_loop()

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        if amount < trading_rule.min_order_size:       # TODO: Implement _trading_rules_polling_loop()
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        api_params = {
                      "market": trading_pair,
                      "type": order_type.name,
                      "side": trade_type.name,
                      "quantity": f"{amount:f}",
                      "price": f"{price:f}",
                      "clientOrderId": order_id
                      }
        self.start_tracking_order(order_id,
                                  None,
                                  trading_pair,
                                  trade_type,
                                  price,
                                  amount,
                                  order_type
                                  )
        try:
            order_result = await self.post_order() #TODO: ID required params for post_order and create post_order()
            exchange_order_id = order_result["orderId"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
            event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_class(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   amount,
                                   price,
                                   order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to Idex for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
        self.trigger_event(MarketEvent.OrderFailure,
                           MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

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
            IdexAuth.base16_to_binary(walletBytes),  # todo: deprecation warning
            IdexAuth.encode("client:" + client_order_id),
        ]
        binary = IdexAuth.binary_concat_array(byteArray)  # todo: deprecation warning
        hash = IdexAuth.hash(binary, 'keccak', 'hex')  # todo: deprecation warning
        self.logger().info(f"Cancel order id: {client_order_id}")
        # todo: deprecation warning
        signature = self._idex_auth.sign_message_string(hash, IdexAuth.binary_to_base16(self._idex_auth.new_wallet_object().key))
        await self._client.trade.cancel_order(
            parameters=RestRequestCancelOrder(
                wallet=self._idex_auth.new_wallet_object().address,
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
        """ Periodically update user balances and order status via REST API. Fallback measure for ws API updates. """

        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
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
            # "trading_rule_initialized": len(self._trading_rules) > 0,
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
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = []
            for tracked_order in tracked_orders:
                order_id = await tracked_order.get_exchange_order_id()
                tasks.append(self.get_order(order_id))
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            update_results = await safe_gather(*tasks, return_exceptions=True)
            for update_result in update_results:
                if isinstance(update_result, Exception):
                    raise update_result
                for fill_msg in update_result["fills"]:
                    await self._process_fill_message(fill_msg)
                self._process_order_message(update_result)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        client_order_id = order_msg["clientOrderId"]
        if client_order_id not in self._in_flight_orders:
            return
        tracked_order = self._in_flight_orders[client_order_id]
        # Update order execution status
        tracked_order.last_state = order_msg["status"]
        if tracked_order.is_cancelled:
            self.logger().info(f"Successfully cancelled order {client_order_id}.")
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(
                                   self.current_timestamp,
                                   client_order_id))
            tracked_order.cancelled_event.set()
            self.stop_tracking_order(client_order_id)
        elif tracked_order.is_failure:
            self.logger().info(f"The market order {client_order_id} has failed according to order status API. "
                               f"Reason: {order_msg['message']}") # TODO: confirm message returned from order fail
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp,
                                   client_order_id,
                                   tracked_order.order_type
                               ))
            self.stop_tracking_order(client_order_id)

    async def _process_trade_message(self, fill_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        """
        for order in self._in_flight_orders.values():
            await order.get_exchange_order_id()
        track_order = [o for o in self._in_flight_orders.values() if fill_msg["orderId"] == o.exchange_order_id]
        if not track_order:
            return
        tracked_order = track_order[0]
        updated = tracked_order.update_with_trade_update(fill_msg)
        if not updated:
            return
        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                Decimal(str(fill_msg["price"])),
                Decimal(str(fill_msg["quantity"])),
                TradeFee(0.0, [(fill_msg["feeAsset"], Decimal(str(fill_msg["fee"])))]),
                exchange_trade_id=fill_msg["orderId"]
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
                tracked_order.executed_amount_base >= tracked_order.amount:
            tracked_order.last_state = "filled"
            self.logger().info(f"The {tracked_order.trade_type.name} order "
                               f"{tracked_order.client_order_id} has completed "
                               f"according to order status API.")
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
            self.stop_tracking_order(tracked_order.client_order_id)

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
        byteArray = [  # todo: deprecation warning
            nonce.bytes,
            IdexAuth.base16_to_binary(walletBytes),
        ]
        binary = IdexAuth.binary_concat_array(byteArray)  # todo: deprecation warning
        hash = IdexAuth.hash(binary, 'keccak', 'hex')  # todo: deprecation warning
        # todo: deprecation warning
        signature = self._idex_auth.sign_message_string(hash, IdexAuth.binary_to_base16(self._idex_auth.new_wallet_object().key))
        await self._client.trade.cancel_order(
            parameters=RestRequestCancelAllOrders(
                wallet=self._idex_auth.new_wallet_object().address,
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
        """ Calls REST API to update total and available balances. """

        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self.get_balance()
        for account in account_info:
            asset_name = account["asset"]
            self._account_available_balances[asset_name] = Decimal(str(account["availableForTrade"]))
            self._account_balances[asset_name] = Decimal(str(account["quantity"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

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
