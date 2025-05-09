import asyncio
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import PerpetualDerivativeInFlightOrder
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.event.events import (
    AccountEvent,
    FundingPaymentCompletedEvent,
    MarketEvent,
    PositionModeChangeEvent,
)
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class PerpetualDerivativePyBase(ExchangePyBase, ABC):
    VALID_POSITION_ACTIONS = [PositionAction.OPEN, PositionAction.CLOSE]

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__(client_config_map)
        self._last_funding_fee_payment_ts: Dict[str, float] = {}

        self._perpetual_trading = PerpetualTrading(self.trading_pairs)
        self._funding_info_listener_task: Optional[asyncio.Task] = None
        self._funding_fee_polling_task: Optional[asyncio.Task] = None
        self._funding_fee_poll_notifier = asyncio.Event()
        self._orderbook_ds: PerpetualAPIOrderBookDataSource = self._orderbook_ds  # for type-hinting

        self._budget_checker = PerpetualBudgetChecker(self)

    @property
    @abstractmethod
    def funding_fee_poll_interval(self) -> int:
        raise NotImplementedError

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various exchange's components. Used to determine if the connector is ready
        """
        status_d = super().status_dict
        status_d["funding_info"] = self._perpetual_trading.is_funding_info_initialized()
        return status_d

    @property
    def position_mode(self) -> PositionMode:
        """Returns the current position mode."""
        return self._perpetual_trading.position_mode

    @property
    def budget_checker(self) -> PerpetualBudgetChecker:
        """Returns the exchange's associated budget checker."""
        return self._budget_checker

    @property
    def account_positions(self) -> Dict[str, Position]:
        """Returns a dictionary of current active open positions."""
        return self._perpetual_trading.account_positions

    @abstractmethod
    def supported_position_modes(self) -> List[PositionMode]:
        raise NotImplementedError

    @abstractmethod
    def get_buy_collateral_token(self, trading_pair: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_sell_collateral_token(self, trading_pair: str) -> str:
        raise NotImplementedError

    def tick(self, timestamp: float):
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
        last_tick = int(self._last_timestamp / self.funding_fee_poll_interval)
        current_tick = int(timestamp / self.funding_fee_poll_interval)
        super().tick(timestamp)
        if current_tick > last_tick:
            self._funding_fee_poll_notifier.set()

    async def start_network(self):
        await super().start_network()
        self._perpetual_trading.start()
        self._funding_info_listener_task = safe_ensure_future(self._listen_for_funding_info())
        if self.is_trading_required:
            self._funding_fee_polling_task = safe_ensure_future(self._funding_payment_polling_loop())

    def set_position_mode(self, mode: PositionMode):
        """
        Sets position mode for perpetual trading, a child class might need to override this to set position mode on
        the exchange
        :param mode: the position mode
        """
        if mode in self.supported_position_modes():
            safe_ensure_future(self._execute_set_position_mode(mode))
        else:
            self.logger().error(f"Position mode {mode} is not supported. Mode not set.")

    def get_leverage(self, trading_pair: str) -> int:
        return self._perpetual_trading.get_leverage(trading_pair)

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        safe_ensure_future(self._execute_set_leverage(trading_pair, leverage))

    def get_funding_info(self, trading_pair: str) -> FundingInfo:
        return self._perpetual_trading.get_funding_info(trading_pair)

    def start_tracking_order(
        self,
        order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        order_type: OrderType,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ):
        """
        Starts tracking an order by adding it to the order tracker.

        :param order_id: the order identifier
        :param exchange_order_id: the identifier for the order in the exchange
        :param trading_pair: the token pair for the operation
        :param trade_type: the type of order (buy or sell)
        :param price: the price for the order
        :param amount: the amount for the order
        :param order_type: type of execution for the order (MARKET, LIMIT, LIMIT_MAKER)
        :param position_action: is the order opening or closing a position
        """
        leverage = self.get_leverage(trading_pair=trading_pair)
        self._order_tracker.start_tracking_order(
            PerpetualDerivativeInFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self.current_timestamp,
                leverage=leverage,
                position=position_action,
            )
        )

    @abstractmethod
    def _create_order_book_data_source(self) -> PerpetualAPIOrderBookDataSource:
        raise NotImplementedError

    @abstractmethod
    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:
        raise NotImplementedError

    @abstractmethod
    async def _update_positions(self):
        raise NotImplementedError

    @abstractmethod
    async def _trading_pair_position_mode_set(
        self, mode: PositionMode, trading_pair: str
    ) -> Tuple[bool, str]:
        """
        :return: A tuple of boolean (true if success) and error message if the exchange returns one on failure.
        """
        raise NotImplementedError

    @abstractmethod
    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        """
        Returns a tuple of the latest funding payment timestamp, funding rate, and payment amount.
        If no payment exists, return (0, -1, -1)
        """
        raise NotImplementedError

    def _stop_network(self):
        self._funding_fee_poll_notifier = asyncio.Event()
        self._perpetual_trading.stop()
        if self._funding_info_listener_task is not None:
            self._funding_info_listener_task.cancel()
            self._funding_info_listener_task = None
        self._last_funding_fee_payment_ts.clear()
        super()._stop_network()

    async def _create_order(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ):
        """
        Creates an order in the exchange using the parameters to configure it

        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :param position_action: is the order opening or closing a position
        """

        if position_action not in self.VALID_POSITION_ACTIONS:
            raise ValueError(
                f"Invalid position action {position_action}. Must be one of {self.VALID_POSITION_ACTIONS}"
            )

        await super()._create_order(
            trade_type,
            order_id,
            trading_pair,
            amount,
            order_type,
            price,
            position_action=position_action,
            **kwargs,
        )

    def get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        """
        Calculates the fee to pay based on the fee information provided by the exchange for
        the account and the token pair. If exchange info is not available it calculates the estimated
        fee an order would pay based on the connector configuration.

        :param base_currency: the order base currency
        :param quote_currency: the order quote currency
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param order_side: if the order is for buying or selling
        :param position_action: the position action associated with the order
        :param amount: the order amount
        :param price: the order price
        :param is_maker: True if the order is a maker order, False if it is a taker order

        :return: the calculated or estimated fee
        """
        return self._get_fee(
            base_currency, quote_currency, order_type, order_side, position_action, amount, price, is_maker
        )

    @abstractmethod
    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        raise NotImplementedError

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_positions(),
            self._update_balances(),
            self._update_order_status(),
        )

    async def _execute_set_position_mode(self, mode: PositionMode):
        success, successful_pairs, msg = await self._execute_set_position_mode_for_pairs(
            mode=mode, trading_pairs=self.trading_pairs
        )

        if not success:
            await self._execute_set_position_mode_for_pairs(
                mode=self._perpetual_trading.position_mode, trading_pairs=successful_pairs
            )
            for trading_pair in self.trading_pairs:
                self.trigger_event(
                    AccountEvent.PositionModeChangeFailed,
                    PositionModeChangeEvent(
                        self.current_timestamp,
                        trading_pair,
                        mode,
                        msg,
                    ),
                )
        else:
            self._perpetual_trading.set_position_mode(mode)
            for trading_pair in self.trading_pairs:
                self.trigger_event(
                    AccountEvent.PositionModeChangeSucceeded,
                    PositionModeChangeEvent(
                        self.current_timestamp,
                        trading_pair,
                        mode,
                    )
                )
            self.logger().debug(f"Position mode switched to {mode}.")

    async def _execute_set_position_mode_for_pairs(
        self, mode: PositionMode, trading_pairs: List[str]
    ) -> Tuple[bool, List[str], str]:
        successful_pairs = []
        success = True
        msg = ""

        for trading_pair in trading_pairs:
            if mode != self._perpetual_trading.position_mode:
                success, msg = await self._trading_pair_position_mode_set(mode, trading_pair)
            if success:
                successful_pairs.append(trading_pair)
            else:
                self.logger().network(f"Error switching {trading_pair} mode to {mode}: {msg}")
                break

        return success, successful_pairs, msg

    async def _execute_set_leverage(self, trading_pair: str, leverage: int):
        success, msg = await self._set_trading_pair_leverage(trading_pair, leverage)
        if success:
            self._perpetual_trading.set_leverage(trading_pair, leverage)
            self.logger().info(f"Leverage for {trading_pair} successfully set to {leverage}.")
        else:
            self.logger().network(f"Error setting leverage {leverage} for {trading_pair}: {msg}")

    async def _listen_for_funding_info(self):
        await self._init_funding_info()
        await self._orderbook_ds.listen_for_funding_info(
            output=self._perpetual_trading.funding_info_stream
        )

    async def _init_funding_info(self):
        for trading_pair in self.trading_pairs:
            funding_info = await self._orderbook_ds.get_funding_info(trading_pair)
            self._perpetual_trading.initialize_funding_info(funding_info)

    async def _funding_payment_polling_loop(self):
        """
        Periodically calls _update_funding_payment(), responsible for handling all funding payments.
        """
        await self._update_all_funding_payments(fire_event_on_new=False)  # initialization of the timestamps
        while True:
            await self._funding_fee_poll_notifier.wait()
            # There is a chance of race condition when the next await allows for a set() to occur before the clear()
            # Maybe it is better to use a asyncio.Condition() instead of asyncio.Event()?
            self._funding_fee_poll_notifier.clear()
            await self._update_all_funding_payments(fire_event_on_new=True)

    async def _update_all_funding_payments(self, fire_event_on_new: bool):
        try:
            tasks = []
            for trading_pair in self.trading_pairs:
                tasks.append(
                    asyncio.create_task(
                        self._update_funding_payment(trading_pair=trading_pair, fire_event_on_new=fire_event_on_new)
                    )
                )
            await safe_gather(*tasks)
        except asyncio.CancelledError:
            raise

    async def _update_funding_payment(self, trading_pair: str, fire_event_on_new: bool) -> bool:
        fetch_success = True
        timestamp = funding_rate = payment_amount = 0
        try:
            timestamp, funding_rate, payment_amount = await self._fetch_last_fee_payment(trading_pair=trading_pair)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Unexpected error while fetching last fee payment for {trading_pair}.",
                exc_info=True,
                app_warning_msg=f"Could not fetch last fee payment for {trading_pair}. Check network connection."
            )
            fetch_success = False
        if fetch_success:
            self._emit_funding_payment_event(trading_pair, timestamp, funding_rate, payment_amount, fire_event_on_new)
        return fetch_success

    def _emit_funding_payment_event(
        self, trading_pair: str, timestamp: int, funding_rate: Decimal, payment_amount: Decimal, fire_event_on_new: bool
    ):
        prev_timestamp = self._last_funding_fee_payment_ts.get(trading_pair, 0)

        if timestamp > prev_timestamp and fire_event_on_new:
            action: str = "paid" if payment_amount < s_decimal_0 else "received"
            self.logger().info(f"Funding payment of {abs(payment_amount)} {action} on {trading_pair} market.")
            self.trigger_event(
                MarketEvent.FundingPaymentCompleted,
                FundingPaymentCompletedEvent(
                    timestamp=timestamp,
                    market=self.name,
                    funding_rate=funding_rate,
                    trading_pair=trading_pair,
                    amount=payment_amount,
                ),
            )
            self._last_funding_fee_payment_ts[trading_pair] = timestamp

        if trading_pair not in self._last_funding_fee_payment_ts:
            self._last_funding_fee_payment_ts[trading_pair] = timestamp
