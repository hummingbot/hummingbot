import aiohttp
import asyncio
from async_timeout import timeout
from decimal import Decimal
import json
import logging
import math
import pandas as pd
import sys
import copy
from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncIterable,
)
from libc.stdint cimport int64_t

from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    TradeType,
    TradeFee,
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.liquid.constants import Constants
from hummingbot.connector.exchange.liquid.liquid_auth import LiquidAuth
from hummingbot.connector.exchange.liquid.liquid_order_book_tracker import LiquidOrderBookTracker
from hummingbot.connector.exchange.liquid.liquid_user_stream_tracker import LiquidUserStreamTracker
from hummingbot.connector.exchange.liquid.liquid_api_order_book_data_source import LiquidAPIOrderBookDataSource
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.event.events import OrderType
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.connector.exchange.liquid.liquid_in_flight_order import LiquidInFlightOrder
from hummingbot.connector.exchange.liquid.liquid_in_flight_order cimport LiquidInFlightOrder
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_nan = Decimal("nan")

cdef class LiquidExchangeTransactionTracker(TransactionTracker):
    cdef:
        LiquidExchange _owner

    def __init__(self, owner: LiquidExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

    def __repr__(self) -> str:
        return f"tx_hash='{self.tx_hash}', has_tx_receipt={self.has_tx_receipt})"


cdef class LiquidExchange(ExchangeBase):
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 liquid_api_key: str,
                 liquid_secret_key: str,
                 poll_interval: float = 5.0,    # interval which the class periodically pulls status from the rest API
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()

        self._trading_required = trading_required
        self._liquid_auth = LiquidAuth(liquid_api_key, liquid_secret_key)
        self._order_book_tracker = LiquidOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = LiquidUserStreamTracker(liquid_auth=self._liquid_auth, trading_pairs=trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._tx_tracker = LiquidExchangeTransactionTracker(self)
        self._trading_rules = {}
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._product_dict = {}
        self._trading_rules_polling_task = None
        self._shared_client = None

        self._real_time_balance_update = False

    @property
    def name(self) -> str:
        """
        *required
        :return: A lowercase name / id for the market. Must stay consistent with market name in global settings.
        """
        return "liquid"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        """
        *required
        Get mapping of all the order books that are being tracked.
        :return: Dict[trading_pair : OrderBook]
        """
        return self._order_book_tracker.order_books

    @property
    def liquid_auth(self) -> LiquidAuth:
        """
        :return: LiquidAuth class (This is unique to liquid market).
        """
        return self._liquid_auth

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        *required
        :return: a dictionary of relevant status checks.
        This is used by `ready` method below to determine if a market is ready for trading.
        """
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True
        }

    @property
    def ready(self) -> bool:
        """
        *required
        :return: a boolean value that indicates if the market is ready for trading
        """
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        """
        *required
        :return: list of active limit orders
        """
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        *required
        :return: Dict[client_order_id: InFlightOrder]
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    @property
    def in_flight_orders(self) -> Dict[str, LiquidInFlightOrder]:
        return self._in_flight_orders

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        *required
        Updates inflight order statuses from API results
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        self._in_flight_orders.update({
            key: LiquidInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        *required
        Used by the discovery strategy to read order books of all actively trading markets,
        and find opportunities to profit
        """
        return await LiquidAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        """
        *required
        c_start function used by top level Clock to orchestrate components of the bot
        """
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    async def start_network(self):
        """
        *required
        Async function used by NetworkBase class to handle when a single market goes online
        """
        self._stop_network()
        self._order_book_tracker.start()
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    def _stop_network(self):
        """
        Synchronous function that handles when a single market goes offline
        """
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        """
        *required
        Async wrapper for `self._stop_network`. Used by NetworkBase class to handle when a single market goes offline.
        """
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        """
        *required
        Async function used by NetworkBase class to check if the market is online / offline.

        STEP 1: This is the entry point of the Market class initialization workflow, a connection
        to exchange will get changed to CONNECTED only if the api response shows positive
        """
        try:
            await self._api_request("get", path_url=Constants.PRODUCTS_URI)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        """
        *required
        Used by top level Clock to orchestrate components of the bot.
        This function is called frequently with every clock tick
        """
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)

        ExchangeBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns: Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           http_method: str,
                           path_url: str = None,
                           url: str = None,
                           data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        A wrapper for submitting API requests to Liquid
        :returns: json data from the endpoints
        """
        assert path_url is not None or url is not None

        url = f"{Constants.BASE_URL}{path_url}" if url is None else url
        data_str = "" if data is None else json.dumps(data)
        headers = self.liquid_auth.get_headers(path_url)

        client = await self._http_client()
        async with client.request(http_method,
                                  url=url, timeout=Constants.API_CALL_TIMEOUT, data=data_str, headers=headers) as response:
            data = await response.json()
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {data}")
            return data

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        """
        *required
        function to calculate fees for a particular order
        :returns: TradeFee class that includes fee percentage and flat fees
        """
        """
        cdef:
            object maker_fee = Decimal("0.0010")
            object taker_fee = Decimal("0.0010")

        if order_type is OrderType.LIMIT and fee_overrides_config_map["liquid_maker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["liquid_maker_fee"].value / Decimal("100"))
        if order_type is OrderType.MARKET and fee_overrides_config_map["liquid_taker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["liquid_taker_fee"].value / Decimal("100"))
        return TradeFee(percent=maker_fee if order_type is OrderType.LIMIT else taker_fee)
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("liquid", is_maker)

    async def _update_balances(self):
        """
        Pulls the API for updated balances

        Types:
        1. Fiat Accounts
        ex.
        [
            {
                "id": 4695,
                "balance": "10000.1773",
                "reserved_balance": "0.0",
                "currency": "USD",
                "currency_symbol": "$",
                "pusher_channel": "user_3020_account_usd",
                "lowest_offer_interest_rate": "0.00020",
                "highest_offer_interest_rate": "0.00060",
                "currency_type": "fiat",

                "exchange_rate": "1.0"
            }
        ]

        2. Crypto Accounts
        ex.
        [
            {
                "id": 4668,
                "balance": "4.99",
                "reserved_balance": "0.0",
                "currency": "BTC",
                "currency_symbol": "฿",
                "pusher_channel": "user_3020_account_btc",
                "minimum_withdraw": 0.02,
                "lowest_offer_interest_rate": "0.00049",
                "highest_offer_interest_rate": "0.05000",
                "currency_type": "crypto",

                "address": "1F25zWAQ1BAAmppNxLV3KtK6aTNhxNg5Hg"
            }
        ]
        """
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        fiat_accounts_path = Constants.FIAT_ACCOUNTS_URI
        crypto_accounts_path = Constants.CRYPTO_ACCOUNTS_URI

        fiat_acct_balances = await self._api_request("get", path_url=fiat_accounts_path) or []
        crypto_acct_balances = await self._api_request("get", path_url=crypto_accounts_path) or []

        for balance_entry in fiat_acct_balances + crypto_acct_balances:
            asset_name = balance_entry["currency"]
            available_balance = Decimal(balance_entry["balance"] - balance_entry['reserved_balance'])
            total_balance = Decimal(balance_entry["balance"])
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self._current_timestamp

    async def _update_trading_rules(self):
        """
        Pulls the API for trading rules (min / max order size, etc)
        """
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) <= 0:
            raw_trading_rules = await self._api_request("get", path_url=Constants.TRADING_RULES_URI)
            products = await self._api_request("get", path_url=Constants.PRODUCTS_URI)
            products = LiquidAPIOrderBookDataSource.reformat_trading_pairs(products)

            trading_rules_list = self._format_trading_rules(raw_trading_rules, products)

            # Update product id and trading pair conversion dict for later use
            for product in products:
                trading_pair = product.get('trading_pair', None)
                if trading_pair:
                    self._product_dict[trading_pair] = product

            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, raw_trading_rules: List[Any], products: List[Any]) -> List[TradingRule]:
        """
        Turns json data from API into TradingRule instances
        :returns: List of TradingRule

        Example product detail:
        [{
            'id': '568',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': None,
            'market_ask': '3.5e-07',
            'market_bid': '3.4e-07',
            'indicator': None,
            'currency': 'BTC',
            'currency_pair_code': 'ILKBTC',
            ...
        }]

        Example trading rule:
        [{
            "currency_type": "crypto",
            "currency": "BTC",
            "symbol": "₿",
            "assets_precision": 8,
            "quoting_precision": 8,
            "minimum_withdrawal": 0.001,
            "withdrawal_fee": 0.0,
            "minimum_fee": null,
            "minimum_order_quantity": 0.001,
            "display_precision": 5,
            "depositable": true,
            "withdrawable": true,
            "discount_fee": 0.5,
            "lendable": true,
            "position_fundable": true,
            "has_memo": false
        }]

        Rules:
        0. Iterate thru products, use 'currency' as the primary key to look up trading rules, in
        the above example, the currency for trading pair 'ILKBTC' is BTC, and then we can find
        its corresponding rules in the second dictionary
        1. When `minimum_order_quantity` is null, fall back to use the smallest permitted number
        asserts_precision supports
        2. As for `price_tick/ min_price_increment`, use the smallest number `quoting_precision`
        supports
        """
        cdef:
            list retval = []

        # Reformat raw trading rule list into a dictionary with currency set as key in first layer
        trading_rules = {}
        for rule in raw_trading_rules:
            trading_rules[rule.get("currency")] = rule

        for product in products:
            try:
                trading_pair = product.get("trading_pair")
                currency = product.get("base_currency")

                # Find the corresponding rule based on currency
                rule = trading_rules.get(currency)

                min_order_size = rule.get("minimum_order_quantity")
                if not min_order_size:
                    min_order_size = math.pow(10, -rule.get(
                        "assets_precision", Constants.DEFAULT_ASSETS_PRECISION))

                min_price_increment = product.get("tick_size")
                if not min_price_increment or min_price_increment == "0.0":
                    min_price_increment = math.pow(10, -rule.get(
                        "quoting_precision", Constants.DEFAULT_QUOTING_PRECISION))

                retval.append(TradingRule(trading_pair,
                                          min_price_increment=Decimal(min_price_increment),
                                          min_order_size=Decimal(min_order_size),
                                          max_order_size=Decimal(sys.maxsize),  # Liquid doesn't specify max order size
                                          supports_market_orders=None))  # Not sure if Liquid has equivalent info
            except Exception:
                self.logger().error(f"Error parsing the trading_pair rule {rule}. Skipping.", exc_info=True)
        return retval

    async def _update_order_status(self):
        """
        Pulls the rest API for for latest order statuses and update local order statuses.

        Example updated dict:
        {
            'id': 1817834299,
            'order_type': 'market',
            'quantity': '10.0',
            'disc_quantity': '0.0',
            'iceberg_total_quantity': '0.0',
            'side': 'buy',
            'filled_quantity': '10.0',
            'price': '0.0004998',
            'created_at': 1575261189,
            'updated_at': 1575261189,
            'status': 'filled',
            'leverage_level': 1,
            'source_exchange': None,
            'product_id': 500,
            'margin_type': None,
            'take_profit': None,
            'stop_loss': None,
            'trading_type': 'spot',
            'product_code': 'CASH',
            'funding_currency': 'ETH',
            'crypto_account_id': None,
            'currency_pair_code': 'CELETH',
            'average_price': '0.0004998',
            'target': 'spot',
            'order_fee': '0.000005',
            'source_action': 'manual',
            'unwound_trade_id': None,
            'trade_id': None,
            'client_order_id': 'buy-CELETH-1575261189133282',
            'settings': None,
            'trailing_stop_type': None,
            'trailing_stop_value': None,
            'executions': [{
                'id': 232722006,
                'quantity': '10.0',
                'price': '0.0004998',
                'taker_side': 'buy',
                'created_at': 1575261189,
                'my_side': 'buy'
            }],
            'stop_triggered_time': None
        }
        """
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_order_update_timestamp <= Constants.UPDATE_ORDERS_INTERVAL:
            return

        tracked_orders = list(self._in_flight_orders.values())
        listed_orders = await self.list_orders()
        order_dict = dict((
            str(listed_order["id"]), listed_order)
            for listed_order in listed_orders.get("models", []))

        for tracked_order in tracked_orders:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            order_update = order_dict.get(str(exchange_order_id))
            client_order_id = tracked_order.client_order_id
            if order_update is None:
                try:
                    order = await self.get_order(client_order_id)
                except IOError as e:
                    if "order not found" in str(e).lower():
                        # The order does not exist. So we should not be tracking it.
                        self.logger().info(
                            f"The tracked order {client_order_id} does not exist on Liquid."
                            f"Order removed from tracking."
                        )
                        self.c_stop_tracking_order(client_order_id)
                        self.c_trigger_event(
                            self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(self._current_timestamp, client_order_id)
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: ",
                        exc_info=True,
                        app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                        f"Check API key and network connection.{e}"
                    )
                continue

            order_status = order_update.get("status")
            # Calculate the newly executed amount for this update.
            new_confirmed_amount = Decimal(order_update["filled_quantity"])
            execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
            execute_price = Decimal(order_update["price"])

            order_type_description = tracked_order.order_type_description
            order_type = tracked_order.order_type
            # Emit event if executed amount is greater than 0.
            if execute_amount_diff > s_decimal_0:
                order_filled_event = OrderFilledEvent(
                    self._current_timestamp,
                    tracked_order.client_order_id,
                    tracked_order.trading_pair,
                    tracked_order.trade_type,
                    order_type,
                    execute_price,
                    execute_amount_diff,
                    self.c_get_fee(
                        tracked_order.base_asset,
                        tracked_order.quote_asset,
                        order_type,
                        tracked_order.trade_type,
                        execute_price,
                        execute_amount_diff,
                    ),
                    exchange_trade_id=exchange_order_id,
                )
                self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                   f"{order_type_description} order {client_order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            # Update the tracked order
            tracked_order.last_state = order_status if order_status in {"filled", "canceled"} else order_update["status"]
            tracked_order.executed_amount_base = new_confirmed_amount
            tracked_order.executed_amount_quote = Decimal(order_update["price"]) * tracked_order.executed_amount_base
            tracked_order.fee_paid = Decimal(order_update["order_fee"])
            if tracked_order.is_done:
                if not tracked_order.is_failure:
                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    (tracked_order.fee_asset
                                                                     or tracked_order.base_asset),
                                                                    tracked_order.executed_amount_base,
                                                                    tracked_order.executed_amount_quote,
                                                                    tracked_order.fee_paid,
                                                                    order_type))
                    else:
                        self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     (tracked_order.fee_asset
                                                                      or tracked_order.quote_asset),
                                                                     tracked_order.executed_amount_base,
                                                                     tracked_order.executed_amount_quote,
                                                                     tracked_order.fee_paid,
                                                                     order_type))
                else:
                    self.logger().info(f"The market order {tracked_order.client_order_id} has failed/been cancelled "
                                       f"according to order status API.")
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                         OrderCancelledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id
                                         ))
                self.c_stop_tracking_order(tracked_order.client_order_id)
        self._last_order_update_timestamp = current_timestamp

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        """
        Iterator for incoming messages from the user stream.
        """
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 1 seconds.", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Update order statuses from incoming messages from the user stream

        Example content:
        {
            'average_price': 0.0,
            'client_order_id': None,
            'created_at': 1575540850,
            'crypto_account_id': None,
            'currency_pair_code': 'ETHUSD',
            'disc_quantity': 0.0,
            'filled_quantity': 0.0,
            'funding_currency': 'USD',
            'iceberg_total_quantity': 0.0,
            'id': 1831228517,
            'leverage_level': 1,
            'margin_interest': 0.0,
            'margin_type': None,
            'margin_used': 0.0,
            'order_fee': 0.0,
            'order_type': 'limit',
            'price': 200.0,
            'product_code': 'CASH',
            'product_id': '27',
            'quantity': 0.01,
            'side': 'sell',
            'source_action': 'manual',
            'source_exchange': 'QUOINE',
            'status': 'cancelled',
            'stop_loss': None,
            'take_profit': None,
            'target': 'spot',
            'trade_id': None,
            'trading_type': 'spot',
            'unwound_trade_id': None,
            'unwound_trade_leverage_level': None,
            'updated_at': 1575540863
        }
        """
        async for event_message in self._iter_user_event_queue():
            try:
                content = json.loads(event_message.get('data', {}))
                event_status = content["status"]

                # Order id retreived from exhcnage, that initially sent by client
                exchange_order_id = content["client_order_id"]
                tracked_order = None

                for order in self._in_flight_orders.values():
                    if order.client_order_id == exchange_order_id:
                        tracked_order = order
                        break

                if tracked_order is None:
                    continue

                order_type_description = tracked_order.order_type_description
                execute_price = Decimal(content["price"])
                execute_amount_diff = Decimal(content["filled_quantity"])

                if execute_amount_diff > s_decimal_0:
                    self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                       f"{order_type_description} order {tracked_order.client_order_id} according to Liquid user stream.")
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
                                             exchange_trade_id=tracked_order.exchange_order_id
                                         ))

                if event_status == "filled":
                    tracked_order.executed_amount_base = Decimal(content["filled_quantity"])
                    tracked_order.executed_amount_quote = Decimal(content["filled_quantity"]) * Decimal(content["price"])
                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to Liquid user stream.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    (tracked_order.fee_asset
                                                                     or tracked_order.base_asset),
                                                                    tracked_order.executed_amount_base,
                                                                    tracked_order.executed_amount_quote,
                                                                    tracked_order.fee_paid,
                                                                    tracked_order.order_type))
                    else:
                        self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                           f"according to Liquid user stream.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     (tracked_order.fee_asset
                                                                      or tracked_order.quote_asset),
                                                                     tracked_order.executed_amount_base,
                                                                     tracked_order.executed_amount_quote,
                                                                     tracked_order.fee_paid,
                                                                     tracked_order.order_type))
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                elif event_status == "cancelled":  # status == "cancelled":
                    tracked_order.last_state = "cancelled"
                    self.logger().info(f"The market order {tracked_order.client_order_id} has failed/been cancelled "
                                       f"according to Liquid user stream.")
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                         OrderCancelledEvent(self._current_timestamp, tracked_order.client_order_id))
                    self.c_stop_tracking_order(tracked_order.client_order_id)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def place_order(self, order_id: str, trading_pair: str, amount: Decimal, is_buy: bool, order_type: OrderType,
                          price: Decimal):
        """
        Async wrapper for placing orders through the rest API.
        :returns: json response from the API
        """
        path_url = Constants.ORDER_CREATION_URI
        product_id = self._product_dict.get(trading_pair).get('id')

        if order_type is OrderType.LIMIT:
            order_type_str = "limit"
        elif order_type is OrderType.LIMIT_MAKER:
            order_type_str = "limit_post_only"

        data = {
            "order": {
                "client_order_id": order_id,
                "price": "{:10.8f}".format(price),
                "quantity": "{:10.8f}".format(amount),
                "product_id": product_id,
                "side": "buy" if is_buy else "sell",
                "order_type": order_type_str,
            }
        }

        order_result = await self._api_request("post", path_url=path_url, data=data)
        return order_result

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):
        """
        Function that takes strategy inputs, auto corrects itself with trading rule,
        and submit an API request to place a buy order

        Example filled order:
        {
            'id': 1817713338,
            'order_type': 'market',
            'quantity': '20.0',
            'disc_quantity': '0.0',
            'iceberg_total_quantity': '0.0',
            'side': 'buy',
            'filled_quantity': '20.0',
            'price': 0.0004998,
            'created_at': 1575258592,
            'updated_at': 1575258592,
            'status': 'filled',
            'leverage_level': 1,
            'source_exchange': 'QUOINE',
            'product_id': 500,
            'margin_type': None,
            'take_profit': None,
            'stop_loss': None,
            'trading_type': 'spot',
            'product_code': 'CASH',
            'funding_currency': 'ETH',
            'crypto_account_id': None,
            'currency_pair_code': 'CELETH',
            'average_price': 0.0,
            'target': 'spot',
            'order_fee': 0.0,
            'source_action': 'manual',
            'unwound_trade_id': None,
            'trade_id': None,
            'client_order_id': 'buy-CELETH-1575258592005015'
        }
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.BUY, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type, decimal_price)
            exchange_order_id = str(order_result["id"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(self._current_timestamp,
                                                      order_type,
                                                      trading_pair,
                                                      decimal_amount,
                                                      decimal_price,
                                                      order_id))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Liquid for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Liquid. "
                                f"Check API key and network connection.{e}"
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_0,
                   dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the buy order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):
        """
        Function that takes strategy inputs, auto corrects itself with trading rule,
        and submit an API request to place a sell order
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.SELL, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price)

            exchange_order_id = str(order_result["id"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(self._current_timestamp,
                                                       order_type,
                                                       trading_pair,
                                                       decimal_amount,
                                                       decimal_price,
                                                       order_id))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Liquid for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Liquid."
                                f"Check API key and network connection.{e}"
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_0,
                    dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the sell order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        """
        Function that makes API request to cancel an active order
        """
        try:
            exchange_order_id = await self._in_flight_orders.get(order_id).get_exchange_order_id()
            path_url = Constants.CANCEL_ORDER_URI.format(exchange_order_id=exchange_order_id)
            res = await self._api_request("put", path_url=path_url)

            order_status = res.get('status')
            cancelled_id = str(res.get('id'))

            if order_status == 'cancelled' and cancelled_id == exchange_order_id:
                self.logger().info(f"Successfully cancelled order {order_id}.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
            elif order_status == "filled" and cancelled_id == exchange_order_id:
                self.logger().info(f"The order {order_id} has already been filled on Liquid. No cancellation needed.")
                await self._update_order_status()  # We do this to correctly process the order fill and stop tracking.
                return order_id
        except IOError as e:
            if "order not found" in str(e).lower():
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on Liquid. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: ",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Liquid. "
                                f"Check API key and network connection.{e}"
            )
        return None

    cdef c_cancel(self, str trading_pair, str order_id):
        """
        *required
        Synchronous wrapper that schedules cancelling an order.
        """
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

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
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg=f"Failed to cancel order on Liquid. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    async def _status_polling_loop(self):
        """
        Background process that periodically pulls for changes from the rest API
        """
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch account updates on Liquid. "
                                    f"Check API key and network connection."
                )

    async def _trading_rules_polling_loop(self):
        """
        Separate background process that periodically pulls for trading rule changes
        (Since trading rules don't get updated often, it is pulled less often.)
        """
        while True:
            try:
                await safe_gather(self._update_trading_rules())
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading rules.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch trading rule updates on Liquid. "
                                    f"Check network connection."
                )
                await asyncio.sleep(0.5)

    async def get_order(self, client_order_id: str) -> Dict[str, Any]:
        """
        Gets status update for a particular order via rest API
        :returns: json response
        """
        order = self._in_flight_orders.get(client_order_id)
        exchange_order_id = await order.get_exchange_order_id()
        path_url = Constants.LIST_ORDER_URI.format(exchange_order_id=exchange_order_id)
        result = await self._api_request("get", path_url=path_url)
        return result

    async def list_orders(self) -> List[Any]:
        """
        Gets a list of the user's active orders via rest API
        :returns: json response
        """
        path_url = Constants.LIST_ORDERS_URI
        result = await self._api_request("get", path_url=path_url)
        return result

    cdef OrderBook c_get_order_book(self, str trading_pair):
        """
        :returns: OrderBook for a specific trading pair
        """
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        """
        Add new order to self._in_flight_orders mapping
        """
        self._in_flight_orders[client_order_id] = LiquidInFlightOrder(
            client_order_id,
            None,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        """
        Delete an order from self._in_flight_orders mapping
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef c_did_timeout_tx(self, str tracking_id):
        """
        Triggers MarketEvent.TransactionFailure when an Ethereum transaction has timed out
        """
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        """
        *required
        Get the minimum increment interval for price
        :return: Min order price increment in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        """
        *required
        Get the minimum increment interval for order size (e.g. 0.01 USD)
        :return: Min order size increment in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        # Liquid is using the min_order_size as max_precision
        # Order size must be a multiple of the min_order_size
        return trading_rule.min_order_size

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        """
        *required
        Check current order amount against trading rule, and correct any rule violations
        :return: Valid order amount in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        global s_decimal_0
        quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)

        # Check against min_order_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing either check, return 0.
        if quantized_amount > trading_rule.max_order_size:
            return s_decimal_0

        return quantized_amount

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_nan, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_nan, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_nan) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
