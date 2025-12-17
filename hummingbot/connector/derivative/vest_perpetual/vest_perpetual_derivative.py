"""
Vest Perpetual Derivative connector implementation.
"""
import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.vest_perpetual.vest_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.vest_perpetual.vest_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_api_order_book_data_source import (
    VestPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_auth import VestPerpetualAuth
from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_user_stream_data_source import (
    VestPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
)
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class VestPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Vest Perpetual exchange connector.
    """

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        vest_perpetual_api_key: str,
        vest_perpetual_signing_key: str,
        vest_perpetual_account_group: int,
        vest_perpetual_use_testnet: bool = False,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        self._api_key = vest_perpetual_api_key
        self._signing_key = vest_perpetual_signing_key
        self._account_group = vest_perpetual_account_group
        self._use_testnet = vest_perpetual_use_testnet
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trade_history_timestamp: Optional[float] = None

        super().__init__(client_config_map)

        self._position_mode = PositionMode.ONEWAY
        self._set_trading_pair_symbol_map(None)

    @property
    def name(self) -> str:
        return "vest_perpetual"

    @property
    def authenticator(self) -> VestPerpetualAuth:
        return VestPerpetualAuth(
            api_key=self._api_key,
            signing_private_key=self._signing_key,
            account_group=self._account_group,
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return ""

    @property
    def client_order_id_max_length(self) -> int:
        return -1

    @property
    def client_order_id_prefix(self) -> str:
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.TICKER_LATEST_PATH_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return trading_pair.split("-")[1]

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return trading_pair.split("-")[1]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return VestPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            use_testnet=self._use_testnet,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return VestPerpetualUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            use_testnet=self._use_testnet,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = Decimal("NaN"),
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base_currency, quote_currency)
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data.maker) if is_maker else Decimal(fees_data.taker)
        else:
            fee_value = Decimal("0.0001")  # Default 0.01%
        return build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
            fee_value=fee_value,
        )

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
        """Place order on Vest exchange."""
        # Will be implemented later
        raise NotImplementedError("Order placement not yet implemented")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """Cancel order on Vest exchange."""
        # Will be implemented later
        raise NotImplementedError("Order cancellation not yet implemented")

    async def _update_trading_rules(self):
        """Update trading rules from exchange info."""
        # Will be implemented later
        pass

    async def _update_balances(self):
        """Update account balances."""
        # Will be implemented later
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """Get trade updates for an order."""
        # Will be implemented later
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Request order status from exchange."""
        # Will be implemented later
        raise NotImplementedError()

    async def _user_stream_event_listener(self):
        """Listen to user stream events."""
        # Will be implemented later
        pass

    def _set_trading_pair_symbol_map(self, trading_pairs: Optional[List[str]]):
        """Set up the trading pair to exchange symbol mapping."""
        if trading_pairs is not None:
            self._trading_pair_symbol_map = bidict(
                {tp: convert_to_exchange_trading_pair(tp) for tp in trading_pairs}
            )
        else:
            self._trading_pair_symbol_map = bidict()
