from __future__ import annotations

import time
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source import (
    ArchitectPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_user_stream_data_source import (
    ArchitectPerpetualUserStreamDataSource,
)
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class ArchitectPerpetualDerivative(PerpetualDerivativePyBase):
    """Architect Perpetual connector.

    The exchange API surface is implemented in a Binance-style fashion (best-effort, based on
    publicly visible endpoint naming).

    IMPORTANT: This module imports cython-dependent Hummingbot components. It is not imported
    by unit tests in this bounty environment.
    """

    web_utils = web_utils

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        architect_perpetual_api_key: str = None,
        architect_perpetual_api_secret: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self.architect_perpetual_api_key = architect_perpetual_api_key
        self.architect_perpetual_api_secret = architect_perpetual_api_secret
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._domain = domain
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> ArchitectPerpetualAuth:
        return ArchitectPerpetualAuth(
            api_key=self.architect_perpetual_api_key,
            api_secret=self.architect_perpetual_api_secret,
            time_provider=self._time_synchronizer,
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth,
        )

    def _create_order_book_data_source(self):
        return ArchitectPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self):
        return ArchitectPerpetualUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or False
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

    async def _api_get(self, path_url: str, params: Optional[dict] = None, is_auth_required: bool = False):
        return await web_utils.api_request(
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            domain=self._domain,
            path_url=path_url,
            method=RESTMethod.GET,
            params=params,
            is_auth_required=is_auth_required,
        )

    async def _api_post(self, path_url: str, data: Optional[dict] = None, is_auth_required: bool = True):
        return await web_utils.api_request(
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            domain=self._domain,
            path_url=path_url,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=is_auth_required,
        )

    async def _api_delete(self, path_url: str, params: Optional[dict] = None, is_auth_required: bool = True):
        return await web_utils.api_request(
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            domain=self._domain,
            path_url=path_url,
            method=RESTMethod.DELETE,
            params=params,
            is_auth_required=is_auth_required,
        )

    async def _format_trading_rules(self, exchange_info_dict: Dict) -> List[TradingRule]:
        rules: List[TradingRule] = []
        for symbol_info in exchange_info_dict.get("symbols", []):
            trading_pair = symbol_info.get("symbol")
            if trading_pair is None:
                continue
            min_qty = Decimal(str(symbol_info.get("min_qty", symbol_info.get("minQty", "0"))))
            min_price = Decimal(str(symbol_info.get("min_price", symbol_info.get("tickSize", "0"))))
            min_notional = Decimal(str(symbol_info.get("min_notional", symbol_info.get("minNotional", "0"))))

            base = symbol_info.get("base") or symbol_info.get("baseAsset") or trading_pair.split("-")[0]
            quote = symbol_info.get("quote") or symbol_info.get("quoteAsset") or trading_pair.split("-")[-1]

            rules.append(
                TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_qty,
                    min_price_increment=min_price,
                    min_base_amount_increment=min_qty,
                    min_notional_size=min_notional,
                    buy_order_collateral_token=quote,
                    sell_order_collateral_token=quote,
                )
            )
        return rules

    async def _update_time_synchronizer(self, *args, **kwargs):
        # Best-effort: use /time endpoint if available
        try:
            resp = await self._api_get(CONSTANTS.SERVER_TIME_URL)
            server_time_ms = resp.get("serverTime") or resp.get("time")
            if server_time_ms is not None:
                self._time_synchronizer.add_time_offset_ms(int(server_time_ms) - int(time.time() * 1e3))
        except Exception:
            return
