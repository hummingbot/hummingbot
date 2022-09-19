import asyncio
import logging
import time
import warnings
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional

from async_timeout import timeout

import hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.coinflex_perpetual.constants as CONSTANTS
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_api_order_book_data_source import (
    CoinflexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_auth import CoinflexPerpetualAuth
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_user_stream_data_source import (
    CoinflexPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_utils import (
    decimal_val_or_none,
    get_new_client_order_id,
    is_exchange_information_valid,
)
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.event.events import (
    AccountEvent,
    FundingPaymentCompletedEvent,
    MarketEvent,
    PositionModeChangeEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None
s_float_NaN = float("nan")
s_decimal_0 = Decimal("0")


class CoinflexPerpetualDerivative(ExchangeBase, PerpetualTrading):
    MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG = MarketEvent.FundingPaymentCompleted

    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3
    HEARTBEAT_TIME_INTERVAL = 30.0

    MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global bpm_logger
        if bpm_logger is None:
            bpm_logger = logging.getLogger(__name__)
        return bpm_logger

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            coinflex_perpetual_api_key: str = None,
            coinflex_perpetual_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._auth: CoinflexPerpetualAuth = CoinflexPerpetualAuth(api_key=coinflex_perpetual_api_key,
                                                                  api_secret=coinflex_perpetual_api_secret)
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._domain = domain
        self._api_factory = web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth)
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None

        ExchangeBase.__init__(self, client_config_map)
        PerpetualTrading.__init__(self, self._trading_pairs)

        self._user_stream_tracker = UserStreamTracker(
            data_source=CoinflexPerpetualUserStreamDataSource(
                auth=self._auth,
                domain=self._domain,
                throttler=self._throttler,
                api_factory=self._api_factory))
        self._order_book_tracker = OrderBookTracker(
            data_source=CoinflexPerpetualAPIOrderBookDataSource(
                trading_pairs=self._trading_pairs,
                domain=self._domain,
                throttler=self._throttler,
                api_factory=self._api_factory),
            trading_pairs=self._trading_pairs,
            domain=self._domain)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._next_funding_fee_timestamp = self.get_next_funding_timestamp()
        self._funding_fee_poll_notifier = asyncio.Event()
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._last_timestamp = 0
        self._trading_rules = {}
        self._position_mode = None
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._funding_fee_polling_task = None
        self._user_stream_tracker_task = None
        self._last_poll_timestamp = 0
        self._budget_checker = PerpetualBudgetChecker(self)
        self._client_order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)

    @property
    def name(self) -> str:
        # Note: domain here refers to the entire exchange name. i.e. coinflex_perpetual or coinflex_perpetual_testnet
        return self._domain

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._client_order_tracker.active_orders

    @property
    def status_dict(self):
        sd = {
            "symbols_mapping_initialized": CoinflexPerpetualAPIOrderBookDataSource.trading_pair_symbol_map_ready(
                domain=self._domain),
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "position_mode": self.position_mode,
            "user_stream_initialized": self._user_stream_tracker.data_source.last_recv_time > 0,
            "funding_info_initialized": self._order_book_tracker._data_source.is_funding_info_initialized(),
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

    def _sleep_time(self, delay: int = 0):
        """
        Function created to enable patching during unit tests execution.
        """
        return delay

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states; this is such that the connector can pick up
        on where it left off should it crash unexpectedly.
        """
        self._client_order_tracker.restore_tracking_states(tracking_states=saved_states)

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
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            self._funding_fee_polling_task = safe_ensure_future(self._funding_fee_polling_loop())

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
            response = await self._api_request(
                method=RESTMethod.GET,
                path=CONSTANTS.PING_URL,
            )
            if str(response["success"]).lower() == "true":
                return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def buy(
            self,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType = OrderType.MARKET,
            price: Decimal = s_decimal_NaN,
            **kwargs,
    ) -> str:
        """
        The function that takes the strategy inputs generates a client order ID
        (used by Hummingbot for local order tracking) and places a buy order by
        calling the _create_order() function.

        Parameters
        ----------
        trading_pair:
            The pair that is being traded
        amount:
            The amount to trade
        order_type:
            LIMIT or MARKET
        position_action:
            OPEN or CLOSE
        price:
            Price for a limit order
        """
        order_id: str = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
        )
        safe_ensure_future(
            self._create_order(TradeType.BUY,
                               order_id,
                               trading_pair,
                               amount,
                               order_type,
                               kwargs["position_action"],
                               price)
        )
        return order_id

    def sell(
            self,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType = OrderType.MARKET,
            price: Decimal = s_decimal_NaN,
            **kwargs,
    ) -> str:
        """
        The function that takes the strategy inputs generates a client order ID
        (used by Hummingbot for local order tracking) and places a sell order by
        calling the _create_order() function.

        Parameters
        ----------
        trading_pair:
            The pair that is being traded
        amount:
            The amount to trade
        order_type:
            LIMIT or MARKET
        position_action:
            OPEN or CLOSE
        price:
            Price for a limit order
        """
        order_id: str = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
        )
        safe_ensure_future(
            self._create_order(TradeType.SELL,
                               order_id,
                               trading_pair,
                               amount,
                               order_type,
                               kwargs["position_action"],
                               price)
        )
        return order_id

    async def cancel_all(self, timeout_seconds: float):
        """
        The function that is primarily triggered by the ExitCommand that cancels all InFlightOrder's
        being tracked by the Client Order Tracker. It confirms the successful cancelation
        of the orders.

        Parameters
        ----------
        timeout_seconds:
            How long to wait before checking whether the orders were canceled
        """
        incomplete_orders = [order for order in self._client_order_tracker.active_orders.values() if not order.is_done]
        tasks = [self._execute_cancel(order.trading_pair, order.client_order_id) for order in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue
                    if isinstance(cr, dict) and "clientOrderId" in cr:
                        client_order_id = cr.get("clientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                "Unexpected error canceling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Coinflex Perpetual. Check API key and network connection."
            )
        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    def cancel(self, trading_pair: str, client_order_id: str):
        """
        The function that takes in the trading pair and client order ID
        from the strategy as inputs and proceeds to a cancel the order
        by calling the _execute_cancel() function.

        Parameters
        ----------
        trading_pair:
            The pair that is being traded
        client_order_id:
            Client order ID
        """
        safe_ensure_future(self._execute_cancel(trading_pair, client_order_id))
        return client_order_id

    def quantize_order_amount(self, trading_pair: str, amount: object, price: object = Decimal(0)):
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        # current_price: object = self.get_price(trading_pair, False)
        quantized_amount = ExchangeBase.quantize_order_amount(self, trading_pair, amount)
        if quantized_amount < trading_rule.min_order_size:
            return Decimal(0)

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
        order_id: str,
        trading_pair: str,
        trading_type: TradeType,
        price: Decimal,
        amount: Decimal,
        order_type: OrderType,
        leverage: int,
        position: PositionAction,
        exchange_order_id: Optional[str] = None,
    ):
        """
        Starts tracking an order by calling the appropriate method in the Client Order Tracker

        Parameters
        ----------
        order_id:
            Client order ID
        trading_pair:
            The pair that is being traded
        trading_type:
            BUY or SELL
        price:
            Price for a limit order
        amount:
            The amount to trade
        order_type:
            LIMIT or MARKET
        leverage:
            Leverage of the position
        position:
            OPEN or CLOSE
        exchange_order_id:
            Order ID on the exhange
        """
        self._client_order_tracker.start_tracking_order(
            InFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trading_type,
                price=price,
                amount=amount,
                leverage=leverage,
                position=position,
                creation_timestamp=self.current_timestamp
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by calling the appropriate method in the Client Order Tracker

        Parameters
        ----------
        order_id:
            Client order ID
        """
        self._client_order_tracker.stop_tracking_order(client_order_id=order_id)

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
        if now >= self._next_funding_fee_timestamp + CONSTANTS.FUNDING_SETTLEMENT_DURATION[1]:
            self._funding_fee_poll_notifier.set()

        self._last_timestamp = timestamp

    # MARKET AND ACCOUNT INFO ---
    def get_fee(self, base_currency: str, quote_currency: str, order_type: object, order_side: object,
                amount: object, price: object, is_maker: Optional[bool] = None):
        """
        To get trading fee, this function is simplified by using a fee override configuration.
        Most parameters to this function are ignored except order_type. Use OrderType.LIMIT_MAKER to specify
        you want a trading fee for the maker order.

        Parameters
        ----------
        base_currency:
            Base currency of the order.
        quote_currency:
            Quote currency of the order.
        order_type:
            LIMIT, MARKET or LIMIT_MAKER
        order_side:
            BUY or SELL
        amount:
            Amount in which the order will be placed
        price:
            Price in which the order will be placed
        """
        warnings.warn(
            "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise DeprecationWarning(
            "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead."
        )

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

    def get_next_funding_timestamp(self):
        # On CoinFLEX Futures, Funding occurs every 1 hour
        int_ts = int(time.time())
        one_hour = 1 * 60 * 60
        mod = int_ts % one_hour
        return int(int_ts - mod + one_hour)

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        self._leverage[trading_pair] = leverage
        self.logger().warning("CoinFLEX does not support setting leverage.")

    def set_position_mode(self, position_mode: PositionMode):
        """
        CoinFLEX only supports ONEWAY position mode.
        """
        self._position_mode = PositionMode.ONEWAY

        if self._trading_pairs is not None:
            for trading_pair in self._trading_pairs:
                if position_mode == PositionMode.ONEWAY:
                    self.trigger_event(AccountEvent.PositionModeChangeSucceeded,
                                       PositionModeChangeEvent(
                                           self.current_timestamp,
                                           trading_pair,
                                           position_mode
                                       ))
                    self.logger().info(f"Using {position_mode.name} position mode.")
                else:
                    self.trigger_event(AccountEvent.PositionModeChangeFailed,
                                       PositionModeChangeEvent(
                                           self.current_timestamp,
                                           trading_pair,
                                           position_mode,
                                           "CoinFLEX only supports ONEWAY position mode."
                                       ))
                    self.logger().error(f"Unable to set postion mode to {position_mode.name}.")
                    self.logger().info(f"Using {self._position_mode.name} position mode.")

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    async def trading_pair_symbol_map(self):
        # This method should be removed and instead we should implement _initialize_trading_pair_symbol_map
        return await CoinflexPerpetualAPIOrderBookDataSource.trading_pair_symbol_map(
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler)

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        # This method should be removed and instead we should implement _get_last_traded_price
        return await CoinflexPerpetualAPIOrderBookDataSource.get_last_traded_prices(
            trading_pairs=trading_pairs,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler,
        )

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
        if self._funding_fee_polling_task is not None:
            self._funding_fee_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = self._funding_fee_polling_task = None

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
                    app_warning_msg="Could not fetch user events from CoinFLEX. Check API key and network connection.",
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
        event_type = event_message.get("table")
        if event_type == "position":
            await self._process_position_message(event_message)
        elif event_type == "balance":
            self._process_balance_message(event_message)
        elif event_type == "order":
            order_data = event_message["data"][0]
            client_order_id = order_data.get("clientOrderId")

            tracked_order = self.in_flight_orders.get(client_order_id)
            if not tracked_order:
                return
            try:
                await tracked_order.get_exchange_order_id()
            except asyncio.TimeoutError:
                self.logger().error(f"Failed to get exchange order id for order: {tracked_order.__dict__}")
                raise
            await self._update_order_fills_from_event_or_create(tracked_order, order_data)
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=int(order_data["timestamp"]) * 1e-3,
                new_state=CONSTANTS.ORDER_STATE[order_data["status"]],
                client_order_id=client_order_id,
                exchange_order_id=str(order_data["orderId"]),
            )
            self._client_order_tracker.process_order_update(order_update=order_update)

    async def _update_trading_rules(self):
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.
        """
        exchange_info = await self._api_request(path=CONSTANTS.EXCHANGE_INFO_URL,
                                                method=RESTMethod.GET,
                                                )
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        trading_pair_rules = exchange_info_dict.get("data", [])
        retval = []
        for rule in filter(is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await CoinflexPerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                    exchange_trading_pair=rule.get("marketCode"),
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)

                min_order_size = Decimal(rule.get("qtyIncrement"))
                tick_size = Decimal(rule.get("tickSize"))
                collateral_token = rule["marginCurrency"]

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=tick_size,
                                min_base_amount_increment=min_order_size,
                                buy_order_collateral_token=collateral_token,
                                sell_order_collateral_token=collateral_token))

            except Exception as e:
                self.logger().error(
                    f"Error parsing the trading pair rule {rule}. Error: {e}. Skipping...", exc_info=True
                )
        return retval

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
                    app_warning_msg="Could not fetch new trading rules from Coinflex Perpetuals. "
                                    "Check network connection.",
                )
                await self._sleep(0.5)

    async def _fetch_funding_payment(self, trading_pair: str) -> bool:
        """
        Fetches the funding settlement details of all the active trading pairs and processes the responses.
        Triggers a FundingPaymentCompleted event as required.
        """
        try:
            response = await self._api_request(
                path=CONSTANTS.GET_INCOME_HISTORY_URL,
                params={
                    "marketCode": await CoinflexPerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                        hb_trading_pair=trading_pair,
                        domain=self._domain,
                        throttler=self._throttler,
                        api_factory=self._api_factory
                    ),
                    "startTime": str(int((self._next_funding_fee_timestamp - 3600) * 1e3)),  # We provide a buffer time of 1hr.
                },
                method=RESTMethod.GET,
                is_auth_required=True,
            )

            for funding_payment in response['data']:
                payment = Decimal(funding_payment["payment"])
                action = "paid" if payment < 0 else "received"
                trading_pair = await CoinflexPerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                    exchange_trading_pair=funding_payment["marketCode"],
                    domain=self._domain,
                    throttler=self._throttler,
                    api_factory=self._api_factory
                )
                if payment != s_decimal_0:
                    funding_info = self.get_funding_info(trading_pair)
                    if funding_info is not None:
                        self.logger().info(f"Funding payment of {payment} {action} on {trading_pair} market.")
                        self.trigger_event(self.MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG,
                                           FundingPaymentCompletedEvent(timestamp=funding_payment["timestamp"],
                                                                        market=self.name,
                                                                        funding_rate=funding_info.rate,
                                                                        trading_pair=trading_pair,
                                                                        amount=payment))
            return True
        except Exception as e:
            self.logger().error(f"Unexpected error occurred fetching funding payment for {trading_pair}. Error: {e}",
                                exc_info=True)
            return False

    async def _funding_fee_polling_loop(self):
        """
        Periodically calls _fetch_funding_payment(), responsible for handling all funding payments.
        """
        while True:
            try:
                await self._funding_fee_poll_notifier.wait()

                tasks = []
                for trading_pair in self._trading_pairs:
                    tasks.append(
                        asyncio.create_task(self._fetch_funding_payment(trading_pair=trading_pair))
                    )
                # Only when all tasks is successful would the event notifier be resetted
                responses: List[bool] = await safe_gather(*tasks)
                if all(responses):
                    self._funding_fee_poll_notifier = asyncio.Event()
                    self._next_funding_fee_timestamp = self.get_next_funding_timestamp()

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error whilst retrieving funding payments. "
                                    f"Error: {e} ",
                                    exc_info=True)

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for
        socket API updates. Calling of both _update_balances() and _update_order_status() functions is
        determined by the _poll_notifier variable.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_positions(),
                    self._update_funding_rates(),
                )
                await self._update_order_status()
                self._last_poll_timestamp = self.current_timestamp
                self._poll_notifier = asyncio.Event()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Coinflex Perpetuals. "
                                                      "Check API key and network connection.")
                await self._sleep(0.5)

    async def _update_funding_rates(self):
        try:
            for trading_pair in self._trading_pairs:
                safe_ensure_future(self._order_book_tracker.data_source.get_funding_info(trading_pair))
        except Exception:
            self.logger().network(
                log_msg="Unknown error.",
                exc_info=True,
                app_warning_msg="Could not fetch funding rates. Check API key and network connection.",
            )

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        account_info = await self._api_request(
            method=RESTMethod.GET,
            path=CONSTANTS.ACCOUNT_INFO_URL,
            is_auth_required=True)

        self._process_balance_message(account_info)

    def _process_balance_message(self, account_info):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        balances = account_info["data"]
        for balance_entry in balances:
            asset_name = balance_entry.get("instrumentId", balance_entry.get("marginCurrency"))
            free_balance = Decimal(balance_entry.get("available", balance_entry.get("availableBalance")))
            total_balance = Decimal(balance_entry.get("total", balance_entry.get("totalBalance")))
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _process_position_message(self, position_list):
        for position_data in position_list.get("data", []):
            trading_pair = position_data.get("instrumentId")
            amount = Decimal(position_data.get("quantity"))
            side = PositionSide.SHORT if amount < s_decimal_0 else PositionSide.LONG
            position = self.get_position(trading_pair, side)
            if position is not None:
                if amount == s_decimal_0:
                    pos_key = self.position_key(trading_pair, side)
                    del self._account_positions[pos_key]
                else:
                    position.update_position(position_side=side,
                                             unrealized_pnl=Decimal(position_data["positionPnl"]),
                                             entry_price=Decimal(position_data["entryPrice"]),
                                             amount=Decimal(amount))
            else:
                await self._update_positions()

    async def _update_positions(self):
        positions = await self._api_request(path=CONSTANTS.POSITION_INFORMATION_URL,
                                            is_auth_required=True,
                                            )
        if not positions['data']:
            return
        for position in positions['data']:
            trading_pair = position.get("instrumentId")
            amount = Decimal(position.get("quantity"))
            position_side = PositionSide.SHORT if amount < s_decimal_0 else PositionSide.LONG
            unrealized_pnl = Decimal(position.get("positionPnl"))
            entry_price = Decimal(position.get("entryPrice"))
            leverage = Decimal('1')
            pos_key = self.position_key(trading_pair, position_side)
            if amount != 0:
                self._account_positions[pos_key] = Position(
                    trading_pair=await CoinflexPerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                        exchange_trading_pair=trading_pair,
                        domain=self._domain,
                        throttler=self._throttler,
                        api_factory=self._api_factory,
                    ),
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage
                )
            else:
                if pos_key in self._account_positions:
                    del self._account_positions[pos_key]

    async def _fetch_order_status(self, tracked_order) -> Dict[str, Any]:
        """
        Helper function to fetch order status.
        Returns a dictionary with the response.
        """
        order_params = {
            "marketCode": await CoinflexPerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                hb_trading_pair=tracked_order.trading_pair,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler)
        }

        # If we get the exchange order id, use that, otherwise use client order id.
        try:
            await tracked_order.get_exchange_order_id()
            order_params["orderId"] = tracked_order.exchange_order_id
        except asyncio.TimeoutError:
            order_params["clientOrderId"] = tracked_order.client_order_id

        return await self._api_request(
            method=RESTMethod.GET,
            path=CONSTANTS.ORDER_STATUS_URL,
            params=order_params,
            is_auth_required=True,
            endpoint_api_version="v2.1")

    async def _update_order_status(self):
        """
        Calls the REST API to get order/trade updates for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._client_order_tracker.active_orders) > 0:
            tracked_orders = list(self._client_order_tracker.active_orders.values())
            tasks = [self._fetch_order_status(o) for o in tracked_orders]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_result, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._client_order_tracker.all_orders:
                    continue

                if isinstance(order_result, Exception) or not order_result.get("data"):
                    if not isinstance(order_result, web_utils.CoinflexPerpetualAPIError) or order_result.error_payload.get("errors") in CONSTANTS.ORDER_NOT_FOUND_ERRORS:
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}, marking as not found: {order_result}.",
                            app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                        )
                        self._process_order_not_found(client_order_id, tracked_order)
                    else:
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: {order_result}.",
                            app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                        )
                    return
                order_update = order_result["data"][0]

                # Update order execution status
                order_update_timestamp = order_update.get("timestamp",
                                                          order_update.get("orderOpenedTimestamp",
                                                                           order_result.get("timestamp")))

                new_order_update: OrderUpdate = OrderUpdate(
                    trading_pair=await CoinflexPerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                        exchange_trading_pair=order_update["marketCode"],
                        domain=self._domain,
                        throttler=self._throttler,
                        api_factory=self._api_factory,
                    ),
                    update_timestamp=int(order_update_timestamp) * 1e-3,
                    new_state=CONSTANTS.ORDER_STATE[order_update["status"]],
                    client_order_id=order_update["clientOrderId"],
                    exchange_order_id=str(order_update["orderId"]),
                )

                self._client_order_tracker.process_order_update(new_order_update)

                # Fill missing trades from order status.
                if len(order_update.get("matchIds", [])):
                    await self._update_order_fills_from_trades(tracked_order, order_update)

    async def _create_order_update_matched(self, trading_pair, client_order_id, new_state, order_result):
        # Process immediately matched orders
        if new_state != OrderState.OPEN:
            order_update: OrderUpdate = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=int(order_result["timestamp"]) * 1e-3,
                new_state=new_state,
                client_order_id=client_order_id,
                exchange_order_id=str(order_result["orderId"]),
            )
            self._client_order_tracker.process_order_update(order_update)
            await self._update_order_fills_from_event_or_create(None, order_result)

    async def _update_order_fills_from_event_or_create(self, tracked_order, order_data):
        """
        Used to update fills from user stream events or order creation.

        :param tracked_order: The tracked order to be updated.
        :param order_data: The order update response from the user websocket or order creation.
        """
        client_order_id = order_data.get("clientOrderId")
        exec_amt_base = decimal_val_or_none(order_data.get("matchQuantity"))
        if not exec_amt_base:
            return
        if not tracked_order:
            tracked_order = self.in_flight_orders.get(client_order_id)
        fill_price = decimal_val_or_none(order_data.get("matchPrice", order_data.get("price")))
        exec_amt_quote = exec_amt_base * fill_price if exec_amt_base and fill_price else None
        fee_asset = order_data.get("feeInstrumentId", tracked_order.quote_asset)
        fee_amount = decimal_val_or_none(order_data.get("fees"))
        position_side = order_data.get("side", "BUY")
        position_action = (PositionAction.OPEN
                           if (tracked_order.trade_type is TradeType.BUY and position_side == "BUY"
                               or tracked_order.trade_type is TradeType.SELL and position_side == "SELL")
                           else PositionAction.CLOSE)
        flat_fees = [] if not fee_amount or fee_amount == s_decimal_0 else [TokenAmount(amount=fee_amount, token=fee_asset)]

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=flat_fees,
        )
        trade_update = TradeUpdate(
            trading_pair=tracked_order.trading_pair,
            trade_id=int(order_data["matchId"]),
            client_order_id=client_order_id,
            exchange_order_id=str(order_data["orderId"]),
            fill_timestamp=int(order_data["timestamp"]) * 1e-3,
            fill_price=fill_price,
            fill_base_amount=exec_amt_base,
            fill_quote_amount=exec_amt_quote,
            fee=fee,
        )
        self._client_order_tracker.process_trade_update(trade_update=trade_update)

    async def _update_order_fills_from_trades(self, tracked_order, order_update):
        """
        This is intended to be a backup measure to get filled events from order status
        in case CoinFLEX's user stream events are not working.

        :param tracked_order: The tracked order to be updated.
        :param order_update: The order update response from the API.
        """
        fee_collected = False
        for match_data in order_update["matchIds"]:
            for trade_id in match_data.keys():
                trade_data = match_data[trade_id]
                exec_amt_base = decimal_val_or_none(trade_data.get("matchQuantity"))
                fill_price = decimal_val_or_none(trade_data.get("matchPrice"))
                exec_amt_quote = exec_amt_base * fill_price if exec_amt_base and fill_price else None
                if not fee_collected and len(order_update.get("fees", {})):
                    fee_collected = True
                    fee_data = order_update.get("fees")
                    fee_asset = list(fee_data.keys())[0]
                    fee_amount = decimal_val_or_none(fee_data[fee_asset])
                else:
                    fee_asset = tracked_order.quote_asset
                    fee_amount = None
                position_side = order_update.get("side", "BUY")
                position_action = (PositionAction.OPEN
                                   if (tracked_order.trade_type is TradeType.BUY and position_side == "BUY"
                                       or tracked_order.trade_type is TradeType.SELL and position_side == "SELL")
                                   else PositionAction.CLOSE)
                flat_fees = [] if not fee_amount or fee_amount == s_decimal_0 else [TokenAmount(amount=fee_amount, token=fee_asset)]

                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=self.trade_fee_schema(),
                    position_action=position_action,
                    percent_token=fee_asset,
                    flat_fees=flat_fees,
                )
                trade_update = TradeUpdate(
                    trading_pair=tracked_order.trading_pair,
                    trade_id=int(trade_id),
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=str(order_update["orderId"]),
                    fill_timestamp=int(trade_data["timestamp"]) * 1e-3,
                    fill_price=fill_price,
                    fill_base_amount=exec_amt_base,
                    fill_quote_amount=exec_amt_quote,
                    fee=fee,
                )
                self._client_order_tracker.process_trade_update(trade_update=trade_update)

    def _process_order_not_found(self,
                                 client_order_id: str,
                                 tracked_order: InFlightOrder) -> bool:
        self._order_not_found_records[client_order_id] = (
            self._order_not_found_records.get(client_order_id, 0) + 1)
        if (self._order_not_found_records[client_order_id] >=
                self.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
            # Wait until the order not found error have repeated a few times before actually treating
            # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601

            order_update: OrderUpdate = OrderUpdate(
                client_order_id=client_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp if self.current_timestamp != s_float_NaN else int(time.time()),
                new_state=OrderState.FAILED,
            )
            self._client_order_tracker.process_order_update(order_update)
            return True
        return False

    # ORDER PLACE AND CANCEL EXECUTIONS ---
    async def _create_order(
            self,
            trade_type: TradeType,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType,
            position_action: PositionAction,
            price: Optional[Decimal] = s_decimal_NaN,
    ):
        """
        This function is responsible for executing the API request to place the order on the exchange.

        Parameters
        ----------
        trade_type:
            BUY or SELL
        order_id:
            Client order ID
        trading_pair:
            The pair that is being traded
        amount:
            The amount to trade
        order_type:
            LIMIT or MARKET
        position_action:
            OPEN or CLOSE
        price:
            Price for a limit order
        """
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        if position_action not in [PositionAction.OPEN, PositionAction.CLOSE]:
            raise ValueError("Specify either OPEN_POSITION or CLOSE_POSITION position_action.")

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        if amount < trading_rule.min_order_size:
            raise ValueError(
                f"Buy order amount {amount} is lower than the minimum order size " f"{trading_rule.min_order_size}"
            )

        symbol = await CoinflexPerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
            hb_trading_pair=trading_pair,
            domain=self._domain,
            throttler=self._throttler,
            api_factory=self._api_factory)

        if self.current_timestamp == s_float_NaN:
            raise ValueError("Cannot create orders while connector is starting/stopping.")

        api_params = {"responseType": "FULL"}
        order_params = {"marketCode": symbol,
                        "side": CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL,
                        "quantity": f"{amount}",
                        "orderType": order_type.name.upper().split("_")[0],
                        "clientOrderId": order_id}
        if order_type is not OrderType.MARKET:
            order_params["price"] = f"{price:f}"
        if order_type is OrderType.LIMIT:
            order_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
        elif order_type is OrderType.LIMIT_MAKER:
            order_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_MAK
        api_params["orders"] = [order_params]

        self.start_tracking_order(
            order_id=order_id,
            trading_pair=trading_pair,
            trading_type=trade_type,
            price=price,
            amount=amount,
            order_type=order_type,
            leverage=self._leverage[trading_pair],
            position=position_action,
        )

        try:
            create_result = await self._api_request(
                path=CONSTANTS.ORDER_CREATE_URL,
                data=api_params,
                method=RESTMethod.POST,
                is_auth_required=True,
                disable_retries=True
            )

            order_result = create_result["data"][0]

            order_state = CONSTANTS.ORDER_STATE[order_result.get("status", create_result.get("event"))]

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=int(order_result["timestamp"]) * 1e-3,
                new_state=OrderState.OPEN,
                client_order_id=order_id,
                exchange_order_id=str(order_result["orderId"]),
            )
            # Since POST /order endpoint is synchrounous, we can update exchange_order_id and
            # last_state of tracked order.
            self._client_order_tracker.process_order_update(order_update)

            # Process immediately matched orders
            safe_ensure_future(self._create_order_update_matched(trading_pair, order_id, order_state, order_result))

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error submitting order to Coinflex Perpetuals for {amount} {trading_pair} "
                f"{'' if order_type is OrderType.MARKET else price}.",
                exc_info=True,
                app_warning_msg=str(e),
            )
            order_update: OrderUpdate = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
                client_order_id=order_id,
            )
            # This should call stop_tracking_order
            self._client_order_tracker.process_order_update(order_update)

    async def _execute_cancel(self, trading_pair: str, client_order_id: str) -> str:
        """
        Cancels the specified in-flight order and returns the client order ID.

        Parameters
        ----------
        trading_pair:
            The pair that is being traded
        client_order_id:
            Client order ID
        """
        try:
            # Checks if order is not being tracked or order is waiting for created confirmation.
            # If so, ignores cancel request.
            tracked_order: Optional[InFlightOrder] = self._client_order_tracker.fetch_tracked_order(client_order_id)
            if not tracked_order or tracked_order.is_pending_create:
                return

            cancel_params = {
                "clientOrderId": client_order_id,
                "marketCode": await CoinflexPerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                    hb_trading_pair=trading_pair,
                    domain=self._domain,
                    throttler=self._throttler,
                    api_factory=self._api_factory
                )
            }
            api_params = {
                "responseType": "FULL",
                "orders": [cancel_params],
            }
            try:
                result = await self._api_request(
                    method=RESTMethod.DELETE,
                    path=CONSTANTS.ORDER_CANCEL_URL,
                    data=api_params,
                    is_auth_required=True)
                cancel_result = result["data"][0]
            except web_utils.CoinflexPerpetualAPIError as e:
                # Catch order not found as cancelled.
                result = {}
                cancel_result = {}
                if e.error_payload.get("errors") in CONSTANTS.ORDER_NOT_FOUND_ERRORS:
                    cancel_result = e.error_payload["data"][0]
                    # If tracked order was filled while being cancelled, ignore the request.
                    if tracked_order.is_done:
                        return
                else:
                    self.logger().error(f"Unhandled error canceling order: {client_order_id}. Error: {e.error_payload}", exc_info=True)
            if cancel_result.get("status", result.get("event")) in CONSTANTS.ORDER_CANCELLED_STATES:
                cancelled_timestamp = cancel_result.get("timestamp", result.get("timestamp"))
                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=int(cancelled_timestamp) * 1e-3 if cancelled_timestamp else self.current_timestamp,
                    new_state=OrderState.CANCELED,
                )
                self._client_order_tracker.process_order_update(order_update)
            else:
                self.logger().debug(f"Unknown Order cancel result for debug: \n{result}")
                if not self._process_order_not_found(client_order_id, tracked_order):
                    raise IOError
            return cancel_result

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"There was an error when requesting cancelation of order {client_order_id}")

    async def _api_request(self,
                           path: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           method: RESTMethod = RESTMethod.GET,
                           is_auth_required: bool = False,
                           domain_api_version: str = None,
                           endpoint_api_version: str = None,
                           limit_id: Optional[str] = None,
                           disable_retries: bool = False):

        return await web_utils.api_request(
            path=path,
            api_factory=self._api_factory,
            throttler=self._throttler,
            domain=self._domain,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            domain_api_version=domain_api_version,
            endpoint_api_version=endpoint_api_version,
            disable_retries=disable_retries,
            limit_id=limit_id)

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)
