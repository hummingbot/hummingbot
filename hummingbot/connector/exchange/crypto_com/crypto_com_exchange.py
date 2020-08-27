import logging
from typing import (
    Dict,
    List,
    Optional,
    Any,
)
from decimal import Decimal
import asyncio
from async_timeout import timeout
import json
import aiohttp
import math
import time

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.core.clock import Clock
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.market.trading_rule import TradingRule
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.connector.exchange_base import ExchangeBase
from .crypto_com_order_book_tracker import CryptoComOrderBookTracker
from .crypto_com_user_stream_tracker import CryptoComUserStreamTracker
from .crypto_com_auth import CryptoComAuth
from .crypto_com_in_flight_order import CryptoComInFlightOrder
from . import crypto_com_utils
from . import crypto_com_constants as Constants
s_logger = None
s_decimal_NaN = Decimal("nan")


class CryptoComExchange(ExchangeBase):
    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 fee_estimates: Dict[bool, Decimal],
                 balance_limits: Dict[str, Decimal],
                 crypto_com_api_key: str,
                 crypto_com_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__(fee_estimates, balance_limits)
        self._crypto_com_auth = CryptoComAuth(crypto_com_api_key, crypto_com_api_secret)
        self._trading_required = trading_required
        self._order_book_tracker = CryptoComOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = CryptoComUserStreamTracker(self._crypto_com_auth, trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, BinanceInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        # self._tx_tracker = BinanceMarketTransactionTracker(self)
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0

    @property
    def name(self) -> str:
        return "crypto_com"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, CryptoComInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: CryptoComInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def start(self, clock: Clock, timestamp: float):
        # self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.start(self, clock, timestamp)

    def stop(self, clock: Clock):
        ExchangeBase.stop(self, clock)
        # self._async_scheduler.stop()

    async def start_network(self):
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            await self._update_account_id()
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            # since there is no ping endpoint, the lowest rate call is to get BTC-USDT ticker
            await self._api_request("get", "public/get-ticker?instrument_name=BTC_USDT")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns: Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Kucoin. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        instruments_info = await self._api_request("get", path_url="public/get-instruments")
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(instruments_info)

    def _format_trading_rules(self, instruments_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Example:
        {
            "id": 11,
            "method": "public/get-instruments",
            "code": 0,
            "result": {
                "instruments": [
                      {
                        "instrument_name": "ETH_CRO",
                        "quote_currency": "CRO",
                        "base_currency": "ETH",
                        "price_decimals": 2,
                        "quantity_decimals": 2
                      },
                      {
                        "instrument_name": "CRO_BTC",
                        "quote_currency": "BTC",
                        "base_currency": "CRO",
                        "price_decimals": 8,
                        "quantity_decimals": 2
                      }
                    ]
              }
        }
        """
        result = {}
        for rule in instruments_info["result"]["instruments"]:
            try:
                trading_pair = crypto_com_utils.convert_from_exchange_trading_pair(rule["instrument_name"])
                price_decimals = Decimal(str(rule["price_decimals"]))
                quantity_decimals = Decimal(str(rule["quantity_decimals"]))
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                quantity_step = Decimal("1") / Decimal(str(math.pow(10, quantity_decimals)))
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_price_increment=price_step,
                                                   min_base_amount_increment=quantity_step)
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {},
                           is_auth_required: bool = False) -> Dict[str, Any]:
        url = f"{Constants.REST_URL}/{path_url}"
        client = await self._http_client()
        if is_auth_required:
            request_id = crypto_com_utils.RequestId.generate_request_id()
            data = {"params": params}
            params = self._crypto_com_auth.generate_auth_dict(path_url, request_id,
                                                              crypto_com_utils.get_ms_timestamp(), data)
            headers = self._crypto_com_auth.get_headers()
        else:
            headers = {"Content-Type": "application/json"}

        if method == "get":
            response = await client.get(url, headers=headers)
        elif method == "post":
            post_json = json.dumps(params)
            response = await client.post(url, data=post_json, headers=headers)
        else:
            raise NotImplementedError

        try:
            parsed_response = json.loads(await response.text())
        except Exception:
            raise IOError(f"Error parsing data from {url}.")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        return parsed_response

    def get_order_price_quantum(self, trading_pair: str, price: Decimal):
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal):
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        order_id: str = crypto_com_utils.get_new_client_order_id(True, trading_pair)
        safe_ensure_future(self.create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, price))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        order_id: str = crypto_com_utils.get_new_client_order_id(False, trading_pair)
        safe_ensure_future(self.create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price))
        return order_id

    def cancel(self, trading_pair: str, order_id: str):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def create_order(self,
                           trade_type: TradeType,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Decimal):
        if not order_type.is_limit_type():
            raise Exception(f"Unsupported order type: {order_type}")
        trading_rule = self._trading_rules[trading_pair]

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        if amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")
        api_params = {"instrument_name": crypto_com_utils.convert_to_exchange_trading_pair(trading_pair),
                      "side": trade_type.name,
                      "type": "LIMIT",
                      "price": f"{price:f}",
                      "quantity": f"{amount:f}",
                      "client_oid": order_id
                      }
        if order_type is OrderType.LIMIT_MAKER:
            api_params["exec_inst"] = "POST_ONLY"
        self.start_tracking_order(order_id,
                                  "",
                                  trading_pair,
                                  trade_type,
                                  price,
                                  amount,
                                  order_type
                                  )
        try:
            order_result = await self._api_request("post", "private/create-order", api_params, True)
            exchange_order_id = str(order_result["result"]["order_id"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.exchange_order_id = exchange_order_id

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
                f"Error submitting {trade_type.name} {order_type.name} order to Binance for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        self._in_flight_orders[order_id] = CryptoComInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def stop_tracking_order(self, order_id: str):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
            await self._api_request("post", "private/cancel-order", {"order_id": tracked_order.exchange_order_id}, True)
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on CryptoCom. "
                                f"Check API key and network connection."
            )

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_fills_from_trades(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Binance. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._api_request("post", "private/get-account-summary", {}, True)
        for account in account_info["result"]["accounts"]:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["balance"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_order_status(self):
        # This is intended to be a backup measure to close straggler orders, in case CrytoCom's user stream events
        # are not working.
        # The minimum poll interval for order status is 10 seconds.
        last_tick = 0  # self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = 1  # self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = [
                self._api_request("post", "private/get-order-detail", {"order_id": o.exchange_order_id}, True)
                for o in tracked_orders
            ]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            update_results = await safe_gather(*tasks, return_exceptions=True)
            for update_result, tracked_order in zip(update_results, tracked_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id not in self._in_flight_orders:
                    continue
                trade_list = update_result["result"]["trade_list"]
                order_info = update_result["result"]["order_info"]
                # Update order execution status
                tracked_order.last_state = order_info["status"]
                executed_amount_base = Decimal(order_info["cumulative_quantity"])
                executed_amount_quote = Decimal(order_info["cumulative_value"])

                if tracked_order.is_done:
                    if not tracked_order.is_failure and not tracked_order.is_cancelled:
                        self.logger().info(f"The market {tracked_order.trade_type.name} order "
                                           f"{tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        total_fee = sum(Decimal(str(t["fee"])) for t in trade_list)
                        event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                            else MarketEvent.SellOrderCompleted
                        event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                            else SellOrderCompletedEvent
                        self.trigger_event(event_tag,
                                           event_class(self.current_timestamp,
                                                       client_order_id,
                                                       tracked_order.base_asset,
                                                       tracked_order.quote_asset,
                                                       (tracked_order.fee_asset
                                                        or tracked_order.base_asset),
                                                       executed_amount_base,
                                                       executed_amount_quote,
                                                       total_fee,
                                                       tracked_order.order_type))
                    else:
                        # check if its a cancelled order
                        # if its a cancelled order, issue cancel and stop tracking order
                        if tracked_order.is_cancelled:
                            self.logger().info(f"Successfully cancelled order {client_order_id}.")
                            self.trigger_event(MarketEvent.OrderCancelled,
                                               OrderCancelledEvent(
                                                   self.current_timestamp,
                                                   client_order_id))
                        else:
                            self.logger().info(f"The market order {client_order_id} has failed according to "
                                               f"order status API. Reason: {order_info['reason']}")
                            self.trigger_event(MarketEvent.OrderFailure,
                                               MarketOrderFailureEvent(
                                                   self.current_timestamp,
                                                   client_order_id,
                                                   tracked_order.order_type
                                               ))
                    self.stop_tracking_order(client_order_id)
                else:
                    for trade in trade_list:
                        if tracked_order.update_with_trade_update(trade):
                            self.trigger_event(
                                MarketEvent.OrderFilled,
                                OrderFilledEvent(
                                    self.current_timestamp,
                                    tracked_order.client_order_id,
                                    tracked_order.trading_pair,
                                    tracked_order.trade_type,
                                    tracked_order.order_type,
                                    Decimal(trade["traded_price"]),
                                    Decimal(trade["traded_quantity"]),
                                    TradeFee(0.0, [trade["fee_currency"], Decimal(str(trade["fee"]))]),
                                    exchange_trade_id=trade["order_id"]
                                )
                            )

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        *required
        Async function that cancels all active orders.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :returns: List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self.execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                results = await safe_gather(*tasks, return_exceptions=True)
                for client_order_id in results:
                    if type(client_order_id) is str:
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
                    else:
                        self.logger().warning(
                            f"Failed to cancel order with error: "
                            f"{repr(client_order_id)}"
                        )
        except Exception as e:
            self.logger().network(
                f"Unexpected error cancelling orders. Error: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel order. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    def tick(self, timestamp: float):
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self.user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = self._last_timestamp / poll_interval
        current_tick = timestamp / poll_interval
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return TradeFee(percent=self.estimate_fee(is_maker))
