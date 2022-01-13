import asyncio
import logging
import time
import warnings

from async_timeout import timeout
from collections import defaultdict
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils
import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source import (
    BinancePerpetualAPIOrderBookDataSource
)
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_order_book_tracker import (
    BinancePerpetualOrderBookTracker
)
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_tracker import (
    BinancePerpetualUserStreamTracker
)
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import (
    BinancePerpetualAuth
)
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import (
    FundingInfo,
    FundingPaymentCompletedEvent,
    MarketEvent,
    OrderType,
    PositionAction,
    PositionMode,
    PositionSide,
    TradeType,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

bpm_logger = None


class BinancePerpetualDerivative(ExchangeBase, PerpetualTrading):
    MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG = MarketEvent.FundingPaymentCompleted

    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3
    HEARTBEAT_TIME_INTERVAL = 30.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global bpm_logger
        if bpm_logger is None:
            bpm_logger = logging.getLogger(__name__)
        return bpm_logger

    def __init__(
            self,
            binance_perpetual_api_key: str = None,
            binance_perpetual_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = "binance_perpetual",
    ):
        self._auth: BinancePerpetualAuth = BinancePerpetualAuth(api_key=binance_perpetual_api_key,
                                                                api_secret=binance_perpetual_api_secret)
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._api_factory = utils.build_api_factory(auth=self._auth)
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._domain = domain

        ExchangeBase.__init__(self)
        PerpetualTrading.__init__(self)
        self._binance_time_synchronizer = TimeSynchronizer()

        self._user_stream_tracker = BinancePerpetualUserStreamTracker(
            auth=self._auth,
            domain=self._domain,
            throttler=self._throttler,
            api_factory=self._api_factory)
        self._order_book_tracker = BinancePerpetualOrderBookTracker(
            trading_pairs=trading_pairs,
            domain=self._domain,
            throttler=self._throttler,
            api_factory=self._api_factory)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._next_funding_fee_timestamp = self.get_next_funding_timestamp()
        self._funding_fee_poll_notifier = asyncio.Event()
        self._order_not_found_records = defaultdict(int)
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
        # Note: domain here refers to the entire exchange name. i.e. binance_perpetual or binance_perpetual_testnet
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
        return {
            "symbols_mapping_initialized": BinancePerpetualAPIOrderBookDataSource.trading_pair_symbol_map_ready(
                domain=self._domain),
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "position_mode": self.position_mode,
            "user_stream_initialized": self._user_stream_tracker.data_source.last_recv_time > 0,
            "funding_info_initialized": self._order_book_tracker.is_funding_info_initialized(),
        }

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
        """
        Restore in-flight orders from saved tracking states; this is such that the connector can pick up
        on where it left off should it crash unexpectedly.
        """
        for data in saved_states.values():
            self._client_order_tracker.start_tracking_order(InFlightOrder.from_json(data))

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
            await self._get_position_mode()
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
            await self.__api_request(path=CONSTANTS.PING_URL)
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
        t_pair: str = trading_pair
        order_id: str = utils.get_client_order_id("buy", t_pair)
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
        t_pair: str = trading_pair
        order_id: str = utils.get_client_order_id("sell", t_pair)
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
        being tracked by the Client Order Tracker. It confirms the successful cancellation
        of the orders.

        Parameters
        ----------
        timeout_seconds:
            How long to wait before checking whether the orders were cancelled
        """
        incomplete_orders = [order for order in self._client_order_tracker.active_orders.values() if not order.is_done]
        tasks = [self._execute_cancel(order.trading_pair, order.client_order_id) for order in incomplete_orders]
        successful_cancellations = []
        failed_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cancel_result, order in zip(cancellation_results, incomplete_orders):
                    if cancel_result and cancel_result == order.client_order_id:
                        successful_cancellations.append(CancellationResult(order.client_order_id, True))
                    else:
                        failed_cancellations.append(CancellationResult(order.client_order_id, False))
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Binance Perpetual. Check API key and network connection."
            )
        return successful_cancellations + failed_cancellations

    async def cancel_all_account_orders(self, trading_pair: str):
        try:
            params = {
                "symbol": trading_pair
            }
            response = await self.__api_request(
                path=CONSTANTS.CANCEL_ALL_OPEN_ORDERS_URL,
                params=params,
                method=RESTMethod.DELETE,
                add_timestamp=True,
                is_auth_required=True,
            )
            if response.get("code") == 200:
                for order_id in list(self._client_order_tracker.active_orders.keys()):
                    self.stop_tracking_order(order_id)
            else:
                raise IOError(f"Error cancelling all account orders. Server Response: {response}")
        except Exception as e:
            self.logger().error("Could not cancel all account orders.")
            raise e

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
        notional_size: object
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
            position: str,
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
        # On Binance Futures, Funding occurs every 8 hours at 00:00 UTC; 08:00 UTC and 16:00
        int_ts = int(time.time())
        eight_hours = 8 * 60 * 60
        mod = int_ts % eight_hours
        return int(int_ts - mod + eight_hours)

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        safe_ensure_future(self._set_leverage(trading_pair, leverage))

    def set_position_mode(self, position_mode: PositionMode):
        safe_ensure_future(self._set_position_mode(position_mode))

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

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
        if self._funding_fee_polling_task is not None:
            self._funding_fee_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = self._funding_fee_polling_task = None

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

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
                    app_warning_msg="Could not fetch user events from Binance. Check API key and network connection.",
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
        event_type = event_message.get("e")
        if event_type == "ORDER_TRADE_UPDATE":
            order_message = event_message.get("o")
            client_order_id = order_message.get("c", None)

            tracked_order: InFlightOrder = self._client_order_tracker.fetch_order(client_order_id)
            if not tracked_order:
                return

            trade_id: str = str(order_message["t"])

            if trade_id != "0":  # Indicates that there has been a trade

                trade_fee_percent = Decimal("0")
                if "n" in order_message:
                    trade_fee_percent = None

                trade_update: TradeUpdate = TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=client_order_id,
                    exchange_order_id=str(order_message["i"]),
                    trading_pair=tracked_order.trading_pair,
                    fill_timestamp=order_message["T"],
                    fill_price=Decimal(order_message["L"]),
                    fill_base_amount=Decimal(order_message["z"]),
                    fill_quote_amount=Decimal(order_message["L"]) * Decimal(order_message["z"]),
                    fee_asset=order_message.get("N", tracked_order.fee_asset),
                    fee_paid=Decimal(order_message.get("n", "0")),
                    trade_fee_percent=trade_fee_percent
                )
                self._client_order_tracker.process_trade_update(trade_update)

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=event_message["T"],
                new_state=CONSTANTS.ORDER_STATE[order_message["X"]],
                client_order_id=client_order_id,
                exchange_order_id=str(order_message["i"]),
            )

            self._client_order_tracker.process_order_update(order_update)

        elif event_type == "ACCOUNT_UPDATE":
            update_data = event_message.get("a", {})
            # update balances
            for asset in update_data.get("B", []):
                asset_name = asset["a"]
                self._account_balances[asset_name] = Decimal(asset["wb"])
                self._account_available_balances[asset_name] = Decimal(asset["cw"])

            # update position
            for asset in update_data.get("P", []):
                trading_pair = asset["s"]
                side = PositionSide[asset['ps']]
                position = self.get_position(trading_pair, side)
                if position is not None:
                    amount = Decimal(asset["pa"])
                    if amount == Decimal("0"):
                        pos_key = self.position_key(trading_pair, side)
                        del self._account_positions[pos_key]
                    else:
                        position.update_position(position_side=PositionSide[asset["ps"]],
                                                 unrealized_pnl=Decimal(asset["up"]),
                                                 entry_price=Decimal(asset["ep"]),
                                                 amount=Decimal(asset["pa"]))
                else:
                    await self._update_positions()
        elif event_type == "MARGIN_CALL":
            positions = event_message.get("p", [])
            total_maint_margin_required = Decimal(0)
            # total_pnl = 0
            negative_pnls_msg = ""
            for position in positions:
                existing_position = self.get_position(position['s'], PositionSide[position['ps']])
                if existing_position is not None:
                    existing_position.update_position(position_side=PositionSide[position["ps"]],
                                                      unrealized_pnl=Decimal(position["up"]),
                                                      amount=Decimal(position["pa"]))
                total_maint_margin_required += Decimal(position.get("mm", "0"))
                if float(position.get("up", 0)) < 1:
                    negative_pnls_msg += f"{position.get('s')}: {position.get('up')}, "
            self.logger().warning("Margin Call: Your position risk is too high, and you are at risk of "
                                  "liquidation. Close your positions or add additional margin to your wallet.")
            self.logger().info(f"Margin Required: {total_maint_margin_required}. "
                               f"Negative PnL assets: {negative_pnls_msg}.")

    async def _update_trading_rules(self):
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.
        """
        last_tick = int(self._last_timestamp / 60.0)
        current_tick = int(self.current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self.__api_request(path=CONSTANTS.EXCHANGE_INFO_URL,
                                                     method=RESTMethod.GET,
                                                     )
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        rules: list = exchange_info_dict.get("symbols", [])
        return_val: list = []
        for rule in rules:
            try:
                if rule["contractType"] == "PERPETUAL" and rule["status"] == "TRADING":
                    trading_pair = combine_to_hb_trading_pair(rule["baseAsset"], rule["quoteAsset"])
                    filters = rule["filters"]
                    filt_dict = {fil["filterType"]: fil for fil in filters}

                    min_order_size = Decimal(filt_dict.get("LOT_SIZE").get("minQty"))
                    step_size = Decimal(filt_dict.get("LOT_SIZE").get("stepSize"))
                    tick_size = Decimal(filt_dict.get("PRICE_FILTER").get("tickSize"))
                    min_notional = Decimal(filt_dict.get("MIN_NOTIONAL").get("notional"))
                    collateral_token = rule["marginAsset"]

                    return_val.append(
                        TradingRule(
                            trading_pair,
                            min_order_size=min_order_size,
                            min_price_increment=Decimal(tick_size),
                            min_base_amount_increment=Decimal(step_size),
                            min_notional_size=Decimal(min_notional),
                            buy_order_collateral_token=collateral_token,
                            sell_order_collateral_token=collateral_token,
                        )
                    )
            except Exception as e:
                self.logger().error(
                    f"Error parsing the trading pair rule {rule}. Error: {e}. Skipping...", exc_info=True
                )
        return return_val

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
                    app_warning_msg="Could not fetch new trading rules from Binance Perpetuals. "
                                    "Check network connection.",
                )
                await self._sleep(0.5)

    async def _fetch_funding_payment(self, trading_pair: str) -> bool:
        """
        Fetches the funding settlement details of all the active trading pairs and processes the responses.
        Triggers a FundingPaymentCompleted event as required.
        """
        try:
            response = await self.__api_request(
                path=CONSTANTS.GET_INCOME_HISTORY_URL,
                params={
                    "symbol": await BinancePerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                        hb_trading_pair=trading_pair,
                        domain=self._domain,
                        throttler=self._throttler),
                    "incomeType": "FUNDING_FEE",
                    "startTime": self._next_funding_fee_timestamp - 3600,  # We provide a buffer time of 1hr.
                },
                method=RESTMethod.GET,
                add_timestamp=True,
                is_auth_required=True,
            )

            for funding_payment in response:
                payment = Decimal(funding_payment["income"])
                action = "paid" if payment < 0 else "received"
                trading_pair = await BinancePerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                    exchange_trading_pair=funding_payment["symbol"],
                    domain=self._domain,
                    throttler=self._throttler,
                )
                if payment != Decimal("0"):
                    funding_info = self.get_funding_info(trading_pair)
                    if funding_info is not None:
                        self.logger().info(f"Funding payment of {payment} {action} on {trading_pair} market.")
                        self.trigger_event(self.MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG,
                                           FundingPaymentCompletedEvent(timestamp=funding_payment["time"],
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
                await self._update_time_synchronizer()
                await safe_gather(
                    self._update_balances(),
                    self._update_positions(),
                )
                await self._update_order_fills_from_trades(),
                await self._update_order_status()
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Binance Perpetuals. "
                                                      "Check API key and network connection.")
                await self._sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self.__api_request(path=CONSTANTS.ACCOUNT_INFO_URL,
                                                is_auth_required=True,
                                                add_timestamp=True,
                                                api_version=CONSTANTS.API_VERSION_V2,
                                                )
        assets = account_info.get("assets")
        for asset in assets:
            asset_name = asset.get("asset")
            available_balance = Decimal(asset.get("availableBalance"))
            wallet_balance = Decimal(asset.get("walletBalance"))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = wallet_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        positions = await self.__api_request(path=CONSTANTS.POSITION_INFORMATION_URL,
                                             add_timestamp=True,
                                             is_auth_required=True,
                                             api_version=CONSTANTS.API_VERSION_V2,
                                             )
        for position in positions:
            trading_pair = position.get("symbol")
            position_side = PositionSide[position.get("positionSide")]
            unrealized_pnl = Decimal(position.get("unRealizedProfit"))
            entry_price = Decimal(position.get("entryPrice"))
            amount = Decimal(position.get("positionAmt"))
            leverage = Decimal(position.get("leverage"))
            pos_key = self.position_key(trading_pair, position_side)
            if amount != 0:
                self._account_positions[pos_key] = Position(
                    trading_pair=await BinancePerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                        exchange_trading_pair=trading_pair,
                        domain=self._domain,
                        throttler=self._throttler,
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

    async def _update_order_fills_from_trades(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._client_order_tracker.active_orders) > 0:
            trading_pairs_to_order_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {})
            for order in self._client_order_tracker.active_orders.values():
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order
            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [
                self.__api_request(
                    path=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    params={"symbol": await BinancePerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                        hb_trading_pair=trading_pair,
                        domain=self._domain,
                        throttler=self._throttler)},
                    is_auth_required=True,
                    add_timestamp=True,
                )
                for trading_pair in trading_pairs
            ]
            self.logger().debug(f"Polling for order fills of {len(tasks)} trading_pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map.get(trading_pair)
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    order_id = str(trade.get("orderId"))
                    if order_id in order_map:
                        tracked_order: InFlightOrder = order_map.get(order_id)
                        trade_update: TradeUpdate = TradeUpdate(
                            trade_id=str(trade["id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=trade["orderId"],
                            trading_pair=tracked_order.trading_pair,
                            fill_timestamp=trade["time"],
                            fill_price=Decimal(trade["price"]),
                            fill_base_amount=Decimal(trade["qty"]),
                            fill_quote_amount=Decimal(trade["quoteQty"]),
                            fee_asset=trade["commissionAsset"],
                            fee_paid=Decimal(trade["commission"])
                        )
                        self._client_order_tracker.process_trade_update(trade_update)

    async def _update_order_status(self):
        """
        Calls the REST API to get order/trade updates for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._client_order_tracker.active_orders) > 0:
            tracked_orders = list(self._client_order_tracker.active_orders.values())
            tasks = [
                self.__api_request(
                    path=CONSTANTS.ORDER_URL,
                    params={
                        "symbol": await BinancePerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                            hb_trading_pair=order.trading_pair,
                            domain=self._domain,
                            throttler=self._throttler),
                        "origClientOrderId": order.client_order_id
                    },
                    method=RESTMethod.GET,
                    add_timestamp=True,
                    is_auth_required=True,
                    return_err=True,
                )
                for order in tracked_orders
            ]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._client_order_tracker.all_orders:
                    continue
                if isinstance(order_update, Exception) or "code" in order_update:
                    if not isinstance(order_update, Exception) and \
                            (order_update["code"] == -2013 or order_update["msg"] == "Order does not exist."):
                        self._client_order_tracker.process_order_not_found(client_order_id)
                    else:
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: " f"{order_update}."
                        )
                    continue

                new_order_update: OrderUpdate = OrderUpdate(
                    trading_pair=await BinancePerpetualAPIOrderBookDataSource.convert_from_exchange_trading_pair(
                        exchange_trading_pair=order_update["symbol"],
                        domain=self._domain,
                        throttler=self._throttler,
                    ),
                    update_timestamp=order_update["updateTime"],
                    new_state=CONSTANTS.ORDER_STATE[order_update["status"]],
                    client_order_id=order_update["clientOrderId"],
                    exchange_order_id=order_update["orderId"],
                    executed_amount_base=Decimal(order_update.get("executedQty", "0")),
                    executed_amount_quote=Decimal(order_update.get("cumQuote", "0")),
                )

                self._client_order_tracker.process_order_update(new_order_update)

    async def _set_leverage(self, trading_pair: str, leverage: int = 1):
        """
        This method may need to be overridden to perform the necessary validations and set the leverage level
        on the exchange.

        Parameters
        ----------
        trading_pair:
            Trading pair for which the leverage should be set
        leverage:
            Leverage level to be set
        """
        symbol = await BinancePerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
            hb_trading_pair=trading_pair,
            domain=self._domain,
            throttler=self._throttler)
        params = {"symbol": symbol,
                  "leverage": leverage}
        set_leverage = await self.__api_request(
            path=CONSTANTS.SET_LEVERAGE_URL,
            data=params,
            method=RESTMethod.POST,
            add_timestamp=True,
            is_auth_required=True,
        )
        if set_leverage["leverage"] == leverage:
            self._leverage[trading_pair] = leverage
            self.logger().info(f"Leverage Successfully set to {leverage} for {trading_pair}.")
        else:
            self.logger().error("Unable to set leverage.")
        return leverage

    async def _set_position_mode(self, position_mode: PositionMode):
        initial_mode = await self._get_position_mode()
        if initial_mode != position_mode:
            params = {
                "dualSidePosition": position_mode.value
            }
            response = await self.__api_request(
                method=RESTMethod.POST,
                path=CONSTANTS.CHANGE_POSITION_MODE_URL,
                data=params,
                add_timestamp=True,
                is_auth_required=True,
                limit_id=CONSTANTS.POST_POSITION_MODE_LIMIT_ID,
                return_err=True
            )
            if response["msg"] == "success" and response["code"] == 200:
                self.logger().info(f"Using {position_mode.name} position mode.")
                self._position_mode = position_mode
            else:
                self.logger().error(f"Unable to set postion mode to {position_mode.name}.")
                self.logger().info(f"Using {initial_mode.name} position mode.")
                self._position_mode = initial_mode
        else:
            self.logger().info(f"Using {position_mode.name} position mode.")
            self._position_mode = position_mode

    async def _get_position_mode(self) -> Optional[PositionMode]:
        # To-do: ensure there's no active order or contract before changing position mode
        if self._position_mode is None:
            response = await self.__api_request(
                method=RESTMethod.GET,
                path=CONSTANTS.CHANGE_POSITION_MODE_URL,
                add_timestamp=True,
                is_auth_required=True,
                limit_id=CONSTANTS.GET_POSITION_MODE_LIMIT_ID,
                return_err=True
            )
            self._position_mode = PositionMode.HEDGE if response["dualSidePosition"] else PositionMode.ONEWAY

        return self._position_mode

    # ORDER PLACE AND CANCEL EXECUTIONS ---
    async def _create_order(
            self,
            trade_type: TradeType,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType,
            position_action: PositionAction,
            price: Optional[Decimal] = Decimal("NaN"),
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

        order_result = None
        api_params = {
            "symbol": await BinancePerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                hb_trading_pair=trading_pair,
                domain=self._domain,
                throttler=self._throttler),
            "side": "BUY" if trade_type is TradeType.BUY else "SELL",
            "type": "LIMIT" if order_type is OrderType.LIMIT else "MARKET",
            "quantity": f"{amount}",
            "newClientOrderId": order_id,
        }
        if order_type == OrderType.LIMIT:
            api_params["price"] = f"{price}"
            api_params["timeInForce"] = "GTC"

        if self._position_mode == PositionMode.HEDGE:
            if position_action == PositionAction.OPEN:
                api_params["positionSide"] = "LONG" if trade_type is TradeType.BUY else "SHORT"
            else:
                api_params["positionSide"] = "SHORT" if trade_type is TradeType.BUY else "LONG"

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
            order_result = await self.__api_request(
                path=CONSTANTS.ORDER_URL,
                data=api_params,
                method=RESTMethod.POST,
                add_timestamp=True,
                is_auth_required=True,
            )

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=order_result["updateTime"],
                new_state=CONSTANTS.ORDER_STATE[order_result["status"]],
                client_order_id=order_id,
                exchange_order_id=str(order_result["orderId"]),
            )
            # Since POST /order endpoint is synchrounous, we can update exchange_order_id and
            # last_state of tracked order.
            self._client_order_tracker.process_order_update(order_update)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error submitting order to Binance Perpetuals for {amount} {trading_pair} "
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
            tracked_order: Optional[InFlightOrder] = self._client_order_tracker.fetch_order(client_order_id)
            if not tracked_order or tracked_order.is_pending_create:
                return

            params = {
                "origClientOrderId": client_order_id,
                "symbol": await BinancePerpetualAPIOrderBookDataSource.convert_to_exchange_trading_pair(
                    hb_trading_pair=trading_pair,
                    domain=self._domain,
                    throttler=self._throttler)
            }
            response = await self.__api_request(
                path=CONSTANTS.ORDER_URL,
                params=params,
                method=RESTMethod.DELETE,
                is_auth_required=True,
                add_timestamp=True,
                return_err=True,
            )
            if response.get("code") == -2011 or "Unknown order sent" in response.get("msg", ""):
                self.logger().debug(f"The order {client_order_id} does not exist on Binance Perpetuals. "
                                    f"No cancellation needed.")
                self.stop_tracking_order(client_order_id)
                return None
            return client_order_id
        except Exception as e:
            self.logger().error(f"Could not cancel order {client_order_id} on Binance Perp. {str(e)}")

    async def __api_request(self,
                            path: str,
                            params: Optional[Dict[str, Any]] = None,
                            data: Optional[Dict[str, Any]] = None,
                            method: RESTMethod = RESTMethod.GET,
                            add_timestamp: bool = False,
                            is_auth_required: bool = False,
                            return_err: bool = False,
                            api_version: str = CONSTANTS.API_VERSION,
                            limit_id: Optional[str] = None):

        rest_assistant = await self._get_rest_assistant()
        async with self._throttler.execute_task(limit_id=limit_id if limit_id else path):
            try:
                if add_timestamp:
                    if method == RESTMethod.POST:
                        data = data or {}
                        data["recvWindow"] = f"{20000}"
                        data["timestamp"] = str(int(self._binance_time_synchronizer.time()) * 1000)
                    else:
                        params = params or {}
                        params["recvWindow"] = f"{20000}"
                        params["timestamp"] = str(int(self._binance_time_synchronizer.time()) * 1000)

                url = utils.rest_url(path, self._domain, api_version)

                request = RESTRequest(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    is_auth_required=is_auth_required,
                    throttler_limit_id=limit_id if limit_id else path
                )
                response = await rest_assistant.call(request=request)

                if response.status != 200:
                    error_response = await response.json()
                    if return_err:
                        return error_response
                    else:
                        raise IOError(f"Error executing request {method.name} {path}. "
                                      f"HTTP status is {response.status}. "
                                      f"Error: {error_response}")
                return await response.json()
            except Exception as e:
                self.logger().error(f"Error fetching {path}", exc_info=True)
                self.logger().warning(f"{e}")
                raise e

    async def _update_time_synchronizer(self):
        try:
            await self._binance_time_synchronizer.update_server_time_offset_with_time_provider(
                time_provider=self._get_current_server_time()
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error requesting time from Binance server")
            raise

    async def _get_current_server_time(self):
        response = await self.__api_request(
            method=RESTMethod.GET,
            path=CONSTANTS.SERVER_TIME_PATH_URL,
        )
        return response["serverTime"]

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)
