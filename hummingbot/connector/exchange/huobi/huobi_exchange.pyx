import aiohttp
from aiohttp.test_utils import TestClient
import asyncio
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import time
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
import ujson

from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.huobi.huobi_api_order_book_data_source import HuobiAPIOrderBookDataSource
from hummingbot.connector.exchange.huobi.huobi_api_user_stream_data_source import (
    HUOBI_SUBSCRIBE_TOPICS,
    HUOBI_ACCOUNT_UPDATE_TOPIC,
    HUOBI_ORDER_UPDATE_TOPIC
)
from hummingbot.connector.exchange.huobi.huobi_auth import HuobiAuth
from hummingbot.connector.exchange.huobi.huobi_in_flight_order import HuobiInFlightOrder
from hummingbot.connector.exchange.huobi.huobi_order_book_tracker import HuobiOrderBookTracker
from hummingbot.connector.exchange.huobi.huobi_utils import (
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair)
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.huobi.huobi_user_stream_tracker import HuobiUserStreamTracker
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

hm_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("NaN")
HUOBI_ROOT_API = "https://api.huobi.pro/v1"


class HuobiAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


cdef class HuobiExchangeTransactionTracker(TransactionTracker):
    cdef:
        HuobiExchange _owner

    def __init__(self, owner: HuobiExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class HuobiExchange(ExchangeBase):
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value
    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hm_logger
        if hm_logger is None:
            hm_logger = logging.getLogger(__name__)
        return hm_logger

    def __init__(self,
                 huobi_api_key: str,
                 huobi_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        self._account_id = ""
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._ev_loop = asyncio.get_event_loop()
        self._huobi_auth = HuobiAuth(api_key=huobi_api_key, secret_key=huobi_secret_key)
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = HuobiOrderBookTracker(
            trading_pairs=trading_pairs
        )
        self._poll_notifier = asyncio.Event()
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = HuobiExchangeTransactionTracker(self)

        self._user_stream_event_listener_task = None
        self._user_stream_tracker = HuobiUserStreamTracker(huobi_auth=self._huobi_auth,
                                                           trading_pairs=trading_pairs)

    @property
    def name(self) -> str:
        return "huobi"

    @property
    def order_book_tracker(self) -> HuobiOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, HuobiInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        self._in_flight_orders.update({
            key: HuobiInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def shared_client(self) -> str:
        return self._shared_client

    @shared_client.setter
    def shared_client(self, client: aiohttp.ClientSession):
        self._shared_client = client

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await HuobiAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        ExchangeBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
        if self._trading_required:
            await self._update_account_id()
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    def _stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(method="get", path_url="/common/timestamp")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            double now = time.time()
            double poll_interval = (self.SHORT_POLL_INTERVAL
                                    if now - self._user_stream_tracker.last_recv_time > 60.0
                                    else self.LONG_POLL_INTERVAL)
            int64_t last_tick = <int64_t>(self._last_timestamp / poll_interval)
            int64_t current_tick = <int64_t>(timestamp / poll_interval)
        ExchangeBase.c_tick(self, timestamp)
        self._tx_tracker.c_tick(timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           method,
                           path_url,
                           params: Optional[Dict[str, Any]] = None,
                           data=None,
                           is_auth_required: bool = False) -> Dict[str, Any]:
        content_type = "application/json" if method == "post" else "application/x-www-form-urlencoded"
        headers = {"Content-Type": content_type}
        url = HUOBI_ROOT_API + path_url
        client = await self._http_client()
        if is_auth_required:
            params = self._huobi_auth.add_auth_to_params(method, path_url, params)

        if not data:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                timeout=self.API_CALL_TIMEOUT
            )
        else:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                data=ujson.dumps(data),
                timeout=self.API_CALL_TIMEOUT
            )

        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
        try:
            parsed_response = await response.json()
        except Exception:
            raise IOError(f"Error parsing data from {url}.")

        data = parsed_response.get("data")
        if data is None:
            self.logger().error(f"Error received for {url}. Response is {parsed_response}.")
            raise HuobiAPIError({"error": parsed_response})
        return data

    async def _update_account_id(self) -> str:
        accounts = await self._api_request("get", path_url="/account/accounts", is_auth_required=True)
        try:
            for account in accounts:
                if account["state"] == "working" and account["type"] == "spot":
                    self._account_id = str(account["id"])
        except Exception as e:
            raise ValueError(f"Unable to retrieve account id: {e}")

    async def _update_balances(self):
        cdef:
            dict data
            list balances
            dict new_available_balances = {}
            dict new_balances = {}
            str asset_name
            object balance

        if not self._account_id:
            await self._update_account_id()
        data = await self._api_request("get", path_url=f"/account/accounts/{self._account_id}/balance", is_auth_required=True)
        balances = data.get("list", [])
        if len(balances) > 0:
            for balance_entry in balances:
                asset_name = balance_entry["currency"].upper()
                balance = Decimal(balance_entry["balance"])
                if balance == s_decimal_0:
                    continue
                if asset_name not in new_available_balances:
                    new_available_balances[asset_name] = s_decimal_0
                if asset_name not in new_balances:
                    new_balances[asset_name] = s_decimal_0

                new_balances[asset_name] += balance
                if balance_entry["type"] == "trade":
                    new_available_balances[asset_name] = balance

            self._account_available_balances.clear()
            self._account_available_balances = new_available_balances
            self._account_balances.clear()
            self._account_balances = new_balances

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        # https://www.hbg.com/en-us/about/fee/
        """

        if order_type is OrderType.LIMIT and fee_overrides_config_map["huobi_maker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["huobi_maker_fee"].value / Decimal("100"))
        if order_type is OrderType.MARKET and fee_overrides_config_map["huobi_taker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["huobi_taker_fee"].value / Decimal("100"))
        return TradeFee(percent=Decimal("0.002"))
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("huobi", is_maker)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request("get", path_url="/common/symbols")
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[convert_from_exchange_trading_pair(trading_rule.trading_pair)] = trading_rule

    def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        for info in raw_trading_pair_info:
            try:
                trading_rules.append(
                    TradingRule(trading_pair=info["symbol"],
                                min_order_size=Decimal(info["min-order-amt"]),
                                max_order_size=Decimal(info["max-order-amt"]),
                                min_price_increment=Decimal(f"1e-{info['price-precision']}"),
                                min_base_amount_increment=Decimal(f"1e-{info['amount-precision']}"),
                                min_quote_amount_increment=Decimal(f"1e-{info['value-precision']}"),
                                min_notional_size=Decimal(info["min-order-value"]))
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """
        Example:
        {
            "id": 59378,
            "symbol": "ethusdt",
            "account-id": 100009,
            "amount": "10.1000000000",
            "price": "100.1000000000",
            "created-at": 1494901162595,
            "type": "buy-limit",
            "field-amount": "10.1000000000",
            "field-cash-amount": "1011.0100000000",
            "field-fees": "0.0202000000",
            "finished-at": 1494901400468,
            "user-id": 1000,
            "source": "api",
            "state": "filled",
            "canceled-at": 0,
            "exchange": "huobi",
            "batch": ""
        }
        """
        path_url = f"/order/orders/{exchange_order_id}"
        params = {
            "order_id": exchange_order_id
        }
        return await self._api_request("get", path_url=path_url, params=params, is_auth_required=True)

    async def _update_order_status(self):
        cdef:
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            for tracked_order in tracked_orders:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                try:
                    order_update = await self.get_order_status(exchange_order_id)
                except HuobiAPIError as e:
                    err_code = e.error_payload.get("error").get("err-code")
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                    self.logger().info(f"Fail to retrieve order update for {tracked_order.client_order_id} - {err_code}")
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(
                            self._current_timestamp,
                            tracked_order.client_order_id,
                            tracked_order.order_type
                        )
                    )
                    continue

                if order_update is None:
                    self.logger().network(
                        f"Error fetching status update for the order {tracked_order.client_order_id}: "
                        f"{order_update}.",
                        app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                        f"The order has either been filled or canceled."
                    )
                    continue

                order_state = order_update["state"]
                # possible order states are "submitted", "partial-filled", "filled", "canceled"

                if order_state not in ["submitted", "filled", "canceled"]:
                    self.logger().debug(f"Unrecognized order update response - {order_update}")

                # Calculate the newly executed amount for this update.
                tracked_order.last_state = order_state
                new_confirmed_amount = Decimal(order_update["field-amount"])  # probably typo in API (filled)
                execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

                if execute_amount_diff > s_decimal_0:
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote = Decimal(order_update["field-cash-amount"])
                    tracked_order.fee_paid = Decimal(order_update["field-fees"])
                    execute_price = Decimal(order_update["field-cash-amount"]) / new_confirmed_amount
                    order_filled_event = OrderFilledEvent(
                        self._current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        execute_price,
                        execute_amount_diff,
                        self.c_get_fee(
                            tracked_order.base_asset,
                            tracked_order.quote_asset,
                            tracked_order.order_type,
                            tracked_order.trade_type,
                            execute_price,
                            execute_amount_diff,
                        ),
                        # Unique exchange trade ID not available in client order status
                        # But can use validate an order using exchange order ID:
                        # https://huobiapi.github.io/docs/spot/v1/en/#query-order-by-order-id
                        exchange_trade_id=exchange_order_id
                    )
                    self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                       f"order {tracked_order.client_order_id}.")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

                if tracked_order.is_open:
                    continue

                if tracked_order.is_done:
                    if not tracked_order.is_cancelled:  # Handles "filled" order
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                               f"according to order status API.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
                                                                        tracked_order.client_order_id,
                                                                        tracked_order.base_asset,
                                                                        tracked_order.quote_asset,
                                                                        tracked_order.fee_asset or tracked_order.base_asset,
                                                                        tracked_order.executed_amount_base,
                                                                        tracked_order.executed_amount_quote,
                                                                        tracked_order.fee_paid,
                                                                        tracked_order.order_type))
                        else:
                            self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                               f"according to order status API.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         tracked_order.client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         tracked_order.fee_asset or tracked_order.quote_asset,
                                                                         tracked_order.executed_amount_base,
                                                                         tracked_order.executed_amount_quote,
                                                                         tracked_order.fee_paid,
                                                                         tracked_order.order_type))
                    else:  # Handles "canceled" or "partial-canceled" order
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        self.logger().info(f"The market order {tracked_order.client_order_id} "
                                           f"has been cancelled according to order status API.")
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp,
                                                                 tracked_order.client_order_id))

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Huobi. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Huobi. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _iter_user_stream_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unknown error. Retrying after 1 second. {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_stream_queue():
            try:
                channel = stream_message.get("ch", None)
                if channel not in HUOBI_SUBSCRIBE_TOPICS:
                    continue

                data = stream_message["data"]
                if len(data) == 0 and stream_message["code"] == 200:
                    # This is a subcribtion confirmation.
                    self.logger().info(f"Successfully subscribed to {channel}")
                    continue

                if channel == HUOBI_ACCOUNT_UPDATE_TOPIC:
                    asset_name = data["currency"].upper()
                    balance = data["balance"]
                    available_balance = data["available"]

                    self._account_balances.update({asset_name: Decimal(balance)})
                    self._account_available_balances.update({asset_name: Decimal(available_balance)})
                    continue

                elif channel == HUOBI_ORDER_UPDATE_TOPIC:
                    order_id = data["orderId"]
                    client_order_id = data["clientOrderId"]
                    trading_pair = data["symbol"]
                    order_status = data["orderStatus"]

                    if order_status not in ["submitted", "partial-filled", "filled", "partially-canceled", "canceled", "canceling"]:
                        self.logger().debug(f"Unrecognized order update response - {stream_message}")

                    tracked_order = self._in_flight_orders.get(client_order_id, None)

                    if tracked_order is None:
                        continue

                    execute_amount_diff = s_decimal_0
                    # tradePrice is documented by Huobi but not sent.
                    # However, orderprice isn't applicable to all order_types, so we assume tradePrice will be sent for such orders
                    execute_price = Decimal(data.get("orderPrice", data.get("tradePrice", "0")))
                    remaining_amount = Decimal(data.get("remainAmt", data["orderSize"]))
                    order_type = data["type"]

                    new_confirmed_amount = Decimal(tracked_order.amount - remaining_amount)

                    execute_amount_diff = Decimal(new_confirmed_amount - tracked_order.executed_amount_base)
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote += Decimal(execute_amount_diff * execute_price)

                    if execute_amount_diff > s_decimal_0:
                        self.logger().info(f"Filed {execute_amount_diff} out of {tracked_order.amount} of order "
                                           f"{order_type.upper()}-{client_order_id}")
                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                             OrderFilledEvent(
                                                 self._current_timestamp,
                                                 tracked_order.client_order_id,
                                                 tracked_order.trading_pair,
                                                 tracked_order.trade_type,
                                                 tracked_order.order_type,
                                                 execute_price,
                                                 execute_amount_diff,
                                                 self.c_get_fee(
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     tracked_order.order_type,
                                                     tracked_order.trade_type,
                                                     execute_price,
                                                     execute_amount_diff,
                                                 ),
                                                 exchange_trade_id=order_id
                                             ))

                    if order_status == "filled":
                        tracked_order.last_state = order_status
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(f"The LIMIT_BUY order {tracked_order.client_order_id} has completed "
                                               f"according to order delta websocket API.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(
                                                     self._current_timestamp,
                                                     tracked_order.client_order_id,
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     tracked_order.fee_asset or tracked_order.quote_asset,
                                                     tracked_order.executed_amount_base,
                                                     tracked_order.executed_amount_quote,
                                                     tracked_order.fee_paid,
                                                     tracked_order.order_type
                                                 ))
                        elif tracked_order.trade_type is TradeType.SELL:
                            self.logger().info(f"The LIMIT_SELL order {tracked_order.client_order_id} has completed "
                                               f"according to order delta websocket API.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(
                                                     self._current_timestamp,
                                                     tracked_order.client_order_id,
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     tracked_order.fee_asset or tracked_order.quote_asset,
                                                     tracked_order.executed_amount_base,
                                                     tracked_order.executed_amount_quote,
                                                     tracked_order.fee_paid,
                                                     tracked_order.order_type
                                                 ))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        continue

                    if order_status == "canceled":
                        tracked_order.last_state = order_status
                        self.logger().info(f"The order {tracked_order.client_order_id} has been cancelled "
                                           f"according to order delta websocket API.")
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp,
                                                                 tracked_order.client_order_id))
                        self.c_stop_tracking_order(tracked_order.client_order_id)

                else:
                    # Ignore all other user stream message types
                    continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop. {e}", exc_info=True)
                await asyncio.sleep(5.0)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_id_initialized": self._account_id != "" if self._trading_required else True,
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def place_order(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal) -> str:
        path_url = "/order/orders/place"
        side = "buy" if is_buy else "sell"
        order_type_str = "limit" if order_type is OrderType.LIMIT else "limit-maker"

        params = {
            "account-id": self._account_id,
            "amount": f"{amount:f}",
            "client-order-id": order_id,
            "symbol": convert_to_exchange_trading_pair(trading_pair),
            "type": f"{side}-{order_type_str}",
        }
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            params["price"] = f"{price:f}"
        exchange_order_id = await self._api_request(
            "post",
            path_url=path_url,
            params=params,
            data=params,
            is_auth_required=True
        )
        return str(exchange_order_id)

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            decimal_amount = self.c_quantize_order_amount(trading_pair, amount)
            decimal_price = self.c_quantize_order_price(trading_pair, price)
            if decimal_amount < trading_rule.min_order_size:
                raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")
        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type, decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.")
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Huobi for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Huobi. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self,
                   str trading_pair,
                   object amount,
                   object order_type=OrderType.LIMIT,
                   object price=s_decimal_0,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = f"buy-{trading_pair}-{tracking_nonce}"

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.c_quantize_order_price(trading_pair, price)

        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {trading_pair}.")
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Huobi for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Huobi. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.LIMIT, object price=s_decimal_0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = f"sell-{trading_pair}-{tracking_nonce}"
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
            path_url = f"/order/orders/{tracked_order.exchange_order_id}/submitcancel"
            response = await self._api_request("post", path_url=path_url, is_auth_required=True)

        except HuobiAPIError as e:
            order_state = e.error_payload.get("error").get("order-state")
            if order_state == 7:
                # order-state is canceled
                self.c_stop_tracking_order(tracked_order.client_order_id)
                self.logger().info(f"The order {tracked_order.client_order_id} has been cancelled according"
                                   f" to order status API. order_state - {order_state}")
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp,
                                                         tracked_order.client_order_id))
            else:
                self.logger().network(
                    f"Failed to cancel order {order_id}: {str(e)}",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel the order {order_id} on Huobi. "
                                    f"Check API key and network connection."
                )

        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Huobi. "
                                f"Check API key and network connection."
            )

    cdef c_cancel(self, str trading_pair, str order_id):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        open_orders = [o for o in self._in_flight_orders.values() if o.is_open]
        if len(open_orders) == 0:
            return []
        cancel_order_ids = [o.exchange_order_id for o in open_orders]
        self.logger().debug(f"cancel_order_ids {cancel_order_ids} {open_orders}")
        path_url = "/order/orders/batchcancel"
        params = {"order-ids": ujson.dumps(cancel_order_ids)}
        data = {"order-ids": cancel_order_ids}
        cancellation_results = []
        try:
            cancel_all_results = await self._api_request(
                "post",
                path_url=path_url,
                params=params,
                data=data,
                is_auth_required=True
            )

            for oid in cancel_all_results.get("success", []):
                cancellation_results.append(CancellationResult(oid, True))
            for cancel_error in cancel_all_results.get("failed", []):
                oid = cancel_error["order-id"]
                cancellation_results.append(CancellationResult(oid, False))
        except Exception as e:
            self.logger().network(
                f"Failed to cancel all orders: {cancel_order_ids}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel all orders on Huobi. Check API key and network connection."
            )
        return cancellation_results

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books.get(trading_pair)

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[client_order_id] = HuobiInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)
            object current_price = self.c_get_price(trading_pair, False)
            object notional_size

        # Check against min_order_size. If not passing check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing check, return maximum.
        if quantized_amount > trading_rule.max_order_size:
            return trading_rule.max_order_size

        if price == s_decimal_0:
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount
        # Add 1% as a safety factor in case the prices changed while making the order.
        if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
            return s_decimal_0

        return quantized_amount

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
