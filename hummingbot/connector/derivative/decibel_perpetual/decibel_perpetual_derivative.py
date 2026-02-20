import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_user_stream_data_source import (
    DecibelPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_utils import (
    convert_to_exchange_symbol,
    get_original_trading_pair,
)
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import PerpetualDerivativeInFlightOrder
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.event.events import AccountEvent, MarketEvent, PositionModeChangeEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DecibelPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Decibel Perpetual connector for Hummingbot
    Implements trading for Decibel's fully on-chain perpetuals exchange
    """

    def __init__(self, client_config_map, bearer_token: str, origin: str = "https://app.decibel.trade"):
        self._bearer_token = bearer_token
        self._origin = origin
        self._auth = DecibelPerpetualAuth(bearer_token, origin)
        
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def auth(self) -> DecibelPerpetualAuth:
        return self._auth

    @property
    def rate_limits(self) -> List:
        return CONSTANTS.RATE_LIMITS

    @property
    def client_order_id_prefix(self) -> str:
        return "dcbl"

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.GET_ALL_AVAILABLE_MARKETS

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.GET_ALL_AVAILABLE_MARKETS

    @property
    def network_check_path(self) -> str:
        return CONSTANTS.GET_ALL_AVAILABLE_MARKETS

    @property
    def funding_fee_poll_interval(self) -> int:
        return 60

    @property
    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def in_flight_orders(self) -> Dict[str, PerpetualDerivativeInFlightOrder]:
        return self._order_tracker.in_flight_orders

    # ====================
    # Funding Info
    # ====================

    async def _get_funding_info(self, trading_pair: str) -> FundingInfo:
        data_source = self._orderbook_ds
        return await data_source.get_funding_info(trading_pair)

    # ====================
    # Order Book Data Source
    # ====================

    def _create_order_book_data_source(self) -> PerpetualAPIOrderBookDataSource:
        return DecibelPerpetualAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            auth=self._auth,
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        from hummingbot.core.web_assistant.ws_assistant import WSAssistant
        
        return WebAssistantsFactory(
            rest_assistant_class=RESTAssistant,
            ws_assistant_class=WSAssistant,
            auth=self._auth,
        )

    # ====================
    # Trading
    # ====================

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
        """Places an order on Decibel Perpetual"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        
        side = "buy" if trade_type == TradeType.BUY else "sell"
        order_type_str = "limit" if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else "market"
        
        order_data = {
            "market": convert_to_exchange_symbol(trading_pair),
            "side": side,
            "size": str(amount),
            "order_type": order_type_str,
        }
        
        if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]:
            order_data["price"] = str(price)
        
        # Add post-only if needed
        if order_type == OrderType.LIMIT_MAKER:
            order_data["post_only"] = True
        
        response = await rest_assistant.post(
            CONSTANTS.REST_URL + CONSTANTS.PLACE_ORDER,
            data=order_data,
            throttler=self._throttler,
            headers=self._auth.get_headers(),
        )
        
        return str(response.get("order_id")), response.get("created_at", 0)

    async def _cancel_order(self, order_id: str, trading_pair: str):
        """Cancels an order on Decibel Perpetual"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        
        cancel_path = CONSTANTS.CANCEL_ORDER.format(order_id=order_id)
        
        await rest_assistant.delete(
            CONSTANTS.REST_URL + cancel_path,
            headers=self._auth.get_headers(),
            throttler=self._throttler,
        )

    async def _update_orders(self, trading_pairs: Optional[List[str]] = None):
        """Updates orders status from the exchange"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        if trading_pairs is None:
            trading_pairs = self.trading_pairs
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        
        for trading_pair in trading_pairs:
            try:
                response = await rest_assistant.get(
                    CONSTANTS.REST_URL + CONSTANTS.GET_ACCOUNT_OPEN_ORDERS,
                    params={"market": convert_to_exchange_symbol(trading_pair)},
                    throttler=self._throttler,
                    headers=self._auth.get_headers(),
                )
                
                # Process open orders and update in-flight orders
                for order_data in response:
                    exchange_order_id = order_data.get("order_id")
                    if exchange_order_id in self._order_tracker.in_flight_orders:
                        order = self._order_tracker.in_flight_orders[exchange_order_id]
                        order.exchange_order_id = exchange_order_id
                        order.update_status(order_data.get("status", "open"))
            except Exception as e:
                self.logger().error(f"Error updating orders for {trading_pair}: {e}")

    # ====================
    # Positions
    # ====================

    async def _update_positions(self):
        """Updates positions from the exchange"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        
        try:
            response = await rest_assistant.get(
                CONSTANTS.REST_URL + CONSTANTS.GET_ACCOUNT_POSITIONS,
                headers=self._auth.get_headers(),
                throttler=self._throttler,
            )
            
            # Clear and update positions
            self._perpetual_trading.clear_positions()
            
            for position_data in response:
                trading_pair = get_original_trading_pair(position_data.get("market", ""))
                size = Decimal(str(position_data.get("size", 0)))
                
                if size != 0:
                    self._perpetual_trading.update_position(
                        trading_pair=trading_pair,
                        position_side=position_data.get("side", "long"),
                        size=size,
                        entry_price=Decimal(str(position_data.get("entry_price", 0))),
                        mark_price=Decimal(str(position_data.get("mark_price", 0))),
                        leverage=position_data.get("leverage", 1),
                    )
        except Exception as e:
            self.logger().error(f"Error updating positions: {e}")

    # ====================
    # Balance
    # ====================

    async def _update_balances(self):
        """Updates account balances from the exchange"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        
        try:
            response = await rest_assistant.get(
                CONSTANTS.REST_URL + CONSTANTS.GET_ACCOUNT_OVERVIEW,
                headers=self._auth.get_headers(),
                throttler=self._throttler,
            )
            
            # Update available balances
            self._account_balances = {
                "USD": Decimal(str(response.get("total_collateral", 0))),
            }
            self._available_balances = {
                "USD": Decimal(str(response.get("available_collateral", 0))),
            }
        except Exception as e:
            self.logger().error(f"Error updating balances: {e}")

    # ====================
    # Position Mode
    # ====================

    async def _trading_pair_position_mode_set(
        self, mode: PositionMode, trading_pair: str
    ) -> Tuple[bool, str]:
        """Sets position mode for a trading pair"""
        # Decibel only supports ONEWAY mode
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """Sets leverage for a trading pair"""
        # Decibel handles leverage at the order level
        self._perpetual_trading.set_leverage(trading_pair, leverage)
        return True, ""

    # ====================
    # Funding
    # ====================

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        """Fetches the last funding fee payment"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        
        try:
            response = await rest_assistant.get(
                CONSTANTS.REST_URL + CONSTANTS.GET_USER_FUNDING_RATE_HISTORY,
                params={"market": convert_to_exchange_symbol(trading_pair)},
                headers=self._auth.get_headers(),
                throttler=self._throttler,
            )
            
            if response and len(response) > 0:
                latest = response[0]
                return (
                    latest.get("timestamp", 0),
                    Decimal(str(latest.get("funding_rate", 0))),
                    Decimal(str(latest.get("payment", 0))),
                )
        except Exception as e:
            self.logger().error(f"Error fetching funding info: {e}")
        
        return 0, Decimal("-1"), Decimal("-1")

    # ====================
    # Trading Rules
    # ====================

    async def _get_trading_rules(self):
        """Fetches trading rules from the exchange"""
        from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
        
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        
        try:
            response = await rest_assistant.get(
                CONSTANTS.REST_URL + CONSTANTS.GET_ALL_AVAILABLE_MARKETS,
                throttler=self._throttler,
            )
            
            trading_rules = []
            for market in response:
                symbol = market.get("symbol", "")
                if symbol:
                    trading_pair = get_original_trading_pair(symbol)
                    
                    from hummingbot.core.data_type.trading_rule import TradingRule
                    trading_rule = TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(market.get("min_size", 0))),
                        max_order_size=Decimal(str(market.get("max_size", 0))),
                        min_price_increment=Decimal(str(market.get("tick_size", 0.01))),
                        min_base_amount_increment=Decimal(str(market.get("step_size", 0.001))),
                    )
                    trading_rules.append(trading_rule)
            
            self._trading_rules = {rule.trading_pair: rule for rule in trading_rules}
        except Exception as e:
            self.logger().error(f"Error fetching trading rules: {e}")

    # ====================
    # Collateral Token
    # ====================

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return "USD"

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return "USD"

    # ====================
    # Fee
    # ====================

    def _get_fee(self, event_type: AccountEvent, trading_pair: Optional[str] = None) -> TradeFeeBase:
        """Returns the fee for an event"""
        # Default fee structure - should be updated based on actual fee schedule
        return TradeFeeBase(
            percent_format_=Decimal("0.0001"),  # 0.01%
        )
