from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_user_stream_data_source import (
    DecibelPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils import build_api_factory, rest_url
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class DecibelPerpetualDerivative(PerpetualDerivativePyBase):
    def __init__(
        self,
        client_config_map,
        decibel_perpetual_bearer_token: str,
        decibel_perpetual_origin: str,
        decibel_perpetual_account_address: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._bearer_token = decibel_perpetual_bearer_token
        self._origin = decibel_perpetual_origin
        self._account_address = decibel_perpetual_account_address
        self._domain = domain
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._market_addr_by_pair: Dict[str, str] = {}
        self._pair_by_market_addr: Dict[str, str] = {}
        super().__init__(client_config_map)

    @property
    def account_address(self) -> str:
        return self._account_address

    @property
    def authenticator(self) -> DecibelPerpetualAuth:
        return DecibelPerpetualAuth(bearer_token=self._bearer_token, origin=self._origin)

    @property
    def name(self) -> str:
        return "decibel_perpetual"

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def client_order_id_max_length(self) -> int:
        return 36

    @property
    def client_order_id_prefix(self) -> str:
        return "decibel-"

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self):
        return build_api_factory(throttler=self._throttler, auth=self.authenticator)

    def _create_order_book_data_source(self) -> PerpetualAPIOrderBookDataSource:
        return DecibelPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DecibelPerpetualAPIUserStreamDataSource(
            auth=self.authenticator,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _get_fee(self, base_currency, quote_currency, order_type, order_side, amount, price=None, is_maker=None):
        is_maker = order_type is OrderType.LIMIT_MAKER
        return build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    async def market_address_associated_to_pair(self, trading_pair: str) -> str:
        if trading_pair not in self._market_addr_by_pair:
            await self._update_symbol_map_if_needed()
        return self._market_addr_by_pair[trading_pair]

    async def trading_pair_associated_to_market_address(self, market_addr: str) -> Optional[str]:
        if market_addr not in self._pair_by_market_addr:
            await self._update_symbol_map_if_needed()
        return self._pair_by_market_addr.get(market_addr)

    async def _update_symbol_map_if_needed(self):
        if self._market_addr_by_pair and self._pair_by_market_addr:
            return
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        markets = await rest_assistant.execute_request(
            url=rest_url(CONSTANTS.MARKETS_PATH_URL, domain=self._domain),
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.MARKETS_PATH_URL,
        )
        await self._initialize_trading_pair_symbols_from_exchange_info(markets)

    async def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        markets = exchange_info if isinstance(exchange_info, list) else exchange_info.get("data", [])
        mapping: Dict[str, str] = {}
        for market in markets:
            market_name = market.get("market_name") or market.get("market") or market.get("name")
            market_addr = market.get("market_addr") or market.get("address")
            if market_name is None or market_addr is None:
                continue
            trading_pair = self.convert_from_exchange_trading_pair(market_name)
            mapping[market_name] = trading_pair
            self._market_addr_by_pair[trading_pair] = market_addr
            self._pair_by_market_addr[market_addr] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules: List[TradingRule] = []
        markets = exchange_info_dict if isinstance(exchange_info_dict, list) else exchange_info_dict.get("data", [])
        for market in markets:
            try:
                market_name = market.get("market_name") or market.get("market") or market.get("name")
                if market_name is None:
                    continue
                trading_pair = self.convert_from_exchange_trading_pair(market_name)
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(market.get("min_size", 0))),
                        min_price_increment=Decimal(str(market.get("tick_size", "0.0"))),
                        min_base_amount_increment=Decimal("1") / (Decimal(10) ** Decimal(str(market.get("sz_decimals", 0)))),
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing trading rules for {market}")
        return trading_rules

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.OPEN,
        **kwargs,
    ) -> Tuple[str, float]:
        raise NotImplementedError("Trading endpoints are not implemented in this connector template.")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        raise NotImplementedError

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        raise NotImplementedError

    async def _update_balances(self):
        return

    async def _update_positions(self):
        return

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        return False, "Not supported"

    async def _fetch_last_fee_payment(self, trading_pair: str):
        return 0, Decimal("0"), Decimal("0")

    async def _status_polling_loop_fetch_updates(self):
        # Keep the base loop alive even if trading isn't implemented.
        await asyncio.sleep(0)

    async def _update_order_status(self):
        return

    async def _update_order_fills_from_trades(self):
        return
