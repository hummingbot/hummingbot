import aiohttp
from aiohttp.test_utils import TestClient
import asyncio
from async_timeout import timeout
import conf
from datetime import datetime
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import pandas as pd
import re
import time
from typing import (
    Any,
    AsyncIterable,
    Coroutine,
    Dict,
    List,
    Optional,
    Tuple
)
import ujson

import hummingbot
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    MarketEvent,
    MarketWithdrawAssetEvent,
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
from hummingbot.market.kraken.kraken_api_order_book_data_source import KrakenAPIOrderBookDataSource
from hummingbot.market.kraken.kraken_auth import KrakenAuth
from hummingbot.market.kraken.kraken_in_flight_order import KrakenInFlightOrder
from hummingbot.market.kraken.kraken_order_book_tracker import KrakenOrderBookTracker
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.market.market_base import (
    MarketBase,
    NaN,
    s_decimal_NaN)

hm_logger = None
s_decimal_0 = Decimal(0)
SYMBOL_SPLITTER = re.compile(r"^(\w+)(USDT|USD|ETH|EUR|XBT|CAD|JPY|DAI|GBP)$")
KRAKEN_ROOT_API = "https://api.kraken.com/0/"


class KrakenAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__()
        self.error_payload = error_payload


cdef class KrakenMarketTransactionTracker(TransactionTracker):
    cdef:
        KrakenMarket _owner

    def __init__(self, owner: KrakenMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class KrakenMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value
    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hm_logger
        if hm_logger is None:
            hm_logger = logging.getLogger(__name__)
        return hm_logger

    def __init__(self,
                 kraken_api_key: str,
                 kraken_secret_key: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._symbols = symbols
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._data_source_type = order_book_tracker_data_source_type
        self._ev_loop = asyncio.get_event_loop()
        self._kraken_auth = KrakenAuth(api_key=kraken_api_key, secret_key=kraken_secret_key)
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = KrakenOrderBookTracker(
            data_source_type=order_book_tracker_data_source_type,
            symbols=symbols
        )
        self._order_tracker_task = None
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = KrakenMarketTransactionTracker(self)
        self._trade_fees = {}

    @staticmethod
    def split_symbol(symbol: str) -> Tuple[str, str]:
        try:
            if symbol.find("/"):
                return symbol.split("/")
            m = SYMBOL_SPLITTER.match(symbol)
            return m.group(1), m.group(2)
        except Exception as e:
            raise ValueError(f"Error parsing symbol {symbol}: {str(e)}")

    @staticmethod
    def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
        # Kraken uses uppercase (ETHUSD)
        base_asset, quote_asset = KrakenMarket.split_symbol(exchange_trading_pair)
        return f"{base_asset}-{quote_asset}"

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pairs: str) -> str:
        # Kraken uses uppercase (ETHUSD)
        return hb_trading_pairs.replace("/", "")

    @property
    def name(self) -> str:
        return "kraken"

    @property
    def order_book_tracker(self) -> KrakenOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, KrakenInFlightOrder]:
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
            key: KrakenInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def shared_client(self) -> str:
        return self._shared_client

    @shared_client.setter
    def shared_client(self, client: aiohttp.ClientSession):
        self._shared_client = client

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await KrakenAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        MarketBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()
        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
            self._order_tracker_task = None
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(method="get", path_url="public/Time")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)
        MarketBase.c_tick(self, timestamp)
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
                           is_auth_required: bool = False) -> Dict[str, Any]:

        url = KRAKEN_ROOT_API + path_url
        if params and "pair" in params:
            params["pair"] = self.convert_to_exchange_trading_pair(params["pair"])

        if is_auth_required:
            headers, data = self._kraken_auth.add_auth_to_params(path_url, params)
            content_type = "application/json" if method == "get" else "application/x-www-form-urlencoded"
            async with aiohttp.ClientSession() as session:
                response_data = await session.post(
                    url,
                    data=data,
                    headers=headers)
        else:
            async with aiohttp.ClientSession() as session:
                response_data = await session.get(url)
                data = await response_data.json()

        if response_data.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response_data.status}.")
        try:
            parsed_response = await response_data.json()
        except Exception:
            raise IOError(f"Error parsing data from {url}.")

        data = parsed_response.get("result")
        if data is None:
            print(f"Error received from {url}. Response is {parsed_response}.")
            raise Exception({"error": parsed_response})
        return data

    async def query_url(self, url) -> any:
        async with aiohttp.ClientSession() as client:
            async with client.get(url, timeout=100) as response:
                if response.status != 200:
                    raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
                data = await response.text()
                return data

    async def _update_balances(self):
        cdef:
            str path_url = "private/Balance"
            dict data
            dict new_available_balances = {}
            dict new_balances = {}
            str asset_name
            object balance

        balances = await self._api_request("post", path_url=path_url, is_auth_required=True)
        if len(balances) > 0:
            for currency, balance in balances.items():
                asset_name = currency
                balance = Decimal(balance)
                if balance == s_decimal_0:
                    continue
                if asset_name not in new_available_balances:
                    new_available_balances[asset_name] = s_decimal_0
                if asset_name not in new_balances:
                    new_balances[asset_name] = s_decimal_0

                new_balances[asset_name] = balance
                new_available_balances[asset_name] = balance

            self._account_available_balances.clear()
            self._account_available_balances = new_available_balances
            self._account_balances.clear()
            self._account_balances = new_balances

    async def _update_trade_fees(self, symbols):
        cdef:
            str path_url = "private/TradeVolume"
            dict params = {"pair": symbols[0], 'fee-info': True}
            object response

        try:
            response = await self._api_request("post", path_url=path_url, params=params, is_auth_required=True)
            self._trade_fees["taker"] = list(response["fees"].values())[0]["fee"]
            self._trade_fees["maker"] = list(response["fees_maker"].values())[0]["fee"]
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network("Error fetching Kraken trade fees.", exc_info=True,
                                    app_warning_msg=f"Could not fetch Kraken trading fees. "
                                                    f"Check network connection.")
            raise

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        if order_type is order_type.MARKET:
            return TradeFee(percent=Decimal(self._trade_fees["taker"]))
        else:
            return TradeFee(percent=Decimal(self._trade_fees["maker"]))

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            trading_rules_list = await self._format_trading_rules()
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule

    def _format_asset_pairs(self, assetPairs):
        retval = {}
        keys = list(assetPairs.keys())
        result = []
        for i in range(0, len(keys)):
            id = keys[i]
            assetPair = assetPairs[id]
            base = assetPair["base"]
            quote = assetPair["quote"]
            if len(base) > 3:
                if (base[0] == "X") or (base[0] == "Z"):
                    base = base[1:]
            if len(quote) > 3:
                if (quote[0] == "X") or (quote[0] == "Z"):
                    quote = quote[1:]
            darkpool = id.find(".d") >= 0
            symbol = assetPair["altname"] if darkpool else (base + "/" + quote)
            maker = None
            retval[symbol] = {
                "base": base,
                "quote": quote,
                "amount_precision": assetPair["lot_decimals"],
                "price_precision": assetPair["pair_decimals"],
            }
        return retval

    async def _format_trading_rules(self) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        html = await self.query_url("https://support.kraken.com/hc/en-us/articles/205893708-What-is-the-minimum-order-size-")
        parts = html.split('<td class="wysiwyg-text-align-right">')
        numParts = len(parts)
        minimum_order_size = {}
        # skip the part before the header and the header itself
        for i in range(2, len(parts)):
            part = parts[i]
            chunks = part.split("</td>")
            amountAndCode = chunks[0]
            if amountAndCode != "To Be Announced":
                pieces = amountAndCode.split(" ")
                numPieces = len(pieces)
                if numPieces == 2:
                    amount = Decimal(pieces[0])
                    code = pieces[1]
                    minimum_order_size[code] = amount
        path_url = "public/AssetPairs"
        assetPairs = await self._api_request(method="get",
                                         path_url=path_url)
        assetPairs = self._format_asset_pairs(assetPairs)
        for symbol, info in assetPairs.items():
            try:
                trading_rules.append(
                    TradingRule(symbol=symbol,
                                min_order_size=Decimal(minimum_order_size.get(info["base"])),
                                min_price_increment=Decimal(f"1e-{info['price_precision']}"),
                                min_base_amount_increment=Decimal(f"1e-{info['amount_precision']}"),
                                min_quote_amount_increment=Decimal(f"1e-{info['amount_precision']}"),
                            ))
            except Exception:
                self.logger().error(f"Error parsing the symbol rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_fee_paid(self, fee: Decimal, executed_amount_quote: Decimal):
        fee_paid = executed_amount_quote * (fee.percent / 100)
        return fee_paid

    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        path_url = "private/QueryOrders"
        params = {"trades": True, "txid": exchange_order_id}
        return await self._api_request("post", path_url=path_url, params=params, is_auth_required=True)

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
                except KrakenAPIError as e:
                    err_code = e.error_payload.get("error").get("error")
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                    self.logger().info(f"The limit order {tracked_order.client_order_id} "
                                       f"has failed according to order status API. - {err_code}")
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
                order_update = order_update[exchange_order_id]
                order_state = order_update["status"]
                # possible order status are "closed", "canceled", "expired", "pending", "open"

                if order_state not in ["closed", "canceled", "pending", "open"]:
                    self.logger().debug(f"Unrecognized order update response - {order_update}")

                # Calculate the newly executed amount for this update.
                tracked_order.last_state = order_state
                new_confirmed_amount = Decimal(order_update["vol_exec"])
                execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

                if execute_amount_diff > s_decimal_0:
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote = Decimal(order_update["price"]) * new_confirmed_amount
                    execute_price = Decimal(order_update["price"])
                    fee = self.c_get_fee(
                            tracked_order.base_asset,
                            tracked_order.quote_asset,
                            tracked_order.order_type,
                            tracked_order.trade_type,
                            execute_price,
                            execute_amount_diff,
                        )
                    fee_paid = await self.get_fee_paid(fee, tracked_order.executed_amount_quote)
                    tracked_order.fee_paid = Decimal(fee_paid)
                    order_filled_event = OrderFilledEvent(
                        self._current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.symbol,
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
                        exchange_trade_id=order_update["trades"][-1]
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
                                      app_warning_msg="Could not fetch account updates from Kraken. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules(),
                    self._update_trade_fees(self._symbols)
                )
                await asyncio.sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Kraken. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "trade_fees_initialized": "maker" in self._trade_fees and "taker" in self._trade_fees
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    async def execute_buy(self,
                          order_id: str,
                          symbol: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            object quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.c_quantize_order_amount(symbol, amount)
        decimal_price = (self.c_quantize_order_price(symbol, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            path_url = "private/AddOrder"
            ordertype = "limit" if order_type is OrderType.LIMIT else "market"
            params = {"pair": symbol, "type": "buy", "ordertype": ordertype, "volume": decimal_amount}
            if order_type is OrderType.LIMIT:
                params.update({"price": decimal_price})
            response = await self._api_request(method="post",
                                               path_url=path_url,
                                               params=params,
                                               is_auth_required=True)
            exchange_order_id = str(response.get("txid")[0])
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                symbol=symbol,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {symbol}.")
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Kraken for "
                f"{decimal_amount} {symbol} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Kraken. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self,
                   str symbol,
                   object amount,
                   object order_type=OrderType.MARKET,
                   object price=s_decimal_0,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = f"buy-{symbol}-{tracking_nonce}"

        safe_ensure_future(self.execute_buy(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           symbol: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.quantize_order_amount(symbol, amount)
        decimal_price = (self.c_quantize_order_price(symbol, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            path_url = "private/AddOrder"
            ordertype = "limit" if order_type is OrderType.LIMIT else "market"
            params = {"pair": symbol, "type": "sell", "ordertype": ordertype, "volume": decimal_amount}
            if order_type is OrderType.LIMIT:
                params.update({"price": decimal_price})
            response = await self._api_request(method="post",
                                               path_url=path_url,
                                               params=params,
                                               is_auth_required=True)
            exchange_order_id = str(response.get("txid")[0])
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                symbol=symbol,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {symbol}.")
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type is OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Kraken for "
                f"{decimal_amount} {symbol} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Kraken. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str symbol,
                    object amount,
                    object order_type=OrderType.MARKET, object price=s_decimal_0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = f"sell-{symbol}-{tracking_nonce}"
        safe_ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
            path_url = "private/CancelOrder"
            exchange_order_id = await tracked_order.get_exchange_order_id()
            params = {"txid": exchange_order_id}
            cancel_result = await self._api_request(method="post",
                                               path_url=path_url,
                                               params=params,
                                               is_auth_required=True)

        except KrakenAPIError as e:
            if "error" in cancel_result:
                order_state = cancel_result["error"]
                self.c_stop_tracking_order(tracked_order.exchange_order_id)
                self.logger().info(f"The order {tracked_order.exchange_order_id} has been cancelled according"
                                   f" to order status API. order_state - {order_state}")
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp,
                                                         tracked_order.exchange_order_id))
                return {
                    "exchange_order_id": exchange_order_id
                }
            else:
                self.logger().network(
                    f"Failed to cancel order {order_id}: {str(e)}",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel the order {order_id} on Kraken. "
                                    f"Check API key and network connection."
                )

        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Kraken. "
                                f"Check API key and network connection."
            )
        cancel_result.update({"exchange_order_id": exchange_order_id})
        return cancel_result

    cdef c_cancel(self, str symbol, str order_id):
        safe_ensure_future(self.execute_cancel(symbol, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self.execute_cancel(o.symbol, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.exchange_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, KrakenAPIError):
                        continue
                    if isinstance(cr, dict) and "error" not in cr:
                        exchange_order_id = cr.get("exchange_order_id")
                        order_id_set.remove(exchange_order_id)
                        successful_cancellations.append(CancellationResult(exchange_order_id, True))
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Kraken. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    cdef OrderBook c_get_order_book(self, str symbol):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if symbol not in order_books:
            raise ValueError(f"No order book exists for '{symbol}'.")
        return order_books.get(symbol)

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str exchange_order_id,
                                str symbol,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[client_order_id] = KrakenInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            symbol=symbol,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str symbol, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str symbol, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str symbol, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            object quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)
            object current_price = self.c_get_price(symbol, False)
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
