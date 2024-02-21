import asyncio
import time
from decimal import Decimal
from typing import Dict, List, Set, Tuple, TYPE_CHECKING, Union

from hummingbot.client.config.trade_fee_schema_loader import TradeFeeSchemaLoader
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.connector.utils import split_hb_trading_pair, TradeFillOrderDetails
from hummingbot.connector.constants import s_decimal_NaN, s_decimal_0
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.network_iterator import NetworkIterator
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.estimate_fee import estimate_fee

if TYPE_CHECKING:
    from hummingbot.client.config.client_config_map import ClientConfigMap
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


cdef class ConnectorBase(NetworkIterator):
    MARKET_EVENTS = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFilled,
        MarketEvent.OrderExpired,
        MarketEvent.OrderFailure,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.FundingPaymentCompleted,
        MarketEvent.RangePositionLiquidityAdded,
        MarketEvent.RangePositionLiquidityRemoved,
        MarketEvent.RangePositionUpdate,
        MarketEvent.RangePositionUpdateFailure,
        MarketEvent.RangePositionFeeCollected,
    ]

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__()

        self._event_reporter = EventReporter(event_source=self.display_name)
        self._event_logger = EventLogger(event_source=self.display_name)
        for event_tag in self.MARKET_EVENTS:
            self.c_add_listener(event_tag.value, self._event_reporter)
            self.c_add_listener(event_tag.value, self._event_logger)

        self._account_balances = {}  # Dict[asset_name:str, Decimal]
        self._account_available_balances = {}  # Dict[asset_name:str, Decimal]
        # _real_time_balance_update is used to flag whether the connector provides real time balance updates.
        # if not, the available will be calculated based on what happened since snapshot taken.
        self._real_time_balance_update = True
        # If _real_time_balance_update is set to False, Sub classes of this connector class need to set values
        # for _in_flight_orders_snapshot and _in_flight_orders_snapshot_timestamp when the update user balances.
        self._in_flight_orders_snapshot = {}  # Dict[order_id:str, InFlightOrderBase]
        self._in_flight_orders_snapshot_timestamp = 0.0
        self._current_trade_fills = set()
        self._exchange_order_ids = dict()
        self._trade_fee_schema = None
        self._trade_volume_metric_collector = client_config_map.anonymized_metrics_mode.get_collector(
            connector=self,
            rate_provider=RateOracle.get_instance(),
            instance_id=client_config_map.instance_id,
        )
        self._client_config: Union[ClientConfigAdapter, ClientConfigMap] = client_config_map  # for IDE autocomplete

    @property
    def real_time_balance_update(self) -> bool:
        return self._real_time_balance_update

    @real_time_balance_update.setter
    def real_time_balance_update(self, value: bool):
        self._real_time_balance_update = value

    @property
    def in_flight_orders_snapshot(self) -> Dict[str, InFlightOrderBase]:
        return self._in_flight_orders_snapshot

    @in_flight_orders_snapshot.setter
    def in_flight_orders_snapshot(self, value: Dict[str, InFlightOrderBase]):
        self._in_flight_orders_snapshot = value

    @property
    def in_flight_orders_snapshot_timestamp(self) -> float:
        return self._in_flight_orders_snapshot_timestamp

    @in_flight_orders_snapshot_timestamp.setter
    def in_flight_orders_snapshot_timestamp(self, value: float):
        self._in_flight_orders_snapshot_timestamp = value

    def estimate_fee_pct(self, is_maker: bool) -> Decimal:
        """
        Estimate the trading fee for maker or taker type of order
        :param is_maker: Whether to get trading for maker or taker order
        :returns An estimated fee in percentage value
        """
        return estimate_fee(self.name, is_maker).percent

    @staticmethod
    def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
        return split_hb_trading_pair(trading_pair)

    def in_flight_asset_balances(self, in_flight_orders: Dict[str, InFlightOrderBase]) -> Dict[str, Decimal]:
        """
        Calculates total asset balances locked in in_flight_orders including fee (estimated)
        For BUY order, this is the quote asset balance locked in the order
        For SELL order, this is the base asset balance locked in the order
        :param in_flight_orders: a dictionary of in-flight orders
        :return A dictionary of tokens and their balance locked in the orders
        """
        asset_balances = {}
        if in_flight_orders is None:
            return asset_balances
        for order in (o for o in in_flight_orders.values() if not (o.is_done or o.is_failure or o.is_cancelled)):
            outstanding_amount = order.amount - order.executed_amount_base
            if order.trade_type is TradeType.BUY:
                outstanding_value = outstanding_amount * order.price
                if order.quote_asset not in asset_balances:
                    asset_balances[order.quote_asset] = s_decimal_0
                fee = self.estimate_fee_pct(True)
                outstanding_value *= Decimal(1) + fee
                asset_balances[order.quote_asset] += outstanding_value
            else:
                if order.base_asset not in asset_balances:
                    asset_balances[order.base_asset] = s_decimal_0
                asset_balances[order.base_asset] += outstanding_amount
        return asset_balances

    def order_filled_balances(self, starting_timestamp = 0) -> Dict[str, Decimal]:
        """
        Calculates total asset balance changes from filled orders since the timestamp
        For BUY filled order, the quote balance goes down while the base balance goes up, and for SELL order, it's the
        opposite. This does not account for fee.
        :param starting_timestamp: The starting timestamp to include filter order filled events
        :returns A dictionary of tokens and their balance
        """
        order_filled_events = list(filter(lambda e: isinstance(e, OrderFilledEvent), self.event_logs))
        order_filled_events = [o for o in order_filled_events if o.timestamp > starting_timestamp]
        balances = {}
        for event in order_filled_events:
            base, quote = event.trading_pair.split("-")[0], event.trading_pair.split("-")[1]
            if event.trade_type is TradeType.BUY:
                quote_value = Decimal("-1") * event.price * event.amount
                base_value = event.amount
            else:
                quote_value = event.price * event.amount
                base_value = Decimal("-1") * event.amount
            if base not in balances:
                balances[base] = s_decimal_0
            if quote not in balances:
                balances[quote] = s_decimal_0
            balances[base] += base_value
            balances[quote] += quote_value
        return balances

    def get_exchange_limit_config(self, market: str) -> Dict[str, object]:
        """
        Retrieves the Balance Limits for the specified market.
        """
        exchange_limits = self._client_config.balance_asset_limit.get(market, {})
        return exchange_limits if exchange_limits is not None else {}

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various connector's components.
        """
        raise NotImplementedError

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def event_logs(self) -> List[any]:
        return self._event_logger.event_log

    @property
    def ready(self) -> bool:
        """
        Indicates whether the connector is ready to be used.
        """
        raise NotImplementedError

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrderBase]:
        raise NotImplementedError

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {}

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restores the tracking states from a previously saved state.
        :param saved_states: Previously saved tracking states from `tracking_states` property.
        """
        pass

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        """
        pass

    cdef c_tick(self, double timestamp):
        NetworkIterator.c_tick(self, timestamp)
        self.tick(timestamp)
        self._trade_volume_metric_collector.process_tick(timestamp)

    cdef c_start(self, Clock clock, double timestamp):
        self.start(clock=clock, timestamp=timestamp)

    def start(self, Clock clock, double timestamp):
        NetworkIterator.c_start(self, clock, timestamp)
        self._trade_volume_metric_collector.start()

    cdef c_stop(self, Clock clock):
        NetworkIterator.c_stop(self, clock)
        self._trade_volume_metric_collector.stop()

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully canceled.
        """
        raise NotImplementedError

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Buys an amount of base asset (of the given trading pair).
        :param trading_pair: The market (e.g. BTC-USDT) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns An order id
        """
        raise NotImplementedError

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                   object price=s_decimal_NaN, dict kwargs={}):
        return self.buy(trading_pair, amount, order_type, price, **kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Sells an amount of base asset (of the given trading pair).
        :param trading_pair: The market (e.g. BTC-USDT) to sell from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns An order id
        """
        raise NotImplementedError

    def batch_order_create(
        self, orders_to_create: List[Union[LimitOrder, MarketOrder]]
    ) -> List[Union[LimitOrder, MarketOrder]]:
        """
        Issues a batch order creation as a single API request for exchanges that implement this feature. The default
        implementation of this method is to send the requests discretely (one by one).
        :param orders_to_create: A list of LimitOrder or MarketOrder objects representing the orders to create. The
            order IDs can be blanc.
        :returns: A list of LimitOrder or MarketOrder objects representing the created orders, complete with the
            generated order IDs.
        """
        creation_results = []
        for order in orders_to_create:
            order_type = OrderType.LIMIT if isinstance(order, LimitOrder) else OrderType.MARKET
            size = order.quantity if order_type == OrderType.LIMIT else order.amount
            if order.is_buy:
                client_order_id = self.buy(
                    trading_pair=order.trading_pair,
                    amount=size,
                    order_type=order_type,
                    price=order.price if order_type == OrderType.LIMIT else s_decimal_NaN
                )
            else:
                client_order_id = self.sell(
                    trading_pair=order.trading_pair,
                    amount=size,
                    order_type=order_type,
                    price=order.price if order_type == OrderType.LIMIT else s_decimal_NaN,
                )
            if order_type == OrderType.LIMIT:
                creation_results.append(
                    LimitOrder(
                        client_order_id=client_order_id,
                        trading_pair=order.trading_pair,
                        is_buy=order.is_buy,
                        base_currency=order.base_currency,
                        quote_currency=order.quote_currency,
                        price=order.price,
                        quantity=size,
                        filled_quantity=order.filled_quantity,
                        creation_timestamp=order.creation_timestamp,
                        status=order.status,
                    )
                )
            else:
                creation_results.append(
                    MarketOrder(
                        order_id=client_order_id,
                        trading_pair=order.trading_pair,
                        is_buy=order.is_buy,
                        base_asset=order.base_asset,
                        quote_asset=order.quote_asset,
                        amount=size,
                        timestamp=order.timestamp,
                    )
                )
        return creation_results

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                    object price=s_decimal_NaN, dict kwargs={}):
        return self.sell(trading_pair, amount, order_type, price, **kwargs)

    cdef c_cancel(self, str trading_pair, str client_order_id):
        self.cancel(trading_pair, client_order_id)

    def cancel(self, trading_pair: str, client_order_id: str):
        """
        Cancel an order.
        :param trading_pair: The market (e.g. BTC-USDT) of the order.
        :param client_order_id: The internal order id (also called client_order_id)
        """
        raise NotImplementedError

    def batch_order_cancel(self, orders_to_cancel: List[LimitOrder]):
        """
        Issues a batch order cancelation as a single API request for exchanges that implement this feature. The default
        implementation of this method is to send the requests discretely (one by one).
        :param orders_to_cancel: A list of the orders to cancel.
        """
        for order in orders_to_cancel:
            self.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)

    cdef c_stop_tracking_order(self, str order_id):
        raise NotImplementedError

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an in-flight order.
        """
        raise NotImplementedError

    def get_all_balances(self) -> Dict[str, Decimal]:
        """
        :return: Dict[asset_name: asst_balance]: Total balances of all assets
        """
        return self._account_balances.copy()

    cdef object c_get_balance(self, str currency):
        return self.get_balance(currency)

    def get_balance(self, currency: str) -> Decimal:
        """
        :param currency: The currency (token) name
        :return: A balance for the given currency (token)
        """
        return self._account_balances.get(currency, s_decimal_0)

    def apply_balance_limit(self, currency: str, available_balance: Decimal, limit: Decimal) -> Decimal:
        """
        Apply budget limit on an available balance, the limit is calculated as followings:
        - Minus balance used in outstanding orders (in flight orders), if the budget is 1 ETH and the bot has already
          used 0.5 ETH to put a maker buy order, the budget is now 0.5
        - Plus balance accredited from filled orders (since the bot started), if the budget is 1 ETH and the bot has
          bought LINK (for 0.5 ETH), the ETH budget is now 0.5. However if later on the bot has sold LINK (for 0.5 ETH)
          the budget is now 1 ETH
        :param currency: The currency (token) name
        :param available_balance: The available balance of the token
        :param limit: The balance limit for the token
        :returns An available balance after the limit has been applied
        """
        in_flight_balance = self.in_flight_asset_balances(self.in_flight_orders).get(currency, s_decimal_0)
        limit -= in_flight_balance
        filled_balance = self.order_filled_balances().get(currency, s_decimal_0)
        limit += filled_balance
        limit = max(limit, s_decimal_0)
        return min(available_balance, limit)

    def apply_balance_update_since_snapshot(self, currency: str, available_balance: Decimal) -> Decimal:
        """
        Applies available balance update as followings
        :param currency: the token symbol
        :param available_balance: the current available_balance, this is also the snap balance taken since last
        _update_balances()
        :returns the real available that accounts for changes in flight orders and filled orders
        """
        snapshot_bal = self.in_flight_asset_balances(self._in_flight_orders_snapshot).get(currency, s_decimal_0)
        in_flight_bal = self.in_flight_asset_balances(self.in_flight_orders).get(currency, s_decimal_0)
        orders_filled_bal = self.order_filled_balances(self._in_flight_orders_snapshot_timestamp).get(currency,
                                                                                                      s_decimal_0)
        actual_available = available_balance + snapshot_bal - in_flight_bal + orders_filled_bal
        return actual_available

    cdef object c_get_available_balance(self, str currency):
        return self.get_available_balance(currency)

    def get_available_balance(self, currency: str) -> Decimal:
        """
        Return available balance for a given currency. The function accounts for balance changes since the last time
        the snapshot was taken if no real time balance update. The function applied limit if configured.
        :param currency: The currency (token) name
        :returns: Balance available for trading for the specified currency
        """
        available_balance = self._account_available_balances.get(currency, s_decimal_0)
        if not self._real_time_balance_update:
            available_balance = self.apply_balance_update_since_snapshot(currency, available_balance)
        balance_limits = self.get_exchange_limit_config(self.name)
        if currency in balance_limits:
            balance_limit = Decimal(str(balance_limits[currency]))
            available_balance = self.apply_balance_limit(currency, available_balance, balance_limit)
        return available_balance

    cdef object c_get_price(self, str trading_pair, bint is_buy):
        return self.get_price(trading_pair, is_buy)

    def get_price(self, trading_pair: str, is_buy: bool, amount: Decimal = s_decimal_NaN) -> Decimal:
        """
        Get price for the market trading pair.
        :param trading_pair: The market trading pair
        :param is_buy: Whether to buy or sell the underlying asset
        :param amount: The amount (to buy or sell) (optional)
        :returns The price
        """
        raise NotImplementedError

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        return self.get_order_price_quantum(trading_pair, price)

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Returns a price step, a minimum price increment for a given trading pair.
        """
        raise NotImplementedError

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        return self.get_order_size_quantum(trading_pair, order_size)

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        """
        Returns an order amount step, a minimum amount increment for a given trading pair.
        """
        raise NotImplementedError

    cdef object c_quantize_order_price(self, str trading_pair, object price):
        if price.is_nan():
            return price
        price_quantum = self.c_get_order_price_quantum(trading_pair, price)
        return (price // price_quantum) * price_quantum

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Applies trading rule to quantize order price.
        """
        return self.c_quantize_order_price(trading_pair, price)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_NaN):
        order_size_quantum = self.c_get_order_size_quantum(trading_pair, amount)
        return (amount // order_size_quantum) * order_size_quantum

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        """
        Applies trading rule to quantize order amount.
        """
        return self.c_quantize_order_amount(trading_pair, amount)

    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """
        Returns a quote price (or exchange rate) for a given amount, like asking how much does it cost to buy 4 apples?
        :param trading_pair: The market trading pair
        :param is_buy: True for buy order, False for sell order
        :param amount: The order amount
        :return The quoted price
        """
        raise NotImplementedError

    async def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """
        Returns a price required for order submission, this price could differ from the quote price (e.g. for
        an exchange with order book).
        :param trading_pair: The market trading pair
        :param is_buy: True for buy order, False for sell order
        :param amount: The order amount
        :return The price to specify in an order.
        """
        raise NotImplementedError

    @property
    def available_balances(self) -> Dict[str, Decimal]:
        return self._account_available_balances

    def add_trade_fills_from_market_recorder(self, current_trade_fills: Set[TradeFillOrderDetails]):
        """
        Gets updates from new records in TradeFill table. This is used in method is_confirmed_new_order_filled_event
        """
        self._current_trade_fills.update(current_trade_fills)

    def add_exchange_order_ids_from_market_recorder(self, current_exchange_order_ids: Dict[str, str]):
        """
        Gets updates from new orders in Order table. This is used in method connector _history_reconciliation
        """
        self._exchange_order_ids.update(current_exchange_order_ids)

    def is_confirmed_new_order_filled_event(self, exchange_trade_id: str, exchange_order_id: str, trading_pair: str):
        """
        Returns True if order to be filled is not already present in TradeFill entries.
        This is intended to avoid duplicated order fills in local DB.
        """
        # Assume (market, exchange_trade_id, trading_pair) are unique. Also order has to be recorded in Order table
        return (not TradeFillOrderDetails(self.display_name, exchange_trade_id, trading_pair) in self._current_trade_fills) and \
               (exchange_order_id in set(self._exchange_order_ids.keys()))

    def trade_fee_schema(self):
        if self._trade_fee_schema is None:
            self._trade_fee_schema = TradeFeeSchemaLoader.configured_schema_for_exchange(exchange_name=self.name)
        return self._trade_fee_schema

    async def all_trading_pairs(self) -> List[str]:
        """
        List of all trading pairs supported by the connector

        :return: List of trading pair symbols in the Hummingbot format
        """
        raise NotImplementedError

    async def _update_balances(self):
        """
        Update local balances requesting the latest information from the exchange.
        """
        raise NotImplementedError

    def _time(self) -> float:
        """
        Method created to enable tests to mock the machine time
        :return: The machine time (time.time())
        """
        return time.time()

    async def _sleep(self, delay: float):
        """
        Method created to enable tests to prevent processes from sleeping
        """
        await asyncio.sleep(delay)
