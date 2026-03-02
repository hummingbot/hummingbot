import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source import (
    ArchitectPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_user_stream_data_source import (
    ArchitectPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class ArchitectPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Hummingbot connector for Architect Perpetual futures exchange.
    """
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
        self,
        architect_perpetual_api_key: str = None,
        architect_perpetual_api_secret: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = architect_perpetual_api_key
        self._api_secret = architect_perpetual_api_secret
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._domain = domain
        self._position_mode = PositionMode.ONEWAY
        self._trading_pair_symbol_map: Optional[bidict] = None
        super().__init__()

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[ArchitectPerpetualAuth]:
        if self._trading_required:
            return ArchitectPerpetualAuth(
                self._api_key,
                self._api_secret,
            )
        return None

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
        return CONSTANTS.INSTRUMENTS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.TICKERS_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

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

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ArchitectPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ArchitectPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Parse exchange instrument info into trading rules.
        """
        trading_rules = []
        
        for instrument in exchange_info_dict:
            try:
                trading_pair = self.exchange_symbol_to_trading_pair(instrument.get("symbol", ""))
                
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(instrument.get("min_order_size", "0.001"))),
                        max_order_size=Decimal(str(instrument.get("max_order_size", "1000000"))),
                        min_price_increment=Decimal(str(instrument.get("tick_size", "0.01"))),
                        min_base_amount_increment=Decimal(str(instrument.get("step_size", "0.001"))),
                        min_notional_size=Decimal(str(instrument.get("min_notional", "10"))),
                    )
                )
            except Exception as e:
                self.logger().warning(f"Error parsing trading rule for {instrument}: {e}")
        
        return trading_rules

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
        """
        Place an order on Architect.
        """
        symbol = self.trading_pair_to_exchange_symbol(trading_pair)
        
        order_data = {
            "symbol": symbol,
            "side": "buy" if trade_type == TradeType.BUY else "sell",
            "type": "limit" if order_type == OrderType.LIMIT else "market",
            "size": str(amount),
            "client_order_id": order_id,
        }
        
        if order_type == OrderType.LIMIT:
            order_data["price"] = str(price)
        
        if position_action == PositionAction.CLOSE:
            order_data["reduce_only"] = True
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.PLACE_ORDER_URL, self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=order_data,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.PLACE_ORDER_URL,
        )
        
        exchange_order_id = response.get("order_id", "")
        transact_time = response.get("timestamp", 0)
        
        return exchange_order_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        Cancel an order on Architect.
        """
        symbol = self.trading_pair_to_exchange_symbol(tracked_order.trading_pair)
        
        cancel_data = {
            "symbol": symbol,
            "order_id": tracked_order.exchange_order_id,
        }
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL, self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=cancel_data,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.CANCEL_ORDER_URL,
        )
        
        return response.get("success", False)

    async def _update_balances(self):
        """
        Update account balances.
        """
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.BALANCES_URL, self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.BALANCES_URL,
        )
        
        self._account_available_balances.clear()
        self._account_balances.clear()
        
        for balance in response:
            asset = balance.get("asset", "")
            total = Decimal(str(balance.get("total", 0)))
            available = Decimal(str(balance.get("available", 0)))
            
            self._account_balances[asset] = total
            self._account_available_balances[asset] = available

    async def _update_positions(self):
        """
        Update account positions.
        """
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.POSITIONS_URL, self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.POSITIONS_URL,
        )
        
        for position_data in response:
            trading_pair = self.exchange_symbol_to_trading_pair(position_data.get("symbol", ""))
            amount = Decimal(str(position_data.get("size", 0)))
            
            if amount != Decimal("0"):
                position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=Decimal(str(position_data.get("unrealized_pnl", 0))),
                    entry_price=Decimal(str(position_data.get("entry_price", 0))),
                    amount=abs(amount),
                    leverage=Decimal(str(position_data.get("leverage", 1))),
                )
                
                self._perpetual_trading.set_position(trading_pair, position_side, position)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Get all trade updates for an order.
        """
        trade_updates = []
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.FILLS_URL, self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params={"order_id": order.exchange_order_id},
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.FILLS_URL,
        )
        
        for fill in response:
            trade_updates.append(
                TradeUpdate(
                    trade_id=fill.get("trade_id", ""),
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=TradeFeeBase.new_perpetual_fee(
                        fee_schema=self._trading_fees,
                        position_action=order.position,
                        percent_token=fill.get("fee_asset", "USD"),
                        flat_fees=[TokenAmount(
                            token=fill.get("fee_asset", "USD"),
                            amount=Decimal(str(fill.get("fee", 0))),
                        )],
                    ),
                    fill_base_amount=Decimal(str(fill.get("size", 0))),
                    fill_quote_amount=Decimal(str(fill.get("size", 0))) * Decimal(str(fill.get("price", 0))),
                    fill_price=Decimal(str(fill.get("price", 0))),
                    fill_timestamp=fill.get("timestamp", 0),
                )
            )
        
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Request order status from Architect.
        """
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.OPEN_ORDERS_URL, self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.OPEN_ORDERS_URL,
        )
        
        for order_data in response:
            if order_data.get("order_id") == tracked_order.exchange_order_id:
                new_state = CONSTANTS.ORDER_STATE.get(
                    order_data.get("status", ""),
                    tracked_order.current_state,
                )
                
                return OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=order_data.get("timestamp", 0),
                    new_state=new_state,
                )
        
        # Order not found in open orders - likely filled or canceled
        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=0,
            new_state=tracked_order.current_state,
        )

    def exchange_symbol_to_trading_pair(self, symbol: str) -> str:
        """
        Convert exchange symbol to Hummingbot trading pair format.
        """
        # Remove -PERP suffix and convert
        symbol = symbol.replace("-PERP", "").replace("_", "-")
        return symbol

    def trading_pair_to_exchange_symbol(self, trading_pair: str) -> str:
        """
        Convert Hummingbot trading pair to exchange symbol format.
        """
        base, quote = trading_pair.split("-")
        return f"{base}-{quote}-PERP"

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Get the last traded price for a trading pair.
        """
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        symbol = self.trading_pair_to_exchange_symbol(trading_pair)
        url = web_utils.public_rest_url(f"{CONSTANTS.TICKER_URL}?symbol={symbol}", self._domain)
        
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TICKERS_URL,
        )
        
        return float(response.get("last_price", 0))
