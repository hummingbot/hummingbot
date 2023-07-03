import asyncio
import json
import logging
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

import hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_utils as utils
import hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.bitmex_perpetual.constants as CONSTANTS
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_api_order_book_data_source import (
    BitmexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_auth import BitmexPerpetualAuth
from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_in_flight_order import (
    BitmexPerpetualInFlightOrder,
)
from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_order_book_tracker import (
    BitmexPerpetualOrderBookTracker,
)
from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_user_stream_tracker import (
    BitmexPerpetualUserStreamTracker,
)
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import (
    AccountEvent,
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    PositionModeChangeEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None


def now():
    return int(time.time()) * 1000


BUY_ORDER_COMPLETED_EVENT = MarketEvent.BuyOrderCompleted
SELL_ORDER_COMPLETED_EVENT = MarketEvent.SellOrderCompleted
ORDER_CANCELLED_EVENT = MarketEvent.OrderCancelled
ORDER_EXPIRED_EVENT = MarketEvent.OrderExpired
ORDER_FILLED_EVENT = MarketEvent.OrderFilled
ORDER_FAILURE_EVENT = MarketEvent.OrderFailure
MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG = MarketEvent.FundingPaymentCompleted
BUY_ORDER_CREATED_EVENT = MarketEvent.BuyOrderCreated
SELL_ORDER_CREATED_EVENT = MarketEvent.SellOrderCreated
API_CALL_TIMEOUT = 10.0

# ==========================================================
UNRECOGNIZED_ORDER_DEBOUCE = 60  # seconds


class LatchingEventResponder(EventListener):
    def __init__(self, callback: any, num_expected: int):
        super().__init__()
        self._callback = callback
        self._completed = asyncio.Event()
        self._num_remaining = num_expected

    def __call__(self, arg: any):
        if self._callback(arg):
            self._reduce()

    def _reduce(self):
        self._num_remaining -= 1
        if self._num_remaining <= 0:
            self._completed.set()

    async def wait_for_completion(self, timeout: float):
        try:
            await asyncio.wait_for(self._completed.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        return self._completed.is_set()

    def cancel_one(self):
        self._reduce()


class BitmexPerpetualDerivativeTransactionTracker(TransactionTracker):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    def did_timeout_tx(self, tx_id: str):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.did_timeout_tx(tx_id)


class BitmexPerpetualDerivative(ExchangeBase, PerpetualTrading):
    MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG = MarketEvent.FundingPaymentCompleted

    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3
    HEARTBEAT_TIME_INTERVAL = 30.0
    UPDATE_ORDERS_INTERVAL = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global bpm_logger
        if bpm_logger is None:
            bpm_logger = logging.getLogger(__name__)
        return bpm_logger

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            bitmex_perpetual_api_key: str = None,
            bitmex_perpetual_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):

        self._bitmex_time_synchronizer = TimeSynchronizer()
        self._auth: BitmexPerpetualAuth = BitmexPerpetualAuth(api_key=bitmex_perpetual_api_key,
                                                              api_secret=bitmex_perpetual_api_secret)

        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._domain = domain
        self._api_factory = web_utils.build_api_factory(
            auth=self._auth)
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None

        ExchangeBase.__init__(self, client_config_map=client_config_map)
        PerpetualTrading.__init__(self, trading_pairs=trading_pairs)

        self._user_stream_tracker = BitmexPerpetualUserStreamTracker(
            auth=self._auth,
            domain=self._domain,
            throttler=self._throttler,
            api_factory=self._api_factory,
            time_synchronizer=self._bitmex_time_synchronizer
        )
        self._order_book_tracker = BitmexPerpetualOrderBookTracker(
            trading_pairs=trading_pairs,
            domain=self._domain,
            throttler=self._throttler,
            api_factory=self._api_factory)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._funding_fee_poll_notifier = asyncio.Event()
        self._order_not_found_records = defaultdict(int)
        self._last_timestamp = 0
        self._trading_rules = {}
        self._in_flight_orders = {}
        self._position_mode = None
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._user_stream_tracker_task = None
        self._last_poll_timestamp = 0
        self._budget_checker = PerpetualBudgetChecker(self)
        self._client_order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)
        self._trading_pair_to_size_type = {}
        self._trading_pair_price_estimate_for_quantize = {}
        self._token_multiplier = {}

    @property
    def name(self) -> str:
        # Note: domain here refers to the entire exchange name. i.e. bitmex_perpetual or bitmex_perpetual_testnet
        return self._domain

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self):
        sd = {
            "symbols_mapping_initialized": BitmexPerpetualAPIOrderBookDataSource.trading_pair_symbol_map_ready(
                domain=self._domain),
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "position_mode": self.position_mode is not None,
            "funding_info_initialized": self._order_book_tracker.is_funding_info_initialized(),
            "user_stream_initialized": self._user_stream_tracker.data_source.last_recv_time > 0,
        }
        return sd

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [order.to_limit_order() for order in self._client_order_tracker.all_orders.values()]

    @property
    def budget_checker(self) -> PerpetualBudgetChecker:
        return self._budget_checker

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        :return active in-flight orders in json format, is used to save in sqlite db.
        """
        return {
            client_order_id: in_flight_order.to_json()
            for client_order_id, in_flight_order in self._client_order_tracker.active_orders.items()
            if not in_flight_order.is_done
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        for order_id, in_flight_repr in saved_states.items():
            if isinstance(in_flight_repr, dict):
                in_flight_json: Dict[str, Any] = in_flight_repr
            else:
                in_flight_json: Dict[str, Any] = json.loads(in_flight_repr)
            order = BitmexPerpetualInFlightOrder.from_json(in_flight_json)
            if not order.is_done:
                self._in_flight_orders[order_id] = order

    def supported_order_types(self) -> List[OrderType]:
        """
        Returns list of OrderType supported by this connector.
        """
        return [OrderType.LIMIT, OrderType.MARKET]

    async def start_network(self):
        """
        This function is required by the NetworkIterator base class and is called automatically.
        It starts tracking order books, polling trading rules, updating statuses, and tracking user data.
        """
        self._order_book_tracker.start()
        await self._update_trading_rules()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            await self._get_position_mode()
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            for trading_pair in self._trading_pairs:
                await self._order_book_tracker.data_source.get_funding_info(trading_pair)
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is required by the NetworkIterator base class and is called automatically.
        It performs the necessary shut down procedure.
        """
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        """
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Ping the network (or call any lightweight public API).
        """
        try:
            await self._api_request(path=CONSTANTS.PING_URL)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def quantize_order_amount(self, trading_pair: str, amount: object, price: object = Decimal(0)):
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        size_type = self._trading_pair_to_size_type[trading_pair]
        # current_price: object = self.get_price(trading_pair, False)
        notional_size: object
        if size_type.is_base:
            quantized_amount = ExchangeBase.quantize_order_amount(self, trading_pair, amount)
            if quantized_amount < trading_rule.min_order_size:
                return Decimal(0)
        else:
            if price == Decimal(0):
                price = self._trading_pair_price_estimate_for_quantize[trading_pair]
            notional_size = price * amount
            if notional_size < trading_rule.min_notional_size:
                return Decimal(0)
            quantized_amount = amount

        return quantized_amount

    def get_order_price_quantum(self, trading_pair: str, price: object):
        """
        Returns a price step, a minimum price increment for a given trading pair.

        Parameters
        ----------
        trading_pair:
            The pair to which the quantization will apply
        price:
            Price to be quantized
        """
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: object):
        """
        Returns an order amount step, a minimum amount increment for a given trading pair.

        Parameters
        ----------
        trading_pair:
            The pair to which the quantization will apply
        order_size:
            Size to be quantized
        """
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def start_tracking_order(
        self,
        order_side: TradeType,
        client_order_id: str,
        order_type: OrderType,
        created_at: float,
        hash: str,
        trading_pair: str,
        price: Decimal,
        amount: Decimal,
        leverage: int,
        position: str,
    ):
        in_flight_order = BitmexPerpetualInFlightOrder(
            client_order_id,
            None,
            trading_pair,
            order_type,
            order_side,
            price,
            amount,
            created_at,
            leverage,
            position
        )
        self._in_flight_orders[in_flight_order.client_order_id] = in_flight_order

    def stop_tracking_order(self, order_id: str):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    def time_now_s(self) -> float:
        return time.time()

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()

        self._last_timestamp = timestamp

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        They are used by the OrderBookCommand to display the order book in the terminal.

        Parameters
        ----------
        trading_pair:
            The pair for which the order book should be obtained
        """
        order_books: dict = self._order_book_tracker.order_books
        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    def get_funding_info(self, trading_pair: str) -> Optional[FundingInfo]:
        """
        Retrieves the Funding Info for the specified trading pair.
        Note: This function should NOT be called when the connector is not yet ready.
        :param: trading_pair: The specified trading pair.
        """
        if trading_pair in self._order_book_tracker.data_source.funding_info:
            return self._order_book_tracker.data_source.funding_info[trading_pair]
        else:
            self.logger().error(f"Funding Info for {trading_pair} not found. Proceeding to fetch using REST API.")
            safe_ensure_future(self._order_book_tracker.data_source.get_funding_info(trading_pair))
            return None

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        self._leverage[trading_pair] = leverage

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _stop_network(self):
        # Reset timestamps and _poll_notifier for status_polling_loop
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._poll_notifier = asyncio.Event()
        self._funding_fee_poll_notifier = asyncio.Event()

        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None

    async def _update_order_status(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            in_flight_orders_copy = self._in_flight_orders.copy()
            for trading_pair in self._trading_pairs:
                exchange_trading_pair = await BitmexPerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                    hb_trading_pair=trading_pair,
                    domain=self._domain,
                    throttler=self._throttler,
                )
                response = await self._api_request(
                    path=CONSTANTS.ORDER_URL,
                    is_auth_required=True,
                    method=RESTMethod.GET,
                    params={"symbol": exchange_trading_pair}
                )
                orders = response
                for order in orders:
                    client_order_id = order.get('clOrdID')
                    if client_order_id is not None:
                        tracked_order = self._in_flight_orders.get(client_order_id)
                        if tracked_order is not None:
                            del in_flight_orders_copy[client_order_id]
                            self._update_inflight_order(tracked_order, order)
            for client_order_id, in_flight_order in in_flight_orders_copy.items():
                if in_flight_order.creation_timestamp < (self.time_now_s() - UNRECOGNIZED_ORDER_DEBOUCE):
                    # We'll just have to assume that this order doesn't exist
                    cancellation_event = OrderCancelledEvent(now(), client_order_id)
                    self.stop_tracking_order(client_order_id)
                    self.trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Bitmex. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Wait for new messages from _user_stream_tracker.user_stream queue and processes them according to their
        message channels. The respective UserStreamDataSource queues these messages.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await self._sleep(5.0)

    async def _process_user_stream_event(self, event_message: Dict[str, Any]):
        topic = event_message.get("table")
        data = event_message.get("data")
        if topic == "position":
            for position in data:
                if 'avgEntryPrice' in position:
                    await self.update_position_from_exchange_data(position)
        elif topic == "wallet":
            for currency_info in data:
                await self.set_balance(currency_info)
        elif topic == "order":
            for order in data:
                client_order_id = order.get("clOrdID")
                if client_order_id is not None:
                    tracked_order = self._in_flight_orders.get(client_order_id)
                    if tracked_order is not None:
                        self._update_inflight_order(tracked_order, order)

    async def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        size_currency_type = self._trading_pair_to_size_type[trading_pair]
        if size_currency_type.is_base:
            return await ExchangeBase.get_order_price(self, trading_pair, is_buy, amount)
        else:
            order_book: OrderBook = self.get_order_book(trading_pair)
            result = order_book.get_price_for_volume(is_buy, float(amount))
            return Decimal(str(result.result_price))

    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        size_currency_type = self._trading_pair_to_size_type[trading_pair]
        if size_currency_type.is_base:
            return await ExchangeBase.get_quote_price(self, trading_pair, is_buy, amount)
        else:
            order_book: OrderBook = self.get_order_book(trading_pair)
            result = order_book.get_vwap_for_volume(is_buy, float(amount))
            return Decimal(str(result.result_price))

    async def _update_trading_rules(self):
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.
        """
        last_tick = int(self._last_timestamp / 60.0)
        current_tick = int(self.current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request(path=CONSTANTS.EXCHANGE_INFO_URL,
                                                    method=RESTMethod.GET,
                                                    params={"filter": json.dumps({"typ": "FFWCSX"})}
                                                    )
            trading_rules_list = await self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule
        await self._update_trading_pair_prices_for_quantize()

    async def _format_trading_rules(self, exchange_info_list: List[Dict[str, Any]]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        return_val: list = []
        for rule in exchange_info_list:
            try:
                if rule["symbol"][-4:] == "_ETH":
                    continue
                trading_pair = combine_to_hb_trading_pair(rule["rootSymbol"], rule["quoteCurrency"])

                if trading_pair in self._trading_pairs:
                    size_currency_type = await utils.get_trading_pair_size_currency(rule['symbol'])
                    self._trading_pair_to_size_type[trading_pair] = size_currency_type
                    max_order_size = Decimal(str(rule.get("maxOrderQty")))
                    if size_currency_type.is_base:
                        min_order_size = Decimal(str(rule.get("lotSize")))
                        multiplier = size_currency_type.multiplier
                        if multiplier is not None:
                            multiplier = Decimal(multiplier)
                            min_order_size /= multiplier
                        tick_size = Decimal(str(rule.get("tickSize")))
                        collateral_token = rule["settlCurrency"].upper()  # not a typo
                        return_val.append(
                            TradingRule(
                                trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=Decimal(tick_size),
                                min_base_amount_increment=Decimal(min_order_size),
                                max_order_size=max_order_size,
                                buy_order_collateral_token=collateral_token,
                                sell_order_collateral_token=collateral_token,
                            )
                        )
                    else:
                        min_notional_size = Decimal(str(rule.get("lotSize")))
                        tick_size = Decimal(str(rule.get("tickSize")))
                        collateral_token = rule["settlCurrency"].upper()  # not a typo
                        return_val.append(
                            TradingRule(
                                trading_pair,
                                min_notional_size=min_notional_size,
                                min_price_increment=Decimal(tick_size),
                                buy_order_collateral_token=collateral_token,
                                sell_order_collateral_token=collateral_token,
                                max_order_size=max_order_size
                            )
                        )

            except Exception as e:
                self.logger().error(
                    f"Error parsing the trading pair rule {rule}. Error: {e}. Skipping...", exc_info=True
                )
        return return_val

    async def _update_trading_pair_prices_for_quantize(self):
        for trading_pair in self._trading_pairs:
            price = await BitmexPerpetualAPIOrderBookDataSource.get_last_traded_price(
                trading_pair,
                self._domain
            )
            self._trading_pair_price_estimate_for_quantize[trading_pair] = Decimal(price)

    async def _trading_rules_polling_loop(self):
        """
        An asynchronous task that periodically updates trading rules.
        """
        while True:
            try:
                await safe_gather(self._update_trading_rules())
                await self._sleep(CONSTANTS.ONE_HOUR)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading rules.",
                    exc_info=True,
                    app_warning_msg="Could not fetch new trading rules from Bitmex Perpetuals. "
                                    "Check network connection.",
                )
                await self._sleep(0.5)

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for
        socket API updates. Calling of both _update_balances() and _update_order_status() functions is
        determined by the _poll_notifier variable.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                # await self._update_time_synchronizer()
                await safe_gather(
                    self._update_balances(),
                    self._update_positions(),
                )
                await self._update_order_status()
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Bitmex Perpetuals. "
                                                      "Check API key and network connection.")
                await self._sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    def _update_inflight_order(self, tracked_order: BitmexPerpetualInFlightOrder, event: Dict[str, Any]):
        size_currency_type = self._trading_pair_to_size_type[tracked_order.trading_pair]
        if size_currency_type.is_base:
            event["amount_remaining"] = Decimal(str(event["leavesQty"])) / size_currency_type.multiplier
        else:
            event["quote_amount_remaining"] = Decimal(str(event["leavesQty"]))
        issuable_events: List[MarketEvent] = tracked_order.update(event)

        # Issue relevent events
        for (market_event, new_amount, new_price, new_fee) in issuable_events:
            base, quote = self.split_trading_pair(tracked_order.trading_pair)
            if market_event == MarketEvent.OrderFilled:
                self.trigger_event(ORDER_FILLED_EVENT,
                                   OrderFilledEvent(self.current_timestamp,
                                                    tracked_order.client_order_id,
                                                    tracked_order.trading_pair,
                                                    tracked_order.trade_type,
                                                    tracked_order.order_type,
                                                    new_price,
                                                    new_amount,
                                                    build_perpetual_trade_fee(
                                                        self._domain,
                                                        True,
                                                        base,
                                                        quote,
                                                        tracked_order.order_type,
                                                        tracked_order.trade_type,
                                                        new_amount,
                                                        new_price
                                                    ),
                                                    tracked_order.client_order_id))
            elif market_event == MarketEvent.OrderCancelled:
                self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}")
                self.stop_tracking_order(tracked_order.client_order_id)
                self.trigger_event(ORDER_CANCELLED_EVENT,
                                   OrderCancelledEvent(self.current_timestamp,
                                                       tracked_order.client_order_id))
            elif market_event == MarketEvent.BuyOrderCompleted:
                self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                   f"according to user stream.")
                self.trigger_event(BUY_ORDER_COMPLETED_EVENT,
                                   BuyOrderCompletedEvent(self.current_timestamp,
                                                          tracked_order.client_order_id,
                                                          base,
                                                          quote,
                                                          tracked_order.executed_amount_base,
                                                          tracked_order.executed_amount_quote,
                                                          tracked_order.order_type,
                                                          tracked_order.exchange_order_id))
            elif market_event == MarketEvent.SellOrderCompleted:
                self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                   f"according to user stream.")
                self.trigger_event(SELL_ORDER_COMPLETED_EVENT,
                                   SellOrderCompletedEvent(self.current_timestamp,
                                                           tracked_order.client_order_id,
                                                           base,
                                                           quote,
                                                           tracked_order.executed_amount_base,
                                                           tracked_order.executed_amount_quote,
                                                           tracked_order.order_type,
                                                           tracked_order.exchange_order_id))
            # Complete the order if relevent
            if tracked_order.is_done:
                self.stop_tracking_order(tracked_order.client_order_id)

    async def _update_positions(self):
        positions = await self._api_request(
            path=CONSTANTS.POSITION_INFORMATION_URL,
            is_auth_required=True,
        )
        for position in positions:
            await self.update_position_from_exchange_data(position)

    async def update_position_from_exchange_data(self, data: Dict[str, Any]):
        trading_pair = await BitmexPerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
            exchange_trading_pair=data.get("symbol"),
            domain=self._domain,
            throttler=self._throttler,
        )
        if trading_pair in self._trading_pairs:
            size_currency_type = self._trading_pair_to_size_type[trading_pair]
            open_order_buy_qty = data.get("execBuyQty")
            if open_order_buy_qty is not None:
                position_side = PositionSide.LONG if data.get("execBuyQty") > 0 else PositionSide.SHORT
            else:
                position_side = PositionSide.SHORT
            pos_key = self.position_key(trading_pair, position_side)
            amount = Decimal(data.get("currentQty"))
            if size_currency_type.is_base:
                if size_currency_type.multiplier is not None:
                    amount /= size_currency_type.multiplier
            if amount != 0:
                unrealized_pnl = Decimal(data.get("unrealisedPnl"))
                entry_price = Decimal(data.get("avgEntryPrice"))
                if not size_currency_type.is_base:
                    amount /= entry_price
                leverage = self._leverage[trading_pair]
                self._account_positions[pos_key] = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage
                )
            else:
                if pos_key in self._account_positions:
                    del self._account_positions[pos_key]

    async def _get_position_mode(self):
        self._position_mode = PositionMode.ONEWAY
        return self._position_mode

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def set_position_mode(self, position_mode: PositionMode):
        for trading_pair in self._trading_pairs:
            self._position_mode = PositionMode.ONEWAY
            self.trigger_event(
                AccountEvent.PositionModeChangeSucceeded,
                PositionModeChangeEvent(
                    self.current_timestamp,
                    trading_pair,
                    position_mode
                ))

    def adjust_quote_based_amounts(
        self,
        trading_pair: str,
        price: Decimal,
        amount: Decimal
    ) -> Tuple[Decimal, Decimal]:
        trading_rule = self._trading_rules[trading_pair]
        lot_size = trading_rule.min_notional_size
        quote_amount = amount * price
        strp_amount = int(quote_amount) % int(lot_size)
        quote_amount = int(quote_amount - strp_amount)
        base_amount = Decimal(quote_amount) / price
        return base_amount, quote_amount

    async def place_order(
        self,
        client_order_id: str,
        trading_pair: str,
        amount: Decimal,
        is_buy: bool,
        order_type: OrderType,
        price: Decimal
    ) -> Dict[str, Any]:

        symbol = await BitmexPerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
            hb_trading_pair=trading_pair,
            domain=self._domain,
            throttler=self._throttler,
        )
        size_currency_type = self._trading_pair_to_size_type[trading_pair]
        if size_currency_type.is_base:
            amount = float(amount) * size_currency_type.multiplier
        else:
            _, amount = self.adjust_quote_based_amounts(trading_pair, price, amount)

        order_side = "Buy" if is_buy else "Sell"
        bitmex_order_type = "Limit" if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else "Market"

        params = {
            "symbol": symbol,
            "side": order_side,
            "orderQty": str(float(amount)),
            "clOrdID": client_order_id,
            "ordType": bitmex_order_type
        }

        if bitmex_order_type == "Limit":
            params['price'] = str(float(price))

        return await self._api_request(
            path=CONSTANTS.ORDER_URL,
            is_auth_required=True,
            params=params,
            method=RESTMethod.POST
        )

    async def execute_order(
        self, order_side, client_order_id, trading_pair, amount, order_type, position_action, price
    ):
        """
        Completes the common tasks from execute_buy and execute_sell.  Quantizes the order's amount and price, and
        validates the order against the trading rules before placing this order.
        """
        if position_action not in [PositionAction.OPEN, PositionAction.CLOSE]:
            raise ValueError("Specify either OPEN_POSITION or CLOSE_POSITION position_action.")
        # Quantize order
        price = self.quantize_order_price(trading_pair, price)
        amount = self.quantize_order_amount(trading_pair, amount, price)

        if amount == Decimal(0):
            raise ValueError(
                "Order amount or notional size is insufficient"
            )
        # Check trading rules
        trading_rule = self._trading_rules[trading_pair]

        if amount > trading_rule.max_order_size:
            raise ValueError(
                f"Order amount({str(amount)}) is greater than the maximum allowable amount({str(trading_rule.max_order_size)})"
            )

        try:
            created_at = self.time_now_s()
            size_currency_type = self._trading_pair_to_size_type[trading_pair]

            if not size_currency_type.is_base:
                base_amount, _ = self.adjust_quote_based_amounts(trading_pair, price, amount)
            else:
                base_amount = amount
            self.start_tracking_order(
                order_side,
                client_order_id,
                order_type,
                created_at,
                None,
                trading_pair,
                price,
                base_amount,
                self._leverage[trading_pair],
                position_action.name,
            )

            try:
                creation_response = await self.place_order(
                    client_order_id,
                    trading_pair,
                    amount,
                    order_side is TradeType.BUY,
                    order_type,
                    price
                )
            except asyncio.TimeoutError:
                return

            # Verify the response from the exchange
            order = creation_response

            status = order["ordStatus"]
            if status not in ["New", "PartiallyFilled", "Filled"]:
                raise Exception(status)

            bitmex_order_id = order["orderID"]

            in_flight_order = self._in_flight_orders.get(client_order_id)
            if in_flight_order is not None:
                # Begin tracking order
                in_flight_order.update_exchange_order_id(bitmex_order_id)
                self.logger().info(
                    f"Created order {client_order_id} for {amount} {trading_pair}."
                )
            else:
                self.logger().info(f"Created order {client_order_id} for {amount} {trading_pair}.")

        except Exception as e:
            self.logger().warning(
                f"Error submitting {order_side.name} {order_type.name} order to bitmex for "
                f"{amount} {trading_pair} at {price}."
            )
            self.logger().info(e, exc_info=True)

            # Stop tracking this order
            self.stop_tracking_order(client_order_id)
            self.trigger_event(ORDER_FAILURE_EVENT, MarketOrderFailureEvent(now(), client_order_id, order_type))

    async def execute_buy(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        position_action: PositionAction,
        price: Optional[Decimal] = Decimal("NaN"),
    ):
        try:
            await self.execute_order(TradeType.BUY, order_id, trading_pair, amount, order_type, position_action, price)
            tracked_order = self.in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.trigger_event(
                    BUY_ORDER_CREATED_EVENT,
                    BuyOrderCreatedEvent(
                        now(),
                        order_type,
                        trading_pair,
                        Decimal(amount),
                        Decimal(price),
                        order_id,
                        tracked_order.creation_timestamp),
                )

        except ValueError as e:
            # never tracked, so no need to stop tracking
            self.trigger_event(ORDER_FAILURE_EVENT, MarketOrderFailureEvent(now(), order_id, order_type))
            self.logger().warning(f"Failed to place {order_id} on bitmex. {str(e)}")

    async def execute_sell(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        position_action: PositionAction,
        price: Optional[Decimal] = Decimal("NaN"),
    ):
        try:
            await self.execute_order(TradeType.SELL, order_id, trading_pair, amount, order_type, position_action, price)
            tracked_order = self.in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.trigger_event(
                    SELL_ORDER_CREATED_EVENT,
                    SellOrderCreatedEvent(
                        now(),
                        order_type,
                        trading_pair,
                        Decimal(amount),
                        Decimal(price),
                        order_id,
                        tracked_order.creation_timestamp,
                    ),
                )

        except ValueError as e:
            # never tracked, so no need to stop tracking
            self.trigger_event(ORDER_FAILURE_EVENT, MarketOrderFailureEvent(now(), order_id, order_type))
            self.logger().warning(f"Failed to place {order_id} on bitmex. {str(e)}")

    def buy(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        client_order_id: str = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=CONSTANTS.BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )
        safe_ensure_future(
            self.execute_buy(client_order_id, trading_pair, amount, order_type, kwargs["position_action"], price)
        )
        return client_order_id

    def sell(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        client_order_id: str = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=CONSTANTS.BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )
        safe_ensure_future(
            self.execute_sell(client_order_id, trading_pair, amount, order_type, kwargs["position_action"], price)
        )
        return client_order_id

    # ----------------------------------------
    # Cancellation

    async def cancel_order(self, client_order_id: str):
        in_flight_order = self._in_flight_orders.get(client_order_id)
        cancellation_event = OrderCancelledEvent(now(), client_order_id)
        exchange_order_id = in_flight_order.exchange_order_id

        if in_flight_order is None:
            self.logger().warning("Cancelled an untracked order {client_order_id}")
            self.trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)
            return False

        try:
            if exchange_order_id is None:
                # Note, we have no way of canceling an order or querying for information about the order
                # without an exchange_order_id
                if in_flight_order.creation_timestamp < (self.time_now_s() - UNRECOGNIZED_ORDER_DEBOUCE):
                    # We'll just have to assume that this order doesn't exist
                    self.stop_tracking_order(in_flight_order.client_order_id)
                    self.trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)
                    return False
            params = {"clOrdID": client_order_id}
            await self._api_request(
                path=CONSTANTS.ORDER_URL,
                is_auth_required=True,
                params=params,
                method=RESTMethod.DELETE
            )
            return True

        except Exception as e:
            if "Not Found" in str(e):
                if in_flight_order.creation_timestamp < (self.time_now_s() - UNRECOGNIZED_ORDER_DEBOUCE):
                    # Order didn't exist on exchange, mark this as canceled
                    self.stop_tracking_order(in_flight_order.client_order_id)
                    self.trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)
                    return False
                else:
                    raise Exception(
                        f"order {client_order_id} does not yet exist on the exchange and could not be cancelled."
                    )
        except Exception as e:
            self.logger().warning(f"Failed to cancel order {client_order_id}")
            self.logger().info(e)
            return False

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        cancellation_queue = self._in_flight_orders.copy()
        if len(cancellation_queue) == 0:
            return []

        order_status = {o.client_order_id: o.is_done for o in cancellation_queue.values()}

        def set_cancellation_status(oce: OrderCancelledEvent):
            if oce.order_id in order_status:
                order_status[oce.order_id] = True
                return True
            return False

        cancel_verifier = LatchingEventResponder(set_cancellation_status, len(cancellation_queue))
        self.add_listener(ORDER_CANCELLED_EVENT, cancel_verifier)

        for order_id, in_flight in cancellation_queue.items():
            try:
                if order_status[order_id]:
                    cancel_verifier.cancel_one()
                elif not await self.cancel_order(order_id):
                    # this order did not exist on the exchange
                    cancel_verifier.cancel_one()
                    order_status[order_id] = True
            except Exception:
                cancel_verifier.cancel_one()
                order_status[order_id] = True

        await cancel_verifier.wait_for_completion(timeout_seconds)
        self.remove_listener(ORDER_CANCELLED_EVENT, cancel_verifier)

        return [CancellationResult(order_id=order_id, success=success) for order_id, success in order_status.items()]

    def cancel(self, trading_pair: str, client_order_id: str):
        return safe_ensure_future(self.cancel_order(client_order_id))

    async def _initialize_token_decimals(self):
        token_info = await self._api_request(
            path=CONSTANTS.TOKEN_INFO_URL
        )
        for asset in token_info:
            zeros = asset['scale']
            currency = asset['asset']
            self._token_multiplier[currency] = Decimal(f"1e{zeros}")
            if currency == "USDT":
                self._token_multiplier['USD'] = Decimal(f"1e{zeros}")

    async def _update_balances(self):
        account_info = await self._api_request(
            path=CONSTANTS.ACCOUNT_INFO_URL,
            is_auth_required=True,
            params={"currency": "all"}
        )
        for currency_info in account_info:
            await self.set_balance(currency_info)

    async def set_balance(self, data: Dict[str, Any]):
        if not (len(self._token_multiplier) > 0):
            await self._initialize_token_decimals()
        asset_name = data['currency'].upper()
        asset_name = "ETH" if asset_name == "GWEI" else asset_name
        total_balance = Decimal(str(data['amount']))
        pending_credit = Decimal(str(data['pendingCredit']))
        pending_debit = Decimal(str(data['pendingDebit']))
        available_balance = total_balance - pending_credit + pending_debit

        multiplier: Decimal = self._token_multiplier[asset_name]
        self._account_balances[asset_name] = Decimal(total_balance) / multiplier
        self._account_available_balances[asset_name] = Decimal(available_balance) / multiplier
        if asset_name == "XBT":
            self._account_balances["USD"] = Decimal('1000') * Decimal(total_balance) / multiplier
            self._account_available_balances["USD"] = Decimal('1000') * Decimal(available_balance) / multiplier

    async def _api_request(self,
                           path: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           method: RESTMethod = RESTMethod.GET,
                           is_auth_required: bool = False,
                           return_err: bool = False,
                           limit_id: Optional[str] = None):

        try:
            return await web_utils.api_request(
                path=path,
                api_factory=self._api_factory,
                throttler=self._throttler,
                domain=self._domain,
                params=params,
                data=data,
                method=method,
                is_auth_required=is_auth_required,
                return_err=return_err,
                limit_id=limit_id)
        except Exception as e:
            self.logger().error(f"Error fetching {path}", exc_info=True)
            self.logger().warning(f"{e}")
            raise e

    async def all_trading_pairs(self) -> List[str]:
        return await BitmexPerpetualAPIOrderBookDataSource.fetch_trading_pairs()

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)
